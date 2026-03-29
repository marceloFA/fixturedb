"""
AST-based fixture and mock detector using Tree-sitter.

FIXTURE DETECTION APPROACH
===========================

For each of the 6 supported languages, we define:

1. **Fixture patterns** — How to identify fixture *definitions* in a test file
   - Python: Functions decorated with @pytest.fixture or @unittest setUp/tearDown
   - Java: Methods with @Before/@BeforeClass, @Setup, or @Test annotations
   - JavaScript/TypeScript: Functions named beforeEach/beforeAll/describe/setUp
   - Go: Functions starting with Test/, functions using testing.T
   - C#: Methods with [SetUp], [Fixture], or [Test] attributes
   
   Pattern matching uses tree-sitter AST node types that are
   language-agnostic (e.g., 'function_declaration', 'decorator', etc.)

2. **Mock patterns** — How to identify mock usages within a fixture
   Uses regex-based heuristics to detect mock framework calls:
   - unittest_mock (Python), Mockito (Java), Jest (JS), Sinon (JS), etc.
   - ~40 framework-specific patterns across 12 mock frameworks
   - Detects both mock *instantiation* and mock *usage*

3. **Fixture metrics** — Quantitative properties of the fixture
   - LOC: Lines of code (non-blank)
   - Cyclomatic Complexity: Branch count (if, for, while, case, catch)
   - Cognitive Complexity: Nesting-depth-weighted branch count (user-facing)
   - num_objects_instantiated: Count of new X(...) constructor calls
   - num_external_calls: Count of I/O patterns (db, file, http, network, etc.)
   - num_parameters: Function signature parameter count

PUBLIC INTERFACE
================

extract_fixtures(file_path: Path, language: str) -> ExtractResult

ExtractResult contains:
  - fixtures: list[FixtureResult] — all fixture definitions found
  - file_loc: int — non-blank lines of code in the file
  - num_test_functions: int — count of test functions in the file

Each FixtureResult carries all the fields needed to populate the DB tables:
  fixture_type, scope, start_line, end_line, loc, 
  cyclomatic_complexity, cognitive_complexity,
  num_objects_instantiated, num_external_calls, num_parameters,
  framework (mock framework used, if any), raw_source text
"""

import re
import logging
from dataclasses import dataclass, field
from pathlib import Path

from collection.config import MAX_FILE_SIZE_BYTES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-load Tree-sitter grammars to avoid import overhead when unused
# ---------------------------------------------------------------------------

_PARSERS: dict = {}


def _get_parser(language: str):
    """Return (and cache) a tree_sitter.Parser for the given language key."""
    if language in _PARSERS:
        return _PARSERS[language]

    try:
        import tree_sitter_python
        import tree_sitter_java
        import tree_sitter_javascript
        import tree_sitter_typescript
        import tree_sitter_go
        import tree_sitter_c_sharp
        from tree_sitter import Language, Parser

        lang_map = {
            "python": Language(tree_sitter_python.language()),
            "java": Language(tree_sitter_java.language()),
            "javascript": Language(tree_sitter_javascript.language()),
            "typescript": Language(tree_sitter_typescript.language_typescript()),
            "go": Language(tree_sitter_go.language()),
            "csharp": Language(tree_sitter_c_sharp.language()),
        }
        for key, lang in lang_map.items():
            p = Parser(lang)
            _PARSERS[key] = p

    except ImportError as e:
        raise ImportError(
            "tree-sitter language bindings not installed. "
            "Run: pip install -r requirements.txt"
        ) from e

    return _PARSERS[language]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class MockResult:
    framework: str
    target_identifier: str
    num_interactions_configured: int
    raw_snippet: str


@dataclass
class FixtureResult:
    name: str
    fixture_type: str  # see per-language constants below
    framework: str  # testing framework: pytest, unittest, junit, nunit, testify, etc.
    scope: str  # per_test / per_class / per_module / global
    start_line: int
    end_line: int
    loc: int  # non-blank lines
    cyclomatic_complexity: int
    cognitive_complexity: int
    num_objects_instantiated: int
    num_external_calls: int
    num_parameters: int
    raw_source: str
    mocks: list[MockResult] = field(default_factory=list)


@dataclass
class ExtractResult:
    """Result of extracting fixtures from a file, including file-level metrics."""

    fixtures: list[FixtureResult]
    file_loc: int  # non-blank lines in the file
    num_test_functions: int  # count of test functions in the file


# ---------------------------------------------------------------------------
# Shared AST utilities
# ---------------------------------------------------------------------------


def _source(node, src_bytes: bytes) -> str:
    """Extract source code text for a tree-sitter node."""
    return src_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _count_loc(text: str) -> int:
    """Count non-blank lines of code in a text string."""
    return sum(1 for line in text.splitlines() if line.strip())


def _count_file_loc(src_bytes: bytes) -> int:
    """Count non-blank lines of code in a source file."""
    try:
        text = src_bytes.decode("utf-8", errors="replace")
        return _count_loc(text)
    except Exception:
        return 0


