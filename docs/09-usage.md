# Using the Dataset for Research

FixtureDB offers two complementary analysis pathways, suited to different research needs and tool preferences:

## Two Main Use Cases

### **Use Case 1: SQLite Database** (`fixturedb.sqlite`)
**Best for:** Complex queries, joins across tables, reproducibility verification, custom analysis  
**Access methods:** `sqlite3` CLI, Python (`sqlite3` module), R (`RSQLite` package), SQL IDE (DBeaver, SQLiteStudio)  
**Data scope:** Full database with all fields, internal infrastructure, complete extraction history  
**Advantages:**
- Powerful joins across repositories, test files, fixtures, and mock usages
- Filter by multiple criteria simultaneously (language, star tier, complexity, domain)
- Verify extraction decisions and explore raw source code
- No data loss—nothing is filtered out

### **Use Case 2: CSV Exports** (`fixtures.csv`, `mock_usages.csv`, language-specific CSVs)
**Best for:** Quick analysis, non-SQL users, Excel/Python/R workflows, reproducible papers  
**Access methods:** Excel, Google Sheets, Python (pandas, polars), R (readr, data.table), SQL imports  
**Data scope:** Curated quantitative metrics only (no raw source code)  
**Advantages:**
- No database knowledge required
- Works in any spreadsheet application
- Language-specific exports pre-filtered for convenience
- Column documentation in [docs/14-csv-export-guide.md](14-csv-export-guide.md)

---

## Use Case 1: Querying the SQLite Database

The SQLite database can be queried directly with any SQL client, `sqlite3`
on the command line, or Python. No additional setup is required.

### Python + Pandas Example
```python
import sqlite3
import pandas as pd

conn = sqlite3.connect("data/corpus.db")  # or fixturedb.sqlite from Zenodo

# All Python fixtures with their complexity metrics
df = pd.read_sql("""
    SELECT f.name, f.fixture_type, f.scope, f.loc,
           f.cyclomatic_complexity, f.num_external_calls,
           r.full_name AS repo, r.domain, r.star_tier
    FROM fixtures f
    JOIN repositories r ON f.repo_id = r.id
    WHERE r.language = 'python' AND r.status = 'analysed'
""", conn)

# Mock prevalence per language
pd.read_sql("""
    SELECT r.language,
           COUNT(DISTINCT f.id)  AS total_fixtures,
           COUNT(DISTINCT m.fixture_id) AS fixtures_with_mocks,
           ROUND(COUNT(DISTINCT m.fixture_id) * 100.0
                 / COUNT(DISTINCT f.id), 1) AS pct_with_mocks
    FROM fixtures f
    JOIN repositories r ON f.repo_id = r.id
    LEFT JOIN mock_usages m ON m.fixture_id = f.id
    WHERE r.status = 'analysed'
    GROUP BY r.language
""", conn)

# Restrict to core tier only (comparable to Hamster's >=500 star threshold)
pd.read_sql("""
    SELECT * FROM fixtures f
    JOIN repositories r ON f.repo_id = r.id
    WHERE r.star_tier = 'core'
""", conn)
```

### Command Line Example (SQLite CLI)
```bash
sqlite3 fixturedb.sqlite

# Find all Java fixtures with cyclomatic complexity > 5
SELECT f.name, f.cyclomatic_complexity, r.full_name
FROM fixtures f
JOIN repositories r ON f.repo_id = r.id
WHERE r.language = 'java' AND f.cyclomatic_complexity > 5
ORDER BY f.cyclomatic_complexity DESC;

# Count fixtures by type per language
SELECT r.language, f.fixture_type, COUNT(*) as count
FROM fixtures f
JOIN repositories r ON f.repo_id = r.id
WHERE r.status = 'analysed'
GROUP BY r.language, f.fixture_type
ORDER BY r.language, count DESC;
```

