# CSV Export Guide

This document describes all CSV files exported when running `python pipeline.py export`.

## Excluded Columns (Database-Only)

The following columns exist in the SQLite database but are intentionally excluded from CSV exports:

| Table | Column | Type | Reason |
|-------|--------|------|--------|
| `fixtures` | `raw_source` | TEXT | Full source text; too large for CSV (available in SQLite) |
| `fixtures` | `category` | TEXT | RQ1 taxonomy classification; subjective, for internal analysis |
| `mock_usages` | `mock_style` | TEXT | Subjective classification (stub, mock, spy, fake) |
| `mock_usages` | `target_layer` | TEXT | Subjective classification (boundary, infrastructure, internal, framework) |
| `mock_usages` | `raw_snippet` | TEXT | Source code snippet; redundant with GitHub URL in language-specific CSVs |

Column names and rationale documented here to clarify schema discrepancies between SQLite and CSV exports.

## Export Structure

The export generates the following CSV files:

```
export/fixturedb_v<version>_<date>/
├── fixturedb.sqlite           (full database)
├── repositories.csv           (all repositories)
├── test_files.csv             (all test files)
├── fixtures.csv               (all fixtures)
├── mock_usages.csv            (all mock usages)
├── fixtures_python.csv        (fixtures for Python repos)
├── fixtures_java.csv          (fixtures for Java repos)
├── fixtures_javascript.csv    (fixtures for JavaScript repos)
├── fixtures_typescript.csv    (fixtures for TypeScript repos)
├── fixtures_go.csv            (fixtures for Go repos)
├── fixtures_csharp.csv        (fixtures for C# repos)
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
| `language` | TEXT | Primary language (python, java, javascript, typescript, go, csharp) |
| `stars` | INT | Star count at collection time |
| `forks` | INT | Fork count at collection time |
| `description` | TEXT | GitHub repository description |
| `topics` | TEXT | JSON array of GitHub topic tags |
| `created_at` | TEXT | ISO 8601 repository creation date |
| `pushed_at` | TEXT | ISO 8601 last push date |
| `clone_url` | TEXT | HTTPS clone URL used for local cloning |
| `pinned_commit` | TEXT | SHA of HEAD commit at analysis time (for reproducibility) |
| `domain` | TEXT | Inferred domain (web, cli, data, infra, library, other) |
| `star_tier` | TEXT | Classification (core: ≥500 stars; extended: 100-499 stars) |
| `status` | TEXT | Collection status (discovered, cloned, analysed, skipped, error) |
| `error_message` | TEXT | Error details if status is 'error' |
| `num_test_files` | INT | Count of test files found in repo |
| `num_fixtures` | INT | Count of fixture definitions found |
| `num_mock_usages` | INT | Count of mock usages detected |
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

**Excluded columns:** `raw_source`, `category` (see [Excluded Columns](#excluded-columns-database-only) table above)

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT | Internal primary key |
| `file_id` | INT | FK → test_files.id |
| `repo_id` | INT | FK → repositories.id |
| `name` | TEXT | Function/method name of the fixture |
| `fixture_type` | TEXT | Detection pattern (pytest_decorator, junit4_before, unittest_setup, etc.) |
| `scope` | TEXT | Execution scope (per_test, per_class, per_module, global) |
| `start_line` | INT | 1-indexed start line in source file |
| `end_line` | INT | 1-indexed end line in source file |
| `loc` | INT | Non-blank lines of code |
| `cyclomatic_complexity` | INT | McCabe complexity: 1 + number of branching statements |
| `cognitive_complexity` | INT | Nesting-depth-weighted complexity (higher = harder to understand) |
| `num_objects_instantiated` | INT | Estimated constructor calls inside fixture |
| `num_external_calls` | INT | Estimated I/O / external API calls (DB, HTTP, filesystem, env) |
| `num_parameters` | INT | Number of function parameters |
| `framework` | TEXT | Detected testing framework (pytest, unittest, junit, nunit, testify, etc.) |

## 4. mock_usages.csv

One row per mock call detected inside a fixture.

**Excluded columns:** `mock_style`, `target_layer`, `raw_snippet` (see [Excluded Columns](#excluded-columns-database-only) table above)

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT | Internal primary key |
| `fixture_id` | INT | FK → fixtures.id |
| `repo_id` | INT | FK → repositories.id |
| `framework` | TEXT | Detected mock framework (unittest_mock, pytest_mock, mockito, jest, sinon, moq, etc.) |
| `target_identifier` | TEXT | String passed to the mock call (e.g., "mymodule.HttpClient") |
| `num_interactions_configured` | INT | Count of return_value / thenReturn / side_effect style calls |

## 5. Language-Specific Fixture CSVs (fixtures_<language>.csv)

One row per fixture with full repository and test file context. Designed for easy analysis without database access.

**Includes:** All columns from fixtures.csv PLUS repository metadata and GitHub URL.

| Column | Type | Description |
|--------|------|-------------|
| `github_id` | INT | GitHub numeric ID of the repository |
| `full_name` | TEXT | Repository slug (e.g., "pytest-dev/pytest") |
| `pinned_commit` | TEXT | Commit SHA for reproducibility |
| `stars` | INT | Star count at collection time |
| `forks` | INT | Fork count at collection time |
| `test_file_path` | TEXT | Path to test file (relative to repo root) |
| `github_url` | TEXT | Direct HTTPS link to fixture location in source (e.g., `https://github.com/pytest-dev/pytest/blob/abc123.../src/test.py#L45`) |
| `fixture_id` | INT | Unique fixture ID in database |
| `fixture_name` | TEXT | Function/method name |
| `fixture_type` | TEXT | Detection pattern |
| `scope` | TEXT | Execution scope |
| `start_line` | INT | 1-indexed start line |
| `end_line` | INT | 1-indexed end line |
| `loc` | INT | Non-blank lines of code |
| `cyclomatic_complexity` | INT | McCabe complexity |
| `cognitive_complexity` | INT | Nesting-depth-weighted complexity |
| `num_objects_instantiated` | INT | Constructor calls |
| `num_external_calls` | INT | External API calls |
| `num_parameters` | INT | Function parameters |
| `fixture_framework` | TEXT | Testing framework |
| `num_mocks` | INT | Total mock usages in fixture |
| `num_mock_frameworks` | INT | Count of distinct mock frameworks |