def _cyclomatic_complexity(node, src_bytes: bytes) -> int:
    """
    Simple proxy: count branching keywords in the fixture source text.
    Not a rigorous McCabe calculation but fast and language-agnostic.
    """
    text = _source(node, src_bytes)
    branch_keywords = r"\b(if|elif|else|for|while|case|catch|except|&&|\|\|)\b"
    return 1 + len(re.findall(branch_keywords, text))


def _cognitive_complexity(node, src_bytes: bytes) -> int:
    """
    Calculate cognitive complexity using tree-sitter AST.

    Cognitive complexity weights code constructs by nesting depth:
    - Control structures (if, while, for, case, catch) increment base score
    - Nesting depth multiplies the score (deeper = harder to understand)
    - Boolean operators (&&, ||) increment at their nesting level
    - Recursion adds a constant penalty

    This is language-agnostic using tree-sitter's consistent node type names.
    """
    complexity = 0

    def walk(n, depth=0):
        nonlocal complexity

        # Control structures that increment complexity
        # Tree-sitter node types are consistent across languages
        control_structures = {
            # Conditionals
            "if_statement",
            "conditional_expression",
            # Loops
            "for_statement",
            "while_statement",
            "do_statement",
            # Switch/Case
            "switch_statement",
            "case_statement",
            # Exception handling
            "try_statement",
            "catch_clause",
            "throw_statement",
            "raise_statement",
            # C# specific
            "try_catch_clause",
        }

        if n.type in control_structures:
            # Base increment of 1, multiplied by nesting depth
            complexity += max(1, depth)

        # Boolean operators (only count when part of binary expression)
        if n.type == "binary_expression":
            op_text = _source(n.child_by_field_name("operator"), src_bytes).strip()
            if op_text in ("&&", "and", "||", "or"):
                complexity += max(1, depth)

        # Recursion detection (rough heuristic)
        if n.type in (
            "function_declaration",
            "method_definition",
            "function_definition",
        ):
            # Try to detect recursive calls
            func_name = None
            name_node = n.child_by_field_name("name")
            if name_node:
                func_name = _source(name_node, src_bytes).strip()

            if func_name:
                # Search for calls to this function within itself
                body = n.child_by_field_name("body")
                if body:
                    body_text = _source(body, src_bytes)
                    if f"{func_name}(" in body_text or f"{func_name} (" in body_text:
                        complexity += 5  # Recursion adds fixed penalty

        # Recurse into children with increased depth for nested structures
        for child in n.children:
            # Depth only increases inside control structure bodies
            next_depth = depth
            if n.type in control_structures:
                next_depth = depth + 1

            walk(child, next_depth)

    walk(node)
    return max(1, complexity)  # Minimum complexity of 1


def _count_instantiations(node, src_bytes: bytes) -> int:
    """
    Count 'new X(...)' calls (Java/JS/TS/Go) or capitalised call expressions
    that look like constructors (Python).
    """
    text = _source(node, src_bytes)
    # Java / JS / TS / Go: new Foo(...)
    new_calls = len(re.findall(r"\bnew\s+\w+\s*\(", text))
    # Python: Foo(...) where Foo starts with uppercase
    py_constructors = len(re.findall(r"\b[A-Z][A-Za-z0-9_]+\s*\(", text))
    return new_calls + py_constructors


def _count_external_calls(node, src_bytes: bytes) -> int:
    """
    Count calls that look like external I/O:
    db/sql/http/file/network/env related method names.
    """
    text = _source(node, src_bytes).lower()
    external_patterns = [
        r"\bopen\s*\(",  # file
        r"\bconnect\s*\(",  # db/network
        r"\bcreate_engine\s*\(",  # SQLAlchemy
        r"\bsession\s*\.",  # db sessions
        r"\brequests?\.",  # HTTP
        r"\bhttpclient\b",  # Go / Java
        r"\bos\.environ\b",  # env config
        r"\bsubprocess\.",  # subprocess
        r"\bsocket\s*\(",  # raw sockets
        r"\btempfile\.",  # filesystem
        r"\bshutil\.",  # filesystem
    ]
    return sum(len(re.findall(p, text)) for p in external_patterns)


# ---------------------------------------------------------------------------
# Mock detection (language-agnostic heuristic pass)
# ---------------------------------------------------------------------------

