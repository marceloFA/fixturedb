# Database Schema

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
| `num_test_funcs` | INTEGER | Estimated number of test function definitions in this file |
| `num_fixtures`  | INTEGER | Number of fixture definitions detected in this file |

## 3.3 `fixtures`

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
| `test_main` | Go | `func TestMain(m *testing.M)` |
| `go_helper` | Go | Non-test helper called from ≥ 2 `TestXxx` functions (heuristic — see §12) |

## 3.4 `mock_usages`

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

### `framework` values

`unittest_mock`, `pytest_mock`, `mockito`, `easymock`, `mockk`, `jest`,
`sinon`, `vitest`, `gomock`, `testify_mock`

## Entity-Relationship Summary

```
repositories (1) ──< test_files (1) ──< fixtures (1) ──< mock_usages
      │                                      │
      └──────────────── repo_id ─────────────┘  (denormalised FK)
```
