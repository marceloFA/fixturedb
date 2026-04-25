# Limitations and Threats to Validity

## Sampling bias

The corpus is drawn from repositories with ≥ 100 GitHub stars. Popular,
actively maintained projects may exhibit higher test discipline than typical
open-source software. This is a known limitation in empirical software
engineering studies (Hamster study by Pan et al., 2025) which also used
star-based sampling to ensure sufficient test coverage. To mitigate this bias
and improve generalizability, the dataset records `star_tier` (`core` for ≥500
stars, `extended` for 100–499) and we recommend stratifying all analyses by tier.
This allows researchers to study both popular and emerging projects separately.

## Language coverage

FixtureDB covers four languages: Python, Java, JavaScript, and TypeScript.
Other languages such as Ruby (RSpec), Kotlin, Scala, Rust, C#, and Go are not included.

## Mock detection completeness

Mock detection uses regular expressions over source text. Framework versions
or unusual coding styles may produce false negatives. The `raw_source`
column is included in the SQLite file specifically so that researchers can
re-run or improve detection against the original fixture text.

## Fixture detection false-negative rates

Fixture detection uses syntax-based patterns (decorators, annotations, named methods) to identify fixture definitions. While this approach provides high precision, some fixtures using uncommon idioms may be missed.

### Expected Detection Recall by Language

| Language   | Expected Recall | Notes |
|------------|-----------------|-------|
| Python     | >95%            | Strong decorator standardization (`@pytest.fixture`, `setUp`/`tearDown` method names). Import variations or dynamically-created fixtures may be missed. |
| Java       | >95%            | Annotation-based detection (@Before, @BeforeClass, @After, @AfterEach) is unambiguous. Custom base class patterns are caught. |
| JavaScript | >90%            | Test framework conventions vary (Jest, Mocha, Jasmine, Vitest). Helper functions not matching common naming patterns may be missed. |
| TypeScript | >90%            | Same as JavaScript; type annotations do not improve detection of fixtures, which rely on runtime hook names. |

### Sources of False Negatives

1. **Custom helper functions**: Functions that implement fixture-like behavior (setup/teardown) but don't match standard naming patterns (e.g., `prepareTestData()` instead of `setUp()`)
2. **Metaprogrammed fixtures**: Dynamic fixture creation using `eval()`, `exec()`, or factory patterns that generate fixtures at runtime
3. **Non-standard fixture mechanisms**: Project-specific setup/teardown wrappers that abstract the standard framework APIs
4. **Language-specific edge cases**:
   - **Python**: Nested functions or lambdas used as fixtures without `@pytest.fixture` decorator
   - **JavaScript**: Dynamic test hook registration or custom test runners that don't use standard `beforeEach` patterns

### Mitigation

- The `raw_source` column in SQLite contains the full fixture source code, allowing researchers to:
  - Manually audit missed fixtures on important projects
  - Implement improved detection heuristics on the original source
  - Quantify false-negative rates for specific use cases
- To assess detection quality for your research: sample 100–200 test files per language, manually check for fixtures our detector missed, and calculate recall

---

## Advanced Metrics Limitations

### `reuse_count` — Under-estimation in Dynamic Tests

- **Limitation**: Does not count parameterized test functions individually
- **Reason**: Parameterized tests (pytest `@pytest.mark.parametrize`, JUnit `@ParameterizedTest`) are counted as single test functions; each parameter set is not tracked separately
- **Impact**: A fixture used by a parameterized test with 10 parameter sets is counted as 1 reuse, not 10
- **Mitigation**: Query `test_files` table to identify parameterized patterns; cross-reference with fixture usage analysis

### `has_teardown_pair` — Heuristic Detection Limits

- **Python**: Highly accurate (yield detection, setUp/tearDown pairing)
- **Java**: Accurate for annotation-based (@After, @AfterEach)
- **JavaScript/TypeScript**: Best-effort scope inference; ambiguous cases may misclassify
- **Limitation**: Implicit cleanup (e.g., connection pooling in frameworks, automatic resource management) is not detected
- **Mitigation**: `raw_source` field available in SQLite for manual verification on important fixtures

### `num_contributors` — GitHub API Pagination Limits

- **Limitation**: GitHub API returns up to ~30 contributors per page; total count capped at API page limit in some scenarios
- **Workaround**: Implemented Link header pagination to retrieve actual page count
- **Impact**: Repositories with >100 contributors may be slightly under-counted
- **Mitigation**: For precise contributor counts on specific repositories, use GitHub's direct API or web interface

### `max_nesting_depth` — Lambda/Closure Detection

- **Limitation**: Nested function definitions increase nesting depth (Python closures, JavaScript arrow functions)
- **Impact**: May over-estimate nesting depth when nesting is logical closure nesting, not control flow nesting
- **Example**: Nested function definitions inside a fixture count as depth increases, even if body is simple
- **Trade-off**: Conservative approach avoids under-counting; classified members and closures are counted together
- **Mitigation**: Combine with `cognitive_complexity` for more accurate assessment of actual code complexity
