# Fixture Detection Logic

Detection is implemented in `collection/detector.py` using
[Tree-sitter](https://tree-sitter.github.io/tree-sitter/) grammars.
Each language has a dedicated detector function that walks the AST
and matches fixture-defining nodes.

Mock detection is a second pass over the fixture's source text using
compiled regular expressions covering all major mock frameworks per language.
It is intentionally language-agnostic to catch cross-language patterns and
runs after the AST phase.

## Language-specific detectors

### Python

Python fixtures are detected in three forms:

1. **pytest decorator style**: `@pytest.fixture` with scope extraction (`function`, `class`, `module`, `session`)
2. **unittest style**: Methods named `setUp`/`tearDown`/`setUpClass`/`tearDownClass`/`setUpModule`/`tearDownModule` in TestCase subclasses
3. **pytest class methods**: `setup_method()`/`teardown_method()`/`setup_class()`/`teardown_class()` in test classes
4. **nose style**: Module/function-level `setup()`/`teardown()`/`setup_module()`/`teardown_module()` fixtures

The detector properly maps scope levels:
- `function`/`setup_method`/`teardown_method` → `per_test`
- `class`/`setup_class`/`teardown_class` → `per_class`
- `module`/`setUpModule`/`tearDownModule` → `per_module`
- `session` → `global`

### Java

Java fixtures are detected via multiple mechanisms:

1. **JUnit 4 annotations**: `@Before`/`@After`/`@BeforeClass`/`@AfterClass`
2. **JUnit 5 annotations**: `@BeforeEach`/`@AfterEach`/`@BeforeAll`/`@AfterAll`
3. **JUnit 3 legacy**: Plain `setUp()`/`tearDown()` methods (no annotations) in TestCase subclasses
4. **TestNG annotations**: `@BeforeMethod`/`@AfterMethod`/`@BeforeClass`/`@AfterClass`
5. **Test rules**: `@Rule` (method-level, per_test) and `@ClassRule` (class-level, per_class) field declarations

Scope mapping is consistent across frameworks:
- per-test setup: `@Before`, `@BeforeEach`, `@BeforeMethod`, `@Rule` → `per_test`
- per-class setup: `@BeforeClass`, `@BeforeAll`, `@ClassRule` → `per_class`

### JavaScript/TypeScript

JavaScript and TypeScript fixtures are detected via testing framework hook calls:

- **Jest/Mocha/Vitest**: `beforeEach()`, `beforeAll()`, `afterEach()`, `afterAll()` calls
- **Mocha implicit**: `before()`, `after()` (assumes per_test scope)
- **Scope mapping**: 
  - `beforeEach`, `afterEach` → `per_test`
  - `beforeAll`, `afterAll` → `per_class`
  - `before`, `after` → `per_test` (ambiguous without full context)

### C#

C# fixtures are detected via attributes on methods:

1. **NUnit framework**: `[SetUp]`/`[TearDown]`/`[OneTimeSetUp]`/`[OneTimeTearDown]`
2. **xUnit framework**: `[Fact]` and `[Theory]` test methods
3. **MSTest framework**: `[TestInitialize]`/`[TestCleanup]`/`[ClassInitialize]`/`[ClassCleanup]`

Scope mapping:
- `[SetUp]`, `[TestInitialize]` → `per_test`
- `[TearDown]`, `[TestCleanup]` → `per_test`
- `[OneTimeSetUp]`, `[ClassInitialize]` → `per_class`
- `[OneTimeTearDown]`, `[ClassCleanup]` → `per_class`

### Go

Go has no formal fixture annotation system. The detector uses a hybrid approach:

1. **Explicit TestMain**: Any `TestMain(m *testing.M)` function is classified as a fixture with `global` scope
2. **Helper heuristic**: Non-test functions (not prefixed `Test`, `Benchmark`, or `Example`) that are:
   - Called from ≥ 3 test functions in the same file (lowered threshold from 2 for precision)
   - AND have names containing setup/teardown/fixture-like keywords (e.g., `setUp`, `initialize`, `prepare`, `teardown`, `cleanup`)
   
   These are classified as `go_helper` fixtures with `per_test` scope.

3. **t.Cleanup() callbacks**: Inline teardown functions registered via `t.Cleanup(func() {...})` are noted but not extracted as top-level fixtures

The semantic filtering (keyword checking) significantly reduces false positives from catching generic helper functions.

## Scope Semantics

Fixture scope is standardized across all languages:

- **per_test**: Fixture runs before/after every individual test (most common)
- **per_class**: Fixture runs once per test class/suite (setup for class, teardown after all tests in class)
- **per_module**: Fixture runs once per module/file (Python-specific)
- **global**: Fixture runs once for entire test suite (Go TestMain, pytest session scope)

## Mock Detection

Mock usage is detected as a separate pass after fixture extraction using 23+ regex patterns covering:

- **Python**: `unittest.mock`, `pytest-mock`, `MagicMock`, `AsyncMock`
- **Java**: Mockito, EasyMock, MockK (Kotlin)
- **JavaScript/TypeScript**: Jest, Sinon, Vitest
- **Go**: GoMock, Testify/mock
- **C#**: Moq, NSubstitute, FakeItEasy, Rhino Mocks

For each mock framework detected, the fixture records:
- Framework name
- Target identifier (if extractable)
- Number of interactions configured (e.g., `.times()`, `.thenReturn()` calls)
- Raw snippet of code for manual inspection

## Fixture Metrics

For each detected fixture, the system computes:

- **LOC** (Lines of Code): Non-blank lines excluding comments

- **Cyclomatic Complexity**: Simple proxy counting branching keywords (if, for, while, try/catch, etc.)

- **Cognitive Complexity**: A refinement of cyclomatic complexity that weights control structures by nesting depth and detects recursion. 
    - Formula: Cognitive Complexity = Σ(nesting_depth) over all control structures + 5 × (number of recursive calls)
    - Example: three nested if-statements at depths 1, 2, 3 contribute 1+2+3 = 6 to cognitive complexity (vs. cyclomatic complexity of 3)
    - Rationale: Nested code is harder to understand than flat code; nesting depth better reflects human cognitive burden
    - See `collection/detector.py` for implementation via tree-sitter AST traversal

- **Object Instantiations**: Count of `new Foo(...)` calls and constructor-like calls

- **External Calls**: Count of database, HTTP, file I/O, and environment access patterns

- **Parameters**: Number of parameters/injection points

- **Has Yield**: Boolean indicating generator/yield expressions (Python fixtures)

These metrics support RQ1 fixture taxonomy classification and fixture quality analysis.

## Limitations and Known Issues

1. **Scope inference limitations** in JavaScript: Dynamically-scoped or conditionally-registered fixtures may be misclassified
2. **Indirect fixture dependencies**: pytest fixtures with `indirect=True` or fixture factories are not tracked
3. **Parametrized test setup**: Multi-run parametrization markers are detected but not correlated with fixtures
4. **Inheritance**: Parent class fixtures in Python/Java/C# are not inferred from super-class analysis
5. **Conditional registration**: Setup code inside if/try blocks or dynamically registered fixtures may be missed

See [Limitations](12-limitations.md) for false-positive and false-negative rates by language.

