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

See [Limitations — Go language exclusion](../reference/12-limitations.md) for rationale.

## Tool Versions (for Reproducibility)

The following tool versions were used during extraction. To exactly replicate the corpus, use identical versions:

```
GitHub API:                    v3 REST API

AST Parsing:
  - Tree-sitter core:          v0.21.0+
  - tree-sitter-python         v0.21.0+
  - tree-sitter-java           v0.21.0+
  - tree-sitter-javascript     v0.21.0+
  - tree-sitter-typescript     v0.21.0+

Code Metrics:
  - Lizard                      v1.21.3+ (cyclomatic complexity, LOC, 
                                          parameters, external call count)
  - complexipy                  v5.0.0+ (Python cognitive complexity, SonarQube-standard)

Runtime:
  - Python                      3.8+
  - SQLite                      3.x
```

**Key Tools & Rationale:**

- **Lizard** (v1.21.3+): Handles cyclomatic complexity, cognitive complexity fallback, LOC, parameters, and external function call detection across all languages. Reduces custom metric code while maintaining reproducibility via industry-standard tool.

- **cognitive-complexity** (v1.3.0+): Python-specific SonarQube-standard cognitive complexity implementation. Provides accurate nesting-depth-weighted complexity for Python; other languages use Lizard-based formula fallback.

- **Tree-sitter** (v0.21.0+): AST parsing for fixture detection, scope analysis, and code structure metrics across 5 languages. Provides consistent abstract syntax representation independent of language syntax quirks.

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

Produces a versioned zip file ready for Zenodo deposit. **This phase creates two complementary formats optimized for different use cases**:

**SQLite Database** (`fixturedb.sqlite`) — For reproducibility verification and raw source inspection:
- `fixturedb.sqlite` — the full database with all fields, internal classifications, and raw source code
- See [Database Schema — SQLite Section](../architecture/03-database-schema.md)

**CSV Exports** (`.csv` files) — For spreadsheet and statistical analysis:
- `repositories.csv`, `test_files.csv`, `fixtures.csv`, `mock_usages.csv` — core tables
- `fixtures_python.csv`, `fixtures_java.csv`, `fixtures_javascript.csv`, `fixtures_typescript.csv` — language-specific
- `stats.txt` — high-level statistics (per-language counts for paper tables)
- `README.txt` — schema documentation

**Key Difference**: The `raw_source` column (full fixture source code) is excluded from CSVs by default because it is large and already available in the SQLite file. Pass `--include-source` to include raw source in `fixtures.csv` if needed.

See [Database Schema — CSV Export Schema](../architecture/03-database-schema.md) for detailed column documentation and [Using the Dataset for Research](../usage/09-usage.md) for guidance on which format to use.
