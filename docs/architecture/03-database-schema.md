# Database Schema

FixtureDB provides data in two formats with different schemas optimized for different use cases:

## Two Data Formats

### **SQLite Database** (`fixturedb.sqlite`)
**Contents:** Complete extraction infrastructure with all fields for reproducibility  
**Tables:** 4 normalized tables (repositories, test_files, fixtures, mock_usages) linked by foreign keys  
**Fields:** All internal columns including reproducibility fields (`raw_source`, `category`, `mock_style`, `target_layer`)  
**Use:** Complex analysis, verification, reproducibility, raw source code inspection

### **CSV Exports** (`.csv` files)
**Contents:** Curated quantitative metrics only, denormalized for spreadsheet analysis  
**Files:** 8 CSV files (fixtures.csv, mock_usages.csv, language-specific, etc.)  
**Fields:** Only quantitative public metrics; no internal classification columns or raw source  
**Use:** Excel, pandas, R workflows; public analysis; paper reproduction

---

## SQLite Database Schema

The database (`data/corpus.db`) is a standard SQLite 3 file with four tables
linked by foreign keys. WAL journal mode is enabled, making it safe to run
read-only queries against the database while the pipeline is still writing.

## 3.1 `repositories`

One row per GitHub repository discovered and processed.

| Column            | Type    | Description |
|-------------------|---------|-------------|
| `id`              | INTEGER PK | Internal identifier |
| `github_id`       | INTEGER UNIQUE | GitHub's numeric repository ID |
| `full_name`       | TEXT    | `"owner/repo"` slug (e.g. `"pytest-dev/pytest"`) |
| `language`        | TEXT    | `python` \| `java` \| `javascript` \| `typescript` |
| `stars`           | INTEGER | GitHub star count at collection time |
| `forks`           | INTEGER | GitHub fork count at collection time |
| `description`     | TEXT    | GitHub repository description |
| `topics`          | TEXT    | JSON array of GitHub topic tags |
| `created_at`      | TEXT    | ISO 8601 repository creation date |
| `pushed_at`       | TEXT    | ISO 8601 date of last push |
| `clone_url`       | TEXT    | HTTPS clone URL |
| `pinned_commit`   | TEXT    | **SHA of the HEAD commit that was analysed** — used for exact reproduction |
| `domain`          | TEXT    | `web` \| `data` \| `cli` \| `infra` \| `library` \| `other` (set by `classify` command) |
| `star_tier`       | TEXT    | `core` (≥ 500 stars, comparable to Hamster) \| `extended` (100–499 stars) |
| `status`          | TEXT    | Pipeline lifecycle state: `discovered` → `cloned` → `analysed` (or `skipped` / `error`) |
| `error_message`   | TEXT    | Populated when `status = 'error'` |
| `num_test_files`  | INTEGER | Count of test files detected in this repository|
| `num_fixtures`    | INTEGER | Total count of fixture definitions in this repository |
| `num_mock_usages` | INTEGER | Total count of mock usages detected across all fixtures in this repository |
| `num_contributors` | INTEGER | GitHub API: number of contributors to the repository |
| `collected_at`    | TEXT    | ISO 8601 timestamp of DB insertion |

### Note on `star_tier`

The `core` tier (≥ 500 stars) directly mirrors the selection criterion used in
Hamster (arXiv:2509.26204), the primary related dataset. The `extended` tier
(100–499 stars) adds diversity. Analyses can be restricted to `core` alone for
strict comparability with prior work, or run over both tiers with stratification.

## 3.2 `test_files`

One row per test file found inside each analysed repository.

| Column          | Type    | Description |
|-----------------|---------|-------------|
| `id`            | INTEGER PK | Internal identifier |
| `repo_id`       | INTEGER FK → `repositories.id` | |
| `relative_path` | TEXT    | Path relative to the repository root |
| `language`      | TEXT    | Same as the parent repository's language |
| `file_loc`      | INTEGER | Non-blank lines of code in this test file |
| `num_test_funcs` | INTEGER | Estimated number of test function definitions in this file |
| `num_fixtures`  | INTEGER | Number of fixture definitions detected in this file |
| `total_fixture_loc` | INTEGER | Sum of `loc` across all fixtures in this file |

## 3.3 `fixtures`

One row per fixture definition. This is the primary analysis table.