MOCK_PATTERNS = [
    # Python
    (r"mock\.patch\s*\(\s*['\"]([^'\"]+)['\"]", "unittest_mock"),
    (r"mocker\.patch\s*\(\s*['\"]([^'\"]+)['\"]", "pytest_mock"),
    (r"MagicMock\s*\(|Mock\s*\(|AsyncMock\s*\(", "unittest_mock"),
    # Java
    (r"Mockito\.mock\s*\(\s*(\w+)\.class", "mockito"),
    (r"@Mock\b", "mockito"),
    (r"EasyMock\.createMock\s*\(\s*(\w+)\.class", "easymock"),
    (r"mock\s*\(\s*(\w+)\.class", "mockk"),  # MockK (Kotlin)
    # JavaScript / TypeScript
    (r"jest\.fn\s*\(", "jest"),
    (r"jest\.spyOn\s*\(", "jest"),
    (r"jest\.mock\s*\(\s*['\"]([^'\"]+)['\"]", "jest"),
    (r"sinon\.(stub|spy|mock)\s*\(", "sinon"),
    (r"vi\.fn\s*\(", "vitest"),
    (r"vi\.mock\s*\(\s*['\"]([^'\"]+)['\"]", "vitest"),
    # Go
    (r"gomock\.NewController", "gomock"),
    (r"testify/mock", "testify_mock"),
    (r"\.On\s*\(\s*['\"](\w+)['\"]", "testify_mock"),
    # C#
    (r"new\s+Mock<", "moq"),  # Moq
    (r"Mock\.Of<", "moq"),  # Moq
    (r"\.Setup\s*\(", "moq"),  # Moq
    (r"\.Verify\s*\(", "moq"),  # Moq
    (r"Substitute\.For<", "nsubstitute"),  # NSubstitute
    (r"\.Received\s*\(", "nsubstitute"),  # NSubstitute
    (
        r"\.Returns\s*\(",
        "nsubstitute",
    ),  # NSubstitute (also Java Android, but NSubstitute more specific)
    (r"A\.Fake<", "fakeiteasy"),  # FakeItEasy
    (r"\.MustHaveHappened\s*\(", "fakeiteasy"),  # FakeItEasy
    (r"MockRepository\.GenerateMock<", "rhino_mocks"),  # Rhino Mocks
    (r"\.Expect\s*\(", "rhino_mocks"),  # Rhino Mocks
    (r"\.VerifyAllExpectations\s*\(", "rhino_mocks"),  # Rhino Mocks
]


def _extract_mocks(node, src_bytes: bytes) -> list[MockResult]:
    text = _source(node, src_bytes)
    found = []
    for pattern, framework in MOCK_PATTERNS:
        for m in re.finditer(pattern, text):
            target = m.group(1) if m.lastindex and m.lastindex >= 1 else ""
            snippet_start = max(m.start() - 20, 0)
            snippet_end = min(m.end() + 60, len(text))
            snippet = text[snippet_start:snippet_end].replace("\n", " ")

            # Count .return_value / .side_effect / when(...).thenReturn style
            interactions = len(
                re.findall(
                    r"return_value|side_effect|thenReturn|thenThrow|doReturn",
                    text[m.start() : m.end() + 200],
                )
            )
            found.append(
                MockResult(
                    framework=framework,
                    target_identifier=target,
                    num_interactions_configured=interactions,
                    raw_snippet=snippet,
                )
            )
    return found


# ---------------------------------------------------------------------------
# Python detector
# ---------------------------------------------------------------------------


def _detect_python(tree, src_bytes: bytes) -> list[FixtureResult]:
    results = []
    root = tree.root_node

    def visit(node):
        # pytest.fixture decorator pattern
        if node.type == "decorated_definition":
            decorators = [c for c in node.children if c.type == "decorator"]
            func_def = next(
                (c for c in node.children if c.type == "function_definition"), None
            )
            if not func_def:
                return

            for dec in decorators:
                dec_text = _source(dec, src_bytes)
                if "fixture" in dec_text and "pytest" in dec_text:
                    scope = "per_test"
                    scope_match = re.search(r'scope\s*=\s*["\'](\w+)["\']', dec_text)
                    if scope_match:
                        scope_map = {
                            "function": "per_test",
                            "class": "per_class",
                            "module": "per_module",
                            "package": "per_module",
                            "session": "global",
                        }
                        scope = scope_map.get(scope_match.group(1), "per_test")

                    results.append(
                        _build_result(
                            node=node,
                            func_node=func_def,
                            src_bytes=src_bytes,
                            fixture_type="pytest_decorator",
                            scope=scope,
                            framework="pytest",
                        )
                    )
                    break

        # unittest setUp/tearDown inside TestCase subclass and setup_method/teardown_method
        elif node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _source(name_node, src_bytes)

                # unittest-style fixtures: setUp/tearDown/setUpClass/tearDownClass/setUpModule/tearDownModule
                if name in (
                    "setUp",
                    "tearDown",
                    "setUpClass",
                    "tearDownClass",
                    "setUpModule",
                    "tearDownModule",
                ):
                    scope = (
                        "per_class"
                        if name in ("setUpClass", "tearDownClass")
                        else "per_test"
                    )
                    if "Module" in name:
                        scope = "per_module"
                    results.append(
                        _build_result(
                            node=node,
                            func_node=node,
                            src_bytes=src_bytes,
                            fixture_type="unittest_setup",
                            scope=scope,
                            framework="unittest",
                        )
                    )

                # TestCase method style (setup_method/teardown_method)
                elif name in (
                    "setup_method",
                    "teardown_method",
                    "setup_class",
                    "teardown_class",
                ):
                    scope = (
                        "per_class"
                        if name in ("setup_class", "teardown_class")
                        else "per_test"
                    )
                    results.append(
                        _build_result(
                            node=node,
                            func_node=node,
                            src_bytes=src_bytes,
                            fixture_type="pytest_class_method",
                            scope=scope,
                            framework="pytest",
                        )
                    )

                # Nose-style fixtures: setup/teardown/setup_module/teardown_module/setup_package/teardown_package
                elif name in (
                    "setup",
                    "teardown",
                    "setup_module",
                    "teardown_module",
                    "setup_package",
                    "teardown_package",
                ):
                    scope = "per_test"
                    if "module" in name:
                        scope = "per_module"
                    elif "package" in name:
                        scope = "per_module"
                    results.append(
                        _build_result(
                            node=node,
                            func_node=node,
                            src_bytes=src_bytes,
                            fixture_type="nose_fixture",
                            scope=scope,
                        )
                    )

        for child in node.children:
            visit(child)

    visit(root)
    return results


