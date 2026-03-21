# Configuration Reference

All collection parameters live in `corpus/config.py`.

## Per-language targets

| Language       | `min_stars` | `target_repos` | Rationale |
|----------------|-------------|----------------|----------|
| Python         | 100         | 1,000          | Large ecosystem, high test culture |
| Java           | 100         | 1,000          | Direct comparability with Hamster |
| JavaScript     | 100         | 800            | Frontend repos often yield few fixtures |
| TypeScript     | 100         | 600            | Younger ecosystem |
| Go             | 100         | 600            | Smaller ecosystem |

## Star tiers

| Tier       | `stars` range | Comparable to |
|------------|---------------|---------------|
| `core`     | ≥ 500         | Hamster (arXiv:2509.26204) selection criterion |
| `extended` | 100–499       | Common MSR floor; adds diversity |

## Quality filters (post-clone)

| Parameter             | Default | Effect |
|-----------------------|---------|--------|
| `MIN_TEST_FILES`      | 5       | Repos with fewer test files are marked `skipped` |
| `MIN_COMMITS`         | 50      | Repos with fewer commits are marked `skipped` |
| `MIN_FIXTURES_FOUND`  | 1       | Repos where extraction finds zero fixtures are marked `skipped` |

## Pipeline tuning

| Parameter           | Default | Notes |
|---------------------|---------|-------|
| `CLONE_WORKERS`     | 4       | Parallel clone threads — increase if network allows |
| `CLONE_BATCH_SIZE`  | 50      | Repos per `clone` invocation |
| `REQUEST_DELAY`     | 2.0 s   | Pause between GitHub Search API pages |