**📊 Metrics Note:** See [Metrics Reference & Calculation Methodology](20-metrics-reference.md) for detailed information about:
- Which metrics use external tools (Lizard, complexipy, Tree-sitter)
- Custom implementations and their reliability assessments  
- Academic references and citations
- Validation and known limitations

| Column                         | Type    | Description |
|--------------------------------|---------|-------------|
| `id`                           | INTEGER PK | Internal identifier |
| `file_id`                      | INTEGER FK → `test_files.id` | |
| `repo_id`                      | INTEGER FK → `repositories.id` | Denormalised for query convenience |
| `name`                         | TEXT    | Function/method name as it appears in source |
| `fixture_type`                 | TEXT    | Detection pattern — see values below |
| `scope`                        | TEXT    | `per_test` \| `per_class` \| `per_module` \| `global` |
| `start_line`                   | INTEGER | 1-indexed start line in the source file |
| `end_line`                     | INTEGER | 1-indexed end line |
| `loc`                          | INTEGER | Non-blank lines of code |
| `cyclomatic_complexity`        | INTEGER | McCabe complexity (1 + branching statements), calculated via **Lizard library** |
| `cognitive_complexity`         | INTEGER | SonarQube-standard cognitive complexity (nesting-depth-weighted), calculated via **complexipy library** for Python and formula-based estimate for other languages |
| `max_nesting_depth`            | INTEGER | Maximum block nesting level (depth of nested if/for/while/try statements), computed from AST |
| `num_objects_instantiated`     | INTEGER | Estimated constructor calls inside the fixture |
| `num_external_calls`           | INTEGER | Estimated I/O / external API calls (DB, HTTP, filesystem, env) |
| `num_parameters`               | INTEGER | Number of function parameters |
| `reuse_count`                  | INTEGER | Number of test functions that use this fixture as a parameter (fixture modularity metric) |
| `has_teardown_pair`            | INTEGER | Binary (0/1): whether fixture has cleanup logic paired with setup (yield, tearDown, @After, etc.) — **excluded from CSV exports** |
| `raw_source`                   | TEXT    | Full source text of the fixture as extracted |
| `category`                     | TEXT    | Fixture classification for internal analysis — **excluded from CSV exports** |
| `framework`                    | TEXT    | Testing framework (pytest, unittest, junit, nunit, testify, jest, vitest, etc.) |

### `fixture_type` values

| Value                    | Language   | Trigger |
|--------------------------|------------|---------|
| `pytest_decorator` | Python | `@pytest.fixture` |
| `unittest_setup` | Python | `setUp`, `tearDown`, `setUpClass`, `tearDownClass`, `setUpModule`, `tearDownModule` |
| `junit5_before_each` | Java | `@BeforeEach` |
| `junit5_before_all` | Java | `@BeforeAll` |
| `junit5_after_each` | Java | `@AfterEach` |
| `junit5_after_all` | Java | `@AfterAll` |
| `junit4_before` | Java | `@Before` |
| `junit4_before_class` | Java | `@BeforeClass` |
| `junit4_after` | Java | `@After` |
| `junit4_after_class` | Java | `@AfterClass` |
| `before_each` | JS/TS | `beforeEach(...)` call |
| `before_all` | JS/TS | `beforeAll(...)` call |
| `mocha_before` | JS/TS | `before(...)` call (Mocha/Jasmine) |
| `after_each` | JS/TS | `afterEach(...)` call |
| `after_all` | JS/TS | `afterAll(...)` call |
| `mocha_after` | JS/TS | `after(...)` call |

## 3.4 `mock_usages`

One row per mock call detected inside a fixture.

| Column                      | Type                           | Description                        |
|-----------------------------|--------------------------------|------------------------------------|
| `id`                        | INTEGER PK                     | Internal identifier                |
| `fixture_id`                | INTEGER FK → `fixtures.id`     |                                    |
| `repo_id`                   | INTEGER FK → `repositories.id` | Denormalised for query convenience |
| `framework`                 | TEXT                           | Detection pattern — see values below |
| `mock_style`                | TEXT                           | `stub` \| `mock` \| `spy` \| `fake` — **excluded from CSV exports** |
| `target_identifier`         | TEXT                           | String passed to the mock call (e.g. `"mymodule.HttpClient"`) |
| `target_layer`              | TEXT                           | `boundary` \| `infrastructure` \| `internal` \| `framework` — **excluded from CSV exports** |
| `num_interactions_configured` | INTEGER                      | Count of `return_value` / `thenReturn` / `side_effect` style calls found near the mock |
| `raw_snippet`               | TEXT                           | Short source snippet (excluded from CSV export; GitHub URL provides direct code access) |