# ---------------------------------------------------------------------------
# Java detector
# ---------------------------------------------------------------------------

JUNIT_FIXTURE_ANNOTATIONS = {
    "@BeforeEach": ("junit5_before_each", "per_test"),
    "@BeforeAll": ("junit5_before_all", "per_class"),
    "@AfterEach": ("junit5_after_each", "per_test"),
    "@AfterAll": ("junit5_after_all", "per_class"),
    "@Before": ("junit4_before", "per_test"),
    "@BeforeClass": ("junit4_before_class", "per_class"),
    "@After": ("junit4_after", "per_test"),
    "@AfterClass": ("junit4_after_class", "per_class"),
    "@BeforeMethod": ("testng_before_method", "per_test"),  # TestNG
    "@BeforeClass": (
        "testng_before_class",
        "per_class",
    ),  # TestNG (same name as JUnit4, handled specially)
    "@AfterMethod": ("testng_after_method", "per_test"),  # TestNG
    "@AfterClass": ("testng_after_class", "per_class"),  # TestNG
    "@DataProvider": ("testng_data_provider", "per_test"),  # TestNG data-driven fixture
    "@Rule": ("junit_rule", "per_test"),  # JUnit @Rule fixture fields
    "@ClassRule": ("junit_class_rule", "per_class"),  # JUnit @ClassRule fixture fields
}


def _detect_java(tree, src_bytes: bytes) -> list[FixtureResult]:
    results = []

    def visit(node):
        if node.type == "method_declaration":
            # Annotations in Java are inside the modifiers node
            annotations = []
            for c in node.children:
                if c.type == "modifiers":
                    # Look for marker_annotation or annotation inside modifiers
                    for mod_child in c.children:
                        if (
                            mod_child.type == "marker_annotation"
                            or mod_child.type == "annotation"
                        ):
                            annotations.append(_source(mod_child, src_bytes).strip())

            # Also check for direct annotation children (fallback)
            for c in node.children:
                if c.type == "marker_annotation" or c.type == "annotation":
                    annotations.append(_source(c, src_bytes).strip())

            for ann in annotations:
                # Strip parameter content for lookup
                ann_key = "@" + ann.lstrip("@").split("(")[0].strip()
                if ann_key in JUNIT_FIXTURE_ANNOTATIONS:
                    fixture_type, scope = JUNIT_FIXTURE_ANNOTATIONS[ann_key]
                    results.append(
                        _build_result(
                            node=node,
                            func_node=node,
                            src_bytes=src_bytes,
                            fixture_type=fixture_type,
                            scope=scope,
                            framework="junit",
                        )
                    )
                    break

            # JUnit 3 style: setUp() / tearDown() methods (no annotations, in TestCase subclass)
            # These are plain methods with specific names, not indicated by annotations
            name_node = node.child_by_field_name("name")
            if name_node:
                method_name = _source(name_node, src_bytes).strip()
                if method_name in ("setUp", "tearDown"):
                    # Check if not already matched by annotation
                    has_annotation = any(
                        ann
                        for ann in annotations
                        if "@Before" in ann or "@After" in ann
                    )
                    if not has_annotation:
                        scope = "per_test"
                        fixture_type = (
                            "junit3_setup"
                            if method_name == "setUp"
                            else "junit3_teardown"
                        )
                        results.append(
                            _build_result(
                                node=node,
                                func_node=node,
                                src_bytes=src_bytes,
                                fixture_type=fixture_type,
                                scope=scope,
                                framework="junit",
                            )
                        )

        # Handle @Rule and @ClassRule field declarations
        elif node.type == "field_declaration":
            annotations = []
            for c in node.children:
                if c.type == "modifiers":
                    for mod_child in c.children:
                        if (
                            mod_child.type == "marker_annotation"
                            or mod_child.type == "annotation"
                        ):
                            annotations.append(_source(mod_child, src_bytes).strip())

            for ann in annotations:
                ann_key = "@" + ann.lstrip("@").split("(")[0].strip()
                if ann_key in ("@Rule", "@ClassRule"):
                    fixture_type, scope = JUNIT_FIXTURE_ANNOTATIONS[ann_key]
                    results.append(
                        _build_result(
                            node=node,
                            func_node=node,
                            src_bytes=src_bytes,
                            fixture_type=fixture_type,
                            scope=scope,
                            framework="junit",
                        )
                    )
                    break

        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return results


