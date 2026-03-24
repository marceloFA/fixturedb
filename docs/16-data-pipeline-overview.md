# Data Pipeline: Collection → Counting → Export

## Overview Diagram

```
GitHub Repositories
        ↓
    Search & Clone
        ↓
    Extract Fixtures
        ↓
  Calculate Counts  ← NEW: num_test_files, num_fixtures, num_mock_usages
        ↓
  Store in Database
    (SQLite)
        ↓
    Export Dataset
        ├── fixturedb.sqlite (full database)
        ├── repositories.csv
        ├── test_files.csv
        ├── fixtures.csv
        ├── mock_usages.csv
        └── fixtures_{language}.csv  ← NEW: language-specific, reader-friendly
                ↓
           Zenodo Archive
```

## 1. Database Schema with Counts

### repositories Table

The `repositories` table now includes three count fields set during extraction:

```sql
CREATE TABLE repositories (
    id              INTEGER PRIMARY KEY,
    github_id       INTEGER UNIQUE,
    full_name       TEXT,
    language        TEXT,
    stars           INTEGER,
    status          TEXT,  -- discovered|cloned|analysed|skipped|error
    
    -- NEW: Criteria tracking columns
    num_test_files  INTEGER DEFAULT 0,
    num_fixtures    INTEGER DEFAULT 0,
    num_mock_usages INTEGER DEFAULT 0,
    
    collected_at    TEXT
);
```

**When are these set?**
- During `extraction` phase in `collection/extractor.py`
- Populated when repo is marked as `analysed` or `skipped`
- Counts are aggregated across all test files in the repository

## 2. Extraction Process

### What Happens During Extraction

```python
# In collection/extractor.py :: extract_repo()

1. Find all test files in repo
   → num_test_files = count

2. For each test file:
   - Run AST detector
   - Extract fixtures detected
     → total_fixtures += fixture_count
   - For each fixture:
     - Detect mocks
       → total_mocks += mock_count

3. Update repository counts:
   set_repo_analysed(
       repo_id,
       num_test_files=<count>,
       num_fixtures=<count>,
       num_mock_usages=<count>
   )
```

### Function: `set_repo_analysed()`

```python
def set_repo_analysed(
    conn: sqlite3.Connection,
    repo_id: int,
    num_test_files: int,      # from _find_test_files()
    num_fixtures: int,        # aggregated sum
    num_mock_usages: int,     # aggregated sum
) -> None:
    """Mark repo as analysed and store extraction counts."""
    conn.execute("""
        UPDATE repositories
        SET status = 'analysed',
            num_test_files = ?,
            num_fixtures = ?,
            num_mock_usages = ?
        WHERE id = ?
    """, (num_test_files, num_fixtures, num_mock_usages, repo_id))
```

## 3. Query Examples: Using Counts

### Basic Statistics

```sql
-- Percentage of repos without test files
SELECT COUNT(*) * 100.0 / (SELECT COUNT(*) FROM repositories WHERE status = 'analysed')
FROM repositories
WHERE status = 'analysed' AND num_test_files = 0;

-- Percentage without fixtures (that had tests)
SELECT COUNT(*) * 100.0 / 
       (SELECT COUNT(*) FROM repositories WHERE status = 'analysed' AND num_test_files > 0)
FROM repositories
WHERE status = 'analysed' AND num_test_files > 0 AND num_fixtures = 0;
```

### Per-Language Breakdown

```sql
SELECT 
    language,
    COUNT(*) as repositories,
    SUM(num_test_files) as total_test_files,
    SUM(num_fixtures) as total_fixtures,
    SUM(num_mock_usages) as total_mocks,
    AVG(num_fixtures) as avg_fixtures_per_repo
FROM repositories
WHERE status = 'analysed'
GROUP BY language
ORDER BY repositories DESC;
```

### Top Repositories by Fixture Count

```sql
SELECT 
    full_name,
    language,
    stars,
    num_test_files,
    num_fixtures,
    num_mock_usages,
    ROUND(num_fixtures * 1.0 / NULLIF(num_test_files, 0), 2) as fixtures_per_file
FROM repositories
WHERE status = 'analysed'
ORDER BY num_fixtures DESC
LIMIT 20;
```

## 4. CSV Export for Zenodo

### Export Command

```bash
python pipeline.py export --version 1.0
```

### Process

