"""
Database layer — SQLite schema and helper functions.

All analysis reads from this DB; all collection writes to it.
Schema is designed to be append-safe: re-running the pipeline on new repos
will not duplicate existing records.
"""

import sqlite3
import json
import time
import logging
from contextlib import contextmanager
from pathlib import Path

from corpus.config import DB_PATH

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
-- -------------------------------------------------------------------------
-- Repositories discovered via GitHub search
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS repositories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    github_id       INTEGER UNIQUE NOT NULL,
    full_name       TEXT NOT NULL,          -- e.g. "pytest-dev/pytest"
    language        TEXT NOT NULL,          -- normalised: python/java/javascript/typescript/go/csharp
    stars           INTEGER,
    forks           INTEGER,
    description     TEXT,
    topics          TEXT,                   -- JSON array of GitHub topics
    created_at      TEXT,
    pushed_at       TEXT,
    clone_url       TEXT,
    pinned_commit   TEXT,                   -- SHA at time of analysis (reproducibility)
    domain          TEXT,                   -- web/cli/data/infra/library/other (filled later)
    star_tier       TEXT,                   -- core (>=500) | extended (100-499)
    status          TEXT DEFAULT 'discovered',
    -- status values: discovered | cloned | analysed | skipped | error
    error_message   TEXT,
    collected_at    TEXT DEFAULT (datetime('now'))
);

-- -------------------------------------------------------------------------
-- Test files found inside each repository
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS test_files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id         INTEGER NOT NULL REFERENCES repositories(id),
    relative_path   TEXT NOT NULL,
    language        TEXT NOT NULL,
    num_test_funcs  INTEGER DEFAULT 0,
    num_fixtures    INTEGER DEFAULT 0,
    UNIQUE(repo_id, relative_path)
);

-- -------------------------------------------------------------------------
-- Individual fixture definitions
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fixtures (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id                 INTEGER NOT NULL REFERENCES test_files(id),
    repo_id                 INTEGER NOT NULL REFERENCES repositories(id),
    name                    TEXT,
    fixture_type            TEXT,   -- pytest_decorator/unittest_setup/before_each/
                                    -- before_all/test_main/go_helper/...
    scope                   TEXT,   -- per_test/per_class/per_module/global
    start_line              INTEGER,
    end_line                INTEGER,
    loc                     INTEGER,   -- lines of code (non-blank)
    cyclomatic_complexity   INTEGER,
    num_objects_instantiated INTEGER DEFAULT 0,
    num_external_calls      INTEGER DEFAULT 0,
    num_parameters          INTEGER DEFAULT 0,
    has_yield               INTEGER DEFAULT 0,  -- boolean (teardown pattern)
    raw_source              TEXT,              -- original source text
    category                TEXT,              -- RQ1 taxonomy label (filled by classifier)
    UNIQUE(file_id, name, start_line)
);

-- -------------------------------------------------------------------------
-- Mock usages found inside fixtures
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mock_usages (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id                  INTEGER NOT NULL REFERENCES fixtures(id),
    repo_id                     INTEGER NOT NULL REFERENCES repositories(id),
    framework                   TEXT,   -- unittest_mock/pytest_mock/mockito/
                                        -- easymock/jest/sinon/gomock/testify/...
    mock_style                  TEXT,   -- stub/mock/spy/fake (filled by classifier)
    target_identifier           TEXT,   -- the string passed to mock (e.g. "mymodule.Client")
    target_layer                TEXT,   -- boundary/infrastructure/internal/framework
                                        -- (filled by classifier)
    num_interactions_configured INTEGER DEFAULT 0,
    raw_snippet                 TEXT    -- the mock call source text
);