# ---------------------------------------------------------------------------
# JavaScript / TypeScript detector
# ---------------------------------------------------------------------------

JS_FIXTURE_CALLS = {
    "beforeEach": ("before_each", "per_test"),
    "beforeAll": ("before_all", "per_class"),
    "afterEach": ("after_each", "per_test"),
    "afterAll": ("after_all", "per_class"),
    "before": (
        "mocha_before",
        "per_test",
    ),  # default to per_test for ambiguous mocha hooks
    "after": (
        "mocha_after",
        "per_test",
    ),  # default to per_test for ambiguous mocha hooks
}

# AVA fixture patterns - using member access like test.before()
AVA_FIXTURE_PATTERNS = {
    "before": ("ava_before", "per_class"),
    "after": ("ava_after", "per_class"),
    "serial.before": ("ava_serial_before", "per_test"),
    "serial.after": ("ava_serial_after", "per_test"),
}


def _detect_js(tree, src_bytes: bytes) -> list[FixtureResult]:
    results = []

    def visit(node):
        if node.type in ("call_expression", "await_expression"):
            target = node
            if node.type == "await_expression":
                target = next(
                    (c for c in node.children if c.type == "call_expression"), None
                )
            if target is None:
                return

            func_node = target.child_by_field_name("function")
            if func_node:
                name = _source(func_node, src_bytes).strip()

                # Check standard hooks (Jest/Mocha style) - ambiguous, so framework=None
                if name in JS_FIXTURE_CALLS:
                    fixture_type, scope = JS_FIXTURE_CALLS[name]
                    results.append(
                        _build_result(
                            node=target,
                            func_node=target,
                            src_bytes=src_bytes,
                            fixture_type=fixture_type,
                            scope=scope,
                            framework=None,  # Ambiguous: could be Jest, Mocha, Vitest, Jasmine, etc.
                        )
                    )

                # Check AVA patterns: test.before, test.after, test.serial.before, test.serial.after
                # These appear as member_access_expression like "test.before" or "test.serial.before"
                elif func_node.type == "member_expression":
                    # Get the full member access chain
                    member_src = _source(func_node, src_bytes).strip()

                    # Check if it's a test.* pattern
                    if member_src.startswith("test."):
                        ava_pattern = member_src[5:]  # Remove "test." prefix
                        if ava_pattern in AVA_FIXTURE_PATTERNS:
                            fixture_type, scope = AVA_FIXTURE_PATTERNS[ava_pattern]
                            results.append(
                                _build_result(
                                    node=target,
                                    func_node=target,
                                    src_bytes=src_bytes,
                                    fixture_type=fixture_type,
                                    scope=scope,
                                    framework="ava",
                                )
                            )

        # TypeScript decorator patterns: @Before, @After, @BeforeEach, etc.
        elif node.type == "method_definition":
            # Check if there's a preceding decorator node
            parent = node.parent
            if parent:
                # Find this node's index in its parent's children
                node_index = None
                for i, child in enumerate(parent.children):
                    if child == node:
                        node_index = i
                        break

                # Check if the preceding sibling is a decorator
                if node_index is not None and node_index > 0:
                    prev_sibling = parent.children[node_index - 1]
                    if prev_sibling.type == "decorator":
                        dec_text = _source(prev_sibling, src_bytes).strip()
                        # Remove @ symbol and check if it's a known decorator
                        dec_name = dec_text.lstrip("@").split("(")[0].strip()

                        # Mapping of TypeScript decorators to fixture types
                        decorator_map = {
                            "Before": ("mocha_before", "per_test"),
                            "After": ("mocha_after", "per_test"),
                            "BeforeEach": ("before_each", "per_test"),
                            "AfterEach": ("after_each", "per_test"),
                            "BeforeAll": ("before_all", "per_class"),
                            "AfterAll": ("after_all", "per_class"),
                        }

                        if dec_name in decorator_map:
                            fixture_type, scope = decorator_map[dec_name]
                            results.append(
                                _build_result(
                                    node=node,
                                    func_node=node,
                                    src_bytes=src_bytes,
                                    fixture_type=fixture_type,
                                    scope=scope,
                                )
                            )

        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return results


# ---------------------------------------------------------------------------
# C# detector
# ---------------------------------------------------------------------------

CSHARP_FIXTURE_ATTRIBUTES = {
    "SetUp": ("nunit_setup", "per_test"),
    "TearDown": ("nunit_teardown", "per_test"),
    "OneTimeSetUp": ("nunit_onetimesetup", "per_class"),
    "OneTimeTearDown": ("nunit_onetimeteardown", "per_class"),
    "TestInitialize": ("mstest_initialize", "per_test"),  # MSTest
    "TestCleanup": ("mstest_cleanup", "per_test"),  # MSTest
    "ClassInitialize": ("mstest_class_initialize", "per_class"),  # MSTest
    "ClassCleanup": ("mstest_class_cleanup", "per_class"),  # MSTest
    "Fact": ("xunit_fact", "per_test"),
    "Theory": ("xunit_theory", "per_test"),
}


