# CSV User Guide

**For researchers who want to analyze FixtureDB without using SQL or SQLite**

> **Quick Links:**  
> - Need SQLite instead? See [Using the Dataset for Research — SQLite Pathway](../usage/09-usage.md)  
> - Need column definitions? See [Database Schema — CSV Section](../architecture/03-database-schema.md)  
> - How are metrics calculated? See [Metrics Reference & Calculation Methodology](../architecture/20-metrics-reference.md) (tools used, reliability, academic references)  
> - Questions about data format? See [Using the Dataset for Research — Comparison](../usage/09-usage.md)

---

## Overview

FixtureDB provides CSV exports of the main analysis tables across 4 programming languages. This guide explains:
- What each column means
- How to use them in Excel, Python (pandas), or R
- How to link tables together
- Common analyses and their queries

---

## Getting Started

### Where to Find CSV Files

In the Zenodo archive (or in your export directory if building locally):
```
fixturedb.zip
├── fixtures.csv                    ← Main table (1 row per fixture)
├── mock_usages.csv                 ← Mock calls (1 row per mock)
├── repositories.csv                ← Repository metadata
├── test_files.csv                  ← Test file listing
├── fixtures_python.csv             ← Python fixtures only
├── fixtures_java.csv               ← Java fixtures only
├── fixtures_javascript.csv         ← JavaScript fixtures only
├── fixtures_typescript.csv         ← TypeScript fixtures only
└── README.txt                      ← Quick reference
```

### Quick Import

**Excel:**
- Right-click → Open With → Excel
- Data will auto-import

**Python (pandas):**
```python
import pandas as pd
df = pd.read_csv('fixtures.csv')
print(df.head())
```

**R:**
```r
df <- read.csv('fixtures.csv')
head(df)
```

---

## Table 1: fixtures.csv (Main Analysis Table)

**What it contains:** One row per test fixture definition (40,672 rows)

### Column Reference

| Column | Type | Units | Description | Example |
|--------|------|-------|-------------|---------|
| `id` | Integer | — | Unique fixture identifier (primary key) | 12345 |
| `repo_id` | Integer | — | Repository ID (links to repositories.csv) | 42 |
| `file_id` | Integer | — | Test file ID (links to test_files.csv) | 987 |
| `name` | Text | — | Fixture function name | `setup_database` |
| `language` | Text | — | Programming language | `python`, `java`, `javascript`, `typescript` |
| `fixture_type` | Text | — | Detection pattern used | See "Fixture Types" below |
| `scope` | Text | — | When fixture runs relative to tests | `per_test`, `per_class`, `per_module`, `global` |
| `start_line` | Integer | lines | First line of fixture in source file (1-indexed) | 150 |
| `end_line` | Integer | lines | Last line of fixture in source file (1-indexed) | 165 |
| `loc` | Integer | lines | **L**ines **O**f **C**ode (non-blank, non-comment) | 12 |
| `cyclomatic_complexity` | Integer | complexity | **McCabe cyclomatic complexity** (1 = no branching) | 3 |
| `cognitive_complexity` | Integer | complexity | **SonarQube cognitive complexity** (nesting-weighted) | 5 |
| `max_nesting_depth` | Integer | levels | Maximum block nesting (if/for/while/try statements) | 2 |
| `num_objects_instantiated` | Integer | count | Estimated object creations in fixture (detected via regex patterns; may include false positives) | 4 |
| `num_external_calls` | Integer | count | Estimated I/O/API calls (DB, HTTP, files, env); heuristic-based with precision limitations | 2 |
| `num_parameters` | Integer | count | Number of function parameters | 1 |
| `reuse_count` | Integer | count | Number of test functions using this fixture (does not inflate for parametrized tests; see limitations) | 12 |

### Complexity Metrics Explained

