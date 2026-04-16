"""
Unit tests for the SEART-GHS CSV loader module.
"""

import pytest
from pathlib import Path
from collection.github_search_loader import (
    _parse_seart_ghs_repo,
    _is_excluded,
    _load_csv_gz,
)
from collection.config import LANGUAGE_CONFIGS


class TestParseSearrGhsRepo:
    """Test conversion of SEART-GHS CSV rows to internal format."""

    def test_parse_basic_repo(self):
        """Test parsing a minimal repo row."""
        row = {
            "id": "12345",
            "name": "owner/repo",
            "stargazers": "100",
            "forks": "5",
            "mainLanguage": "Python",
            "description": "A test repository",
            "topics": "testing;pytest",
            "createdAt": "2020-01-01T00:00:00Z",
            "pushedAt": "2023-06-15T12:30:00Z",
        }

        result = _parse_seart_ghs_repo(row)

        assert result["github_id"] == 12345
        assert result["full_name"] == "owner/repo"
        assert result["language"] == "python"  # lowercased
        assert result["stars"] == 100
        assert result["forks"] == 5
        assert result["clone_url"] == "https://github.com/owner/repo.git"
        assert result["star_tier"] in ["core", "extended"]  # depends on star count
        assert "topics" in result

    def test_parse_repo_missing_optional_fields(self):
        """Test parsing a repo with missing optional fields."""
        row = {
            "id": "999",
            "name": "test/empty",
            "stargazers": "0",
            "forks": "0",
        }

        result = _parse_seart_ghs_repo(row)

        assert result["github_id"] == 999
        assert result["full_name"] == "test/empty"
        assert result["description"] == ""
        assert result["created_at"] == ""
        assert result["clone_url"] == "https://github.com/test/empty.git"

    def test_parse_high_star_repo(self):
        """Test that star_tier is correctly assigned for high-star repos."""
        row = {
            "id": "1",
            "name": "pandas/pandas",
            "stargazers": "50000",
            "forks": "10000",
            "mainLanguage": "Python",
        }

        result = _parse_seart_ghs_repo(row)

        assert result["stars"] == 50000
        assert result["star_tier"] == "core"  # >= 500 stars


class TestIsExcluded:
    """Test the exclusion filter."""

    def test_exclude_by_keyword_in_name(self):
        """Test that repos with exclusion keywords in name are filtered."""
        config = LANGUAGE_CONFIGS["python"]
        repo = {
            "name": "python-tutorial",
            "description": "Learn Python basics",
            "isFork": False,
            "isArchived": False,
        }

        is_excluded, reason = _is_excluded(repo, config)

        assert is_excluded
        assert "keyword" in reason

    def test_exclude_by_keyword_in_description(self):
        """Test that repos with exclusion keywords in description are filtered."""
        config = LANGUAGE_CONFIGS["python"]
        repo = {
            "name": "my-awesome-lib",
            "description": "A course on testing",
            "isFork": False,
            "isArchived": False,
        }

        is_excluded, reason = _is_excluded(repo, config)

        assert is_excluded
        assert "keyword" in reason

    def test_exclude_archived_repo(self):
        """Test that archived repos are filtered."""
        config = LANGUAGE_CONFIGS["python"]
        repo = {
            "name": "archived-lib",
            "description": "Old project",
            "isFork": False,
            "isArchived": True,
        }

        is_excluded, reason = _is_excluded(repo, config)

        assert is_excluded
        assert "archived" in reason.lower()

    def test_exclude_fork(self):
        """Test that forks are filtered."""
        config = LANGUAGE_CONFIGS["python"]
        repo = {
            "name": "my-fork",
            "description": "A fork of something",
            "isFork": True,
            "isArchived": False,
        }

        is_excluded, reason = _is_excluded(repo, config)

        assert is_excluded
        assert "fork" in reason.lower()

    def test_include_quality_repo(self):
        """Test that quality repos are NOT excluded."""
        config = LANGUAGE_CONFIGS["python"]
        repo = {
            "name": "pytest-dev/pytest",
            "description": "The pytest framework and plugin ecosystem",
            "isFork": False,
            "isArchived": False,
        }

        is_excluded, reason = _is_excluded(repo, config)

        assert not is_excluded
        assert reason == ""


class TestPerLanguageLimit:
    """Test that 500-repo target is correctly documented as a clone/analyze constraint."""

    def test_load_all_languages_no_per_language_limit(self):
        """Test that load_all_languages() does not enforce a per-language limit.

        All repos that pass basic quality filters should be loaded.
        The 500-per-language target is enforced at clone/analyze phase.
        """
        from collection.config import LANGUAGE_CONFIGS

        # Verify the function signature doesn't have max_per_language parameter
        import inspect

        sig = inspect.signature(
            __import__(
                "collection.github_search_loader", fromlist=["load_all_languages"]
            ).load_all_languages
        )
        assert (
            "max_per_language" not in sig.parameters
        ), "load_all_languages() should not have max_per_language parameter"

    def test_load_repos_for_language_no_max_repos_limit(self):
        """Test that load_repos_for_language() does not enforce a max_repos limit."""
        from collection.github_search_loader import load_repos_for_language

        # Verify the function signature doesn't have max_repos parameter
        import inspect

        sig = inspect.signature(load_repos_for_language)
        assert (
            "max_repos" not in sig.parameters
        ), "load_repos_for_language() should not have max_repos parameter"