def _detect_csharp(tree, src_bytes: bytes) -> list[FixtureResult]:
    results = []

    def detect_fixture_attributes(node, src_bytes):
        """Extract fixture attributes from a node."""
        attributes = []
        for c in node.children:
            if c.type == "attribute_list":
                # Extract attributes from inside the attribute_list
                for attr_node in c.children:
                    if attr_node.type == "attribute":
                        attr_text = _source(attr_node, src_bytes).strip()
                        attributes.append(attr_text)
        return attributes

    def get_method_name(node, src_bytes):
        """Get method name from method_declaration or local_function_statement."""
        # For method_declaration, try 'name' field
        name_node = node.child_by_field_name("name")
        if name_node:
            return _source(name_node, src_bytes)

        # For local_function_statement, find the first identifier
        for c in node.children:
            if c.type == "identifier":
                return _source(c, src_bytes)
        return ""

    def visit(node):
        # Handle both method_declaration and local_function_statement
        if node.type in ("method_declaration", "local_function_statement"):
            # Get method name
            method_name = get_method_name(node, src_bytes)

            # Collect all attributes for this method
            attributes = detect_fixture_attributes(node, src_bytes)

            # Check if any known fixture attribute is present
            # Sort by length descending so more specific attributes match first (e.g., OneTimeSetUp before SetUp)
            for attr in attributes:
                matched = False
                for attr_name in sorted(
                    CSHARP_FIXTURE_ATTRIBUTES.keys(), key=len, reverse=True
                ):
                    # Use word boundary checking to avoid "SetUp" matching "OneTimeSetUp"
                    if (
                        attr_name == attr
                        or attr.startswith(attr_name + "[")
                        or attr.startswith(attr_name + "(")
                    ):
                        fixture_type, scope = CSHARP_FIXTURE_ATTRIBUTES[attr_name]
                        # Determine framework based on attribute
                        if attr_name in (
                            "SetUp",
                            "TearDown",
                            "OneTimeSetUp",
                            "OneTimeTearDown",
                        ):
                            framework = "nunit"
                        elif attr_name in (
                            "TestInitialize",
                            "TestCleanup",
                            "ClassInitialize",
                            "ClassCleanup",
                        ):
                            framework = "mstest"
                        elif attr_name in ("Fact", "Theory"):
                            framework = "xunit"
                        else:
                            framework = None
                        results.append(
                            _build_result(
                                node=node,
                                func_node=node,
                                src_bytes=src_bytes,
                                fixture_type=fixture_type,
                                scope=scope,
                                framework=framework,
                            )
                        )
                        matched = True
                        break
                if matched:
                    break  # Only one fixture type per method

            # IAsyncLifetime interface methods: InitializeAsync and DisposeAsync
            # Only for method_declaration (not local functions)
            if (
                node.type == "method_declaration" and not attributes
            ):  # Only if no explicit attributes were found
                if method_name in ("InitializeAsync", "DisposeAsync"):
                    fixture_type = (
                        "xunit_async_initialize"
                        if method_name == "InitializeAsync"
                        else "xunit_async_dispose"
                    )
                    scope = "per_class"
                    results.append(
                        _build_result(
                            node=node,
                            func_node=node,
                            src_bytes=src_bytes,
                            fixture_type=fixture_type,
                            scope=scope,
                        )
                    )

        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return results


# ---------------------------------------------------------------------------
# Go detector
# ---------------------------------------------------------------------------


