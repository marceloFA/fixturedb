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

Python fixtures are detected in five forms:

1. **pytest decorator style**: `@pytest.fixture` with scope extraction (`function`, `class`, `module`, `session`)
   - Scope properly mapped to test lifecycle: function → per_test, class → per_class, module → per_module, session → global

2. **unittest style**: Methods named `setUp`/`tearDown`/`setUpClass`/`tearDownClass`/`setUpModule`/`tearDownModule` in TestCase subclasses

3. **pytest class methods**: `setup_method()`/`teardown_method()`/`setup_class()`/`teardown_class()` in test classes

4. **nose style**: Module/function-level `setup()`/`teardown()`/`setup_module()`/`teardown_module()` fixtures

5. **Behave BDD fixtures** (NEW): `@given(...)`, `@when(...)`, `@then(...)`, `@step(...)` decorators for behavior-driven testing
   - Scope: Always per_test (steps execute within scenario context)
   - Framework: Behave (Python BDD framework)

The detector properly maps scope levels across all fixtures:
- `function`/`setup_method`/`teardown_method` → `per_test`
- `class`/`setup_class`/`teardown_class` → `per_class`
- `module`/`setUpModule`/`tearDownModule` → `per_module`
- `session` → `global`
- BDD steps → `per_test`

### Java

Java fixtures are detected via multiple mechanisms:

1. **JUnit 4 annotations**: `@Before`/`@After`/`@BeforeClass`/`@AfterClass`
2. **JUnit 5 annotations**: `@BeforeEach`/`@AfterEach`/`@BeforeAll`/`@AfterAll`
3. **JUnit 3 legacy**: Plain `setUp()`/`tearDown()` methods (no annotations) in TestCase subclasses
4. **TestNG annotations**: `@BeforeMethod`/`@AfterMethod`/`@BeforeClass`/`@AfterClass`
5. **Test rules**: `@Rule` (method-level, per_test) and `@ClassRule` (class-level, per_class) field declarations
6. **Spring Framework fixtures** (NEW):
   - `@Bean` — Factory method for test bean creation (scope: per_class)
   - `@TestConfiguration` — Test-specific configuration class (scope: per_class)
   - Framework: Spring, Spring Boot Test
7. **Cucumber BDD step definitions** (NEW):
   - `@Given(...)`, `@When(...)`, `@Then(...)`, `@And(...)`, `@But(...)` — Gherkin step definitions
   - `@Attachment` — Cucumber report attachment hooks
   - Scope: Always per_test (steps execute within scenario context)
   - Framework: Cucumber (Java BDD framework)

Scope mapping is consistent across frameworks:
- per-test setup: `@Before`, `@BeforeEach`, `@BeforeMethod`, `@Rule` → `per_test`
- per-class setup: `@BeforeClass`, `@BeforeAll`, `@ClassRule`, `@Bean`, `@TestConfiguration` → `per_class`
- BDD steps: `@Given`, `@When`, `@Then`, etc. → `per_test`

### JavaScript/TypeScript

JavaScript and TypeScript fixtures are detected via testing framework hook calls:

- **Jest/Mocha/Vitest**: `beforeEach()`, `beforeAll()`, `afterEach()`, `afterAll()` calls
- **Mocha implicit**: `before()`, `after()` (assumes per_test scope)
- **Scope mapping**: 
  - `beforeEach`, `afterEach` → `per_test`
  - `beforeAll`, `afterAll` → `per_class`
  - `before`, `after` → `per_test` (ambiguous without full context)

## Scope Semantics

Fixture scope is standardized across all languages:

- **per_test**: Fixture runs before/after every individual test (most common)
- **per_class**: Fixture runs once per test class/suite (setup for class, teardown after all tests in class)
- **per_module**: Fixture runs once per module/file (Python-specific)
- **global**: Fixture runs once for entire test suite (pytest session scope)

## Mock Detection

Mock usage is detected as a separate pass after fixture extraction using 23+ regex patterns covering:

- **Python**: `unittest.mock`, `pytest-mock`, `MagicMock`, `AsyncMock`
- **Java**: Mockito, EasyMock, MockK (Kotlin)
- **JavaScript/TypeScript**: Jest, Sinon, Vitest

