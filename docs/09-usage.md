# Using the Dataset for Research

The SQLite database can be queried directly with any SQL client, `sqlite3`
on the command line, or Python. No additional setup is required.

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
