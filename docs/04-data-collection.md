# Data Collection Process

The pipeline runs in five sequential phases. Each phase is idempotent — if it
is interrupted and restarted, already-completed work is skipped.

## Phase 1 — Repository Discovery (`search`)

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

## Phase 2 — Cloning (`clone`)

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

## Phase 3 — Extraction (`extract`)

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

## Phase 4 — Domain Classification (`classify`)

A keyword-based heuristic assigns each repository a domain label by matching
against its name, description, and GitHub topics. Labels: `web`, `data`,
`cli`, `infra`, `library`, `other`. This runs in-database and takes seconds.

## Phase 5 — Export (`export`)

Produces a versioned zip file ready for Zenodo deposit containing:
- `fixturedb.sqlite` — the full database
- `repositories.csv`, `test_files.csv`, `fixtures.csv`, `mock_usages.csv`
- `README.txt` — schema documentation
- `stats.txt` — per-language counts for Table 1 of the paper

The `raw_source` column is excluded from `fixtures.csv` by default
(it is large text already present in the SQLite file). Pass `--include-source`
to include it.
