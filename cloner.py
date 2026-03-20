"""
Clone repositories and apply post-clone quality filters.

After cloning we can measure things that are invisible from the GitHub API:
  - actual number of test files (path-based heuristic)
  - commit count
  - pinned HEAD commit SHA

Repos that fail quality thresholds are marked 'skipped' in the DB.
Repos that pass are marked 'cloned' and are ready for AST extraction.
"""

import logging
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pydriller import Repository

from corpus.config import (
    CLONES_DIR,
    LANGUAGE_CONFIGS,
    MIN_COMMITS,
    MIN_TEST_FILES,
    CLONE_WORKERS,
)
from corpus.db import db_session, get_repos_by_status, set_repo_status

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Single-repo clone + quality check
# ---------------------------------------------------------------------------

def clone_repo(repo_id: int, full_name: str, clone_url: str,
               language: str) -> tuple[int, str, str | None]:
    """
    Shallow-clone a repository.

    Returns (repo_id, status, pinned_commit_or_None).
    status is one of: 'cloned' | 'skipped' | 'error'
    """
    target_dir = CLONES_DIR / full_name.replace("/", "__")

    # Skip if already cloned (allows resuming interrupted runs)
    if target_dir.exists():
        try:
            commit = _get_head_sha(target_dir)
            logger.debug(f"[clone] {full_name} already present at {commit[:8]}")
            return repo_id, "cloned", commit
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)

    logger.info(f"[clone] Cloning {full_name} …")
    try:
        result = subprocess.run(
            [
                "git", "clone",
                "--depth", "1",          # snapshot only — no history needed
                "--single-branch",
                "--no-tags",
                clone_url,
                str(target_dir),
            ],
            capture_output=True,
            text=True,
            timeout=300,                 # 5-minute hard timeout per repo
        )
        if result.returncode != 0:
            msg = result.stderr.strip()[:300]
            logger.warning(f"[clone] Failed {full_name}: {msg}")
            return repo_id, "error", None

    except subprocess.TimeoutExpired:
        shutil.rmtree(target_dir, ignore_errors=True)
        return repo_id, "error", "clone timed out"

    # Quality filter 1: commit count
    # Even with --depth 1 we can approximate via git rev-list --count
    commit_count = _count_commits(target_dir)
    if commit_count < MIN_COMMITS:
        shutil.rmtree(target_dir, ignore_errors=True)
        logger.debug(f"[clone] Skip {full_name}: only {commit_count} commits")
        return repo_id, "skipped", None

    # Quality filter 2: test file count
    config = LANGUAGE_CONFIGS.get(language)
    test_file_count = _count_test_files(target_dir, config)
    if test_file_count < MIN_TEST_FILES:
        shutil.rmtree(target_dir, ignore_errors=True)
        logger.debug(f"[clone] Skip {full_name}: only {test_file_count} test files")
        return repo_id, "skipped", None

    commit = _get_head_sha(target_dir)
    logger.info(
        f"[clone] ✓ {full_name} "
        f"({test_file_count} test files, commit {commit[:8]})"
    )
    return repo_id, "cloned", commit


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _get_head_sha(repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        timeout=10,
    )
    result.check_returncode()
    return result.stdout.strip()


def _count_commits(repo_dir: Path) -> int:
    """
    With --depth 1 git rev-list reports only 1 commit, so we fetch a
    small amount of history first to get a realistic count.
    We cap at 500 to avoid fetching huge histories.
    """
    try:
        subprocess.run(
            ["git", "fetch", "--depth", "500", "origin"],
            cwd=repo_dir,
            capture_output=True,
            timeout=60,
        )
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return int(result.stdout.strip())
    except Exception:
        return 0


def _count_test_files(repo_dir: Path, config) -> int:
    """Count files that match the language's test file naming conventions."""
    if config is None:
        return 0
    count = 0
    for suffix in config.test_file_suffixes:
        count += len(list(repo_dir.rglob(f"*{suffix}")))
    # Also check path-pattern-based directories
    for pattern in config.test_path_patterns:
        for path in repo_dir.rglob("*"):
            if pattern in str(path.relative_to(repo_dir)) and path.is_file():
                count += 1
                break   # count the directory once, not every file in it
    return count


# ---------------------------------------------------------------------------
# Batch cloning
# ---------------------------------------------------------------------------

def clone_pending_repos(language: str | None = None,
                        batch_size: int = 50) -> dict:
    """
    Clone all repos in 'discovered' status (optionally filtered by language).
    Uses a thread pool for parallel cloning.
    Returns a summary dict.
    """
    with db_session() as conn:
        rows = get_repos_by_status(conn, "discovered")
        if language:
            rows = [r for r in rows if r["language"] == language]
        batch = list(rows)[:batch_size]

    if not batch:
        logger.info("No repos in 'discovered' status to clone.")
        return {"cloned": 0, "skipped": 0, "error": 0}

    logger.info(f"Cloning batch of {len(batch)} repos with {CLONE_WORKERS} workers …")
    summary = {"cloned": 0, "skipped": 0, "error": 0}

    with ThreadPoolExecutor(max_workers=CLONE_WORKERS) as executor:
        futures = {
            executor.submit(
                clone_repo,
                row["id"], row["full_name"],
                row["clone_url"], row["language"]
            ): row
            for row in batch
        }
        for future in as_completed(futures):
            repo_id, status, commit = future.result()
            summary[status] = summary.get(status, 0) + 1
            with db_session() as conn:
                set_repo_status(conn, repo_id, status,
                                pinned_commit=commit)

    logger.info(f"Batch done: {summary}")
    return summary


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def delete_clone(full_name: str) -> None:
    """Remove the local clone once extraction is complete."""
    target_dir = CLONES_DIR / full_name.replace("/", "__")
    if target_dir.exists():
        shutil.rmtree(target_dir)
        logger.debug(f"[cleanup] Removed {target_dir}")


def get_clone_path(full_name: str) -> Path:
    return CLONES_DIR / full_name.replace("/", "__")
