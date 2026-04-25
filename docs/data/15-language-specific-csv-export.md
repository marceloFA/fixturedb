# Language-Specific Fixture CSV Export

## Overview

The exporter now generates language-specific CSV files for easy access and analysis by readers. Each row represents one fixture occurrence, including full repository context and mock usage metadata.

## Usage

Export the dataset for Zenodo:

```bash
python pipeline.py export --version 1.0
```

This generates:
- `export/fixturedb_<date>/` directory containing:
  - `fixtures.db` — Full database (SQLite 3)
  - `repositories.csv` — All repositories
  - `test_files.csv` — All test files
  - `fixtures.csv` — All fixtures (raw_source excluded)
  - `mock_usages.csv` — All mock usages

  - **`fixtures_csharp.csv`** — Fixtures for C# projects
  - `stats.txt` — High-level corpus statistics
  - `README.txt` — Schema documentation

The directory is then zipped into `fixturedb_v1.0_<date>.zip` for upload to Zenodo.

## Language-Specific CSV Format

### File Structure
- One row per fixture occurrence
- 20 columns including repository context, fixture metadata, and mock counts
- Sorted by repository stars (descending), then by repository name

### Columns

| Column | Type | Description |
|--------|------|-------------|
| `github_id` | INT | GitHub numeric ID of the repository |
| `full_name` | TEXT | Repository slug (e.g., "pytest-dev/pytest") |
| `pinned_commit` | TEXT | Commit SHA for repo at analysis time |
| `stars` | INT | Star count at collection time |
| `forks` | INT | Fork count at collection time |
| `num_contributors` | INT | Repository contributor count |
| `test_file_path` | TEXT | Path to the test file (relative to repo root) |
| `github_url` | TEXT | Direct HTTPS GitHub link to fixture in source |
| `fixture_id` | INT | Unique fixture ID in database |
| `fixture_name` | TEXT | Function/method name of the fixture |
| `fixture_type` | TEXT | Detection pattern (pytest_decorator, junit4_before, etc.) |
| `scope` | TEXT | Execution scope (per_test, per_class, per_module, global) |
| `start_line` | INT | 1-indexed start line in test file |
| `end_line` | INT | 1-indexed end line in test file |
| `loc` | INT | Non-blank lines of code in the fixture |
| `cyclomatic_complexity` | INT | Code complexity (branches + 1) |
| `cognitive_complexity` | INT | Nesting-depth-weighted complexity |
| `max_nesting_depth` | INT | Maximum block nesting level |
| `reuse_count` | INT | Test functions using this fixture |
| `num_objects_instantiated` | INT | Estimated constructor calls |
| `num_external_calls` | INT | Estimated I/O and external API calls |
| `num_parameters` | INT | Number of function parameters |
| `fixture_framework` | TEXT | Testing framework (pytest, unittest, junit, nunit, etc.) |
| `num_mocks` | INT | Total mock usages in this fixture |
| `num_mock_frameworks` | INT | Count of distinct mock frameworks used |

### Example Row

```csv
github_id,full_name,pinned_commit,stars,forks,num_contributors,test_file_path,github_url,fixture_id,fixture_name,fixture_type,scope,start_line,end_line,loc,cyclomatic_complexity,cognitive_complexity,max_nesting_depth,reuse_count,num_objects_instantiated,num_external_calls,num_parameters,fixture_framework,num_mocks,num_mock_frameworks
101,pytest-dev/pytest,abc123def456,7850,1200,150,src/pytest/test_config.py,https://github.com/pytest-dev/pytest/blob/abc123def456/src/pytest/test_config.py#L45,1,setup_test_db,pytest_decorator,per_test,45,62,18,2,3,2,5,3,2,1,pytest,2,1
```

## Usage in Analysis

### Load in Python

```python
import pandas as pd

# Load Python fixtures
df_python = pd.read_csv("fixtures_python.csv")

# Count fixtures by type
print(df_python.groupby('fixture_type').size())

# Find fixtures with mocks
print(f"Fixtures with mocks: {(df_python['num_mocks'] > 0).sum()}")

# Average complexity by scope
print(df_python.groupby('scope')['cyclomatic_complexity'].mean())
```

### Common Queries

**Count fixtures by repository:**
```python
fixtures_per_repo = df_python.groupby('full_name').size()
print(fixtures_per_repo.sort_values(ascending=False).head(10))
```

**Analyze mock usage patterns:**
```python
# Repos using mocks extensively
mock_heavy = df_python[df_python['num_mocks'] > 0].groupby('full_name').agg({
    'fixture_id': 'count',
    'num_mocks': 'sum',
    'stars': 'first'
}).sort_values('num_mocks', ascending=False)
```

**Distribution analysis:**
```python
# LOC distribution
print(df_python['loc'].describe())

# Complexity distribution
print(df_python['cyclomatic_complexity'].value_counts().sort_index())
```

## Design Decisions

### Why counts instead of joining tables?

The CSV format uses **aggregated mock counts** rather than requiring joins back to the database:
- More accessible to non-programmers
- Self-contained for easy distribution to Zenodo
- Faster exploratory analysis with pandas
- Database remains the source of truth for detailed queries

### Why one row per fixture?

- Aligns with typical data analysis workflows (one observation per row)
- Easier to compute statistics and distributions
- Straightforward to filter and aggregate
- Reduces redundancy compared to denormalized alternatives

### Why separate CSVs per language?

- Clearer organization for domain-specific analysis
- Smaller file sizes for targeted studies
- Simpler queries when focusing on one language
- Standard practice in multi-language repositories

## Integration with Zenodo

The exported archive is ready for Zenodo:
1. SQLite database provides full queryability
2. CSV files provide accessible analysis-ready datasets
3. README.txt documents the schema
4. stats.txt shows the corpus scope

Include citation in `README.txt`:
```
TODO: Citation information
```