**McCabe Cyclomatic Complexity** (`cyclomatic_complexity`)
- Measures branching: 1 = straight line, no branches
- Formula: 1 + (number of decision points: if, switch, for, while)
- Range in FixtureDB: 1–36
- Interpretation:
  - 1–2: Simple, easy to understand
  - 3–5: Moderate complexity, acceptable
  - 6–10: Complex, consider refactoring
  - 10+: Very complex, recommend refactoring

**SonarQube Cognitive Complexity** (`cognitive_complexity`)
- Refinement of cyclomatic that penalizes nested structures harder
- Better correlates with developer cognition
- Typically lower than cyclomatic (nesting reduces it)
- Range in FixtureDB: 0–22

**Max Nesting Depth** (`max_nesting_depth`)
- How deeply nested are the control structures?
- 1 = no nesting (just sequential code)
- 3+ = significant nesting
- Correlates strongly with cyclomatic (see RQ5 in [EXAMPLE-ANALYSES.md](EXAMPLE-ANALYSES.md))

### Fixture Types

| Value | Language | Trigger | Meaning |
|-------|----------|---------|---------|
| `pytest_decorator` | Python | `@pytest.fixture` | pytest decorator-syntax fixture |
| `unittest_setup` | Python | `setUp`, `tearDown`, etc. | unittest class setup methods |
| `junit5_before_each` | Java | `@BeforeEach` | JUnit 5: per-test setup |
| `junit5_before_all` | Java | `@BeforeAll` | JUnit 5: per-class setup |
| `junit4_before` | Java | `@Before` | JUnit 4: per-test setup |
| `before_each` | JS/TS | `beforeEach(...)` | Modern test framework |
| `before_all` | JS/TS | `beforeAll(...)` | Modern test framework |

(See [docs/11-detection.md](../architecture/11-detection.md) for complete list and detection methodology)

### Scope Values Explained

| Scope | Meaning | When It Runs | Use Case |
|-------|---------|--------------|----------|
| `per_test` | Within test | Before each individual test | Most common; isolated setup |
| `per_class` | Within class/suite | Before each test class/suite | Shared setup for class tests |
| `per_module` | Entire module | Once per test module/file | Expensive setup (DB connection) |
| `global` | Application | Once at startup | Very rare; global state setup |

### Missing Values

- **`NULL`** in complexity columns: Indicates error during metric calculation
  - Rare (< 0.1% of fixtures)
  - Safe to exclude or set to 0 for aggregates
