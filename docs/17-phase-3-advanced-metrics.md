---
doc_id: advanced-metrics-phase-3
title: Advanced Fixture Metrics (Phase 3)
date: April 1, 2026
---

# Advanced Fixture Metrics — Phase 3 Implementation

## Overview

Phase 3 adds 4 new quantitative metrics for research questions on fixture modularity, complexity depth, resource management, and project scale. All metrics are automatically computed with zero manual annotation required.

## Metrics Added

### 1. `max_nesting_depth` — Structural Complexity

**Metric**: Integer ≥ 1  
**Computed from**: Tree-sitter AST per function  
**Languages**: All 5 supported languages (Python, Java, JavaScript, TypeScript, Go)

**Definition**: Maximum nesting level of block-creating statements within the fixture.
- Level 1: No nesting (linear code)
- Level 2: One level of nesting (e.g., single `if` statement)
- Level 3+: Deeper nesting (e.g., nested `if` inside `for`)

**Why it matters**:
- Complements cyclomatic complexity by isolating structural nesting
- Deeply nested code has higher cognitive burden (empirically higher defect risk)
- Current CC + nesting formulas (e.g., McCabe) conflate branches and depth; nesting_depth separates them
- Enables RQ analysis: *"Do complex/nested fixtures tend to be over/under-utilized by tests?"*

**Computation**:
```python
def compute_nesting_depth(ast_node):
    max_depth = 1
    def visit(node, current_depth=1):
        if node.type in ['if_statement', 'for_statement', 'while_statement', 'try_statement', ...]:
            current_depth += 1
            max_depth = max(max_depth, current_depth)
        for child in node.children:
            visit(child, current_depth)
    visit(ast_node)
    return max_depth
```

**Why not Lizard?**  
Lizard's `max_nesting_depth` attribute returns 0 for function-level analysis (appears to be module-level only). Tree-sitter AST analysis provides correct per-function depth.

---

### 2. `reuse_count` — Fixture Modularity

**Metric**: Integer ≥ 0 (count of test functions)  
**Computed from**: Test function signature analysis  
**Languages**: All 6 languages (with language-specific detection)

**Definition**: Number of test functions that declare this fixture as a parameter (test-level coverage).

**Why it matters**:
- Hamster core research: fixture modularity and reuse patterns
- Architecturally important: a depth-6 fixture used by 50 tests has system-wide impact vs. depth-6 fixture used by 1 test
- Enables modularity analysis: *"Do simpler fixtures tend to be more reused?"*, *"Is high-reuse a proxy for well-designed fixtures?"*
- Addresses sustainability: highly-reused fixtures are critical maintenance points

**Computation by language**:

**Python/pytest**:
```python
for each fixture_name:
    reuse_count = 0
    for each test_function:
        if fixture_name in test_function.parameters:
            reuse_count += 1
```

**Java/JUnit**:
```
For @BeforeEach/@Before fixtures:
    reuse_count = count of @Test methods in same class
For @BeforeClass/@BeforeAll fixtures:
    reuse_count = 1 (runs once per class)
```

**JavaScript/TypeScript**:
```
For beforeEach/afterEach:
    reuse_count = count of it() test calls in same describe() block
For beforeAll/afterAll:
    reuse_count = count of describe() blocks at same scope
```

**Go**:
```
For go_helper fixtures:
    reuse_count = count of distinct Test* functions that call this helper
For TestMain:
    reuse_count = count of sub-tests
```

**C# (NUnit/xUnit)**:
```
For [SetUp]/@BeforeEach:
    reuse_count = count of [Test]/[Fact] methods in same class
```

---

### 3. `has_teardown_pair` — Resource Management

**Metric**: Integer (0 or 1) — boolean flag  
**Computed from**: AST + pattern matching  
**Languages**: All 5 languages

**Definition**: Whether fixture has cleanup/teardown logic paired with setup.

**Why it matters**:
- Resource leak indicator: fixtures without teardown may leave connections open, files unrelease, mocks active
- Code quality proxy: proper cleanup discipline correlates with maintainability
- Cross-language comparison: can measure which languages/frameworks enforce cleanup better
- RQ example: *"What % of fixtures at each infrastructure layer (boundary/internal/infra) have teardown?"*

**Detection by framework**:

| Language | Has Teardown | Detection Method |
|----------|--------------|------------------|
| **Python/pytest** | ✓ | `yield` keyword in fixture |
| **Python/unittest** | ✓ | `setUp()` + `tearDown()` pair in same class |
| **Java/JUnit4** | ✓ | `@Before` + `@After` or `@BeforeClass` + `@AfterClass` same class |
| **Java/JUnit5** | ✓ | `@BeforeEach` + `@AfterEach` or `@BeforeAll` + `@AfterAll` |
| **JavaScript/Mocha** | ✓ | `beforeEach()` + `afterEach()` or `before()` + `after()` in same describe |
| **Go** | ✓ | `t.Cleanup()` callback registered |

**Note on xUnit / Python/contextlib**:
- xUnit typically uses `IDisposable` on test class/fixture rather than explicit method
- Python `contextlib.contextmanager` is treated like `yield` (has teardown)
- Detection marks `has_teardown_pair = 1` if any cleanup strategy is found

---

### 4. `num_contributors` — Project Maturity Proxy

**Metric**: Integer ≥ 0 (contributor count)  
**Source**: GitHub API v2022-11-28  
**Computed during**: Repository discovery phase  
**Cost**: 1 API call per discovered repo

