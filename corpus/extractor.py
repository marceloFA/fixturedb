"""
Extraction orchestrator.

Walks every 'cloned' repository, identifies test files, runs the AST
detector, and writes fixtures + mock usages to the database.

After successful extraction the repo status is updated to 'analysed'.
After extraction the local clone is deleted to reclaim disk space.
"""

import logging
from pathlib import Path

from corpus.config import LANGUAGE_CONFIGS, MIN_FIXTURES_FOUND
from corpus.cloner import get_clone_path, delete_clone
from corpus.db import (
    db_session,
    get_repos_by_status,
    set_repo_status,
    upsert_test_file,
    update_test_file_counts,
    insert_fixture,
    insert_mock_usage,
    get_corpus_stats,
)
from corpus.detector import extract_fixtures

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test file discovery
# ---------------------------------------------------------------------------

def _find_test_files(repo_dir: Path, language: str) -> list[Path]:
    """
    Return all files in repo_dir that match the language's test file
    naming conventions. Excludes vendor / third-party directories.
    """
    config = LANGUAGE_CONFIGS.get(language)
    if config is None:
        return []

    SKIP_DIRS = {
        "vendor", "node_modules", ".git", "dist", "build",
        "target", ".gradle", "__pycache__", ".tox", "venv", ".venv",
        "site-packages", "third_party", "third-party",
        "resources", "resource",  # test resource data directories
    }

    # Non-source-code file extensions to skip (resource files, data, config, etc.)
    NON_CODE_EXTENSIONS = {
        ".txt", ".json", ".xml", ".yaml", ".yml", ".properties",
        ".md", ".csv", ".tsv", ".sql", ".html", ".css", ".scss", ".less",
        ".svg", ".png", ".jpg", ".jpeg", ".gif", ".ico",
        ".woff", ".woff2", ".ttf", ".eot", ".map",
        ".lock", ".log", ".tmp",
        ".mod", ".sum",  # Go dependency files
    }

    test_files: list[Path] = []

    for path in repo_dir.rglob("*"):
        # Skip excluded directories anywhere in the path
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue

        name = path.name.lower()
        rel = str(path.relative_to(repo_dir))

        # Skip files with no extension (typically data/resource files)
        if "." not in name:
            continue

        # Skip non-source-code files
        if any(name.endswith(ext) for ext in NON_CODE_EXTENSIONS):
            continue

        matched = any(name.endswith(suf.lower()) for suf in config.test_file_suffixes)
        if not matched:
            matched = any(pat.lower() in rel.lower()
                          for pat in config.test_path_patterns)

        if matched:
            test_files.append(path)

    return test_files


# ---------------------------------------------------------------------------
# Single-repo extraction
# ---------------------------------------------------------------------------

def extract_repo(repo_id: int, full_name: str, language: str) -> dict:
    """
    Extract fixtures from a single cloned repository.
    Returns a summary dict with counts.
    """
    repo_dir = get_clone_path(full_name)
    if not repo_dir.exists():
        logger.error(f"[extract] Clone not found for {full_name}")
        with db_session() as conn:
            set_repo_status(conn, repo_id, "error", "clone directory missing")
        return {}

    test_files = _find_test_files(repo_dir, language)
    logger.info(f"[extract] {full_name}: {len(test_files)} test files found")

    total_fixtures = 0
    total_mocks = 0

    for tf_path in test_files:
        relative = str(tf_path.relative_to(repo_dir))

        # Register the test file in DB
        with db_session() as conn:
            file_id = upsert_test_file(conn, repo_id, relative, language)

        fixtures = extract_fixtures(tf_path, language)
        file_fixture_count = len(fixtures)
        file_test_count = _estimate_test_count(tf_path, language)

        with db_session() as conn:
            update_test_file_counts(conn, file_id, file_test_count, file_fixture_count)

            for fix in fixtures:
                fixture_record = {
                    "file_id":                  file_id,
                    "repo_id":                  repo_id,
                    "name":                     fix.name,
                    "fixture_type":             fix.fixture_type,
                    "scope":                    fix.scope,
                    "start_line":               fix.start_line,
                    "end_line":                 fix.end_line,
                    "loc":                      fix.loc,
                    "cyclomatic_complexity":    fix.cyclomatic_complexity,
                    "num_objects_instantiated": fix.num_objects_instantiated,
                    "num_external_calls":       fix.num_external_calls,
                    "num_parameters":           fix.num_parameters,
                    "has_yield":                int(fix.has_yield),
                    "raw_source":               fix.raw_source,
                }
                fixture_id = insert_fixture(conn, fixture_record)

                for mock in fix.mocks:
                    mock_record = {
                        "fixture_id":                   fixture_id,
                        "repo_id":                      repo_id,
                        "framework":                    mock.framework,
                        "target_identifier":            mock.target_identifier,
                        "num_interactions_configured":  mock.num_interactions_configured,
                        "raw_snippet":                  mock.raw_snippet,
                    }
                    insert_mock_usage(conn, mock_record)
                    total_mocks += 1

        total_fixtures += file_fixture_count

    # Apply the minimum-fixtures quality filter
    if total_fixtures < MIN_FIXTURES_FOUND:
        logger.info(
            f"[extract] Skip {full_name}: "
            f"only {total_fixtures} fixtures found (threshold: {MIN_FIXTURES_FOUND})"
        )
        with db_session() as conn:
            set_repo_status(conn, repo_id, "skipped",
                            f"only {total_fixtures} fixtures found")
        delete_clone(full_name)
        return {"fixtures": 0, "mocks": 0}

    with db_session() as conn:
        set_repo_status(conn, repo_id, "analysed")

    delete_clone(full_name)

    logger.info(
        f"[extract] ✓ {full_name}: "
        f"{total_fixtures} fixtures, {total_mocks} mock usages"
    )
    return {"fixtures": total_fixtures, "mocks": total_mocks}


# ---------------------------------------------------------------------------
# Test function count estimator (lightweight, no full parse needed)
# ---------------------------------------------------------------------------

import re

TEST_FUNC_PATTERNS = {
    "python":     re.compile(r"^\s*def\s+test_", re.MULTILINE),
    "java":       re.compile(r"@Test\b"),
    "javascript": re.compile(r"\bit\s*\(|\btest\s*\("),
    "typescript": re.compile(r"\bit\s*\(|\btest\s*\("),
    "go":         re.compile(r"^func\s+Test[A-Z]", re.MULTILINE),
}


def _estimate_test_count(file_path: Path, language: str) -> int:
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        pattern = TEST_FUNC_PATTERNS.get(language)
        if pattern:
            return len(pattern.findall(text))
    except Exception:
        pass
    return 0


# ---------------------------------------------------------------------------
# Batch extraction
# ---------------------------------------------------------------------------

def extract_all_cloned(language: str | None = None) -> dict:
    """
    Extract fixtures from all repos in 'cloned' status.
    Returns aggregate summary.
    """
    with db_session() as conn:
        rows = get_repos_by_status(conn, "cloned")
        if language:
            rows = [r for r in rows if r["language"] == language]

    if not rows:
        logger.info("No cloned repos to extract.")
        return {}

    logger.info(f"Extracting {len(rows)} repos …")
    totals: dict[str, int] = {"fixtures": 0, "mocks": 0}

    for row in rows:
        summary = extract_repo(row["id"], row["full_name"], row["language"])
        for k, v in summary.items():
            totals[k] = totals.get(k, 0) + v

    with db_session() as conn:
        stats = get_corpus_stats(conn)

    logger.info(f"Extraction complete. Corpus stats: {stats}")
    return totals