### R Example (RSQLite)
```r
library(RSQLite)
library(tidyverse)

db <- dbConnect(SQLite(), "fixturedb.sqlite")

# All JavaScript fixtures with mock adoption rate
fixtures_with_mocks <- dbGetQuery(db, "
    SELECT f.id, f.name, f.fixture_type, f.scope, f.loc,
           f.cyclomatic_complexity, r.full_name,
           CASE WHEN m.id IS NOT NULL THEN 1 ELSE 0 END as has_mock
    FROM fixtures f
    JOIN repositories r ON f.repo_id = r.id
    LEFT JOIN mock_usages m ON f.id = m.fixture_id
    WHERE r.language = 'javascript' AND r.status = 'analysed'
")

# Compute adoption rate
fixtures_with_mocks %>%
  summarise(mock_adoption = mean(has_mock, na.rm = TRUE))

dbDisconnect(db)
```

### Exploring Raw Source Code
The SQLite database includes the **raw fixture source code** in the `fixtures.raw_source` column. Use this to verify extraction decisions or improve detection:

```python
# Find a specific fixture and inspect its raw source
df = pd.read_sql("""
    SELECT f.name, f.fixture_type, f.raw_source, r.full_name
    FROM fixtures f
    JOIN repositories r ON f.repo_id = r.id
    WHERE f.name = 'setup_database' AND r.language = 'python'
    LIMIT 1
""", conn)

print(df['raw_source'].iloc[0])  # Print the fixture's original code
```

---

## Use Case 2: Analyzing CSV Exports

The CSV exports provide a curated, denormalized view of the dataset optimized for spreadsheet and statistical software. Each export includes only **quantitative metrics**; raw source code is available only in the SQLite database.

### CSV Files Available

| File | Contents | Key Columns |
|------|----------|-------------|
| `fixtures.csv` | All fixtures across all 4 languages | `id`, `repo_id`, `name`, `fixture_type`, `scope`, `loc`, `cyclomatic_complexity`, `cognitive_complexity`, `has_teardown_pair`, `num_parameters`, `num_external_calls`, `num_objects_instantiated` |
| `fixtures_python.csv` | Python fixtures only (pre-filtered) | Same as above + language context |
| `fixtures_java.csv` | Java fixtures only | Same as above |
| `fixtures_javascript.csv` | JavaScript fixtures only | Same as above |
| `fixtures_typescript.csv` | TypeScript fixtures only | Same as above |
| `mock_usages.csv` | Mock framework detections | `fixture_id`, `mock_framework`, `mocked_target` |
| `repositories.csv` | Repository metadata | `id`, `full_name`, `language`, `stars`, `forks`, `domain`, `star_tier`, `status`, `num_test_files`, `num_fixtures`, `num_mock_usages` |
| `test_files.csv` | Metadata per test file | `id`, `repo_id`, `file_path`, `num_fixtures` |

**Full column documentation:** See [docs/14-csv-export-guide.md](14-csv-export-guide.md)

### Python (Pandas) Examples

```python
import pandas as pd

# Load the full fixtures dataset
fixtures = pd.read_csv("fixtures.csv")

# Quick overview
print(fixtures.describe())
print(fixtures['fixture_type'].value_counts())

# Filter: Complex fixtures (CC > 5) across all languages
complex_fixtures = fixtures[fixtures['cyclomatic_complexity'] > 5]
print(f"{len(complex_fixtures)} complex fixtures found")

# Load repositories and join with fixtures for context
repos = pd.read_csv("repositories.csv")
fixtures_with_repo = fixtures.merge(repos, left_on='repo_id', right_on='id', suffixes=('_fixture', '_repo'))

# Analyze by star tier
star_tier_analysis = fixtures_with_repo.groupby('star_tier').agg({
    'cyclomatic_complexity': 'mean',
    'cognitive_complexity': 'mean',
    'num_external_calls': 'mean',
    'loc': 'mean'
}).round(2)

# Mock prevalence: join fixtures with mock_usages
mocks = pd.read_csv("mock_usages.csv")
fixtures_with_mocks = fixtures.merge(mocks, left_on='id', right_on='fixture_id', how='left')
mock_adoption_pct = (fixtures_with_mocks['mock_framework'].notna().sum() / len(fixtures)) * 100
print(f"Mock adoption rate: {mock_adoption_pct:.1f}%")
```

