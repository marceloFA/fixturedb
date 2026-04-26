# CSV Export Guide

**For CSV users and spreadsheet analysis** — If you need to query the full database or access raw source code, see [Database Schema (SQLite)](../architecture/03-database-schema.md) or [Using the Dataset for Research (SQLite pathways)](../usage/09-usage.md).

This document describes all CSV files exported when running `python pipeline.py export`.

## Excluded Columns (Database-Only)

The following columns exist in the SQLite database but are intentionally excluded from CSV exports:

| Table | Column | Type | Reason |
|-------|--------|------|--------|
| `fixtures` | `category` | TEXT | Internal fixture classification; excluded from public CSV exports |
| `fixtures` | `fixture_type` | TEXT | Qualitative/categorical classification (detection pattern); excluded from CSV (quantitative only) |
| `fixtures` | `has_teardown_pair` | INT | Qualitative cleanup indicator; internal analysis only |
| `mock_usages` | `raw_snippet` | TEXT | Source code snippet; redundant with fixtures table and SQLite full-text search |

Column names and rationale documented here to clarify schema discrepancies between SQLite and CSV exports.

## Export Structure

The export generates the following CSV files:

```
export/fixturedb_v<version>_<date>/
├── fixtures.db                (full database)
├── repositories.csv           (all repositories)
├── test_files.csv             (all test files)
├── fixtures.csv               (all fixtures)
├── mock_usages.csv            (all mock usages)
├── stats.txt                  (high-level statistics)
└── README.txt                 (schema documentation)
```

## 1. repositories.csv

One row per repository discovered during GitHub search.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT | Internal primary key |
| `github_id` | INT | GitHub repository numeric ID |
| `full_name` | TEXT | Repository slug (e.g., "pytest-dev/pytest") |
| `language` | TEXT | Primary language (python, java, javascript, typescript, csharp) |
| `stars` | INT | Star count at collection time |
| `forks` | INT | Fork count at collection time |
| `description` | TEXT | GitHub repository description |
| `topics` | TEXT | JSON array of GitHub topic tags |
| `created_at` | TEXT | ISO 8601 repository creation date |
| `pushed_at` | TEXT | ISO 8601 last push date |
| `clone_url` | TEXT | HTTPS clone URL used for local cloning |
| `pinned_commit` | TEXT | SHA of HEAD commit at analysis time (for reproducibility) |
| `num_contributors` | INT | GitHub contributor count |
| `collected_at` | TEXT | ISO 8601 timestamp of DB insertion |

## 2. test_files.csv

One row per test file found during repository analysis.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT | Internal primary key |
| `repo_id` | INT | FK → repositories.id |
| `relative_path` | TEXT | Path relative to repository root |
| `language` | TEXT | Source language (same as parent repo) |
| `file_loc` | INT | Non-blank lines of code in test file |
| `num_test_funcs` | INT | Count of test function definitions detected |
| `num_fixtures` | INT | Count of fixture definitions in this file |
| `total_fixture_loc` | INT | Sum of LOC across all fixtures in this file |

## 3. fixtures.csv

One row per fixture definition found during extraction.

**Excluded columns:** `category`, `fixture_type` (see [Excluded Columns](#excluded-columns-database-only) table above)

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT | Internal primary key |
| `file_id` | INT | FK → test_files.id |
| `repo_id` | INT | FK → repositories.id |
| `name` | TEXT | Function/method name of the fixture |
| `scope` | TEXT | Execution scope (per_test, per_class, per_module, global) |
| `start_line` | INT | 1-indexed start line in source file |
| `end_line` | INT | 1-indexed end line in source file |
| `loc` | INT | Non-blank lines of code |
| `cyclomatic_complexity` | INT | McCabe complexity: 1 + number of branching statements |
| `cognitive_complexity` | INT | Nesting-depth-weighted complexity (higher = harder to understand) |
| `max_nesting_depth` | INT | Maximum block nesting level |
| `num_objects_instantiated` | INT | Estimated constructor calls inside fixture (detected via regex; see limitations) |
| `num_external_calls` | INT | Estimated I/O / external API calls (DB, HTTP, filesystem, env); see limitations for accuracy notes |
| `num_parameters` | INT | Number of function parameters |
| `reuse_count` | INT | Number of test functions using this fixture |
| `num_mocks` | INT | Count of distinct mock usages within this fixture (0 if no mocks detected) |
| `framework` | TEXT | Detected testing framework (pytest, unittest, junit, nunit, testify, etc.) |
| `raw_source` | TEXT | Complete source code of the fixture (for reproducibility and verification) |

## 4. mock_usages.csv

One row per mock call detected inside a fixture.

**Excluded columns:** `raw_snippet` (see [Excluded Columns](#excluded-columns-database-only) table above)

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT | Internal primary key |
| `fixture_id` | INT | FK → fixtures.id |
| `repo_id` | INT | FK → repositories.id |
| `framework` | TEXT | Detected mock framework (unittest_mock, pytest_mock, mockito, jest, sinon, moq, etc.) |
| `target_identifier` | TEXT | String passed to the mock call (e.g., "mymodule.HttpClient") |
| `num_interactions_configured` | INT | Count of return_value / thenReturn / side_effect style calls |

## Design Rationale

### CSV Export Strategy

The public CSV exports contain **quantitative metrics only** for this dataset. The full SQLite database includes additional infrastructure columns for reproducibility and future research, but these are intentionally excluded from CSV exports:

**Internal-only fields (excluded from CSV):**
- `category` (fixture) — Internal fixture classification infrastructure; enables future taxonomy work

**Source code (excluded from CSV):**
- `raw_source` (fixture) — Full source text is bulky; available in SQLite for researchers who need it
- `raw_snippet` (mock usage) — Code snippet redundant with github_url pointing to exact location

### Design principles

1. **Quantitative focus:** CSV exports contain only measurable, objective facts (LOC, counts, metrics)
2. **Reproducible:** Full SQLite database available for verification of extraction decisions
3. **Traceable:** github_url enables verification of any finding directly in source code
4. **Archivable:** Zenodo deposit includes both SQLite (for transparency and future research) and CSV (for paper analysis)

## See Also

- [Database Schema](../architecture/03-database-schema.md) — Complete schema including excluded fields
- [Collection & Extraction](../data/04-data-collection.md) — How metrics and detections are computed
