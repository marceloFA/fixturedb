"""
Export utility — produces the Zenodo-ready dataset artifact.

Generates:
  export/
  ├── fixtures.db               (full database)
  ├── repositories.csv
  ├── test_files.csv
  ├── fixtures.csv              (raw_source excluded by default — too large)
  ├── mock_usages.csv
  ├── fixtures_with_source.csv  (opt-in, includes raw_source)
  ├── stats.txt                 (high-level statistics)
  └── README.txt                (schema and column documentation)

Then zips everything into fixturedb_v<version>.zip.

Usage:
    python -m scripts.export --version 1.0
    # or
    python pipeline.py export --version 1.0
"""

import shutil
import sqlite3
import zipfile
import logging
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

from collection.config import DB_PATH, ROOT_DIR

logger = logging.getLogger(__name__)

EXPORT_DIR = ROOT_DIR / "export"

# ---------------------------------------------------------------------------
# Column documentation for the README
# ---------------------------------------------------------------------------

SCHEMA_DOCS = """
FixtureDB — Dataset Schema Documentation
=========================================

TABLE: repositories
  id               INTEGER  Internal primary key
  github_id        INTEGER  GitHub repository numeric ID
  full_name        TEXT     "owner/repo" slug
  language         TEXT     python | java | javascript | typescript | go | csharp
  stars            INTEGER  GitHub star count at collection time
  forks            INTEGER  GitHub fork count at collection time
  description      TEXT     GitHub repository description
  topics           TEXT     JSON array of GitHub topic tags
  created_at       TEXT     ISO 8601 repository creation date
  pushed_at        TEXT     ISO 8601 last push date
  clone_url        TEXT     HTTPS clone URL
  pinned_commit    TEXT     SHA of the HEAD commit analysed (reproducibility)
  num_contributors INTEGER  GitHub API: repository contributor count
  collected_at     TEXT     ISO 8601 timestamp of DB insertion

TABLE: test_files
  id               INTEGER  Internal primary key
  repo_id          INTEGER  FK → repositories.id
  relative_path    TEXT     Path relative to repository root
  language         TEXT     Same as repositories.language
  num_test_funcs   INTEGER  Number of test function definitions detected
  num_fixtures     INTEGER  Number of fixture definitions detected

TABLE: fixtures
  id                       INTEGER  Internal primary key
  file_id                  INTEGER  FK → test_files.id
  repo_id                  INTEGER  FK → repositories.id
  name                     TEXT     Function/method name of the fixture
  fixture_type             TEXT     Detection pattern used:
                                    pytest_decorator | unittest_setup |
                                    junit5_before_each | junit5_before_all |
                                    junit4_before | junit4_before_class |
                                    before_each | before_all | mocha_before |
                                    nunit_setup | nunit_teardown |
                                    nunit_onetimesetup | nunit_onetimeteardown |
                                    xunit_fact | xunit_theory |
                                    test_main | go_helper
  scope                    TEXT     per_test | per_class | per_module | global
  start_line               INTEGER  1-indexed start line in the source file
  end_line                 INTEGER  1-indexed end line in the source file
  loc                      INTEGER  Non-blank lines of code
  cyclomatic_complexity    INTEGER  1 + number of branching statements
  cognitive_complexity     INTEGER  Nesting-depth-weighted code complexity
  num_objects_instantiated INTEGER  Estimated constructor calls
  num_external_calls       INTEGER  Estimated I/O / external API calls
  num_parameters           INTEGER  Number of function parameters
  raw_source               TEXT     Full source text (excluded from CSV export)
  category                 TEXT     Fixture taxonomy (internal analysis only; excluded from CSV export — subjective)

TABLE: mock_usages
  id                           INTEGER  Internal primary key
  fixture_id                   INTEGER  FK → fixtures.id
  repo_id                      INTEGER  FK → repositories.id
  framework                    TEXT     unittest_mock | pytest_mock | mockito |
                                        easymock | jest | sinon | vitest |
                                        gomock | testify_mock | moq |
                                        nsubstitute | fakeiteasy | rhino_mocks
  target_identifier            TEXT     String passed to the mock call
  num_interactions_configured  INTEGER  return_value / thenReturn calls counted
  raw_snippet                  TEXT     Short source snippet (excluded from CSV export — GitHub URL provides access)
"""


# ---------------------------------------------------------------------------
# Export logic
# ---------------------------------------------------------------------------