```python
# In collection/exporter.py :: export_dataset()

1. Copy database to staging/fixturedb.sqlite
2. Export all tables as CSV:
   - repositories.csv
   - test_files.csv
   - fixtures.csv (raw_source excluded)
   - mock_usages.csv

3. NEW: Export language-specific fixtures
   For each language (python, java, javascript, typescript, go, csharp):
   → fixtures_{language}.csv
   
   Query structure:
   SELECT
       r.github_id, r.full_name, r.stars, r.forks,
       tf.relative_path,
       f.id, f.name, f.fixture_type, f.scope,
       f.start_line, f.end_line, f.loc, f.cyclomatic_complexity,
       f.num_objects_instantiated, f.num_external_calls,
       f.num_parameters, f.has_yield, f.category,
       COUNT(DISTINCT m.id) as num_mocks,
       COUNT(DISTINCT m.framework) as num_mock_frameworks
    FROM fixtures f
    JOIN repositories r ON f.repo_id = r.id
    JOIN test_files tf ON f.file_id = tf.id
    LEFT JOIN mock_usages m ON f.id = m.fixture_id
    WHERE r.language = ? AND r.status = 'analysed'
    GROUP BY f.id
    ORDER BY r.stars DESC, r.full_name, f.id

4. Generate documentation (README.txt, stats.txt)
5. Zip everything into fixturedb_v1.0_<date>.zip
```

### Output Structure

```
export/
└── fixturedb_v1.0_2026-03-24/
    ├── fixturedb.sqlite           (full queryable database)
    ├── repositories.csv            (all repos)
    ├── test_files.csv             (all test files)
    ├── fixtures.csv               (all fixtures)
    ├── mock_usages.csv            (all mocks)
    ├── fixtures_python.csv        (≈50,000 rows for Python)
    ├── fixtures_java.csv          (≈45,000 rows for Java)
    ├── fixtures_javascript.csv    (≈30,000 rows for JavaScript)
    ├── fixtures_typescript.csv    (≈25,000 rows for TypeScript)
    ├── fixtures_go.csv            (≈15,000 rows for Go)
    ├── fixtures_csharp.csv        (≈20,000 rows for C#)
    ├── stats.txt                  (corpus statistics table)
    └── README.txt                 (schema documentation)
    
    ↓ Compressed into:
    fixturedb_v1.0_2026-03-24.zip
```

## 5. Data Flow and Dependencies

```
Extraction Phase:
  _find_test_files(repo)
        ↓ (count)
    num_test_files
        ↓
   extract_fixtures() per file
        ↓ (aggregate)
    total_fixtures
        ↓
   extract_mocks() per fixture
        ↓ (aggregate)
    total_mocks
        ↓ → set_repo_analysed(num_test_files, num_fixtures, num_mocks)
       DB Update
        ↓
   repositories.num_test_files = ?
   repositories.num_fixtures = ?
   repositories.num_mock_usages = ?

Export Phase:
   set_repo_analysed() ← populated by extraction
        ↓ (query with joins)
   _export_language_specific_fixtures()
        ↓ (aggregate in SQL) 
        
   SELECT ... COUNT(mock_id) as num_mocks ...
        ↓
   Export to CSV
        ↓
   fixtures_python.csv
   fixtures_java.csv
   ... etc
```

## 6. Why This Design?

### Counts in Database
- **When**: Computed once during extraction, stored atomically
- **Why**: Fast database queries, no repeated aggregation
- **Benefit**: Enables tail analytics (% without fixtures, distributions, etc.)

### Language-Specific CSVs
- **When**: Generated during export phase
- **Why**: Accessible for readers, pre-computed aggregations
- **Benefit**: Self-contained analysis without database software

### Both Database + CSVs
- **Development**: Use SQLite for detailed queries and reproducibility
- **Publication**: Use CSVs for accessibility and simplicity
- **Complementary**: Database is source of truth, CSVs are derived views

## 7. Testing

All new functionality has comprehensive test coverage:

```bash
tests/test_export/test_language_specific_fixtures.py
  ✓ test_export_language_specific_fixtures
  ✓ test_fixture_csv_has_expected_columns
```

Tests verify:
- Correct CSV generation per language
- All expected columns present
- Proper data mapping from database to CSV
- Mock usage counts aggregated correctly

## 8. Integration Timeline

```
Phase 1: Data Collection (RUNNING)
└─ Populate repositories table (discovered → cloned → analysed)
└─ Extract fixtures and mocks
└─ Set num_test_files, num_fixtures, num_mock_usages for each repo

Phase 2: Analysis (READY)
└─ Query database with count conditions
└─ Generate language-specific summaries
└─ Identify patterns by fixture type, scope, complexity

Phase 3: Export (READY)
└─ python pipeline.py export --version 1.0
└─ Generates analysis-ready CSVs per language
└─ Produces zipmable artifact for Zenodo
```

## See Also

- [docs/14-criteria-tracking.md](14-criteria-tracking.md) — Repository count columns and SQL query examples
- [docs/15-language-specific-csv-export.md](15-language-specific-csv-export.md) — CSV format documentation and pandas examples
