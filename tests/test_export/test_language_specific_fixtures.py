"""Test language-specific fixture CSV export."""

import tempfile
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from collection.db import initialise_db, get_connection
from collection.config import DB_PATH


@pytest.fixture
def temp_db():
    """Create a temporary database with test data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = Path(f.name)
    
    conn = get_connection(temp_path)
    conn.executescript("""
    CREATE TABLE repositories (
        id INTEGER PRIMARY KEY,
        github_id INTEGER UNIQUE,
        full_name TEXT,
        language TEXT,
        stars INTEGER,
        forks INTEGER,
        status TEXT DEFAULT 'discovered',
        pinned_commit TEXT
    );
    
    CREATE TABLE test_files (
        id INTEGER PRIMARY KEY,
        repo_id INTEGER,
        relative_path TEXT,
        language TEXT,
        UNIQUE(repo_id, relative_path)
    );
    
    CREATE TABLE fixtures (
        id INTEGER PRIMARY KEY,
        file_id INTEGER,
        repo_id INTEGER,
        name TEXT,
        fixture_type TEXT,
        scope TEXT,
        start_line INTEGER,
        end_line INTEGER,
        loc INTEGER,
        cyclomatic_complexity INTEGER,
        num_objects_instantiated INTEGER,
        num_external_calls INTEGER,
        num_parameters INTEGER,
        has_yield INTEGER,
        category TEXT,
        UNIQUE(file_id, name, start_line)
    );
    
    CREATE TABLE mock_usages (
        id INTEGER PRIMARY KEY,
        fixture_id INTEGER,
        repo_id INTEGER,
        framework TEXT
    );
    """)
    
    # Insert test data
    conn.execute(
        "INSERT INTO repositories VALUES (1, 12345, 'pytest-dev/pytest', 'python', 5000, 500, 'analysed', 'abc123def456')"
    )
    conn.execute(
        "INSERT INTO repositories VALUES (2, 12346, 'junit-team/junit4', 'java', 4000, 400, 'analysed', 'xyz789uvw012')"
    )
    conn.execute(
        "INSERT INTO test_files VALUES (1, 1, 'testing/test_config.py', 'python')"
    )
    conn.execute(
        "INSERT INTO test_files VALUES (2, 2, 'src/test/java/org/junit/ConfigTest.java', 'java')"
    )
    
    # Fixtures
    conn.execute(
        """INSERT INTO fixtures VALUES 
           (1, 1, 1, 'setup_config', 'pytest_decorator', 'per_test', 10, 20, 11, 2, 2, 1, 0, 0, 'setup')"""
    )
    conn.execute(
        """INSERT INTO fixtures VALUES 
           (2, 1, 1, 'teardown_config', 'pytest_decorator', 'per_test', 22, 25, 4, 1, 0, 0, 0, 1, 'teardown')"""
    )
    conn.execute(
        """INSERT INTO fixtures VALUES 
           (3, 2, 2, 'setUp', 'junit4_before', 'per_test', 15, 25, 11, 2, 1, 0, 0, 0, 'setup')"""
    )
    
    # Mock usages
    conn.execute("INSERT INTO mock_usages VALUES (1, 1, 1, 'pytest_mock')")
    conn.execute("INSERT INTO mock_usages VALUES (2, 1, 1, 'unittest_mock')")
    conn.execute("INSERT INTO mock_usages VALUES (3, 3, 2, 'mockito')")
    
    conn.commit()
    conn.close()
    
    yield temp_path
    
    # Cleanup
    temp_path.unlink()


def test_export_language_specific_fixtures(temp_db):
    """Test that language-specific fixture CSVs are exported correctly."""
    from collection.exporter import _export_language_specific_fixtures
    
    with tempfile.TemporaryDirectory() as tmpdir:
        staging = Path(tmpdir)
        
        conn = get_connection(temp_db)
        _export_language_specific_fixtures(conn, staging)
        conn.close()
        
        # Check Python CSV was created
        python_csv = staging / "fixtures_python.csv"
        assert python_csv.exists(), "fixtures_python.csv not created"
        
        df_python = pd.read_csv(python_csv)
        assert len(df_python) == 2, "Expected 2 Python fixtures"
        assert list(df_python["fixture_name"]) == ["setup_config", "teardown_config"]
        assert list(df_python["num_mocks"]) == [2, 0]
        assert df_python.iloc[0]["full_name"] == "pytest-dev/pytest"
        
        # Check GitHub URL was added correctly
        expected_url = "https://github.com/pytest-dev/pytest/blob/abc123def456/testing/test_config.py#L10"
        assert df_python.iloc[0]["github_url"] == expected_url, f"GitHub URL mismatch: got {df_python.iloc[0]['github_url']}"
        
        # Check Java CSV was created
        java_csv = staging / "fixtures_java.csv"
        assert java_csv.exists(), "fixtures_java.csv not created"
        
        df_java = pd.read_csv(java_csv)
        assert len(df_java) == 1, "Expected 1 Java fixture"
        assert df_java.iloc[0]["fixture_name"] == "setUp"
        assert df_java.iloc[0]["num_mocks"] == 1
        
        # Check GitHub URL for Java fixture
        expected_java_url = "https://github.com/junit-team/junit4/blob/xyz789uvw012/src/test/java/org/junit/ConfigTest.java#L15"
        assert df_java.iloc[0]["github_url"] == expected_java_url, f"GitHub URL mismatch: got {df_java.iloc[0]['github_url']}"
        
        # Check that other language CSVs exist but are empty/not created
        for lang in ["javascript", "typescript", "go", "csharp"]:
            csv_path = staging / f"fixtures_{lang}.csv"
            # These might not exist since we have no data for them
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                assert len(df) == 0, f"Expected no {lang} fixtures"


def test_fixture_csv_has_expected_columns():
    """Test that the exported CSV has all expected columns."""
    from collection.exporter import _export_language_specific_fixtures
    import tempfile
    
    # Create a test database with minimal data
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = Path(f.name)
    
    conn = get_connection(temp_path)
    conn.executescript("""
    CREATE TABLE repositories (
        id INTEGER PRIMARY KEY,
        github_id INTEGER UNIQUE,
        full_name TEXT,
        language TEXT,
        stars INTEGER,
        forks INTEGER,
        status TEXT DEFAULT 'discovered',
        pinned_commit TEXT
    );
    
    CREATE TABLE test_files (
        id INTEGER PRIMARY KEY,
        repo_id INTEGER,
        relative_path TEXT,
        language TEXT,
        UNIQUE(repo_id, relative_path)
    );
    
    CREATE TABLE fixtures (
        id INTEGER PRIMARY KEY,
        file_id INTEGER,
        repo_id INTEGER,
        name TEXT,
        fixture_type TEXT,
        scope TEXT,
        start_line INTEGER,
        end_line INTEGER,
        loc INTEGER,
        cyclomatic_complexity INTEGER,
        num_objects_instantiated INTEGER,
        num_external_calls INTEGER,
        num_parameters INTEGER,
        has_yield INTEGER,
        category TEXT,
        UNIQUE(file_id, name, start_line)
    );
    
    CREATE TABLE mock_usages (
        id INTEGER PRIMARY KEY,
        fixture_id INTEGER,
        repo_id INTEGER,
        framework TEXT
    );
    """)
    
    conn.execute(
        "INSERT INTO repositories VALUES (1, 11111, 'test/repo', 'python', 100, 10, 'analysed', 'abc1234567890')"
    )
    conn.execute("INSERT INTO test_files VALUES (1, 1, 'test.py', 'python')")
    conn.execute(
        """INSERT INTO fixtures VALUES 
           (1, 1, 1, 'my_fixture', 'pytest_decorator', 'per_test', 5, 15, 10, 2, 1, 2, 3, 0, NULL)"""
    )
    
    conn.commit()
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            staging = Path(tmpdir)
            _export_language_specific_fixtures(conn, staging)
            
            csv_path = staging / "fixtures_python.csv"
            df = pd.read_csv(csv_path)
            
            # Check all expected columns are present
            expected_columns = [
                'github_id', 'full_name', 'pinned_commit', 'stars', 'forks', 'test_file_path',
                'github_url', 'fixture_id', 'fixture_name', 'fixture_type', 'scope',
                'start_line', 'end_line', 'loc', 'cyclomatic_complexity',
                'num_objects_instantiated', 'num_external_calls', 'num_parameters',
                'has_yield', 'category', 'num_mocks', 'num_mock_frameworks'
            ]
            
            for col in expected_columns:
                assert col in df.columns, f"Missing column: {col}"
            
            # Verify data
            assert df.iloc[0]['fixture_name'] == 'my_fixture'
            assert df.iloc[0]['fixture_type'] == 'pytest_decorator'
            assert df.iloc[0]['loc'] == 10
            assert df.iloc[0]['cyclomatic_complexity'] == 2
            
            # Verify GitHub URL is constructed correctly
            expected_url = "https://github.com/test/repo/blob/abc1234567890/test.py#L5"
            assert df.iloc[0]['github_url'] == expected_url, f"GitHub URL mismatch: {df.iloc[0]['github_url']}"
            
    finally:
        conn.close()
        temp_path.unlink()