def _detect_go(tree, src_bytes: bytes) -> list[FixtureResult]:
    """
    Go has no formal fixture annotation. We detect:
      1. TestMain(m *testing.M) — package-level setup
      2. Functions that are NOT TestXxx/BenchmarkXxx/ExampleXxx but are
         called from 3+ test functions in the same file (helper fixtures).
         Only functions with setup/teardown/fixture-like keywords are included
         to reduce false positives.
      3. t.Cleanup(func() { ... }) inline teardowns (noted but not extracted
         as top-level fixtures — counted inside calling test)
    """
    results = []
    all_func_names: set[str] = set()
    test_func_calls: dict[str, set[str]] = {}  # test_func -> {called functions}

    def collect_functions(node):
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                all_func_names.add(_source(name_node, src_bytes))
        for child in node.children:
            collect_functions(child)

    def collect_calls(node, current_test: str | None):
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                fname = _source(name_node, src_bytes)
                if re.match(r"^Test[A-Z]", fname):
                    current_test = fname
                    test_func_calls.setdefault(fname, set())

        if current_test and node.type == "call_expression":
            func = node.child_by_field_name("function")
            if func:
                test_func_calls[current_test].add(
                    _source(func, src_bytes).split("(")[0]
                )

        for child in node.children:
            collect_calls(child, current_test)

    collect_functions(tree.root_node)
    collect_calls(tree.root_node, None)

    # Helper functions called from ≥ 3 test functions (raised from 2 to reduce false positives)
    # Also filter to only include functions with setup/teardown/fixture-like keywords
    helper_call_count: dict[str, int] = {}
    for calls in test_func_calls.values():
        for c in calls:
            if c in all_func_names and not re.match(r"^(Test|Benchmark|Example)", c):
                helper_call_count[c] = helper_call_count.get(c, 0) + 1

    # Semantic filtering: only keep helpers with setup/teardown/fixture-like keywords
    setup_keywords = r"\b(setup|setUp|initialize|Init|prepare|create|build|Before|After|teardown|cleanup|Clean|Destroy|tear)\b"
    multi_used_helpers = {
        n
        for n, cnt in helper_call_count.items()
        if cnt >= 3  # Threshold raised from 2 to 3
        and re.search(setup_keywords, n, re.IGNORECASE)  # Semantic filtering
    }

    # Also include all TestMain functions regardless of calls
    multi_used_helpers_all = multi_used_helpers.copy()

    def extract_fixtures(node):
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _source(name_node, src_bytes)
                if name == "TestMain":
                    results.append(
                        _build_result(
                            node=node,
                            func_node=node,
                            src_bytes=src_bytes,
                            fixture_type="test_main",
                            scope="global",
                            framework="golang_testing",
                        )
                    )
                elif name in multi_used_helpers_all:
                    results.append(
                        _build_result(
                            node=node,
                            func_node=node,
                            src_bytes=src_bytes,
                            fixture_type="go_helper",
                            scope="per_test",
                            framework=None,  # Heuristic-detected helper, not framework-specific
                        )
                    )

        # testify/suite methods: SetupSuite, TeardownSuite, SetupTest, TeardownTest
        elif node.type == "method_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _source(name_node, src_bytes)
                if name in ("SetupSuite", "TeardownSuite", "SetupTest", "TeardownTest"):
                    scope = (
                        "per_class"
                        if name in ("SetupSuite", "TeardownSuite")
                        else "per_test"
                    )
                    fixture_type_map = {
                        "SetupSuite": "go_setup_suite",
                        "TeardownSuite": "go_teardown_suite",
                        "SetupTest": "go_setup_test",
                        "TeardownTest": "go_teardown_test",
                    }
                    results.append(
                        _build_result(
                            node=node,
                            func_node=node,
                            src_bytes=src_bytes,
                            fixture_type=fixture_type_map[name],
                            scope=scope,
                            framework="testify",
                        )
                    )

        for child in node.children:
            extract_fixtures(child)

    extract_fixtures(tree.root_node)
    return results


# ---------------------------------------------------------------------------
# Shared result builder
# ---------------------------------------------------------------------------


def _build_result(
    node,
    func_node,
    src_bytes: bytes,
    fixture_type: str,
    scope: str,
    framework: str = None,
) -> FixtureResult:
    src_text = _source(func_node, src_bytes)
    name_node = func_node.child_by_field_name("name")
    name = (
        _source(name_node, src_bytes)
        if name_node
        else f"<anonymous>_{node.start_point[0]}"
    )

    params_node = func_node.child_by_field_name("parameters")
    num_params = 0
    if params_node:
        num_params = sum(
            1 for c in params_node.children if c.type not in ("(", ")", ",")
        )

    return FixtureResult(
        name=name,
        fixture_type=fixture_type,
        framework=framework,
        scope=scope,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        loc=_count_loc(src_text),
        cyclomatic_complexity=_cyclomatic_complexity(node, src_bytes),
        cognitive_complexity=_cognitive_complexity(node, src_bytes),
        num_objects_instantiated=_count_instantiations(node, src_bytes),
        num_external_calls=_count_external_calls(node, src_bytes),
        num_parameters=num_params,
        raw_source=src_text,
        mocks=_extract_mocks(node, src_bytes),
    )


# ---------------------------------------------------------------------------
# Test function counting helpers
# ---------------------------------------------------------------------------


def _count_test_functions_python(tree, src_bytes: bytes) -> int:
    """Count test functions/methods in Python (test_* or inside TestCase)."""
    count = 0

    def visit(node):
        nonlocal count
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _source(name_node, src_bytes)
                if name.startswith("test_"):
                    count += 1
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return count


def _count_test_functions_java(tree, src_bytes: bytes) -> int:
    """Count test methods in Java (annotated with @Test or similar)."""
    count = 0
    test_annotations = {
        "@Test",
        "@Before",
        "@After",
        "@BeforeClass",
        "@AfterClass",
        "@BeforeEach",
        "@AfterEach",
    }

    def visit(node):
        nonlocal count
        if node.type == "method_declaration":
            # Check for test annotations
            for c in node.children:
                if c.type == "modifiers":
                    for mod_child in c.children:
                        if mod_child.type in ("marker_annotation", "annotation"):
                            ann_text = _source(mod_child, src_bytes).strip()
                            if any(ann_text.startswith(ta) for ta in test_annotations):
                                count += 1
                                return
            # Count methods starting with test (heuristic fallback)
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _source(name_node, src_bytes)
                if name.startswith("test"):
                    count += 1
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return count