### Example Row

```csv
github_id,full_name,pinned_commit,stars,forks,test_file_path,github_url,fixture_id,fixture_name,fixture_type,scope,start_line,end_line,loc,cyclomatic_complexity,cognitive_complexity,num_objects_instantiated,num_external_calls,num_parameters,fixture_framework,num_mocks,num_mock_frameworks
101,pytest-dev/pytest,abc123def456,7850,1200,src/pytest/test_config.py,https://github.com/pytest-dev/pytest/blob/abc123def456/src/pytest/test_config.py#L45,1,setup_test_db,pytest_decorator,per_test,45,62,18,2,3,3,2,1,pytest,2,1
```

## Usage Examples

### Load in Python

```python
import pandas as pd

# Load language-specific fixtures
df_python = pd.read_csv("fixtures_python.csv")

# Find fixtures with the most mocks
high_mock_fixtures = df_python[df_python['num_mocks'] > 5].sort_values('num_mocks', ascending=False)
print(high_mock_fixtures[['full_name', 'fixture_name', 'num_mocks']])

# Compare complexity metrics by scope
complexity_by_scope = df_python.groupby('scope')[['cyclomatic_complexity', 'cognitive_complexity']].mean()
print(complexity_by_scope)

# Find repositories with most fixtures
repos_by_fixture_count = df_python.groupby('full_name').size().sort_values(ascending=False).head(10)
print(repos_by_fixture_count)
```

### Join with repositories metadata

```python
# Load multiple datasets
repos = pd.read_csv("repositories.csv")
fixtures_py = pd.read_csv("fixtures_python.csv")

# Join to get additional repo info
merged = fixtures_py.merge(
    repos[['github_id', 'created_at', 'pushed_at']],
    on='github_id'
)

# Analyze fixture count vs repo age
print(merged.groupby('created_at')['fixture_id'].count())
```

### Analyze mock frameworks

```python
mock_usage = pd.read_csv("mock_usages.csv")

# Most common mock frameworks
print(mock_usage['framework'].value_counts())

# Average interactions per framework
print(mock_usage.groupby('framework')['num_interactions_configured'].mean())
```

## Design Rationale

### Why are some fields excluded?

**Database-only (subjective classifications):**
- `category` (fixture) — RQ1 taxonomy labels are researcher-subjective and not part of the objective dataset
- `mock_style` (mock usage) — Classifications of stub/mock/spy/fake are judgement calls
- `target_layer` (mock usage) — Classifications of infrastructure layers are context-dependent

**Database-only (source code):**
- `raw_source` (fixture) — Full source text is bulky and redundant (available in SQLite); language-specific CSVs have github_url for direct access
- `raw_snippet` (mock usage) — Code snippet redundant with github_url pointing to exact location

### Design principles

1. **Objective only:** CSVs contain measurable facts (LOC, counts, metrics), not subjective labels
2. **Traceable:** github_url enables verification of any finding directly in source code
3. **Self-contained:** Language-specific CSVs need no database access for analysis
4. **Archivable:** Zenodo deposit includes both SQLite (for future research) and CSV (for immediate use)

## File Sizes

Typical sizes for ~1000 repositories (60-100 repos per language):

| File | Size |
|------|------|
| fixturedb.sqlite | ~50–100 MB |
| All CSVs combined | ~30–50 MB |
| Compressed archive | ~5–10 MB |

## Checking Data Integrity

After export, verify completeness:

```bash
# Count rows in each CSV
wc -l export/fixturedb_v1.0_<date>/*.csv

# Spot-check GitHub URLs
head -5 export/fixturedb_v1.0_<date>/fixtures_python.csv | cut -d',' -f7 | tail -n +2
```

## See Also

- [Database Schema](03-database-schema.md) — Complete schema including excluded fields
- [Language-Specific Fixture CSV Export](15-language-specific-csv-export.md) — Detailed guide for language-specific fixtures
- [Collection & Extraction](04-data-collection.md) — How metrics and detections are computed
