# Data Collection Process

**Collection Metadata**  
- **Collection Period**: April 1–2, 2026
- **Repositories Collected**: 160 (4 languages: Python, Java, JavaScript, TypeScript; Go excluded by design)
- **Total Fixtures Extracted**: 40,672
- **Extraction Timestamp Range**: 2026-04-01 20:16:59 to 2026-04-01 23:18:03 UTC
- **Reproducibility**: All collection parameters pinned in code; repos at specific commits preserved

### Go Language Handling

**Clarification**: While the collection codebase (`collection/detector.py`, `collection/config.py`) contains Go extraction logic for reference, **Go is not included in the FixtureDB dataset**. The distinction:

1. **Code Level**: Go detection logic exists in `detector.py` and language config in `config.py` (retained for reference)
2. **Data Level**: The database (`data/corpus.db`) contains only 4 languages: Python, Java, JavaScript, TypeScript
3. **CSV Level**: CSV exports (`fixtures.csv`, `fixtures_python.csv`, etc.) contain only data from the 4 languages

See [Limitations — Go language exclusion](12-limitations.md#go-language-exclusion) for rationale.

## Tool Versions (for Reproducibility)

The following tool versions were used during extraction. To exactly replicate the corpus, use identical versions:

```
GitHub API:                    v3 REST API
Tree-sitter core:             v0.21.0+
Tree-sitter grammars:         v0.21.0+
  - tree-sitter-python        v0.21.0+
  - tree-sitter-java          v0.21.0+
  - tree-sitter-javascript    v0.21.0+
  - tree-sitter-typescript    v0.21.0+

Complexity Metrics:
  - Lizard (cyclomatic)        v1.21.0+
  - cognitive_complexity       v1.3.0+

Python:                        3.8+
SQLite:                        3.x
```

See [requirements.txt](../requirements.txt) for exact pinned versions used in this execution.

## Collection Strategy

**Why This Matters for Reproducibility:**
- GitHub API evolves; newer versions may return different results
- Tree-sitter grammars receive updates that change AST structure
- Complexity metric implementations can change between versions
- We pinned all versions to ensure bit-for-bit reproducibility

**Time Window:**
Corpus was collected over ~3 hours (April 1–2, 2026 20:16–23:18 UTC). During this window:
- GitHub API availability was stable
- No major GitHub service incidents occurred
- All 160 repositories successfully cloned and analyzed (Go not included by design)

---

## Collection Pipeline

The pipeline runs in five sequential phases. Each phase is idempotent — if it
is interrupted and restarted, already-completed work is skipped.

## Phase 1 — Repository Discovery (`search`)

The GitHub Search API is queried for repositories matching per-language
criteria. **By default, repositories are collected sorted by star count
(most stars first)** to maximize the percentage of high-quality (500+ stars)
repositories.

The default `--sort-by-stars` strategy paginates through results
(up to 35 pages × 100 results) ordered by GitHub's native star ranking.

### Alternative: Stratified collection

If temporal balance is desired, use `--stratified` flag to collect repos
proportionally from each year (2015–present). This strategy splits the search
into **1-year creation-date buckets** and allocates repos per bucket to ensure
even representation across time. This is useful if analyzing the evolution of
testing practices over the years.

**Note:** GitHub caps search results at 1,000 per query. Both strategies
respect this limit via pagination (star-count: 35 pages of results; stratified:
one query per year, paginated up to 10 pages per bucket).

### Common to all strategies

Repositories are written to the `repositories` table with `status = 'discovered'`.
Repos that match **exclusion keywords** in their name or description
(`tutorial`, `homework`, `exercise`, `bootcamp`, `demo`, `awesome-`, etc.)
are silently dropped before writing.

Authenticated requests (with `GITHUB_TOKEN`) are rate-limited to
30 search requests/minute. The pipeline respects this with a 2-second delay
between requests and backs off automatically on 403 responses.

## Phase 2 — Cloning (`clone`)

Repositories in `discovered` status are shallow-cloned (`git clone --depth 1`)
in parallel using a configurable thread pool (default: 4 workers).
After cloning, two **quality filters** are applied to ensure we capture
repositories with mature testing practices:

- **Commit count** ≥ 50: the pipeline fetches up to 500 commits of history
  to get a realistic count. This threshold filters out prototype and toy
  projects. Repos below the threshold are marked `skipped` and the clone is deleted.
- **Test file count** ≥ 5: path and suffix heuristics are used to count
  test files (Ahmed et al., 2025). Repos with fewer test files suggest
  minimal testing culture and are marked `skipped`. This aligns with observed
  patterns in large-scale test suite studies (Pan et al., 2025).

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