-- -------------------------------------------------------------------------
-- Indexes for common query patterns
-- -------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_fixtures_repo    ON fixtures(repo_id);
CREATE INDEX IF NOT EXISTS idx_fixtures_type    ON fixtures(fixture_type);
CREATE INDEX IF NOT EXISTS idx_fixtures_category ON fixtures(category);
CREATE INDEX IF NOT EXISTS idx_mocks_fixture    ON mock_usages(fixture_id);
CREATE INDEX IF NOT EXISTS idx_mocks_framework  ON mock_usages(framework);
CREATE INDEX IF NOT EXISTS idx_test_files_repo  ON test_files(repo_id);
"""


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30.0)  # 30 second timeout for lock waits
    conn.row_factory = sqlite3.Row  # rows behave like dicts
    conn.execute("PRAGMA journal_mode=WAL")  # safe for concurrent reads
    conn.execute("PRAGMA busy_timeout=30000")  # 30s busy timeout (milliseconds)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_session(db_path: Path = DB_PATH, max_retries: int = 5):
    """
    Context manager that commits on success, rolls back on exception.
    Retries on database lock with exponential backoff.
    """
    conn = None
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            conn = get_connection(db_path)
            yield conn
            conn.commit()
            conn.close()
            return  # Success
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < max_retries - 1:
                # Database locked - retry with exponential backoff
                wait_time = (2 ** attempt) * 0.1  # 0.1s, 0.2s, 0.4s, 0.8s, 1.6s
                logger.debug(f"Database locked, retrying in {wait_time:.2f}s (attempt {attempt + 1}/{max_retries})")
                if conn:
                    conn.rollback()
                    conn.close()
                time.sleep(wait_time)
                last_exception = e
                continue
            else:
                # Not a lock error, or max retries reached
                if conn:
                    conn.rollback()
                    conn.close()
                raise
        except Exception:
            # Other exceptions - rollback and raise
            if conn:
                conn.rollback()
                conn.close()
            raise
    
    # Should not reach here, but just in case
    if last_exception:
        raise last_exception


def initialise_db(db_path: Path = DB_PATH) -> None:
    """
    Create all tables and indexes if they do not already exist.
    Safe to call multiple times — never drops or truncates existing data.
    """
    with db_session(db_path) as conn:
        conn.executescript(SCHEMA)
    print(f"[db] Initialised database at {db_path}")


def db_is_initialised(db_path: Path = DB_PATH) -> bool:
    """Return True if the database already has the repositories table."""
    try:
        conn = get_connection(db_path)
        result = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='repositories'"
        ).fetchone()
        conn.close()
        return result is not None
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Repository helpers
# ---------------------------------------------------------------------------


def upsert_repository(conn: sqlite3.Connection, repo: dict) -> tuple[int, bool]:
    """
    Insert or update a repository record.

    Returns (internal_row_id, is_new) where is_new=True means this was a
    genuine insert (repo not previously in the DB), False means it already
    existed and was updated in place.

    Callers that want to count new discoveries should only increment their
    counter when is_new=True.
    """
    # Check existence before the upsert so we can report is_new accurately.
    existing = conn.execute(
        "SELECT id FROM repositories WHERE github_id = ?", (repo["github_id"],)
    ).fetchone()
    is_new = existing is None

    conn.execute(
        """
        INSERT INTO repositories (
            github_id, full_name, language, stars, forks,
            description, topics, created_at, pushed_at, clone_url,
            star_tier
        ) VALUES (
            :github_id, :full_name, :language, :stars, :forks,
            :description, :topics, :created_at, :pushed_at, :clone_url,
            :star_tier
        )
        ON CONFLICT(github_id) DO UPDATE SET
            stars       = excluded.stars,
            pushed_at   = excluded.pushed_at,
            star_tier   = excluded.star_tier
    """,
        repo,
    )

    row_id = (
        existing["id"]
        if existing
        else conn.execute(
            "SELECT id FROM repositories WHERE github_id = ?", (repo["github_id"],)
        ).fetchone()["id"]
    )

    return row_id, is_new


def set_repo_status(
    conn: sqlite3.Connection,
    repo_id: int,
    status: str,
    error: str = None,
    pinned_commit: str = None,
) -> None:
    conn.execute(
        """
        UPDATE repositories
        SET status = ?, error_message = ?,
            pinned_commit = COALESCE(?, pinned_commit)
        WHERE id = ?
    """,
        (status, error, pinned_commit, repo_id),
    )


def get_repos_by_status(conn: sqlite3.Connection, status: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM repositories WHERE status = ?", (status,)
    ).fetchall()


# ---------------------------------------------------------------------------
# Test file helpers
# ---------------------------------------------------------------------------


def upsert_test_file(
    conn: sqlite3.Connection, repo_id: int, relative_path: str, language: str
) -> int:
    conn.execute(
        """
        INSERT INTO test_files (repo_id, relative_path, language)
        VALUES (?, ?, ?)
        ON CONFLICT(repo_id, relative_path) DO NOTHING
    """,
        (repo_id, relative_path, language),
    )
    row = conn.execute(
        "SELECT id FROM test_files WHERE repo_id = ? AND relative_path = ?",
        (repo_id, relative_path),
    ).fetchone()
    return row["id"]


def update_test_file_counts(
    conn: sqlite3.Connection, file_id: int, num_test_funcs: int, num_fixtures: int
) -> None:
    conn.execute(
        """
        UPDATE test_files
        SET num_test_funcs = ?, num_fixtures = ?
        WHERE id = ?
    """,
        (num_test_funcs, num_fixtures, file_id),
    )


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def insert_fixture(conn: sqlite3.Connection, fixture: dict) -> int:
    """Insert a fixture record. Returns the new row id, or existing id on conflict."""
    cursor = conn.execute(
        """
        INSERT INTO fixtures (
            file_id, repo_id, name, fixture_type, scope,
            start_line, end_line, loc, cyclomatic_complexity,
            num_objects_instantiated, num_external_calls,
            num_parameters, has_yield, raw_source
        ) VALUES (
            :file_id, :repo_id, :name, :fixture_type, :scope,
            :start_line, :end_line, :loc, :cyclomatic_complexity,
            :num_objects_instantiated, :num_external_calls,
            :num_parameters, :has_yield, :raw_source
        )
        ON CONFLICT(file_id, name, start_line) DO NOTHING
    """,
        fixture,
    )
    if cursor.lastrowid:
        return cursor.lastrowid
    row = conn.execute(
        "SELECT id FROM fixtures WHERE file_id=? AND name=? AND start_line=?",
        (fixture["file_id"], fixture["name"], fixture["start_line"]),
    ).fetchone()
    return row["id"]


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def insert_mock_usage(conn: sqlite3.Connection, mock: dict) -> None:
    conn.execute(
        """
        INSERT INTO mock_usages (
            fixture_id, repo_id, framework, target_identifier,
            num_interactions_configured, raw_snippet
        ) VALUES (
            :fixture_id, :repo_id, :framework, :target_identifier,
            :num_interactions_configured, :raw_snippet
        )
    """,
        mock,
    )


# ---------------------------------------------------------------------------
# Stats helper (useful for progress reporting)
# ---------------------------------------------------------------------------


def get_corpus_stats(conn: sqlite3.Connection) -> dict:
    stats = {}
    for status in ("discovered", "cloned", "analysed", "skipped", "error"):
        row = conn.execute(
            "SELECT COUNT(*) as n FROM repositories WHERE status = ?", (status,)
        ).fetchone()
        stats[f"repos_{status}"] = row["n"]

    for table in ("test_files", "fixtures", "mock_usages"):
        row = conn.execute(f"SELECT COUNT(*) as n FROM {table}").fetchone()
        stats[table] = row["n"]

    return stats