### `framework` values

**Python:** `unittest_mock`, `pytest_mock`

**Java:** `mockito`, `easymock`, `mockk`

**JavaScript/TypeScript:** `jest`, `sinon`, `vitest`

**C#:** `moq`, `nsubstitute`, `fakeiteasy`, `rhino_mocks`

## Entity-Relationship Summary

```
repositories (1) ──< test_files (1) ──< fixtures (1) ──< mock_usages
      │                                      │
      └──────────────── repo_id ─────────────┘  (denormalised FK)
```

---

## CSV Export Schema

The CSV exports provide a denormalized, curated view of the dataset optimized for spreadsheet and statistical analysis. These contain **quantitative metrics only**; internal classification columns and raw source are excluded.

### What's Excluded from CSVs

The following SQLite columns are **not included** in CSV exports:
- `raw_source` (use SQLite database if you need to inspect original code)
- `category` (internal fixture classification)
- `mock_style` (internal classification: stub, mock, spy, fake)
- `target_layer` (internal: boundary, infrastructure, internal, framework)
- `raw_snippet` (short mock detection code snippet)

### CSV Files and Schemas

#### 1. `fixtures.csv` (All Fixtures, All Languages)

Contains one row per fixture across all 4 languages. Use this for cross-language analysis or when language context is needed.

