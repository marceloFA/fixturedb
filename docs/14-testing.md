# Testing Strategy and Execution

This document describes the comprehensive test suite for FixtureDB, including test organization, how to run tests, and guidelines for creating new tests.

## Test Overview

The test suite validates the **fixture extraction module** (`collection/detector.py`), which uses Tree-sitter ASTs to detect test fixtures across 6 programming languages. The suite has 204+ test cases organized into 6 categories.

**Key metrics:**
- **204+ test methods** across all categories
- **6 languages covered**: Python, Java, JavaScript, TypeScript, Go, C#
- **Language-specific test files** for clarity in academic papers
- **Test framework**: pytest with custom assertion helpers

## Test Organization

### Directory Structure

```
tests/
├── conftest.py                      # Shared pytest fixtures and helpers
├── TEST_PLAN.md                     # Comprehensive test strategy document
├── fixtures/                        # Test data files (future use)
├── test_extractor_unit/             # Category 1: Unit tests
│   ├── test_python_fixtures.py      (22 tests)
│   ├── test_java_fixtures.py        (13 tests)
│   ├── test_javascript_fixtures.py  (10 tests)
│   ├── test_typescript_fixtures.py  (8 tests)
│   ├── test_go_fixtures.py          (5 tests)
│   └── test_csharp_fixtures.py      (10 tests)
├── test_extractor_metadata/         # Category 2: Metadata accuracy
│   ├── test_line_numbers.py         (30+ tests)
│   └── test_fixture_types_and_scopes.py (25+ tests)
├── test_extractor_edge_cases/       # Category 3: Edge case robustness
│   └── test_edge_cases.py           (50+ tests)
├── test_mock_detection/             # Category 5: Mock patterns
│   ├── test_python_mock_patterns.py (10 tests)
│   ├── test_java_mock_patterns.py   (6 tests)
│   ├── test_javascript_mock_patterns.py (4 tests)
│   ├── test_typescript_mock_patterns.py (4 tests)
│   ├── test_go_mock_patterns.py     (3 tests)
│   └── test_csharp_mock_patterns.py (3 tests)
└── test_integration/                # Category 6: Realistic fixtures
    ├── test_python_realistic_fixtures.py (8 tests)
    ├── test_java_realistic_fixtures.py (3 tests)
    ├── test_javascript_realistic_fixtures.py (3 tests)
    ├── test_typescript_realistic_fixtures.py (2 tests)
    ├── test_go_realistic_fixtures.py (2 tests)
    └── test_csharp_realistic_fixtures.py (3 tests)
```

## Test Categories

### 1. Unit Tests (Per-Language) — 68 tests

**Scope:** Small code snippets (1-10 lines)

**What they test:**
- Positive detection: Fixtures are found when they exist
- Negative detection: Non-fixtures are correctly excluded
- Multiple fixture types per language
- Different fixture scopes (per-test, per-class, module-level)

**Examples:**
- **Python**: `setUp()`, `@pytest.fixture`, module-level setup
- **Java**: `@Before`, `@After`, `@BeforeClass`, `@BeforeEach` (JUnit 5)
- **JavaScript**: `beforeEach()`, `afterEach()`, `before()`, `after()`
- **TypeScript**: Jest/Mocha hooks with type annotations
- **Go**: Setup functions, table-driven patterns
- **C#**: `[SetUp]`, `[TearDown]`, `[OneTimeSetUp]`, async patterns

### 2. Metadata Tests — 55+ tests

**Scope:** Validation of extracted fixture metadata

**What they test:**
- **Line numbers**: `start_line` and `end_line` accuracy
- **Lines of code**: LOC counting (excluding blanks/comments)
- **Fixture type**: Correct classification (setUp, fixture, etc.)
- **Fixture scope**: per_test, per_class, per_module, per_session
- **Complexity metrics**: Cyclomatic complexity, parameter counts
- **Code metrics**: Objects instantiated, external calls

### 3. Edge Cases — 50+ tests