def _count_test_functions_js(tree, src_bytes: bytes) -> int:
    """Count test blocks in JavaScript/TypeScript (describe, it, test calls)."""
    count = 0

    def visit(node):
        nonlocal count
        if node.type == "call_expression":
            func = node.child_by_field_name("function")
            if func:
                func_name = _source(func, src_bytes).strip().split("(")[0].strip()
                if func_name in ("it", "test", "describe"):
                    count += 1
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return count


def _count_test_functions_go(tree, src_bytes: bytes) -> int:
    """Count test functions in Go (functions starting with Test)."""
    count = 0

    def visit(node):
        nonlocal count
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _source(name_node, src_bytes)
                if name.startswith("Test"):
                    count += 1
        elif node.type == "method_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _source(name_node, src_bytes)
                if name.startswith("Test"):
                    count += 1
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return count


def _count_test_functions_csharp(tree, src_bytes: bytes) -> int:
    """Count test methods in C# (with test attributes or StartsWith Test)."""
    count = 0
    test_attributes = {"[Test]", "[TestMethod]", "[Fact]", "[Theory]"}

    def visit(node):
        nonlocal count
        if node.type in ("method_declaration", "local_function_statement"):
            # Check for test attributes
            for c in node.children:
                if c.type == "attribute_list":
                    for attr_node in c.children:
                        if attr_node.type == "attribute":
                            attr_text = _source(attr_node, src_bytes).strip()
                            if any(
                                attr_text.startswith(ta.rstrip("]"))
                                for ta in test_attributes
                            ):
                                count += 1
                                return
            # Heuristic: count methods/functions starting with "Test"
            name_node = node.child_by_field_name("name")
            if name_node:
                name = _source(name_node, src_bytes)
                if name.startswith("Test"):
                    count += 1
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return count


def _count_test_functions(tree, src_bytes: bytes, language: str) -> int:
    """Dispatch to language-specific test function counter."""
    counters = {
        "python": _count_test_functions_python,
        "java": _count_test_functions_java,
        "javascript": _count_test_functions_js,
        "typescript": _count_test_functions_js,
        "go": _count_test_functions_go,
        "csharp": _count_test_functions_csharp,
    }
    counter = counters.get(language)
    return counter(tree, src_bytes) if counter else 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

DETECTORS = {
    "python": _detect_python,
    "java": _detect_java,
    "javascript": _detect_js,
    "typescript": _detect_js,  # TypeScript shares JS grammar for this purpose
    "go": _detect_go,
    "csharp": _detect_csharp,
}


def extract_fixtures(file_path: Path, language: str) -> ExtractResult:
    """
    Parse a test file and return all fixture definitions found in it,
    along with file-level metrics (LOC, test function count).

    Returns ExtractResult with empty fixtures list if the file cannot be parsed
    or the language is not supported.
    """
    if language not in DETECTORS:
        logger.warning(f"No detector for language '{language}'")
        return ExtractResult(fixtures=[], file_loc=0, num_test_functions=0)

    # Log file size before reading (helps identify memory issues with large files)
    try:
        file_size_bytes = file_path.stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)
        # logger.info(f"[extract] Reading {file_path.name} ({file_size_mb:.2f} MB) for {language}")

        # Skip files larger than MAX_FILE_SIZE_BYTES (not real test files)
        if file_size_bytes > MAX_FILE_SIZE_BYTES:
            logger.warning(
                f"[extract] Skipping oversized file: {file_path.name} is {file_size_mb:.2f} MB (> {MAX_FILE_SIZE_BYTES / (1024*1024):.0f} MB limit)"
            )
            return ExtractResult(fixtures=[], file_loc=0, num_test_functions=0)

        # Warn if file is large but within limits
        if file_size_mb > 3:
            logger.info(
                f"[extract] Processing large test file: {file_path.name} ({file_size_mb:.2f} MB)"
            )
    except Exception as e:
        logger.debug(f"Could not get file size for {file_path}: {e}")

    try:
        src_bytes = file_path.read_bytes()
    except (OSError, PermissionError) as e:
        logger.warning(f"Cannot read {file_path}: {e}")
        return ExtractResult(fixtures=[], file_loc=0, num_test_functions=0)

    if not src_bytes.strip():
        return ExtractResult(fixtures=[], file_loc=0, num_test_functions=0)

    try:
        parser = _get_parser(language)
        tree = parser.parse(src_bytes)
    except Exception as e:
        logger.warning(f"Parse error in {file_path}: {e}")
        return ExtractResult(fixtures=[], file_loc=0, num_test_functions=0)

    try:
        fixtures = DETECTORS[language](tree, src_bytes)
        file_loc = _count_file_loc(src_bytes)
        num_test_functions = _count_test_functions(tree, src_bytes, language)
        return ExtractResult(
            fixtures=fixtures, file_loc=file_loc, num_test_functions=num_test_functions
        )
    except Exception as e:
        logger.warning(f"Detection error in {file_path}: {e}")
        return ExtractResult(fixtures=[], file_loc=0, num_test_functions=0)