**Row count:** ~40,672 (total fixtures)

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Internal fixture ID (matches SQLite `fixtures.id`) |
| `repo_id` | INTEGER | Repository ID (matches SQLite `repositories.id`) |
| `file_id` | INTEGER | Test file ID (matches SQLite `test_files.id`) |
| `name` | TEXT | Fixture function/method name |
| `fixture_type` | TEXT | `pytest_decorator`, `unittest_setup`, `junit5_before_each`, `before_each`, etc. (see [fixture_type reference](#fixture_type-values) above) |
| `scope` | TEXT | `per_test`, `per_class`, `per_module`, or `global` |
| `language` | TEXT | **ADDED FOR CSV:** `python`, `java`, `javascript`, `typescript` |
| `loc` | INTEGER | Lines of code |
| `cyclomatic_complexity` | INTEGER | McCabe complexity |
| `cognitive_complexity` | INTEGER | Cognitive complexity (SonarQube standard) |
| `max_nesting_depth` | INTEGER | Max nesting level |
| `num_objects_instantiated` | INTEGER | Estimated constructors called |
| `num_external_calls` | INTEGER | Estimated I/O / external calls |
| `num_parameters` | INTEGER | Function parameters |
| `reuse_count` | INTEGER | Number of tests using this fixture |
| `has_teardown_pair` | BOOLEAN | Whether this fixture has a matching teardown |
| `framework` | TEXT | Testing framework (pytest, unittest, junit4, junit5, jest, mocha, etc.) |
| `repo_full_name` | TEXT | **ADDED FOR CSV:** Repository slug (`owner/repo`) |
| `stars` | INTEGER | **ADDED FOR CSV:** GitHub stars |
| `star_tier` | TEXT | **ADDED FOR CSV:** `core` or `extended` |
| `domain` | TEXT | **ADDED FOR CSV:** Repository domain (`web`, `data`, `cli`, `infra`, `library`, `other`) |

#### 2. `fixtures_python.csv`, `fixtures_java.csv`, `fixtures_javascript.csv`, `fixtures_typescript.csv`

Same columns as `fixtures.csv`, but pre-filtered to a single language. Use these for language-specific analysis without joins.

| Language-Specific File | Row Count |
|------------------------|-----------|
| `fixtures_python.csv` | ~4,900 |
| `fixtures_java.csv` | ~11,200 |
| `fixtures_javascript.csv` | ~5,500 |
| `fixtures_typescript.csv` | ~19,000 |

#### 3. `mock_usages.csv`

One row per mock framework call detected inside a fixture. Join with `fixtures.csv` to analyze mock patterns by fixture characteristics.

**Row count:** ~12,800 (total mock usages across all fixtures)

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Internal mock usage ID |
| `fixture_id` | INTEGER | Fixture ID (join key to `fixtures.csv`) |
| `repo_id` | INTEGER | Repository ID |
| `framework` | TEXT | Mock framework detected (`unittest_mock`, `pytest_mock`, `mockito`, `jest`, `sinon`, etc.) |
| `target_identifier` | TEXT | String passed to the mock (e.g., `"mymodule.DatabaseClient"`) |
| `num_interactions_configured` | INTEGER | Number of mock behavior configurations detected (return_value, side_effect, etc.) |

**Usage Example (joining with fixtures):**
```sql
SELECT f.name, f.fixture_type, m.framework, COUNT(*) as mock_count
FROM fixtures.csv f
JOIN mock_usages.csv m ON f.id = m.fixture_id
GROUP BY f.name, f.fixture_type, m.framework
```

#### 4. `repositories.csv`

One row per repository analyzed. Use this to filter fixtures by repository metadata (stars, domain, language).

**Row count:** 160 (total repositories with analyzable fixtures)

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Repository ID (join key to `fixtures.csv`) |
| `github_id` | INTEGER | GitHub's numeric repository ID |
| `full_name` | TEXT | Repository slug (`owner/repo`) |
| `language` | TEXT | `python`, `java`, `javascript`, `typescript` |
| `stars` | INTEGER | GitHub star count at collection time |
| `forks` | INTEGER | GitHub fork count |
| `created_at` | TEXT | ISO 8601 creation date |
| `pushed_at` | TEXT | ISO 8601 last push date |
| `domain` | TEXT | Repository domain (`web`, `data`, `cli`, `infra`, `library`, `other`) |
| `star_tier` | TEXT | `core` (≥500) or `extended` (100–499) |
| `status` | TEXT | Pipeline status (`analysed`, `skipped`, `error`) |
| `num_test_files` | INTEGER | Count of test files in repo |
| `num_fixtures` | INTEGER | Total fixtures in repo |
| `num_mock_usages` | INTEGER | Total mock usages in repo |
| `num_contributors` | INTEGER | GitHub contributor count |

#### 5. `test_files.csv`

One row per test file analyzed. Use this to study test file characteristics and fixture distribution across files.

**Row count:** ~228,000 (total test files analyzed)

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Test file ID |
| `repo_id` | INTEGER | Repository ID |
| `relative_path` | TEXT | Path relative to repo root (e.g., `tests/test_auth.py`) |
| `language` | TEXT | `python`, `java`, `javascript`, `typescript` |
| `file_loc` | INTEGER | Non-blank lines in test file |
| `num_test_funcs` | INTEGER | Estimated test function count |
| `num_fixtures` | INTEGER | Fixtures defined in this file |
| `total_fixture_loc` | INTEGER | Sum of fixture LOC in this file |

---

## CSV vs. SQLite Comparison

| Aspect | CSV | SQLite |
|--------|-----|--------|
| **Columns Included** | Quantitative metrics + context | All columns (includes raw_source, internal classifications) |
| **Denormalization** | Yes (repo/domain columns added to fixtures) | No (normalized tables) |
| **Row Counts** | Single table per export | Across 4 related tables |
| **Joins Required** | Minimal (mostly to mock_usages) | Complex (across 4 tables) |
| **Internal Fields** | Excluded | Included |
| **Best for** | Spreadsheet analysis, reproducible papers | Verification, raw source inspection |

---

## Guidelines for Using Each Format

### Use **CSVs** if:
- Analyzing fixtures in Excel, Google Sheets, or Tableau
- Writing a paper and want a clean, quantitative-only dataset
- You prefer pandas/R dataframes to SQL
- You don't need raw source code or internal classifications

### Use **SQLite** if:
- You need to verify extraction decisions (inspect raw_source)
- You're performing complex multi-table joins
- You want to trace fixture → mock_usages → repository lineage
- You're reproducing results and need every field (error_message, pinned_commit, etc.)

---

## Column Documentation

For detailed descriptions of what each metric means and how it's calculated, see:
- **[Fixture Detection Logic](../architecture/11-detection.md)** — How each metric is computed and which tools are used; includes Phase 3 metrics (max_nesting_depth, reuse_count, has_teardown_pair, num_contributors)
- **[Limitations and Threats to Validity](../reference/12-limitations.md)** — Known limitations of Phase 3 metrics and mitigation strategies
- **[CSV Export Guide](../data/14-csv-export-guide.md)** — Column-by-column definitions (consolidated reference)
