# FixtureDB — Corpus Collection Pipeline

Replication package for the paper:

> **FixtureDB: A Multi-Language Dataset of Test Fixture Definitions from Open-Source Software**  
> João Almeida, Andre Hora  
> *ICSME 2026 — Tool Demonstration and Data Showcase Track*  
> TODO: add DOI once published

This repository contains the extraction pipeline that builds FixtureDB.
The dataset itself (SQLite database + CSV exports) is archived separately
on Zenodo at **TODO: Zenodo DOI**.

---

## Table of Contents

1. [What is FixtureDB?](#1-what-is-fixturedb)
2. [Repository Structure](#2-repository-structure)
3. [Database Schema](#3-database-schema)
4. [Data Collection Process](#4-data-collection-process)
5. [Storage and Scale Estimates](#5-storage-and-scale-estimates)
6. [Setup and Requirements](#6-setup-and-requirements)
7. [Running the Pipeline](#7-running-the-pipeline)
8. [Reproducing the Paper Corpus](#8-reproducing-the-paper-corpus)
9. [Using the Dataset for Research](#9-using-the-dataset-for-research)
10. [Configuration Reference](#10-configuration-reference)
11. [Fixture Detection Logic](#11-fixture-detection-logic)
12. [Limitations and Threats to Validity](#12-limitations-and-threats-to-validity)
13. [License](#13-license)

---

## 1. What is FixtureDB?

FixtureDB is a structured dataset of **test fixture definitions** extracted
from open-source software repositories on GitHub across five language variants:
Python, Java, JavaScript, TypeScript, and Go.

A *test fixture* is any code that prepares or tears down state before or after
a test runs. Each ecosystem has its own idiom:

| Language       | Fixture mechanisms covered |
|----------------|---------------------------|
| Python         | `@pytest.fixture` (all scopes), `setUp`/`tearDown`/`setUpClass`/`tearDownClass` (unittest) |
| Java           | `@Before`, `@BeforeClass` (JUnit 4), `@BeforeEach`, `@BeforeAll` (JUnit 5), and `After` counterparts |
| JavaScript     | `beforeEach`, `beforeAll`, `before`, `afterEach`, `afterAll` (Jest, Mocha, Jasmine, Vitest) |
| TypeScript     | Same as JavaScript |
| Go             | `TestMain`, helper functions called from ≥ 2 `TestXxx` functions in the same file |

For each fixture definition the dataset records structural metadata (size,
complexity, scope, type), and for each mock call found inside a fixture it
records the framework used and the mocked target identifier.

**Why this dataset matters.**
Prior empirical work on fixtures (TestHound, TestEvoHound) and on mocking
(Mostafa & Wang 2014, Spadini et al. 2017, Chaker et al. 2024) is exclusively
Java-based. FixtureDB is the first cross-language resource that treats the
fixture as its primary unit of analysis, enabling research that was previously
impossible.

---

## 2. Repository Structure

```
fixture-corpus/
│
├── pipeline.py              # Main CLI — entry point for all operations
├── requirements.txt         # Python dependencies
├── .env.example             # Template for GitHub token configuration
│
├── corpus/                  # Core pipeline modules
│   ├── config.py            # All tunable parameters (thresholds, targets, paths)
│   ├── db.py                # SQLite schema definition and query helpers
│   ├── search.py            # GitHub Search API client (repo discovery)
│   ├── cloner.py            # Shallow git clone + post-clone quality filters
│   ├── detector.py          # Tree-sitter AST queries (fixture + mock detection)
│   ├── extractor.py         # Per-repo orchestration: files → fixtures → DB
│   ├── classifier.py        # Keyword-based domain labelling (web/cli/data/…)
│   ├── exporter.py          # Produces the Zenodo-ready zip (SQLite + CSVs)
│   └── validator.py         # Manual precision/recall validation scaffold
│
├── clones/                  # Temporary — shallow git clones live here during
│                            # extraction, then are deleted to reclaim disk space
├── data/
│   └── corpus.db            # The SQLite database (primary pipeline output)
│
├── export/                  # Output of `pipeline.py export` — Zenodo artifact
│   └── fixturedb_v*.zip     # Versioned zip: SQLite + CSVs + README
│
├── validation/              # Output of `pipeline.py validate`
│   └── sample_*.csv         # Stratified fixture samples for manual review
│
└── logs/
    └── pipeline.log         # Full pipeline run log
```

---

## 3. Database Schema

The database (`data/corpus.db`) is a standard SQLite 3 file with four tables
linked by foreign keys. WAL journal mode is enabled, making it safe to run
read-only queries against the database while the pipeline is still writing.

---

### 3.1 `repositories`

One row per GitHub repository discovered and processed.

| Column            | Type    | Description |
|-------------------|---------|-------------|
| `id`              | INTEGER PK | Internal identifier |
| `github_id`       | INTEGER UNIQUE | GitHub's numeric repository ID |
| `full_name`       | TEXT    | `"owner/repo"` slug (e.g. `"pytest-dev/pytest"`) |
| `language`        | TEXT    | `python` \| `java` \| `javascript` \| `typescript` \| `go` |
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
| `collected_at`    | TEXT    | ISO 8601 timestamp of DB insertion |

**Note on `star_tier`:** The `core` tier (≥ 500 stars) directly mirrors the
selection criterion used in Hamster (arXiv:2509.26204), the primary related
dataset. The `extended` tier (100–499 stars) adds diversity. Analyses can be
restricted to `core` alone for strict comparability with prior work, or run
over both tiers with stratification.

---

### 3.2 `test_files`

One row per test file found inside each analysed repository.

| Column          | Type    | Description |
|-----------------|---------|-------------|
| `id`            | INTEGER PK | Internal identifier |
| `repo_id`       | INTEGER FK → `repositories.id` | |
| `relative_path` | TEXT    | Path relative to the repository root |
| `language`      | TEXT    | Same as the parent repository's language |
| `num_test_funcs` | INTEGER | Estimated number of test function definitions in this file |
| `num_fixtures`  | INTEGER | Number of fixture definitions detected in this file |

---

### 3.3 `fixtures`

One row per fixture definition. This is the primary analysis table.

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
| `cyclomatic_complexity`        | INTEGER | 1 + number of branching statements (proxy metric) |
| `num_objects_instantiated`     | INTEGER | Estimated constructor calls inside the fixture |
| `num_external_calls`           | INTEGER | Estimated I/O / external API calls (DB, HTTP, filesystem, env) |
| `num_parameters`               | INTEGER | Number of function parameters |
| `has_yield`                    | INTEGER | `1` if the fixture contains a `yield` statement (signals a teardown section) |
| `raw_source`                   | TEXT    | Full source text of the fixture as extracted |
| `category`                     | TEXT    | RQ1 taxonomy label — `NULL` until manually classified |

**`fixture_type` values:**

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
| `test_main` | Go | `func TestMain(m *testing.M)` |
| `go_helper` | Go | Non-test helper called from ≥ 2 `TestXxx` functions (heuristic — see §12) |

---

### 3.4 `mock_usages`

One row per mock call detected inside a fixture.

| Column                      | Type                           | Description                        |
|-----------------------------|--------------------------------|------------------------------------|
| `id`                        | INTEGER PK                     | Internal identifier                |
| `fixture_id`                | INTEGER FK → `fixtures.id`     |                                    |
| `repo_id`                   | INTEGER FK → `repositories.id` | Denormalised for query convenience |
| `framework`                 | TEXT                           | Detection pattern — see values below |
| `mock_style`                | TEXT                           | `stub` \| `mock` \| `spy` \| `fake` — `NULL` until classified |
| `target_identifier`         | TEXT                           | String passed to the mock call (e.g. `"mymodule.HttpClient"`) |
| `target_layer`              | TEXT                           | `boundary` \| `infrastructure` \| `internal` \| `framework` — `NULL` until classified |
| `num_interactions_configured` | INTEGER                      | Count of `return_value` / `thenReturn` / `side_effect` style calls found near the mock |
| `raw_snippet`               | TEXT                           | Short source snippet surrounding the mock call |

**`framework` values:** `unittest_mock`, `pytest_mock`, `mockito`, `easymock`,
`mockk`, `jest`, `sinon`, `vitest`, `gomock`, `testify_mock`

---

### 3.5 Entity-Relationship Summary

```
repositories (1) ──< test_files (1) ──< fixtures (1) ──< mock_usages
      │                                      │
      └──────────────── repo_id ─────────────┘  (denormalised FK)
```

---

## 4. Data Collection Process

The pipeline runs in five sequential phases. Each phase is idempotent — if it
is interrupted and restarted, already-completed work is skipped.

### Phase 1 — Repository Discovery (`search`)

The GitHub Search API is queried for repositories matching per-language
criteria. Because GitHub caps search results at 1,000 per query, the search
is split into **6-month creation-date buckets** going back to January 2015.
Each bucket is a separate query, and results within a bucket are paginated
(up to 10 pages × 100 results = 1,000 per bucket).

Repositories are written to the `repositories` table with `status = 'discovered'`.
Repos that match **exclusion keywords** in their name or description
(`tutorial`, `homework`, `exercise`, `bootcamp`, `demo`, `awesome-`, etc.)
are silently dropped before writing.

Authenticated requests (with `GITHUB_TOKEN`) are rate-limited to
30 search requests/minute. The pipeline respects this with a 2-second delay
between pages and backs off automatically on 403 responses.

### Phase 2 — Cloning (`clone`)

Repositories in `discovered` status are shallow-cloned (`git clone --depth 1`)
in parallel using a configurable thread pool (default: 4 workers).
After cloning, two **quality filters** are applied:

- **Commit count** ≥ 50: the pipeline fetches up to 500 commits of history
  to get a realistic count. Repos below the threshold are marked `skipped`
  and the clone is deleted.
- **Test file count** ≥ 5: path and suffix heuristics are used to count
  test files. Repos below the threshold are marked `skipped`.

Repos passing both filters are marked `cloned`. The clone directory is kept
until extraction completes.

### Phase 3 — Extraction (`extract`)

For each `cloned` repository the extractor:

1. Walks all test files (identified by path and suffix heuristics,
   skipping `vendor/`, `node_modules/`, `dist/`, etc.)
2. Reads each file's source bytes
3. Parses it with the appropriate **Tree-sitter grammar**
4. Runs language-specific AST queries to find fixture definitions
5. For each fixture, runs regex-based mock detection over the fixture's
   source text
6. Writes results to `test_files`, `fixtures`, and `mock_usages`
7. Marks the repo `analysed` and deletes the local clone

Repos where zero fixtures are found after full extraction are marked `skipped`.

### Phase 4 — Domain Classification (`classify`)

A keyword-based heuristic assigns each repository a domain label by matching
against its name, description, and GitHub topics. Labels: `web`, `data`,
`cli`, `infra`, `library`, `other`. This runs in-database and takes seconds.

### Phase 5 — Export (`export`)

Produces a versioned zip file ready for Zenodo deposit containing:
- `fixturedb.sqlite` — the full database
- `repositories.csv`, `test_files.csv`, `fixtures.csv`, `mock_usages.csv`
- `README.txt` — schema documentation
- `stats.txt` — per-language counts for Table 1 of the paper

The `raw_source` column is excluded from `fixtures.csv` by default
(it is large text already present in the SQLite file). Pass `--include-source`
to include it.

---

## 5. Storage and Scale Estimates

### During collection (temporary)

Each shallow clone occupies roughly 50–200 MB depending on repository size.
With 4 parallel workers the peak transient disk usage is:

```
4 workers × 200 MB = ~800 MB peak during cloning
```

Clones are deleted immediately after extraction, so sustained disk usage
stays low even over a long collection run.

### Final dataset (permanent)

Based on the target collection of ~4,000 searched repos and an expected
~60 % survival rate after filters (~2,400 analysed repos):

| Item                                   | Estimate |
|----------------------------------------|-------------|
| SQLite database (without `raw_source`) | ~150–300 MB |
| SQLite database (with `raw_source`)    | ~1–3 GB |
| All CSV exports (without `raw_source`) | ~80–150 MB |
| Zenodo zip (without `raw_source`)      | ~100–200 MB |

The `raw_source` column dominates storage. The Zenodo deposit excludes it
from CSV by default but includes it in the SQLite file, giving researchers
access to the full fixture text while keeping the primary download size
manageable.

### Database (corpus.db) growth during a run

The pipeline writes incrementally. You can query progress at any time:

```bash
python pipeline.py stats
```

---

## 6. Setup and Requirements

### Prerequisites

- Python 3.11+
- Git (must be on `PATH`)
- A GitHub personal access token (free, no special scopes needed)

### Installation

```bash
git clone https://github.com/marcelofa/fixture-corpus.git
cd fixture-corpus

pip install -r requirements.txt

cp .env.example .env
# Open .env and set GITHUB_TOKEN=<your token>
# Get a token at: https://github.com/settings/tokens

python pipeline.py init
```

### Dependencies

| Package         | Purpose |
|-----------------|---------|
| `pydriller`     | Repository traversal and git metadata |
| `tree-sitter` + language bindings | AST parsing for all five languages |
| `requests`      | GitHub Search API client |
| `python-dotenv` | `.env` file loading |
| `pandas`        | CSV export and validation sample generation |
| `tqdm`          | Progress bars |
| `gitpython`     | Git operations in the cloner |

---

## 7. Running the Pipeline

### Full run (recommended)

```bash
# All languages, full targets (~4,000 repos searched, ~2,400 expected to survive)
python pipeline.py run

# Single language, full target
python pipeline.py run --language python

# Smoke test with a small batch
python pipeline.py run --language python --max 20
```

The `run` command executes all phases in order: init → search → clone → extract → classify.

### Running phases independently

```bash
# Phase 1: discover repos (writes to DB, no cloning yet)
python pipeline.py search --language java --max 1000

# Phase 2: clone a batch of discovered repos
python pipeline.py clone --language java --batch 50

# Phase 3: extract fixtures from all cloned repos
python pipeline.py extract --language java

# Phase 4: assign domain labels
python pipeline.py classify

# Check current counts
python pipeline.py stats
```

Running phases independently is useful for incremental collection — you can
run `clone` and `extract` in a loop, processing repos in batches without
re-running the search phase.

### Validation (for the paper's precision/recall numbers)

```bash
# Step 1: generate a stratified sample (50 fixtures per language)
python pipeline.py validate --sample 50

# Step 2: open validation/sample_<timestamp>.csv
# For each row, read 'raw_source' and set 'is_true_fixture' to 1 or 0

# Step 3: compute precision
python pipeline.py validate --compute validation/sample_<timestamp>.csv
```

### Export (Zenodo deposit)

```bash
python pipeline.py export --version 1.0
# Produces: export/fixturedb_v1.0_<date>.zip
```

---

## 8. Reproducing the Paper Corpus

The exact state of every repository analysed in the paper is reproducible
via the `pinned_commit` SHA stored in the `repositories` table.

```bash
# Query the pinned commit for a specific repo
sqlite3 data/corpus.db \
  "SELECT full_name, clone_url, pinned_commit FROM repositories
   WHERE full_name = 'pytest-dev/pytest';"

# Re-clone at the exact state used in the paper
git clone <clone_url>
cd <repo>
git fetch --depth 1 origin <pinned_commit>
git checkout <pinned_commit>
```

To fully replicate the corpus from scratch:

1. Clone this repository
2. Set up your GitHub token
3. Run `python pipeline.py run`

Note that GitHub repositories may be deleted or made private after the paper
was published. The Zenodo deposit includes the SQLite database with all
extracted data, so the analytical corpus remains available regardless.

---

## 9. Using the Dataset for Research

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

---

## 10. Configuration Reference

All collection parameters live in `corpus/config.py`.

### Per-language targets

| Language       | `min_stars` | `target_repos` | Rationale |
|----------------|-------------|----------------|----------|
| Python         | 100         | 1,000          | Large ecosystem, high test culture |
| Java           | 100         | 1,000          | Direct comparability with Hamster |
| JavaScript     | 100         | 800            | Frontend repos often yield few fixtures |
| TypeScript     | 100         | 600            | Younger ecosystem |
| Go             | 100         | 600            | Smaller ecosystem |

### Star tiers

| Tier       | `stars` range | Comparable to |
|------------|---------------|---------------|
| `core`     | ≥ 500         | Hamster (arXiv:2509.26204) selection criterion |
| `extended` | 100–499       | Common MSR floor; adds diversity |

### Quality filters (post-clone)

| Parameter             | Default | Effect |
|-----------------------|---------|--------|
| `MIN_TEST_FILES`      | 5       | Repos with fewer test files are marked `skipped` |
| `MIN_COMMITS`         | 50      | Repos with fewer commits are marked `skipped` |
| `MIN_FIXTURES_FOUND`  | 1       | Repos where extraction finds zero fixtures are marked `skipped` |

### Pipeline tuning

| Parameter           | Default | Notes |
|---------------------|---------|-------|
| `CLONE_WORKERS`     | 4       | Parallel clone threads — increase if network allows |
| `CLONE_BATCH_SIZE`  | 50      | Repos per `clone` invocation |
| `REQUEST_DELAY`     | 2.0 s   | Pause between GitHub Search API pages |

---

## 11. Fixture Detection Logic

Detection is implemented in `corpus/detector.py` using
[Tree-sitter](https://tree-sitter.github.io/tree-sitter/) grammars.
Each language has a dedicated detector function that walks the AST
and matches fixture-defining nodes.

Mock detection is a second pass over the fixture's source text using
compiled regular expressions covering all major mock frameworks per language.
It is intentionally language-agnostic to catch cross-language patterns and
runs after the AST phase.

### Go heuristic

Go has no formal fixture annotation. The detector applies a call-graph
heuristic: a non-test function (not prefixed `Test`, `Benchmark`, or
`Example`) that is called from ≥ 2 `TestXxx` functions in the same file
is classified as a `go_helper` fixture.

This heuristic has lower precision than the annotation-based detectors
for other languages. See [§12](#12-limitations-and-threats-to-validity)
for the validated false-positive rate and the manual validation procedure.

---

## 12. Limitations and Threats to Validity

**Sampling bias.**
The corpus is drawn from repositories with ≥ 100 GitHub stars. Popular,
actively maintained projects may exhibit higher test discipline than typical
open-source software. A prior study from our institution (Coelho et al.,
MSR 2020) shows that star-based sampling over-represents JavaScript projects
and web frameworks; this is why `star_tier` is recorded and why we recommend
stratifying analyses by tier.

**Go heuristic precision.**
The `go_helper` detector is heuristic-based. TODO: insert false-positive rate
from manual validation once completed.

**Snapshot corpus.**
Each repository is captured at a single commit. The dataset does not support
longitudinal analyses of fixture evolution.

**Language coverage.**
This release covers five language variants. Ruby (RSpec), C# (NUnit/xUnit),
and Rust (built-in test module) are not included.

**Mock detection completeness.**
Mock detection uses regular expressions over source text. Framework versions
or unusual coding styles may produce false negatives. The `raw_source`
column is included in the SQLite file specifically so that researchers can
re-run or improve detection against the original fixture text.

---

## 13. License

| Artifact                               | License |
|----------------------------------------|---------|
| Pipeline source code (this repository) | MIT |
| FixtureDB dataset (Zenodo deposit)     | CC BY 4.0 |

All source repositories in the corpus were collected from public GitHub
under their original open-source licenses. No proprietary or private code
is included. Source snippets stored in `raw_source` and `raw_snippet` are
reproduced solely to enable reproducible research, consistent with academic
fair use.