For each mock framework detected, the fixture records:
- Framework name
- Target identifier (if extractable)
- Number of interactions configured (e.g., `.times()`, `.thenReturn()` calls)
- Raw snippet of code for manual inspection

## Fixture Metrics

For each detected fixture, the system computes the following quantitative metrics using industry-standard external tools where available:

### Code Complexity Metrics

**Cyclomatic Complexity**
- **Tool**: [Lizard](https://github.com/terryyin/lizard) v1.21.3+
- **Language Support**: Python, Java, JavaScript, TypeScript
- **Definition**: McCabe complexity (1 + count of decision points: if, for, while, try, catch, case)
- **Accuracy**: Academic standard metric, widely used in SonarQube and Codecov

**Cognitive Complexity**
- **Python**: Calculated via [complexipy library](https://github.com/rohaquinlop/complexipy) v5.0.0+ (fast Rust-based implementation of SonarQube cognitive complexity)
  - Metric: Nesting-depth-weighted complexity (higher nesting increases cost)
  - Formula: Σ(nesting_depth) over all control structures, following SonarQube's G. Ann Campbell research
  - Example: Three nested if-statements at depths 1, 2, 3 contribute 1+2+3=6 to cognitive complexity (vs. cyclomatic complexity of 3)
  
- **Other languages** (Java, JavaScript, TypeScript): Formula-based fallback
  - Formula: Cognitive Complexity = cyclomatic_complexity × average_nesting_depth
  - Rationale: Nested code is harder to understand than flat code; nesting depth better reflects human cognitive burden
  - Accuracy: Reasonable estimate when official Python implementation unavailable

### Code Structure Metrics

**Number of Parameters**
- **Tool**: [Lizard](https://github.com/terryyin/lizard) v1.21.3+
- **Language Support**: Python, Java, JavaScript, TypeScript
- **Definition**: Count of parameters in function/method signature
- **Accuracy**: Native Lizard metric, exact count

**Object Instantiations**
- **Tool**: [Lizard](https://github.com/terryyin/lizard) v1.21.3+ with post-processing
- **Language Support**: Python, Java, JavaScript, TypeScript
- **Definition**: Count of object creation via constructor calls
- **Implementation**: Filters Lizard's `external_call_count` for constructor patterns:
  - Java/JavaScript/TypeScript: `new ClassName(...)` or `new ClassName<T>(...)`
  - Python: `ClassName(...)` where ClassName starts with uppercase letter
- **Rationale**: Lizard counts all external function calls (too broad); we filter for constructors specifically using regex pattern matching
- **Accuracy**: Hybrid approach minimizes DIY logic while maintaining semantic accuracy

**Lines of Code (LOC)**
- **Tool**: [Lizard](https://github.com/terryyin/lizard) v1.21.3+
- **Language Support**: Python, Java, JavaScript, TypeScript
- **Definition**: Non-blank, non-comment lines of code
- **Accuracy**: Consistent with industry-standard LOC measurement

### Domain-Specific Metrics

**External I/O Calls**
- **Tool**: Custom regex pattern matching (no external tool captures I/O-specific operations)
- **Definition**: Count of database, HTTP, file I/O, and environment access patterns
- **Patterns**: `open(`, `requests.`, `http`, `socket(`, `subprocess.`, database connection strings, etc.
- **Rationale**: Lizard's external_call_count measures *function calls* (architecture metric), not *I/O operations* (dependency metric)
- **Accuracy**: Regex-based detection provides precision for analyzing fixture external dependencies

**Max Nesting Depth**
- **Tool**: Tree-sitter AST traversal (custom)
- **Language Support**: Python, Java, JavaScript, TypeScript
- **Definition**: Maximum level of nested block structures (if/for/while/try statements)
- **Ranges**: 1 (no nesting) to N (deeply nested)
- **Rationale**: Isolates structural nesting independent of control flow decisions; complementary to cognitive complexity
- **CSV Export**: Included (quantitative)

### Framework Detection

**Framework Identification**
- **Tool**: FRAMEWORK_REGISTRY (config.py) with regex pattern matching fallback
- **Supported Frameworks**: 40+ frameworks across 4 languages
  - Python: pytest, unittest, nose, nose2, doctest, behave, pytest-bdd, pytest-asyncio, testtools, trial, etc.
  - Java: junit, testng, spock, cucumber, mockito, easymock, powermock, etc.
  - JavaScript: jest, mocha, jasmine, ava, vitest, cucumber, sinon, tap, etc.
  - TypeScript: jest, mocha, vitest, cucumber, sinon, etc.
- **Registry**: Authoritative list of known frameworks per language maintained in `collection/config.py`
- **Validation**: `is_known_framework()` and `_validate_framework()` functions validate framework names
- **Extensibility**: Registry can generate detection patterns in future versions

### Mock Detection

Mock usage is detected as a separate pass after fixture extraction using 40+ regex patterns covering:

- **Python**: `unittest.mock`, `pytest-mock`, `MagicMock`, `AsyncMock`, `patch`, `Mock`, `Mock.assert_*`
- **Java**: Mockito (`when`, `thenReturn`, `verify`), EasyMock (`expect`, `replay`), MockK (Kotlin)
- **JavaScript/TypeScript**: Jest (`jest.mock`, `jest.fn`, `jest.spyOn`), Sinon (`sinon.spy`, `sinon.stub`, `sinon.mock`), Vitest (`vi.mock`, `vi.spyOn`)

For each mock framework detected, the fixture records:
- **framework**: Name of mock framework (e.g., `mockito`, `unittest_mock`, `sinon`)
- **mock_style**: Classification of mock usage (stub/mock/spy/fake)
- **target_layer**: What is being mocked (boundary/infra/internal)
- **num_interactions_configured**: Count of `.verify()`, `.thenReturn()`, or similar assertion calls
- **raw_snippet**: Code snippet for manual inspection and validation

---

## Documentation References

For detailed fixture patterns, examples, and framework reference:
- [16-fixture-patterns-reference.md](../usage/16-fixture-patterns-reference.md) — Comprehensive catalog of all 50+ fixture types, frameworks, detection patterns, and examples across 4 languages (Python, Java, JavaScript, TypeScript)

**For detailed metric calculations, external tools, and academic references:**
- [20-metrics-reference.md](20-metrics-reference.md) — Complete documentation of all quantitative metrics, including which use external tools (Lizard, complexipy, Tree-sitter) vs. custom implementations, reliability assessments, and academic citations for publication

---

## Post-Processing & Relationship Detection

After initial AST-based detection, fixtures undergo post-processing to calculate file-wide context metrics and detect fixture relationships:

### Fixture Reuse Count

- **Tool**: AST analysis (custom)
- **Definition**: Number of test functions that use this fixture as a parameter
- **Implementation**: 
  - **Python/pytest**: Scans test function signatures for fixture name in parameter lists
  - **Java**: Counts test methods in same class as setup annotations
  - **JavaScript/TypeScript**: Counts test functions using fixture in scope
- **Calculation Timing**: Post-processing step after all fixtures detected (requires file-wide fixture name registry)
- **Utility**: Fixture modularity metric; complex fixtures used by many tests have system-wide impact
- **CSV Export**: Included (quantitative metric)

### Teardown Pairing

- **Tool**: AST pattern matching (custom)
- **Definition**: Binary indicator (0/1) whether fixture has cleanup logic paired with setup
- **Detection**:
  - **Python**: Presence of `yield` statement (fixture-style cleanup) or `tearDown` method paired with `setUp`
  - **Java**: `@AfterEach`/`@After` or `@AfterAll`/`@AfterClass` in same class as setup annotations
  - **JavaScript**: `afterEach()` or `afterAll()` call paired with `beforeEach()` or `beforeAll()`
- **Calculation Timing**: Post-processing step (after initial detection, cross-references setup/teardown pairs)
- **Utility**: Indicator of resource cleanup discipline; fixtures without teardown are potential leak indicators
- **CSV Export**: Excluded (qualitative indicator, internal analysis only)

### Repository Contributor Count

- **Tool**: GitHub REST API v2022-11-28
- **Definition**: Number of unique contributors to the GitHub repository
- **Source**: GitHub API endpoint `/repos/{owner}/{repo}/contributors`
- **Implementation**: Fetches contributor count via Link header pagination (handles API caps)
- **Utility**: Project maturity and team size proxy; correlates with test practice variation
- **CSV Export**: Included (quantitative metric)

---

- **Tool**: Regex pattern matching on function signatures (custom)
- **Definition**: List of fixture names that this fixture depends on via parameter injection
- **Implementation**: `_detect_fixture_dependencies()` in `detector.py`
  - For **pytest fixtures**: Parses `@pytest.fixture def fixture_name(dep1, dep2, ...):` to extract parameters
  - Matches parameter names against registry of known fixtures in same file
  - Records only confirmed fixture dependencies (ignoring non-fixture parameters)
- **Example**: 
  ```python
  @pytest.fixture
  def db():
      return MockDB()
  
  @pytest.fixture
  def service(db):  # <- depends on 'db' fixture
      return UserService(db)
  
  def test_something(service):  # test depends on 'service' which depends on 'db'
      pass
  ```
  Dependency: `service.fixture_dependencies = ['db']`
- **Calculation Timing**: Post-processing step immediately after AST detection
- **Utility**: Enables fixture dependency graph analysis, modularity analysis, scope constraint validation
- **Language Scope**: Currently implemented for **Python/pytest only** (other frameworks don't have explicit dependency syntax)

### Fixture Scope Propagation

- **Tool**: Constraint satisfaction (custom graph algorithm)
- **Definition**: Propagates scope constraints based on fixture dependencies to ensure valid configurations
- **Implementation**: `_propagate_fixture_scopes()` in `detector.py`
- **Scope Hierarchy**: `per_test < per_class < per_module < global`
  - When fixture A depends on fixture B, scope(A) ≤ scope(B)
  - If violated, downgrade A's scope to match B's
- **Example**:
  ```python
  @pytest.fixture(scope="module")
  def db():
      return setup_expensive_db()
  
  @pytest.fixture(scope="global")  # Would be invalid!
  def service(db):  # depends on module-scoped fixture
      return UserService(db)
  
  # After propagation: service.scope = "module" (downgraded from "global")
  ```
- **Rationale**: Prevents impossible configurations where broader-scoped fixtures depend on narrower-scoped ones
- **Calculation Timing**: Post-processing step after dependency detection (may require multiple passes for dependency chains)
- **Language Scope**: Currently implemented for **Python/pytest only**

### Post-Processing Order

The fixture post-processing pipeline executes in this order (see `extract_fixtures()` in `detector.py`):

1. **Initial detection**: AST-based fixture identification per language
2. **Mock detection**: Regex patterns for mock framework usage
3. **Reuse counting**: Count test functions using each fixture
4. **Fixture dependency detection**
5. **Scope propagation**
6. **Teardown pairing**: Detect setup/cleanup pairs

---

## File-Level Metrics

In addition to fixture-level metrics, the system collects file-level aggregates:

### File Lines of Code (file_loc)

- **Tool**: [Lizard](https://github.com/terryyin/lizard) v1.21.3+
- **Language Support**: Python, Java, JavaScript, TypeScript, Go
- **Definition**: Total lines of code in file
- **Implementation**: `complexity_provider.get_file_loc()` extracts `file_measure.total_lines` from Lizard analysis
- **Basis**: Reuses already-parsed file data from complexity analysis; consistent with fixture-level metrics approach
- **Benefit**: Reuses already-parsed file data from complexity analysis; consistent with fixture-level metrics approach

### Number of Test Functions (num_test_funcs)

- **Tool**: [Lizard](https://github.com/terryyin/lizard) v1.21.3+
- **Language Support**: Python, Java, JavaScript, TypeScript, Go
- **Definition**: Count of all functions/methods in file
- **Implementation**: `complexity_provider.get_file_function_count()` returns `len(lizard_result.function_list)`
- **Basis**: Migrated from AST-based counting per language
- **Accuracy Note**: Counts all functions (including helpers), not just test functions; on test files this distinction is minimal
- **Benefit**: Consistency with fixture-level metrics; leverages proven Lizard infrastructure

**File-Level Aggregates** (not extracted directly):
- `num_fixtures`: Aggregated from `fixtures` table (SQL: `COUNT(*)` where `is_fixture=true`)
- `total_fixture_loc`: Aggregated from `fixtures` table (SQL: `SUM(loc)` of fixture-level LOC)

---

## Metrics Architecture Overview & Tool Decisions

This section provides the complete audit of which metrics use external tools vs. custom implementations, with rationale for each decision.

### Fixture-Level Metrics Summary Table

| Metric | Type | Tool(s) Used | Phase | Phase | Rationale |
|--------|------|-------------|-------|-------|-----------|
| `loc` | Code Property | Lizard v1.21.3+ | P2 | Fixture | Industry-standard code metric; consistent with fix-level metrics |
| `cyclomatic_complexity` | Code Property | Lizard v1.21.3+ | P1 | Fixture | McCabe's standard; widely recognized metric |
| `cognitive_complexity` | Code Property | Lizard + complexipy v5.0.0+ | P1 | Fixture | SonarQube standard; Python-native, fallback formula for others |
| `num_parameters` | Syntax | Lizard v1.21.3+ | P2 | Fixture | Direct extraction from Lizard's parameter_count |
| `num_objects_instantiated` | Semantic | Lizard v1.21.3+ (post-processed) | P2 | Fixture | Filters Lizard's external_call_count for constructor patterns |
| `num_external_calls` | Semantic | Custom regex | P2 | Fixture | Domain-specific I/O detection (not general function calls) |
| `fixture_type` | Classification | Custom AST + regex | P1 | Fixture | Domain-specific framework patterns; no generalizable tool |
| `scope` | Classification | Tree-sitter (AST) | P1 | Fixture | Built-in; custom scope rules per language |
| `framework` | Classification | FRAMEWORK_REGISTRY + regex | P2 | Fixture | Standardized registry of 44+ frameworks; extensible design |
| `max_nesting_depth` | Code Property | Tree-sitter AST | P1 | Fixture | Structual nesting independent of complexity |
| `reuse_count` | Usage | Custom AST | P1 | Fixture | Post-processing metric; requires file-wide fixture context |
| `has_teardown_pair` | Pattern | Custom AST + regex | P1 | Fixture | Framework-specific cleanup patterns |
| `fixture_dependencies` | Relationships | Custom regex | P4 | Fixture | pytest-specific parameter injection (post-processing) |
| `raw_source` | Data | N/A | P1 | Fixture | Text extraction for reproducibility |

### External Tools Migrations

**5 metrics completed migration to industry-standard tools:**

1. **cyclomatic_complexity** (P1) → Lizard v1.21.3+
   - Replaces: Custom Tree-sitter decision point counting
   - Benefit: McCabe-standard metric, proven library

2. **cognitive_complexity** (P1) → complexipy v5.0.0+ (Python) + formula (others)
   - Replaces: Custom complexity heuristics
   - Benefit: SonarQube-standard metric for Python with fast Rust implementation; formula fallback for cross-language consistency

3. **num_parameters** (P2) → Lizard v1.21.3+
   - Replaces: Direct AST parameter counting
   - Benefit: Consistent parameter definition across languages

4. **num_objects_instantiated** (P2) → Lizard external_call_count + post-processing
   - Replaces: Regex pattern matching for `new X(...)` 
   - Benefit: Reduces DIY code; Lizard's counting provides baseline validation

5. **framework** (P2) → FRAMEWORK_REGISTRY + regex
   - Replaces: Ad-hoc framework detection
   - Benefit: Standardized registry; extensible for new frameworks

### Custom Metrics (Domain-Specific, No Tool Available)

**4 metrics kept as custom implementations:**

These metrics require domain knowledge about testing frameworks that no generalizable tool provides.

---

## Why Certain Metrics Are Custom (Detailed Rationale)

### num_external_calls: I/O Operations vs. Function Calls

**Problem**: Lizard's `external_call_count` is NOT suitable for our use case.

**Difference**:
| Metric | Definition | Use Case |
|--------|-----------|----------|
| **Lizard's external_call_count** | Calls to external functions (across module boundaries) | Architectural coupling analysis |
| **Our num_external_calls** | External I/O and system operations (database, HTTP, files, subprocess) | Testing infrastructure dependencies |

**Why we need custom implementation:**
- Lizard counts *all* external function calls (e.g., calling a helper function in another module)
- We specifically want *I/O operations* (e.g., `db.query()`, `requests.get()`, `open()`, `subprocess.run()`)
- These are semantically different: a fixture might call many internal functions but only interact with one external system
- Custom regex patterns for I/O (file operations, HTTP, database, subprocess) provide precision

**Patterns detected** (Python examples):
```python
# I/O operations we detect:
open(...)           # File operations
connect(...)        # Network/DB connections
requests.get()      # HTTP client
session.query()     # SQLAlchemy
subprocess.run()    # System calls
socket(...)         # Raw sockets
tempfile.NamedTemporaryFile()  # Temp file creation
```

**Decision**: Keep custom regex implementation; Lizard's metric serves different purpose (architectural coupling, not infrastructure dependency)

---

### fixture_type: Domain-Specific Framework Patterns

**Problem**: No tool can distinguish between fixture definitions, helper functions, and test functions.

**Why domain knowledge is essential:**

1. **Semantic distinction requires framework patterns**:
   ```python
   # Which of these are fixtures?
   def my_fixture():  # Helper function
       return data
   
   @pytest.fixture  # pytest fixture
   def my_fixture():
       return data
   
   def setUp(self):  # unittest fixture (convention-based)
       pass
   
   def my_helper():  # Helper function
       return data
   ```
   No AST tool can reliably distinguish these without framework-specific knowledge.

2. **Different frameworks use entirely different patterns**:
   - **pytest**: `@pytest.fixture` decorator (explicit)
   - **unittest**: `def setUp(self)` method name (convention)
   - **Jest**: `beforeEach(() => {})` function call (API)
   - **JUnit**: `@BeforeEach` annotation (metadata)

3. **Tool analysis**:

| Tool | Support | Capability | Limitation |
|------|---------|-----------|------------|
| **AST Libraries** | Partial | Can identify decorators/names | No semantic understanding of fixture vs. helper |
| **Type checkers** (mypy, tsc) | No | Would require type hints | Not all fixtures have type hints; Python-centric |
| **Pre-trained models** | No | Could classify by naming conventions | No public models for fixture classification |
| **Custom pattern matching** | Full | Encodes framework-specific rules | Requires maintenance as frameworks evolve |

**Current implementation strengths**:
- Accurate: Validated against real fixtures across 4 languages
- Fast: Regex-based detection is computationally efficient
- Extensible: Easy to add new fixture types/frameworks
- Maintainable: Patterns organized clearly by language

**Decision**: Keep custom implementation; no viable tool alternative exists, and current approach is well-tested.

---

### num_interactions_configured: Mock Configuration Counting

**Problem**: Counting mock assertions/verifications requires understanding mock framework semantics.

**Why custom implementation**:
- Different frameworks use different assertion syntax
  - unittest_mock: `.assert_called()`, `.assert_called_with()`
  - Mockito: `.verify(mock).method()`
  - Jest: `.toHaveBeenCalled()`, `.toHaveBeenCalledWith()`
  - Sinon: `.calledWith()`, `.calledOnce()`
- Custom regex patterns recognize all frameworks and assertion patterns
- Counts are validated through test suite to match expected values

---

## Framework & Mock Framework Validation

### FRAMEWORK_REGISTRY (44+ Frameworks)

Central registry maintaining all supported testing frameworks:

**Location**: `collection/config.py`

**Coverage**:
- **Python** (12+ frameworks): pytest, unittest, nose, nose2, behave, doctest, testtools, trial, testscenarios, etc.
- **Java** (10+ frameworks): junit, testng, spock, cucumber, mockito, easymock, powermock, jmockit, etc.
- **JavaScript** (12+ frameworks): jest, mocha, jasmine, ava, vitest, cucumber, tap, qunit, etc.
- **TypeScript** (8+ frameworks): jest, mocha, vitest, cucumber, sinon, etc.

**Functions**:
- `is_known_framework(framework, language)`: Validate framework exists in registry
- `get_known_frameworks(language)`: Return all registered frameworks for a language
- `_validate_framework()`: Log warning if detected framework not in registry (forward-compatible)

**Design**: Allows system to be forward-compatible (unknown frameworks are recorded but noted) while maintaining canonical registry of known ones.

---

## Framework References & Official Homepages

This section provides direct links to the official homepages and documentation for all supported testing and mocking frameworks. Use these links to learn more about framework-specific features, installation, and best practices.

### Python Testing Frameworks

| Framework | Type | Official Homepage | Documentation |
|-----------|------|-------------------|-----------------|
| **pytest** | Unit Testing | https://pytest.org/ | https://docs.pytest.org/ |
| **unittest** | Unit Testing | https://docs.python.org/3/library/unittest.html | https://docs.python.org/3/library/unittest.html |
| **nose** | Test Discovery | https://nose.readthedocs.io/ | https://nose.readthedocs.io/ |
| **nose2** | Test Discovery | https://nose2.readthedocs.io/ | https://nose2.readthedocs.io/ |
| **doctest** | Documentation Testing | https://docs.python.org/3/library/doctest.html | https://docs.python.org/3/library/doctest.html |
| **behave** | BDD Framework | https://behave.readthedocs.io/ | https://behave.readthedocs.io/ |
| **pytest-bdd** | BDD Framework | https://pytest-bdd.readthedocs.io/ | https://pytest-bdd.readthedocs.io/ |
| **testtools** | Extended Testing | https://testtools.readthedocs.io/ | https://testtools.readthedocs.io/ |
| **trial** | Async Testing | https://twistedmatrix.com/documents/current/core/howto/trial.html | https://twistedmatrix.com/documents/current/core/howto/trial.html |

### Python Mocking Frameworks

| Framework | Type | Official Homepage | Documentation |
|-----------|------|-------------------|-----------------|
| **unittest.mock** | Built-in Mocking | https://docs.python.org/3/library/unittest.mock.html | https://docs.python.org/3/library/unittest.mock.html |
| **pytest-mock** | Pytest Fixtures | https://pytest-mock.readthedocs.io/ | https://pytest-mock.readthedocs.io/ |
| **pytest-asyncio** | Async Fixtures | https://pytest-asyncio.readthedocs.io/ | https://pytest-asyncio.readthedocs.io/ |

### Java Testing Frameworks

| Framework | Type | Official Homepage | Documentation |
|-----------|------|-------------------|-----------------|
| **JUnit** | Unit Testing | https://junit.org/ | https://junit.org/junit4/ (v4) / https://junit.org/junit5/ (v5) |
| **TestNG** | Unit Testing | https://testng.org/ | https://testng.org/doc/ |
| **Spock** | BDD Framework | https://spockframework.org/ | https://spockframework.org/spock/docs/ |
| **Cucumber** | BDD Framework | https://cucumber.io/ | https://cucumber.io/docs/cucumber/ |
| **Arquillian** | Container Testing | https://arquillian.org/ | https://arquillian.org/docs/ |

### Java Mocking Frameworks

| Framework | Type | Official Homepage | Documentation |
|-----------|------|-------------------|-----------------|
| **Mockito** | Mocking Framework | https://site.mockito.org/ | https://javadoc.io/doc/org.mockito/mockito-core/latest/org/mockito/Mockito.html |
| **EasyMock** | Mocking Framework | https://easymock.org/ | https://easymock.org/user-guide.html |
| **PowerMock** | Advanced Mocking | https://powermock.github.io/ | https://github.com/powermock/powermock/wiki |

### JavaScript Testing Frameworks

| Framework | Type | Official Homepage | Documentation |
|-----------|------|-------------------|-----------------|
| **Jest** | Unit Testing | https://jestjs.io/ | https://jestjs.io/docs/getting-started |
| **Mocha** | Unit Testing | https://mochajs.org/ | https://mochajs.org/#getting-started |
| **Jasmine** | Unit Testing | https://jasmine.github.io/ | https://jasmine.github.io/pages/getting_started.html |
| **AVA** | Test Runner | https://github.com/avajs/ava | https://github.com/avajs/ava#readme |
| **Vitest** | Unit Testing | https://vitest.dev/ | https://vitest.dev/guide/ |
| **Cucumber** | BDD Framework | https://cucumber.io/ | https://cucumber.io/docs/cucumber/ |
| **TAP** | Test Protocol | https://node-tap.org/ | https://node-tap.org/docs/ |
| **uvu** | Test Runner | https://github.com/lukeed/uvu | https://github.com/lukeed/uvu#readme |

### JavaScript Mocking Frameworks

| Framework | Type | Official Homepage | Documentation |
|-----------|------|-------------------|-----------------|
| **Sinon.JS** | Spies, Stubs, Mocks | https://sinonjs.org/ | https://sinonjs.org/releases/latest/ |

### TypeScript Testing Frameworks

| Framework | Type | Official Homepage | Documentation |
|-----------|------|-------------------|-----------------|
| **Jest** | Unit Testing | https://jestjs.io/ | https://jestjs.io/docs/getting-started |
| **Mocha** | Unit Testing | https://mochajs.org/ | https://mochajs.org/#getting-started |
| **Jasmine** | Unit Testing | https://jasmine.github.io/ | https://jasmine.github.io/pages/getting_started.html |
| **Vitest** | Unit Testing | https://vitest.dev/ | https://vitest.dev/guide/ |
| **AVA** | Test Runner | https://github.com/avajs/ava | https://github.com/avajs/ava#readme |
| **Cucumber** | BDD Framework | https://cucumber.io/ | https://cucumber.io/docs/cucumber/ |

### TypeScript Mocking Frameworks

| Framework | Type | Official Homepage | Documentation |
|-----------|------|-------------------|-----------------|
| **Sinon.JS** | Spies, Stubs, Mocks | https://sinonjs.org/ | https://sinonjs.org/releases/latest/ |

---

### Mock Framework Dependency Validation

**Function**: `is_mock_framework_available(framework, language, repo_path)`

**Purpose**: Secondary validation that detected mock frameworks are actually installed in the project.

**Implementation**: Scans language-specific dependency files for framework packages.

**Language-Specific Coverage**:

1. **Python**: Scans `requirements.txt`, `setup.py`, `pyproject.toml`, `poetry.lock`
   - Maps: unittest_mock → built-in, pytest_mock → pytest-mock, mockito → mockito-python, etc.

2. **Java**: Scans `pom.xml`, `build.gradle`, `build.gradle.kts`
   - Searches for `<artifactId>` and `<groupId>` containing framework names

3. **JavaScript/TypeScript**: Scans `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`
   - Checks both `dependencies` and `devDependencies` sections

**Return Behavior**:
- Returns `True` if framework found in any dependency file
- Returns `False` if framework NOT found (repo context provided)
- Returns `True` if no repo context provided (conservative default)

**Rationale**: Reduces false positives from pattern matching; confirms detected frameworks are actually available.

---

## Limitations and Known Issues

1. **Scope inference limitations** in JavaScript: Dynamically-scoped or conditionally-registered fixtures may be misclassified
2. **Indirect fixture dependencies**: pytest fixtures with `indirect=True` or fixture factories are not tracked
3. **Parametrized test setup**: Multi-run parametrization markers are detected but not correlated with fixtures
4. **Inheritance**: Parent class fixtures in Python/Java/C# are not inferred from super-class analysis
5. **Conditional registration**: Setup code inside if/try blocks or dynamically registered fixtures may be missed
6. **BDD Feature Files**: `.feature` files with Gherkin syntax are not parsed directly; only step definition code is detected

See [Limitations](../reference/12-limitations.md) for false-positive and false-negative rates by language.

