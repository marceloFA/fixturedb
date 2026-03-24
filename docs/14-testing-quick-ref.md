# Quick Test Reference

## Installation

```bash
pip install pytest pytest-cov
# or
pip install -r requirements.txt
```

## Most Common Commands

```bash
# Run all tests
pytest tests/ -v

# Run one language's unit tests
pytest tests/test_extractor_unit/test_python_fixtures.py -v

# Run all Python-related tests
pytest tests/ -v -k "python"

# Run with coverage
pytest tests/ --cov=collection.detector --cov-report=html

# Run and stop on first failure
pytest tests/ -v -x

# List all available tests
pytest tests/ --collect-only -q
```

## By Category

| Category | Command |
|----------|---------|
| All unit tests | `pytest tests/test_extractor_unit/ -v` |
| Unit tests by language | `pytest tests/test_extractor_unit/test_<language>_fixtures.py -v` |
| Metadata tests | `pytest tests/test_extractor_metadata/ -v` |
| Edge cases | `pytest tests/test_extractor_edge_cases/ -v` |
| Mock detection | `pytest tests/test_mock_detection/ -v` |
| Integration | `pytest tests/test_integration/ -v` |

## By Language

| Language | Command |
|----------|---------|
| Python | `pytest tests/ -v -k "python"` |
| Java | `pytest tests/ -v -k "java"` |
| JavaScript | `pytest tests/ -v -k "javascript" or "jest" or "mocha"` |
| TypeScript | `pytest tests/ -v -k "typescript"` |
| Go | `pytest tests/ -v -k "go"` |
| C# | `pytest tests/ -v -k "csharp"` |

## Test Statistics

- **Total tests**: 204+
- **Languages**: 6 (Python, Java, JavaScript, TypeScript, Go, C#)
- **Test files**: 24 language-specific files
- **Framework**: pytest

For full details, see [Testing Strategy & Execution](14-testing.md)
