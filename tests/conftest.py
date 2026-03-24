"""
Shared test utilities and fixtures for extractor tests.
"""

import pytest
import tempfile
from pathlib import Path
from collection.detector import extract_fixtures, FixtureResult


@pytest.fixture
def temp_test_file():
    """Create a temporary test file and clean it up after test."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        temp_path = Path(f.name)
    yield temp_path
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


def create_test_file(language: str, code: str) -> Path:
    """Helper to create a temporary test file with given code."""
    suffix_map = {
        'python': '.py',
        'java': '.java',
        'javascript': '.js',
        'typescript': '.ts',
        'go': '.go',
        'csharp': '.cs',
    }
    
    suffix = suffix_map.get(language, '.txt')
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
        f.write(code)
        return Path(f.name)


def extract_and_find_fixtures(code: str, language: str, fixture_name: str = None) -> list[FixtureResult]:
    """
    Helper to extract fixtures from code and optionally filter by name.
    
    Args:
        code: Source code string
        language: Language key ('python', 'java', etc.)
        fixture_name: Optional name to filter by
        
    Returns:
        List of FixtureResult objects (or filtered by name)
    """
    temp_file = create_test_file(language, code)
    try:
        fixtures = extract_fixtures(temp_file, language)
        if fixture_name:
            fixtures = [f for f in fixtures if f.name == fixture_name]
        return fixtures
    finally:
        if temp_file.exists():
            temp_file.unlink()


def assert_fixture_detected(code: str, language: str, fixture_name: str, 
                            fixture_type: str = None, scope: str = None):
    """Assert that a fixture with given name is detected."""
    fixtures = extract_and_find_fixtures(code, language, fixture_name)
    assert len(fixtures) > 0, f"Fixture '{fixture_name}' not detected in {language}"
    
    fixture = fixtures[0]
    if fixture_type:
        assert fixture.fixture_type == fixture_type, \
            f"Expected type {fixture_type}, got {fixture.fixture_type}"
    if scope:
        assert fixture.scope == scope, \
            f"Expected scope {scope}, got {fixture.scope}"
    return fixture


def assert_fixture_not_detected(code: str, language: str, fixture_name: str):
    """Assert that a fixture is NOT detected."""
    fixtures = extract_and_find_fixtures(code, language, fixture_name)
    assert len(fixtures) == 0, f"Fixture '{fixture_name}' was detected but shouldn't be"


def assert_fixture_count(code: str, language: str, expected_count: int):
    """Assert the number of detected fixtures."""
    fixtures = extract_and_find_fixtures(code, language)
    assert len(fixtures) == expected_count, \
        f"Expected {expected_count} fixtures, got {len(fixtures)}"


def assert_line_range(fixture: FixtureResult, expected_start: int, expected_end: int):
    """Assert fixture line number range."""
    assert fixture.start_line == expected_start, \
        f"Expected start_line {expected_start}, got {fixture.start_line}"
    assert fixture.end_line == expected_end, \
        f"Expected end_line {expected_end}, got {fixture.end_line}"


def assert_loc(fixture: FixtureResult, expected_loc: int):
    """Assert lines of code count."""
    assert fixture.loc == expected_loc, \
        f"Expected {expected_loc} LOC, got {fixture.loc}"


def assert_fixture_metrics(fixture: FixtureResult, 
                          min_complexity: int = None,
                          max_complexity: int = None,
                          num_parameters: int = None,
                          has_yield: bool = None):
    """Assert fixture metrics."""
    if min_complexity is not None:
        assert fixture.cyclomatic_complexity >= min_complexity, \
            f"Expected complexity >= {min_complexity}, got {fixture.cyclomatic_complexity}"
    
    if max_complexity is not None:
        assert fixture.cyclomatic_complexity <= max_complexity, \
            f"Expected complexity <= {max_complexity}, got {fixture.cyclomatic_complexity}"
    
    if num_parameters is not None:
        assert fixture.num_parameters == num_parameters, \
            f"Expected {num_parameters} parameters, got {fixture.num_parameters}"
    
    if has_yield is not None:
        assert fixture.has_yield == has_yield, \
            f"Expected has_yield={has_yield}, got {fixture.has_yield}"


def assert_fixture_with_type_detected(code: str, language: str, fixture_type: str,
                                      scope: str = None, count: int = 1):
    """Assert that a fixture with given type is detected (useful for anonymous functions).
    
    Args:
        code: Source code string
        language: Language key ('python', 'java', etc.)
        fixture_type: Expected fixture type (e.g., 'before_each', 'mocha_before')
        scope: Optional expected scope
        count: Expected number of fixtures with this type (default 1)
        
    Returns:
        List of matching FixtureResult objects
    """
    fixtures = extract_and_find_fixtures(code, language)
    matching = [f for f in fixtures if f.fixture_type == fixture_type]
    assert len(matching) == count, \
        f"Expected {count} fixture(s) with type '{fixture_type}', found {len(matching)}"
    
    if scope:
        for fixture in matching:
            assert fixture.scope == scope, \
                f"Expected scope {scope}, got {fixture.scope}"
    
    return matching[0] if count == 1 else matching