- **`0`** in count columns: Legitimate (fixture doesn't instantiate objects, call external APIs, etc.)
  - Use `IS NULL` to find errors, not `= 0`

---

## Table 2: mock_usages.csv

**What it contains:** One row per mock/stub/spy/fake call detected in a fixture (9,202 rows)

### Column Reference

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `id` | Integer | Unique mock usage ID | 45678 |
| `fixture_id` | Integer | Fixture this mock is in (links to fixtures.csv) | 12345 |
| `repo_id` | Integer | Repository this mock is in | 42 |
| `framework` | Text | Mock framework detected | `unittest_mock`, `mockito`, `jest`, etc. |
| `target_identifier` | Text | What's being mocked (class/module name) | `"mymodule.HttpClient"` |

### Key Points

- Join to `fixtures.csv` on `fixture_id`
- Multiple rows per fixture if fixture uses multiple mocks
- `target_identifier` is a string; may need parsing for analysis
- `framework` values: see RQ4 in [EXAMPLE-ANALYSES.md](EXAMPLE-ANALYSES.md)

### Common Analyses

**Q: What fraction of fixtures use mocking?**
```sql-like (Excel/pandas logic):
COUNT(DISTINCT fixture_id) / (SELECT COUNT(*) FROM fixtures) as adoption_rate
```

**Q: Which mock frameworks are most common?**
```
GROUP BY framework
COUNT(*) as count
ORDER BY count DESC
```

---

## Table 3: repositories.csv

**What it contains:** Metadata about the 160 analyzed repositories (4 languages)

### Key Columns

| Column | Description | Example |
|--------|-------------|---------|
| `id` | Unique repo ID | 42 |
| `full_name` | GitHub slug | `"pytest-dev/pytest"` |
| `language` | Programming language | `python` |
| `stars` | Star count at collection time | 54000 |
| `forks` | Fork count | 8500 |
| `domain` | Inferred category | `web`, `data`, `cli`, `infra`, `library`, `other` |
| `pinned_commit` | Git commit SHA we analyzed | `abc123def456...` |
| `status` | Collection status | Usually `analysed` |
| `num_fixtures` | How many fixtures in this repo | 187 |
| `num_mock_usages` | How many mock calls | 42 |
| `created_at` | Repo creation date (ISO 8601) | `2015-03-12` |
| `pushed_at` | Last commit date | `2026-03-31` |

---

## Table 4: test_files.csv

**What it contains:** Metadata about test files analyzed (228,971 rows)

**Key columns:**
- `id`: File ID
- `repo_id`: Repository ID (link to repositories.csv)
- `relative_path`: Path within repo (e.g., `src/tests/test_app.py`)
- `file_loc`: Total lines of code in file
- `num_fixtures`: Fixtures found in this file
- `language`: Same as repo language

---

## Language-Specific CSVs

For convenience, language-specific CSVs are provided:
- `fixtures_python.csv`
- `fixtures_java.csv`
- `fixtures_javascript.csv`
- `fixtures_typescript.csv`

Each contains only fixtures for that language; all columns identical to `fixtures.csv`.

---

## Common Analyses

Each example below shows how to answer a research question. Choose your approach based on the tool you're using: **Excel** for quick exploration, **SQL** (SQLite) for reproducible queries from the original database, **pandas** for exploratory data analysis in Python, or **R** for statistical analysis.

### Q1: What's the distribution of fixture complexity?

**Excel**: 
1. Open `fixtures.csv`
2. Create a new column with binned complexity ranges using formulas (0–2, 3–5, 6–10, 10+)
3. Create a pivot table with `language` in rows and count of bins in values

**SQL (SQLite)**:
```sql
SELECT 
  CASE 
    WHEN cyclomatic_complexity <= 2 THEN '1-2 (Simple)'
    WHEN cyclomatic_complexity <= 5 THEN '3-5 (Moderate)'
    WHEN cyclomatic_complexity <= 10 THEN '6-10 (Complex)'
    ELSE '11+ (Very Complex)'
  END as complexity_band,
  COUNT(*) as count
FROM fixtures
GROUP BY complexity_band
ORDER BY complexity_band;
```

**pandas**:
```python
pd.cut(fixtures['cyclomatic_complexity'], 
       bins=[0, 2, 5, 10, 100], 
       labels=['Simple', 'Moderate', 'Complex', 'Very Complex']
      ).value_counts().sort_index()
```

---

### Q2: Do more complex fixtures get reused more?

**Excel**: 
- Create scatter plot with X=`cyclomatic_complexity`, Y=`reuse_count`
- Visually inspect for correlation

**SQL (SQLite)**:
```sql
SELECT 
  ROUND(cyclomatic_complexity / 5.0) * 5 as cc_band,
  COUNT(*) as fixture_count,
  ROUND(AVG(reuse_count), 2) as avg_reuse
FROM fixtures
GROUP BY cc_band
ORDER BY cc_band;
```

**pandas**:
```python
correlation = fixtures['cyclomatic_complexity'].corr(fixtures['reuse_count'])
print(f"Pearson correlation: {correlation:.3f}")

# Grouped analysis
fixtures.groupby(pd.cut(fixtures['cyclomatic_complexity'], bins=5))['reuse_count'].agg(['mean', 'median', 'count'])
```

---

### Q3: Which repositories have the most complex fixtures on average?

**SQL (SQLite)**:
```sql
SELECT 
  r.full_name,
  r.language,
  ROUND(AVG(f.cyclomatic_complexity), 2) as avg_cc,
  COUNT(f.id) as fixture_count,
  SUM(f.loc) as total_loc
FROM fixtures f
JOIN repositories r ON f.repo_id = r.id
GROUP BY r.full_name
ORDER BY avg_cc DESC
LIMIT 10;
```

**pandas**:
```python
complexity_by_repo = (fixtures
  .merge(repos[['id', 'full_name', 'language']], left_on='repo_id', right_on='id')
  .groupby('full_name')
  .agg({
    'cyclomatic_complexity': 'mean',
    'id': 'count',
    'loc': 'sum'
  })
  .rename(columns={'id': 'fixture_count'})
  .sort_values('cyclomatic_complexity', ascending=False)
  .head(10)
)
```

---

### Q4: What's the relationship between nesting depth and cognitive complexity?

**SQL (SQLite)**:
```sql
SELECT 
  language,
  ROUND(AVG(max_nesting_depth), 2) as avg_nesting,
  ROUND(AVG(cognitive_complexity), 2) as avg_cognitive,
  COUNT(*) as fixture_count
FROM fixtures
WHERE max_nesting_depth IS NOT NULL 
  AND cognitive_complexity IS NOT NULL
GROUP BY language
ORDER BY avg_nesting DESC;
```

**pandas**:
```python
# Overall correlation
corr = fixtures['max_nesting_depth'].corr(fixtures['cognitive_complexity'])
print(f"Correlation: {corr:.3f}")

# By language
fixtures.groupby('language').apply(
  lambda x: x['max_nesting_depth'].corr(x['cognitive_complexity'])
).round(3)
```

---

### Q5: How many fixtures perform I/O (external calls)?

**SQL (SQLite)**:
```sql
SELECT 
  language,
  COUNT(*) as total_fixtures,
  SUM(CASE WHEN num_external_calls > 0 THEN 1 ELSE 0 END) as with_io,
  ROUND(100.0 * SUM(CASE WHEN num_external_calls > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_with_io
FROM fixtures
GROUP BY language
ORDER BY pct_with_io DESC;
```

**pandas**:
```python
# Overall
with_io = (fixtures['num_external_calls'] > 0).sum()
print(f"Total with I/O: {with_io} / {len(fixtures)} ({100*with_io/len(fixtures):.1f}%)")

# By language
fixtures.groupby('language').apply(
  lambda x: (x['num_external_calls'] > 0).sum() / len(x)
).mul(100).round(1)
```

---

## Data Quality Notes

**Missing Values:**
- `NULL` in complexity fields: Mathematical error during calculation (< 0.1%)
- `0` in count fields: Legitimate (fixture doesn't instantiate objects)
- Missing `target_identifier` in mocks: Rare, indicates detection ambiguity

**Consistency Checks:**
- All `fixture_id` in `mock_usages.csv` should exist in `fixtures.csv`
- All `repo_id` references should exist in `repositories.csv`
- No duplicate (fixture_id, fixture_name) pairs

**Detection Reliability:**
- **All languages** (Python, Java, JavaScript, TypeScript): Syntax-based detection, high confidence (~95%+)

**Limitations:**
- Snapshot at one commit per repository (no time series)
- Mock detection uses pattern matching (may miss unusual patterns)

---

## Need Help?

- **Database access needed?** Use SQLite viewer or SQL commands (see [docs/09-usage.md](../usage/09-usage.md))
- **Want raw source code?** Available in SQLite database (`fixtures.raw_source`)
- **Specific research question?** See [EXAMPLE-ANALYSES.md](EXAMPLE-ANALYSES.md) for 5 exemplar analyses
- **Schema details?** See [docs/03-database-schema.md](../architecture/03-database-schema.md)

---

## Citation

If you use FixtureDB CSVs in your research, cite:

```bibtex
@data{fixturedb2026,
  title={FixtureDB: A Multi-Language Dataset of Test Fixture Definitions},
  author={Almeida, João and Hora, Andre},
  year={2026},
  publisher={Zenodo}
}
```