### Excel Examples

1. **Open fixtures.csv in Excel**
   - Use Data → Pivot Table to create summaries by language, fixture_type, or scope
   - Use conditional formatting to highlight complex fixtures (CC > 5)

2. **Merge with repositories.csv**
   - Use VLOOKUP or Power Query to join fixture data with repository metadata (stars, domain)
   - Example: `=VLOOKUP(A2, repositories.csv!A:K, 3, FALSE)` to get language for each fixture

3. **Statistical summaries**
   - Use AVERAGE, MEDIAN, STDEV to compute complexity statistics by language
   - Use COUNTIFS to filter by multiple criteria (e.g., Python + core tier + has_teardown)

### R (data.table / tidyverse) Examples

```r
library(data.table)
library(ggplot2)

# Load CSVs
fixtures <- fread("fixtures.csv")
repos <- fread("repositories.csv")

# Quick statistics
fixtures[, .(avg_cc = mean(cyclomatic_complexity),
             avg_loc = mean(loc),
             count = .N),
         by = fixture_type]

# Join with repos and filter for core tier
fixtures_core <- fixtures[repos[star_tier == 'core', .(id)], 
                          on = .(repo_id = id)]

# Visualization: complexity by scope
ggplot(fixtures, aes(x = scope, y = cyclomatic_complexity)) +
  geom_boxplot() +
  facet_wrap(~fixture_type) +
  theme_minimal()

# Export filtered dataset for a paper
fixtures_analysis <- fixtures_core[cyclomatic_complexity > 3]
fwrite(fixtures_analysis, "fixtures_core_complex.csv")
```

---

## Key Differences: SQLite vs. CSV

| Aspect | SQLite | CSV |
|--------|--------|-----|
| **Setup** | None; just open the `.db` file | None; just open `.csv` file |
| **Querying** | SQL joins across 4 tables | Spreadsheet operations or pandas/R imports |
| **Data completeness** | Full: all fields, raw source code, extraction metadata | Curated: quantitative metrics only |
| **Filtering complexity** | Easy: complex WHERE clauses and aggregations | Moderate: requires spreadsheet functions or code |
| **Performance** | Fast even for large queries | Good for files <100k rows; slower for full dataset |
| **Best for** | Verification, custom analysis, reproducibility | Quick summaries, Excel workflows, sharing with colleagues |

---

## Common Analyses

### "What percentage of Python fixtures use mocks?"

**SQLite:**
```sql
SELECT 
    COUNT(DISTINCT f.id) as total,
    COUNT(DISTINCT m.fixture_id) as with_mocks,
    ROUND(100.0 * COUNT(DISTINCT m.fixture_id) / COUNT(DISTINCT f.id), 1) as pct
FROM fixtures f
JOIN repositories r ON f.repo_id = r.id
LEFT JOIN mock_usages m ON f.id = m.fixture_id
WHERE r.language = 'python' AND r.status = 'analysed';
```

**CSV (Python):**
```python
fixtures = pd.read_csv("fixtures_python.csv")
mocks = pd.read_csv("mock_usages.csv")
with_mocks = fixtures.merge(mocks, left_on='id', right_on='fixture_id', how='inner')['id'].nunique()
pct = (with_mocks / len(fixtures)) * 100
print(f"{pct:.1f}%")
```

---

## Need help?

- **CSV column meanings:** See [docs/14-csv-export-guide.md](14-csv-export-guide.md)
- **Full CSV guide with tool-specific walkthrough:** See [docs/15-csv-user-guide.md](15-csv-user-guide.md)
- **Schema details:** See [docs/03-database-schema.md](03-database-schema.md)