def export_dataset(version: str = "1.0", include_raw_source: bool = False) -> Path:
    """
    Export the full dataset to EXPORT_DIR and produce a zip archive.
    Returns the path to the zip file.
    """
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    archive_name = f"fixturedb_v{version}_{timestamp}"
    staging = EXPORT_DIR / archive_name
    staging.mkdir(exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # --- SQLite copy ---
    dest_db = staging / "fixtures.db"
    shutil.copy2(DB_PATH, dest_db)
    logger.info(f"Copied database → {dest_db}")

    # --- CSV exports ---
    # repositories: exclude internal tracking fields (star_tier, status, domain, error_message)
    _export_table(
        conn,
        "repositories",
        staging / "repositories.csv",
        exclude_cols=["star_tier", "status", "domain", "error_message", "skip_reason"],
    )
    _export_table(conn, "test_files", staging / "test_files.csv")
    # mock_usages: exclude classification fields (subjective) and raw_snippet (redundant with GitHub URL)
    _export_table(
        conn,
        "mock_usages",
        staging / "mock_usages.csv",
        exclude_cols=["raw_snippet"],
    )

    # fixtures: exclude category, has_teardown_pair, and fixture_type by default
    # category: subjective fixture classification, for internal analysis only
    # has_teardown_pair: qualitative cleanup indicator, internal analysis only
    # fixture_type: qualitative/categorical classification (how fixture detected), not quantitative metric
    # raw_source: included for reproducibility (actual fixture source code)
    if include_raw_source:
        _export_table(
            conn,
            "fixtures",
            staging / "fixtures_with_source.csv",
            exclude_cols=["category", "has_teardown_pair", "fixture_type"],
        )
    else:
        _export_table(
            conn,
            "fixtures",
            staging / "fixtures.csv",
            exclude_cols=["category", "has_teardown_pair", "fixture_type"],
        )

    conn.close()

    # --- README ---
    readme = staging / "README.txt"
    _write_readme(readme, version)
    logger.info(f"Written README → {readme}")

    # --- Stats summary ---
    _write_stats(conn, staging / "stats.txt")

    # --- Zip ---
    zip_path = EXPORT_DIR / f"{archive_name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in staging.rglob("*"):
            zf.write(f, f.relative_to(staging))

    logger.info(f"Archive ready → {zip_path}  ({zip_path.stat().st_size // 1024} KB)")
    return zip_path


def _export_table(
    conn: sqlite3.Connection, table: str, dest: Path, exclude_cols: list[str] = None
) -> None:
    exclude_cols = exclude_cols or []
    df = pd.read_sql(f"SELECT * FROM {table}", conn)
    if exclude_cols:
        df = df.drop(columns=[c for c in exclude_cols if c in df.columns])
    df.to_csv(dest, index=False)
    logger.info(f"  {table}: {len(df):,} rows → {dest.name}")





def _write_readme(path: Path, version: str) -> None:
    header = f"""FixtureDB v{version}
Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}

A multi-language dataset of test fixture definitions extracted from
open-source software repositories on GitHub.

CITATION
--------
TODO: Add paper citation once published.

ACCESS
------
  Full database:  fixtures.db  (SQLite 3)
  Tables as CSV:  repositories.csv, test_files.csv,
                  fixtures.csv, mock_usages.csv

QUICK START (Python)
--------------------
  import sqlite3, pandas as pd
  conn = sqlite3.connect("fixtures.db")
  df = pd.read_sql("SELECT * FROM fixtures", conn)

LICENSE
-------
  Dataset: CC BY 4.0  (https://creativecommons.org/licenses/by/4.0/)
  Pipeline source code: MIT

"""
    path.write_text(header + SCHEMA_DOCS, encoding="utf-8")


def _write_stats(conn, path: Path) -> None:
    """Write a human-readable stats summary (useful for the paper's Table 1)."""
    conn2 = sqlite3.connect(DB_PATH)
    conn2.row_factory = sqlite3.Row
    lines = ["FixtureDB — Corpus Statistics\n", "=" * 40 + "\n\n"]

    for lang in ("python", "java", "javascript", "typescript"):
        r = conn2.execute(
            "SELECT COUNT(*) n FROM repositories WHERE language=? AND status='analysed'",
            (lang,),
        ).fetchone()["n"]
        tf = conn2.execute(
            "SELECT COUNT(*) n FROM test_files tf "
            "JOIN repositories r ON tf.repo_id=r.id WHERE r.language=?",
            (lang,),
        ).fetchone()["n"]
        fx = conn2.execute(
            "SELECT COUNT(*) n FROM fixtures f "
            "JOIN repositories r ON f.repo_id=r.id WHERE r.language=?",
            (lang,),
        ).fetchone()["n"]
        mk = conn2.execute(
            "SELECT COUNT(*) n FROM mock_usages m "
            "JOIN repositories r ON m.repo_id=r.id WHERE r.language=?",
            (lang,),
        ).fetchone()["n"]
        lines.append(
            f"{lang:12s}  repos={r:4d}  test_files={tf:6d}  "
            f"fixtures={fx:7d}  mocks={mk:6d}\n"
        )

    conn2.close()
    path.write_text("".join(lines), encoding="utf-8")
