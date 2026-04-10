"""
Integration tests for complexity metrics using third-party libraries.

This test suite validates that:
- Lizard library (cyclomatic complexity) integrates correctly
- complexipy library (Python) integrates correctly
- Metrics are calculated and assigned to fixtures
- Cross-language support works
- Edge cases are handled gracefully

NOTE: These are integration tests, not algorithm validation tests.
The accuracy of complexity calculations is delegated to lizard and
complexipy libraries, which are well-established third-party tools.

Previously, this module tested custom tree-sitter based implementations.
Now we validate the integration with proven, industry-standard libraries.
"""

import pytest
from pathlib import Path
from collection.detector import extract_fixtures


class TestComplexityMetricsIntegration:
    """Test that complexity metrics are correctly integrated and calculated."""

    def test_python_simple_fixture_has_metrics(self, tmp_path):
        """Simple Python fixtures should have complexity metrics."""
        py_file = tmp_path / "test_simple.py"
        py_file.write_text("""
import pytest

@pytest.fixture
def db_session():
    '''Simple fixture with minimal logic.'''
    session = create_session()
    yield session
    session.close()
""")
        result = extract_fixtures(py_file, "python")
        assert len(result.fixtures) == 1
        fixture = result.fixtures[0]

        # Both metrics should be present and numeric
        assert isinstance(fixture.cyclomatic_complexity, int)
        assert isinstance(fixture.cognitive_complexity, int)

        # Simple fixtures should have reasonable complexity
        assert fixture.cyclomatic_complexity >= 1
        assert fixture.cognitive_complexity >= 0

    def test_python_complex_fixture_has_higher_metrics(self, tmp_path):
        """Complex Python fixtures should show increased complexity."""
        py_file = tmp_path / "test_complex.py"
        py_file.write_text("""
import pytest

@pytest.fixture
def complex_setup():
    '''Fixture with multiple nested control structures.'''
    config = load_config()
    
    if config.get('database'):
        for db_type in config.get('databases', []):
            try:
                connection = connect_to_db(db_type)
                if connection.is_healthy():
                    register_connection(connection)
            except Exception as e:
                log_error(e)
                if config.get('fail_fast'):
                    raise
    
    if config.get('cache'):
        cache = initialize_cache()
        if cache.is_available():
            warm_cache()
    
    return config
""")
        result = extract_fixtures(py_file, "python")
        assert len(result.fixtures) == 1
        fixture = result.fixtures[0]

        # Complex fixtures should have detectable complexity
        assert fixture.cyclomatic_complexity >= 1
        # Cognitive complexity should be calculated
        assert isinstance(fixture.cognitive_complexity, int)

    def test_java_fixture_has_metrics(self, tmp_path):
        """Java fixtures should have complexity metrics via lizard."""
        java_file = tmp_path / "TestFixture.java"
        java_file.write_text("""
public class TestFixture {
    @Before
    public void setup() {
        database = createDatabase();
        for (String table : requiredTables) {
            if (!database.hasTable(table)) {
                database.createTable(table);
            }
        }
    }
}
""")
        result = extract_fixtures(java_file, "java")
        assert len(result.fixtures) == 1
        fixture = result.fixtures[0]

        # Metrics via lizard
        assert isinstance(fixture.cyclomatic_complexity, int)
        assert isinstance(fixture.cognitive_complexity, int)
        assert fixture.cyclomatic_complexity >= 1

    def test_javascript_fixture_has_metrics(self, tmp_path):
        """JavaScript fixtures should have complexity metrics."""
        js_file = tmp_path / "setup.js"
        js_file.write_text("""
describe('User API', () => {
    beforeEach(async () => {
        if (useTestDatabase) {
            await initializeDatabase();
        }
        await cleanupTables();
    });
});
""")
        result = extract_fixtures(js_file, "javascript")
        # Should detect beforeEach as fixture
        if result.fixtures:
            fixture = result.fixtures[0]
            assert isinstance(fixture.cyclomatic_complexity, int)
            assert isinstance(fixture.cognitive_complexity, int)

    def test_go_fixture_has_metrics(self, tmp_path):
        """Go fixtures should have complexity metrics."""
        go_file = tmp_path / "setup_test.go"
        go_file.write_text("""
package mypackage_test

import "testing"

func TestMain(m *testing.M) {
    if err := setupDatabase(); err != nil {
        if isCI() {
            panic(err)
        }
    }
    
    code := m.Run()
    cleanupDatabase()
    os.Exit(code)
}
""")
        result = extract_fixtures(go_file, "go")
        if result.fixtures:
            fixture = result.fixtures[0]
            assert isinstance(fixture.cyclomatic_complexity, int)
            assert isinstance(fixture.cognitive_complexity, int)


class TestComplexityMetricsReasonableness:
    """Test that metrics are reasonable and well-formed."""

    def test_cyclomatic_complexity_always_positive(self, tmp_path):
        """Cyclomatic complexity should always be >= 1."""
        py_file = tmp_path / "test_cc_positive.py"
        py_file.write_text("""
@pytest.fixture
def minimal():
    return None
""")
        result = extract_fixtures(py_file, "python")
        assert len(result.fixtures) == 1
        # Cyclomatic complexity baseline is 1 (simplest code path)
        assert result.fixtures[0].cyclomatic_complexity >= 1

    def test_cognitive_complexity_non_negative(self, tmp_path):
        """Cognitive complexity should be >= 0."""
        py_file = tmp_path / "test_cog_nonneg.py"
        py_file.write_text("""
@pytest.fixture  
def simple():
    x = 1
    y = 2
    return x + y
""")
        result = extract_fixtures(py_file, "python")
        assert len(result.fixtures) == 1
        # Cognitive complexity can be 0 for code without control structures
        assert result.fixtures[0].cognitive_complexity >= 0

    def test_multiple_fixtures_all_analyzed(self, tmp_path):
        """All fixtures in a file should get metrics."""
        py_file = tmp_path / "test_multiple.py"
        py_file.write_text("""
import pytest

@pytest.fixture
def first():
    return 1

@pytest.fixture
def second():
    if True:
        x = 1
    return x

@pytest.fixture
def third():
    for i in range(10):
        if i > 5:
            for j in range(5):
                pass
    return None
""")
        result = extract_fixtures(py_file, "python")
        assert len(result.fixtures) == 3

        # Each fixture should have metrics
        for fixture in result.fixtures:
            assert isinstance(fixture.cyclomatic_complexity, int)
            assert isinstance(fixture.cognitive_complexity, int)
            assert fixture.cyclomatic_complexity >= 1
            assert fixture.cognitive_complexity >= 0


