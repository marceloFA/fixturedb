# Limitations and Threats to Validity

## Sampling bias

The corpus is drawn from repositories with ≥500 GitHub stars. Popular,
actively maintained projects may exhibit higher test discipline than typical
open-source software. This is a known limitation in empirical software
engineering studies (Hamster study by Pan et al., 2025) which also used
star-based sampling to ensure sufficient test coverage. To mitigate this bias
and improve generalizability, we collected all available open-source repositories
with ≥500 stars across 4 programming languages.

## Language coverage

FixtureDB covers four languages: Python, Java, JavaScript, and TypeScript.
Other languages such as Ruby (RSpec), Kotlin, Scala, Rust, C#, and Go are not included.

## Parametrized Tests — Critical Impact on Metrics

**IMPORTANT**: Parametrized test functions (e.g., pytest `@pytest.mark.parametrize`, JUnit `@ParameterizedTest`, Jest `test.each()`) are counted as **single test functions**, not multiplied by parameter set count.

**Impact on metrics**:
- **`reuse_count`**: A fixture used by a parametrized test with 10 parameter sets is counted as reuse=1 (not 10)
- **Fixture count**: Parametrized fixtures appear once, even if instantiated multiple times during test execution
- **Test-to-fixture ratio**: May under-represent fixture reuse in projects heavily using parametrized tests

**Why**: Test function definitions are the unit of analysis; parameter instantiation is runtime behavior not reflected in static AST.

**Mitigation for analysis**:
- Query `test_files` table to identify parametrized patterns (regex: `parametrize|ParameterizedTest|test.each`)
- For projects with heavy parametrization, multiply `reuse_count` estimates by observed average parameter count
- Combine with `raw_source` inspection for validation-critical research

**Language-specific notes**:
- **Python**: `pytest.mark.parametrize`, `@parameterized.expand`, manual parameter loops
- **Java**: `@ParameterizedTest`, `@MethodSource`, junit-params library
- **JavaScript/TypeScript**: `test.each()`, `describe.each()` (Jest/Vitest), manual loops

---

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

---

## Validation Status and Reliability

**IMPORTANT**: FixtureDB employs heuristic-based detection methods. This section documents validation completeness and reliability measures.

### Inter-Rater Reliability

**Status**: Not measured. This release does **not** include inter-rater reliability metrics (e.g., Cohen's kappa for fixture detection consistency across multiple annotators).

**Why**: Single-coder implementation focused on scale; comprehensive validation deferred to future releases.

**Impact**: Absolute confidence intervals unavailable; detection quality should be validated per-project for high-stakes research.

**Recommended action**: For critical research, manually inspect 50–100 fixtures per language to establish project-specific precision and recall.

### Language-Specific Validation Coverage

| Language | Validation Status | Notes |
|----------|---|---|
| **Python** | High confidence | Decorator-based fixture detection is unambiguous; mock detection validated across pytest, unittest |
| **Java** | High confidence | Annotation-based detection (@Before, @Test) is unambiguous; Mockito detection comprehensive |
| **JavaScript** | Medium confidence | Framework conventions vary (Jest, Mocha, Jasmine); helper function detection relies on naming patterns |
| **TypeScript** | Medium confidence | Same as JavaScript; type annotations do not improve fixture detection |
| **Go** | **INCOMPLETE** | Helper function detection validated but fixture categorization incomplete; awaiting formal validation study |

### Known Validation Gaps

1. **Go helpers**: Fixture/helper classification heuristics defined but not formally validated against codebase patterns
2. **False-positive rates**: Not quantified for any detector; estimated 5–15% for `num_objects_instantiated` (Python), ~10% for `num_external_calls`
3. **Cognitive complexity (non-Python)**: Formula-based approximation; not validated against SonarQube or other tools
4. **Parametrized test detection**: Patterns identified but edge cases (custom parametrization libraries) not exhaustively tested

---

## Heuristic Limitations

FixtureDB uses several **heuristic-based detection methods** that provide pragmatic detection at scale. These are documented below with their limitations.

### Constructor Call Detection (`num_objects_instantiated`)

**What it detects**: Regex pattern matching for `new ClassName(...)` in Java and Java-like syntax; capitalized-name pattern for Python `ClassName(...)` calls.

**Limitations**:
- **Python false positives**: Capital-case function calls (e.g., `Config(...)`, `Constants(...)`) are counted as constructor calls but may be factory functions
- **False negatives**: Indirect instantiation via factory methods (e.g., `builder.build()`) is not detected
- **Language-specific**: No detection for C#, Go, or Kotlin constructor patterns in this release
- **Dynamic instantiation**: `eval()`, `exec()`, reflection-based construction are not detected

**Usage recommendation**: Use `num_objects_instantiated` as a relative complexity indicator rather than absolute truth. Combine with `raw_source` inspection for high-stakes analysis.

### External Call Detection (`num_external_calls`)

**What it detects**: Regex patterns for I/O operations: `open()`, `.query()`, `.request()`, `subprocess`, database drivers, HTTP libraries.

**Limitations**:
- **Framework assumptions**: Detects common patterns (SQLite, MySQL, `requests`, `httpx`) but may miss project-specific database abstractions
- **Language variance**: JavaScript detection is less precise than Python (no built-in framework standardization)
- **False positives**: Calls with similar names (e.g., `my_query()` local method) may be counted
- **False negatives**: Implicit I/O via object methods (e.g., `logger.info()` to remote syslog) not detected

**Usage recommendation**: Use as a comparative metric within language groups. Validate with spot-checks on `raw_source`.

### Mock Detection Framework Completeness

**What it detects**: Mock usage via framework-specific patterns: `unittest.mock`, `pytest-mock`, Mockito, Jest, Sinon, Vitest.

**Limitations**:
- **Coverage**: Detects 40+ framework patterns; some niche frameworks (custom mocking libraries, older versions) not included
- **Test scope**: Only detects mocks *within* fixture definitions; does not count mocks in test bodies
- **Version sensitivity**: Assumes standard API signatures; unusual mock configurations may be missed

**Usage recommendation**: Treat `num_mocks == 0` as reliable (no mocks detected); use `num_mocks > 0` as "fixture contains at least one mock" rather than exact count.

### Cognitive Complexity Heuristic (Non-Python Languages)

**What it detects**: For Java, JavaScript, TypeScript: nesting-depth-weighted complexity via formula `CC × nesting_depth`.

**Limitations**:
- **Formula assumption**: Not validated against SonarQube's actual cognitive complexity implementation for these languages
- **Nesting definition**: Counts all block nesting including closures, not just control flow nesting (may over-estimate)
- **No validation data**: No inter-tool comparison available; treated as approximation

**Usage recommendation**: For non-Python languages, prefer `cyclomatic_complexity` as primary complexity metric. Use cognitive complexity only for relative comparisons within the same language.

---

## Known Future Improvements

1. **False-positive validation**: Manual sampling of 50+ fixtures per language to quantify error rates
2. **Framework detection coverage**: Extend mock framework patterns for Kotlin, Scala, C#
3. **Cognitive complexity calibration**: Validate non-Python formula against multiple tools
4. **Parametrized test handling**: Document interaction with parametrized tests and multiple fixture invocations