**Scope:** Unusual but valid code patterns

**What they test:**
- Large fixtures (100+ lines)
- Deeply nested structures
- False positive prevention (comments, strings)
- Special characters and unicode
- Indentation variations
- Multiple fixtures in same class
- Empty/minimal fixtures
- Malformed but parseable code
- Line ending variations (Unix/Windows/Mac)
- Lambda and comprehension patterns

### 4. Language-Specific Tests — *planned*

**Scope:** Framework-specific patterns

**Will test:**
- All documented fixture types per language
- Language-specific syntax variations
- Async/await patterns and generators
- Context managers and lifecycle
- Inheritance-based fixtures
- Parameterized/data-driven fixtures

### 5. Mock Detection — 30 tests

**Scope:** Mock framework identification (across languages)

**What they test:**
- **Python**: `unittest.mock`, `pytest-mock`, `monkeypatch`
- **Java**: Mockito, PowerMock
- **JavaScript**: Jest mocks, Sinon stubs
- **TypeScript**: ts-mockito, Jest with types
- **Go**: GoMock patterns
- **C#**: Moq, NSubstitute

### 6. Integration Tests — 21 tests

**Scope:** Realistic, multi-language test code

**What they test:**
- Django TestCase hierarchy (Python)
- JUnit 5 with nested classes (Java)
- Jest with beforeAll/afterAll (JavaScript)
- Type-annotated Jest (TypeScript)
- Table-driven tests (Go)
- xUnit collection fixtures (C#)
- Complex fixture dependencies
- Large test modules with many fixtures

## Running Tests

### Prerequisites

Ensure pytest is installed:

```bash
pip install pytest pytest-cov
```

Or install from updated requirements:

```bash
pip install -r requirements.txt
```

### Quick Start

```bash
# Run all tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_extractor_unit/test_python_fixtures.py -v

# Run a specific test class
pytest tests/test_extractor_unit/test_python_fixtures.py::TestPythonUnittestFixtures -v

# Run a specific test method
pytest tests/test_extractor_unit/test_python_fixtures.py::TestPythonUnittestFixtures::test_setUp_method_detected -v
```

### Running by Category

```bash
# Unit tests for all languages
pytest tests/test_extractor_unit/ -v

# Unit tests for specific language
pytest tests/test_extractor_unit/test_python_fixtures.py -v
pytest tests/test_extractor_unit/test_java_fixtures.py -v

# Metadata tests
pytest tests/test_extractor_metadata/ -v

# Edge case tests
pytest tests/test_extractor_edge_cases/ -v

# Mock detection tests
pytest tests/test_mock_detection/ -v

# Integration tests
pytest tests/test_integration/ -v
```

### Running with Coverage

```bash
# Generate coverage report
pytest tests/ --cov=collection.detector --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

This generates an HTML report showing coverage of `collection/detector.py`.

### Running with Different Options

```bash
# Run tests with detailed output
pytest tests/ -vv

# Run tests with print statements visible
pytest tests/ -v -s

# Run tests and stop on first failure
pytest tests/ -v -x

# Run tests and show slowest 10
pytest tests/ -v --durations=10

# Run tests matching a pattern
pytest tests/ -v -k "python"  # All tests with "python" in name
pytest tests/ -v -k "setUp"   # All tests related to setUp

# Run with parallel execution (if pytest-xdist installed)
pytest tests/ -v -n auto
```

### Collecting Tests (without running)

```bash
# List all available tests
pytest tests/ --collect-only -q

# Count total number of tests
pytest tests/ --collect-only -q | wc -l
```

## Test Helpers (conftest.py)

The `tests/conftest.py` file provides reusable pytest fixtures and assertion helpers:

```python
# Create a temporary test file
create_test_file(language, code)

# Extract fixtures and find specific fixture
extract_and_find_fixtures(code, language)
fixture = extract_and_find_fixtures(code, language, fixture_name='setUp')

# Assertion helpers
assert_fixture_detected(code, language, name)
assert_fixture_not_detected(code, language, name)
assert_fixture_count(code, language, expected_count)
assert_line_range(fixture, start_line, end_line)
assert_loc(fixture, expected_loc)
assert_fixture_metrics(fixture, **kwargs)
```

Example usage:

```python
def test_setUp_detected(self):
    code = """
class Test(unittest.TestCase):
    def setUp(self):
        self.x = 1
"""
    fixture = assert_fixture_detected(code, 'python', 'setUp')
    assert fixture.scope == 'per_test'
    assert_loc(fixture, 1)
```

## Test Success Criteria

The test suite validates the following metrics:

| Metric | Target | Status |
|--------|--------|--------|
| **Precision** | >95% of detected items are actual fixtures | Planned |
| **Recall** | >90% of actual fixtures are detected | Planned |
| **Language Coverage** | All 6 languages thoroughly tested | ✅ Implemented |
| **Edge Case Handling** | Graceful degradation on malformed code | ✅ Tested |
| **Metadata Accuracy** | Line numbers and metrics correct | ✅ Tested |
| **Performance** | No fixture timeout violations | ✅ Tested |

## Adding New Tests

### 1. Identify the Category

- **Unit tests**: Single fixture patterns (use `test_extractor_unit/test_<language>_fixtures.py`)
- **Metadata tests**: Fixture metadata accuracy (use `test_extractor_metadata/`)
- **Edge cases**: Unusual patterns (use `test_extractor_edge_cases/`)
- **Mock detection**: Mock framework patterns (use `test_mock_detection/test_<language>_mock_patterns.py`)
- **Integration tests**: Real-world code (use `test_integration/test_<language>_realistic_fixtures.py`)

### 2. Use Existing Helpers

Import from conftest and use assertion helpers:

```python
from ..conftest import (
    extract_and_find_fixtures,
    assert_fixture_detected,
    assert_fixture_not_detected,
    assert_fixture_count,
)

class TestNewFeature:
    def test_example(self):
        code = "..."
        fixture = assert_fixture_detected(code, 'python', 'setUp')
        assert fixture.fixture_type == 'setUp'
```

### 3. Follow Naming Conventions

- **Test class**: `Test<FeatureOrLanguage><Pattern>`
- **Test method**: `test_<what_is_tested>`
- **File name**: `test_<language>_<category>.py`

Example:

```python
class TestPythonAsyncFixtures:
    def test_async_setUp_with_await(self):
        ...
```

### 4. Add Docstrings

```python
def test_setUp_with_parameters(self):
    """setUp method with multiple initialization parameters"""
    code = """..."""
    fixture = assert_fixture_detected(code, 'python', 'setUp')
    assert fixture.num_parameters >= 2
```

## Common Issues

### ImportError: No module named 'conftest'

Use relative imports:

```python
from ..conftest import assert_fixture_detected  # ✅ Correct
from conftest import assert_fixture_detected    # ❌ Wrong
```

### Tests not being discovered

Ensure:
- File name starts with `test_`
- Test classes start with `Test`
- Test methods start with `test_`
- `__init__.py` exists in all test subdirectories

### Tests failing because detector not imported

The conftest automatically imports from `collection.detector`. Ensure the module is installed:

```bash
cd /path/to/project
pip install -e .
```

## Future Test Categories

Planned but not yet implemented:

- **Category 4**: Language-specific pattern tests
- **Category 7**: Integration tests with real test files from popular projects
- **Category 8**: Regression tests for known issues and tricky cases
- **Category 9**: Performance tests (file timeout validation, large file handling)

See `tests/TEST_PLAN.md` for complete specification.

## References

- **Test Plan**: [tests/TEST_PLAN.md](../tests/TEST_PLAN.md)
- **Detector Implementation**: [collection/detector.py](../collection/detector.py)
- **FixtureResult Dataclass**: [collection/detector.py](../collection/detector.py#L75-L91)
- **Pytest Documentation**: https://docs.pytest.org/