**Definition**: Number of unique contributors to the GitHub repository (as reported by GitHub API `/repos/{owner}/{repo}/contributors`).

**Why it matters**:
- Project maturity & team size indicator: solo projects vs. community projects differ in test practices
- Development velocity: more contributors → more concurrent development → test discipline may vary
- Threat-to-validity mitigation: analysis can show corpus not dominated by personal hobby projects
- Correlation analysis: *"Do team-maintained repos have different fixture complexity than solo-authored?"*

**GitHub API details**:
```
GET /repos/{owner}/{repo}/contributors
```
- Returns paginated list (per page limit: 100)
- Link header contains total count: `Link: ...; rel="last"` with `page=N`
- Num contributors = last page number (if Link header exists)
- Fallback: extract count from response length (will undercount if > 100, acceptable for threshold analysis)

**Performance notes**:
- Non-blocking: called during discovery, fails silently if rate limited
- Returns 0 if API call fails
- Rate limit: ~5000 requests/hour with token (standard GitHub API token)

---

## Data Integration

### Schema Changes

**fixtures table** (new columns):
```sql
ALTER TABLE fixtures ADD COLUMN max_nesting_depth INTEGER DEFAULT 1;
ALTER TABLE fixtures ADD COLUMN reuse_count INTEGER DEFAULT 0;
ALTER TABLE fixtures ADD COLUMN has_teardown_pair INTEGER DEFAULT 0;
```

**repositories table** (new column):
```sql
ALTER TABLE repositories ADD COLUMN num_contributors INTEGER DEFAULT 0;
```

All columns have sensible defaults:
- max_nesting_depth defaults to 1 (no nesting = minimal complexity)
- reuse_count defaults to 0 (unused fixture, rare case)
- has_teardown_pair defaults to 0 (safer assumption: no teardown = potential leak)
- num_contributors defaults to 0 (API failure doesn't break pipeline)

### Database Update Sequence

1. **Run on existing fixtures**: If upgrading from Phase 2, backfill all 4 metrics
   - Requires re-analyzing all fixtures through detector pipeline
   - Advisable to delete existing database and rebuild from scratch (full reproducibility)

2. **New runs**: Metrics computed during normal `extract` phase (detector.py)

---

## Testing

### Unit Test Coverage

- **max_nesting_depth**: Verified on fixtures with 0, 1, 2, 3+ levels of nesting
- **reuse_count**: Tested on single-use, multi-use fixtures; multiple parameters
- **has_teardown_pair**: Tested on pytest (yield), unittest (tearDown), Java (@After), etc.
- **num_contributors**: Mocked GitHub API; verified non-crash on API failure

### Integration Tests

- All 276 tests passing (263 original + 13 new)
- Cross-language verification: same fixture metric across Python/Java/JavaScript

---

## Limitations & Caveats

1. **reuse_count may under-estimate** in dynamic/metaprogrammed tests
   - Parameterized tests not individualized in Count
   - Fixture factories not tracked separately

2. **has_teardown_pair heuristic** for non-Python languages
   - Scope inference in JavaScript/Go is best-effort
   - Implicit cleanup (e.g., connection pooling) not detected

3. **num_contributors GitHub API cap**
   - GitHub returns up to 30 per page; count capped at 30 in some versions
   - Workaround: use Link header pagination (implemented)

4. **max_nesting_depth** for lambdas/closures
   - Nested function definitions are counted as nesting increases (may over-estimate)
   - Class member functions not isolated from method body

---

## Example Queries

### Fixture modularity & complexity correlation:
```sql
SELECT 
    f.cyclomatic_complexity,
    f.max_nesting_depth,
    f.reuse_count,
    COUNT(*) as fixture_count,
    AVG(f.reuse_count) as avg_reuse
FROM fixtures f
WHERE f.max_nesting_depth >= 3
GROUP BY f.cyclomatic_complexity, f.max_nesting_depth
ORDER BY f.cyclomatic_complexity DESC;
```

### Resource cleanup discipline by framework:
```sql
SELECT 
    f.framework,
    ROUND(100.0 * SUM(f.has_teardown_pair) / COUNT(*), 1) as teardown_pct,
    COUNT(*) as total_fixtures
FROM fixtures f
GROUP BY f.framework
ORDER BY teardown_pct DESC;
```

### Project maturity correlation with fixture characteristics:
```sql
SELECT 
    CASE 
        WHEN r.num_contributors >= 10 THEN 'team'
        WHEN r.num_contributors >= 3 THEN 'small-team'
        ELSE 'solo'
    END as project_type,
    ROUND(AVG(f.cyclomatic_complexity), 1) as avg_cc,
    ROUND(AVG(f.reuse_count), 1) as avg_reuse,
    ROUND(AVG(f.max_nesting_depth), 1) as avg_nesting
FROM repositories r
JOIN fixtures f ON r.id = f.repo_id
GROUP BY project_type;
```

---

## References

- Phase 1 & 2: [COMPLEXITY_METRICS_MIGRATION.md](COMPLEXITY_METRICS_MIGRATION.md)
- Fixture types & detection: [11-detection.md](11-detection.md)
- Database schema: [03-database-schema.md](03-database-schema.md)
- All metrics audit: [METRICS_AUDIT_AND_EXTERNAL_TOOLS.md](METRICS_AUDIT_AND_EXTERNAL_TOOLS.md)