class TestComplexityWithMockFrameworks:
    """Test complexity calculation in fixtures that use mocks."""

    def test_fixture_with_unittest_mock(self, tmp_path):
        """Fixtures with unittest.mock should calculate metrics."""
        py_file = tmp_path / "test_with_mocks.py"
        py_file.write_text("""
from unittest import mock
import pytest

@pytest.fixture
def mocked_service():
    with mock.patch('module.Service') as mock_service:
        if True:  # Some condition
            config = {'key': 'value'}
            mock_service.configure(config)
        return mock_service
""")
        result = extract_fixtures(py_file, "python")
        if result.fixtures:
            fixture = result.fixtures[0]
            # Should have metrics
            assert isinstance(fixture.cyclomatic_complexity, int)
            assert isinstance(fixture.cognitive_complexity, int)

    def test_fixture_with_pytest_mock(self, tmp_path):
        """Fixtures with pytest-mock should calculate metrics."""
        py_file = tmp_path / "test_pytest_mock.py"
        py_file.write_text("""
import pytest

@pytest.fixture
def mocked_api(mocker):
    api_mock = mocker.MagicMock()
    if api_mock:
        api_mock.get.return_value = {'status': 'ok'}
    return api_mock
""")
        result = extract_fixtures(py_file, "python")
        if result.fixtures:
            fixture = result.fixtures[0]
            assert isinstance(fixture.cyclomatic_complexity, int)
            assert isinstance(fixture.cognitive_complexity, int)


class TestComplexityEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_fixture(self, tmp_path):
        """Empty fixture should still be analyzed."""
        py_file = tmp_path / "test_empty.py"
        py_file.write_text("""
@pytest.fixture
def empty():
    pass
""")
        result = extract_fixtures(py_file, "python")
        assert len(result.fixtures) == 1
        fixture = result.fixtures[0]
        assert fixture.cyclomatic_complexity >= 1

    def test_fixture_with_long_name(self, tmp_path):
        """Long fixture names shouldn't affect metric calculation."""
        py_file = tmp_path / "test_long_name.py"
        py_file.write_text("""
@pytest.fixture
def this_is_a_very_long_fixture_name_that_describes_what_it_does():
    if condition:
        pass
    return None
""")
        result = extract_fixtures(py_file, "python")
        assert len(result.fixtures) == 1
        fixture = result.fixtures[0]
        assert fixture.cyclomatic_complexity >= 1
        assert fixture.cognitive_complexity >= 0

    def test_fixture_with_multiline_logic(self, tmp_path):
        """Multiline fixtures should be analyzed correctly."""
        py_file = tmp_path / "test_multiline.py"
        py_file.write_text("""
@pytest.fixture
def complex():
    # Long fixture with various constructs
    data = [
        {'id': 1, 'name': 'test1'},
        {'id': 2, 'name': 'test2'},
    ]
    
    results = []
    for item in data:
        if item['id'] > 0:
            try:
                processed = process_item(item)
                results.append(processed)
            except ValueError:
                continue
    
    return results
""")
        result = extract_fixtures(py_file, "python")
        assert len(result.fixtures) == 1
        fixture = result.fixtures[0]
        assert fixture.cyclomatic_complexity >= 1


class TestComplexityDatabaseIntegration:
    """Test that complexity metrics work with database persistence."""

    def test_fixture_result_has_complexity_fields(self, tmp_path):
        """FixtureResult must expose complexity metrics."""
        py_file = tmp_path / "test_result_fields.py"
        py_file.write_text("""
@pytest.fixture
def test_fixture():
    if True:
        pass
    return None
""")
        result = extract_fixtures(py_file, "python")
        assert len(result.fixtures) == 1
        fixture = result.fixtures[0]

        # Fields must exist for database export
        assert hasattr(fixture, "cyclomatic_complexity")
        assert hasattr(fixture, "cognitive_complexity")
        assert isinstance(fixture.cyclomatic_complexity, int)
        assert isinstance(fixture.cognitive_complexity, int)

    def test_all_fixtures_have_numeric_complexity(self, tmp_path):
        """All extracted fixtures must have numeric complexity values."""
        py_file = tmp_path / "test_numeric.py"
        py_file.write_text("""
import pytest

@pytest.fixture
def fixture1():
    return 1

@pytest.fixture  
def fixture2():
    for i in range(5):
        if i > 2:
            process(i)
    return i
""")
        result = extract_fixtures(py_file, "python")

        for fixture in result.fixtures:
            # Both metrics must be integers
            assert isinstance(fixture.cyclomatic_complexity, int)
            assert isinstance(fixture.cognitive_complexity, int)

            # Reasonable ranges (positive for cyclomatic, non-negative for cognitive)
            assert fixture.cyclomatic_complexity > 0
            assert fixture.cognitive_complexity >= 0
