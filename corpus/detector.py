"""
AST-based fixture and mock detector using Tree-sitter.

For each language we define:
  1. how to identify test files (path heuristics already applied upstream)
  2. how to identify fixture *definitions* inside a test file
  3. how to identify mock *usages* inside a fixture subtree

The public interface is:
    extract_fixtures(file_path: Path, language: str) -> list[FixtureResult]

Each FixtureResult carries all the fields needed to populate the DB tables.
"""

import re
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum file size to process (5 MB). Test files should never be this large.
# Files larger than this are likely generated code, data files, or corrupted.
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

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
    scope: str  # per_test / per_class / per_module / global
    start_line: int
    end_line: int
    loc: int  # non-blank lines
    cyclomatic_complexity: int
    num_objects_instantiated: int
    num_external_calls: int
    num_parameters: int
    has_yield: bool
    raw_source: str
    mocks: list[MockResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Shared AST utilities
# ---------------------------------------------------------------------------


def _source(node, src_bytes: bytes) -> str:
    return src_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _count_loc(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def _cyclomatic_complexity(node, src_bytes: bytes) -> int:
    """
    Simple proxy: count branching keywords in the fixture source text.
    Not a rigorous McCabe calculation but fast and language-agnostic.
    """
    text = _source(node, src_bytes)
    branch_keywords = r"\b(if|elif|else|for|while|case|catch|except|&&|\|\|)\b"
    return 1 + len(re.findall(branch_keywords, text))


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
                        )
                    )
                
                # Nose-style fixtures: setup/teardown/setup_module/teardown_module
                elif name in (
                    "setup",
                    "teardown",
                    "setup_module",
                    "teardown_module",
                ):
                    scope = "per_module" if "module" in name else "per_test"
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
    "@BeforeClass": ("testng_before_class", "per_class"),  # TestNG (same name as JUnit4, handled specially)
    "@AfterMethod": ("testng_after_method", "per_test"),  # TestNG
    "@AfterClass": ("testng_after_class", "per_class"),  # TestNG
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
                        if mod_child.type == "marker_annotation" or mod_child.type == "annotation":
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
                    has_annotation = any(ann for ann in annotations if "@Before" in ann or "@After" in ann)
                    if not has_annotation:
                        scope = "per_test"
                        fixture_type = "junit3_setup" if method_name == "setUp" else "junit3_teardown"
                        results.append(
                            _build_result(
                                node=node,
                                func_node=node,
                                src_bytes=src_bytes,
                                fixture_type=fixture_type,
                                scope=scope,
                            )
                        )
        
        # Handle @Rule and @ClassRule field declarations
        elif node.type == "field_declaration":
            annotations = []
            for c in node.children:
                if c.type == "modifiers":
                    for mod_child in c.children:
                        if mod_child.type == "marker_annotation" or mod_child.type == "annotation":
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
    "before": ("mocha_before", "per_test"),  # default to per_test for ambiguous mocha hooks
    "after": ("mocha_after", "per_test"),  # default to per_test for ambiguous mocha hooks
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
                if name in JS_FIXTURE_CALLS:
                    fixture_type, scope = JS_FIXTURE_CALLS[name]
                    results.append(
                        _build_result(
                            node=target,
                            func_node=target,
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

    def visit(node):
        if node.type == "method_declaration":
            # Collect all attributes for this method
            # Attributes are in attribute_list children
            attributes = []
            for c in node.children:
                if c.type == "attribute_list":
                    # Extract attributes from inside the attribute_list
                    for attr_node in c.children:
                        if attr_node.type == "attribute":
                            attr_text = _source(attr_node, src_bytes).strip()
                            attributes.append(attr_text)
            
            # Check if any known fixture attribute is present
            for attr in attributes:
                for attr_name, (fixture_type, scope) in CSHARP_FIXTURE_ATTRIBUTES.items():
                    if attr_name in attr:
                        results.append(
                            _build_result(
                                node=node,
                                func_node=node,
                                src_bytes=src_bytes,
                                fixture_type=fixture_type,
                                scope=scope,
                            )
                        )
                        break  # Only one fixture type per method

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
        n for n, cnt in helper_call_count.items() 
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
    node, func_node, src_bytes: bytes, fixture_type: str, scope: str
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

    has_yield = "yield" in src_text

    return FixtureResult(
        name=name,
        fixture_type=fixture_type,
        scope=scope,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        loc=_count_loc(src_text),
        cyclomatic_complexity=_cyclomatic_complexity(node, src_bytes),
        num_objects_instantiated=_count_instantiations(node, src_bytes),
        num_external_calls=_count_external_calls(node, src_bytes),
        num_parameters=num_params,
        has_yield=has_yield,
        raw_source=src_text,
        mocks=_extract_mocks(node, src_bytes),
    )


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


def extract_fixtures(file_path: Path, language: str) -> list[FixtureResult]:
    """
    Parse a test file and return all fixture definitions found in it.
    Returns an empty list if the file cannot be parsed or the language
    is not supported.
    """
    if language not in DETECTORS:
        logger.warning(f"No detector for language '{language}'")
        return []

    # Log file size before reading (helps identify memory issues with large files)
    try:
        file_size_bytes = file_path.stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)
        #logger.info(f"[extract] Reading {file_path.name} ({file_size_mb:.2f} MB) for {language}")
        
        # Skip files larger than MAX_FILE_SIZE_BYTES (not real test files)
        if file_size_bytes > MAX_FILE_SIZE_BYTES:
            logger.warning(f"[extract] Skipping oversized file: {file_path.name} is {file_size_mb:.2f} MB (> {MAX_FILE_SIZE_BYTES / (1024*1024):.0f} MB limit)")
            return []
        
        # Warn if file is large but within limits
        if file_size_mb > 3:
            logger.info(f"[extract] Processing large test file: {file_path.name} ({file_size_mb:.2f} MB)")
    except Exception as e:
        logger.debug(f"Could not get file size for {file_path}: {e}")

    try:
        src_bytes = file_path.read_bytes()
    except (OSError, PermissionError) as e:
        logger.warning(f"Cannot read {file_path}: {e}")
        return []

    if not src_bytes.strip():
        return []

    try:
        parser = _get_parser(language)
        tree = parser.parse(src_bytes)
    except Exception as e:
        logger.warning(f"Parse error in {file_path}: {e}")
        return []

    try:
        return DETECTORS[language](tree, src_bytes)
    except Exception as e:
        logger.warning(f"Detection error in {file_path}: {e}")
        return []
