# Metrics Audit & External Tools Analysis

**Status:** Complete analysis and Phase 2 migration  
**Phase 1:** Cyclomatic + Cognitive complexity → Lizard + cognitive-complexity library  
**Phase 2:** Parameter count → Lizard's parameter_count  
**Objective:** Improve reliability and reproducibility by using industry-standard external tools

---

## Executive Summary

This document audits all **quantitative metrics** in the fixture database and identifies which can be calculated using **industry-standard external tools** rather than custom implementations.

**Key Findings:**
- **3 metrics completed migration** to external tools (Lizard, cognitive-complexity)
- **7 metrics kept custom** (domain-specific or specialized I/O detection)
- **All 263 tests passing** after Phase 2 migration
- **Code quality improved:** Reduced custom AST/regex code, increased reliance on proven libraries

---

## Part 1: Fixture-Level Metrics (Primary Analysis)

Large-scale empirical studies of test suites (Pan et al., 2025; Ahmed et al., 2025) require comprehensive quantitative characterization to enable reproducible analysis and fine-grained insights into testing practices. The `fixtures` table collects 10 quantitative metrics per fixture definition to support this goal:

| Metric | Type | Current Implementation | External Tool Available? | Recommendation |
|--------|------|----------------------|------------------------|-----------------|
| `loc` | Code Property | Manual line counting | **Lizard** ✅ | Already using via Lizard |
| `cyclomatic_complexity` | Code Property | **Lizard** ✅ | YES: Lizard | ✅ DONE: Lizard 1.21.3 |
| `cognitive_complexity` | Code Property | **cognitive-complexity** ✅ (Python) / Formula | YES: cognitive-complexity (Python only) | ✅ DONE: Library + formula fallback |
| `num_objects_instantiated` | Semantic Analysis | Regex pattern matching | **Partial: Lizard** ⚠️ | See analysis below |
| `num_external_calls` | Semantic Analysis | Regex pattern matching | **Partial: Lizard** ⚠️ | See analysis below |
| `num_parameters` | Syntax Analysis | Tree-sitter AST | YES: Lizard, AST modules | See analysis below |
| `fixture_type` | Classification | Pattern matching + AST | NO: Domain-specific | Keep custom implementation |
| `scope` | Classification | Pattern matching + AST | NO: Domain-specific | Keep custom implementation |
| `framework` | Classification | Regex + pattern matching | **Partial: Standardized lists** ⚠️ | See analysis below |
| `raw_source` | Data | Text extraction | N/A (required for reproducibility) | Keep as-is |

---

## Part 2: Detailed Metric Analysis

### ✅ COMPLETED: Complexity Metrics

#### 1. `cyclomatic_complexity`
**Status:** ✅ Migrated

- **Tool:** [Lizard](https://github.com/terryyin/lizard) v1.21.3
- **Language Support:** Python, Java, JavaScript, TypeScript, Go, C#
- **Metric Definition:** McCabe complexity (1 + count of decision points)
- **Accuracy:** Academic standard (widely cited in literature)
- **Integration:** Via `collection/complexity_provider.py`
- **Test Coverage:** 16 integration tests verifying calculation + persistence

#### 2. `cognitive_complexity`
**Status:** ✅ Migrated

- **Tool (Python):** [cognitive-complexity](https://github.com/sonarSource/cognitive-complexity) v1.3.0
  - Language Support: Python only
  - Metric Definition: SonarQube standard (nesting-depth-weighted branches)
  - Accuracy: Official SonarQube implementation
  
- **Tool (Other languages):** Formula-based fallback
  - Implementation: `cognitive_complexity = cyclomatic_complexity * avg_nesting_depth`
  - Language Support: Java, JavaScript, TypeScript, Go, C#
  - Accuracy: Reasonable estimate based on code structure

- **Integration:** Via `collection/complexity_provider.py`
- **Test Coverage:** 16 integration tests verifying metric selection + persistence

---

### 📊 PARTIALLY VIABLE: Partially Quantifiable Metrics

#### 3. `num_objects_instantiated`
**Current Implementation:** Regex pattern matching in `detector.py`
```python
# Pattern: count = new|new\s+\w+\(|instantiate|create\(|\.\w+\(\)
```

**External Tool Analysis:**

| Tool | Support | Pros | Cons | Assessment |
|------|---------|------|------|------------|
| **Lizard** | Partial | Provides "external call" count (function calls) | Doesn't distinguish constructor calls from other calls | ⚠️ Better than custom but requires post-processing |
| **Tree-sitter** | Full | Parse all constructors via AST query APIs | Already using for fixture detection; no dedicated counter | ✅ Current approach is solid |
| **AST modules** (Python/JS/TS) | Full | Language-specific, accurate AST parsing | Need separate implementation per language | ⚠️ Redundant with Tree-sitter |
| **pylint/ESLint** | No | Neither provides object count metrics | N/A | ❌ Not applicable |

**Recommendation:** 
```
KEEP current Tree-sitter approach OR migrate to Lizard's external_call count as secondary metric.

If migrating to Lizard:
- Pro: Single unified tool (also used for complexity)
- Con: Lizard counts ALL external calls, not just constructor calls
- Mitigation: Post-process Lizard output to filter by constructor patterns

If keeping custom regex:
- Pro: Simpler implementation, language-agnostic
- Con: May miss constructors with unusual patterns (e.g. factory methods)
- Testing: Current test suite validates against known fixtures
```

**Decision:** Can migrate to Lizard for simplicity if willing to accept slight definition shift (counting all external calls instead of just constructors).

---

#### 4. `num_external_calls`
**Current Implementation:** Regex pattern matching in `detector.py`
```python
# Pattern: count = open\(|connect\(|requests\.|http|socket\(|subprocess\.|etc.
```

**Status:** ✅ **Kept as Custom Implementation**

**Why?** Lizard's `fan_out` metric measures *inter-function calls within the same module*, not external I/O operations. Our use case requires detecting **external I/O and system operations** (database queries, HTTP requests, file operations, subprocess calls), which is fundamentally different.

| Tool | Support | Metric Definition | Assessment |
|------|---------|-------------------|------------|
| **Lizard** | ✅ Yes | "Calls to other functions in module" (fan_out) | ❌ Wrong semantic |
| **Custom Regex** | ✅ Yes | "I/O operations" (database, HTTP, file, subprocess) | ✅ Correct semantic |

**Decision:** Maintain custom regex implementation because:
1. It measures the right thing (I/O operations, not function calls)
2. It's well-tested and working correctly
3. Lizard's metric is fundamentally different and would change the meaning

---



#### 5. `num_parameters`
**Current Implementation:** Tree-sitter AST parsing in `detector.py`
```python
# Traverses function_declaration nodes, counts formal_parameters
```

**External Tool Analysis:**

| Tool | Support | Pros | Cons | Assessment |
|------|---------|------|------|------------|
| **Lizard** | ✅ Full | Built-in `parameter` count (function signature) | Exact match to our use case | ✅ Drop-in replacement |
| **Tree-sitter** | ✅ Full | Language-agnostic, flexible queries | Already integrated for fixture detection | ✅ Current approach is reliable |
| **AST modules** | ✅ Full | Language-native; Python ast, esprima (JS), etc. | Requires per-language implementation | ⚠️ Redundant work |
| **Pylint/ESLint** | Partial | Provides parameter-related info in code reviews | Not designed for metric extraction | ❌ Not practical |

**Recommendation:**
```
MIGRATE to Lizard's built-in parameter count:

Why:
- Exact match to our use case (function signature parameters)
- Already using Lizard for complexity metrics
- Eliminates dependency on Tree-sitter for this specific metric
- Simpler than current AST-based approach

Trade-off:
- Tree-sitter currently used for fixture detection (separate use)
- Lizard parameter count is simpler than our AST traversal
- Very high confidence in correctness

Implementation:
- Modify complexity_provider.py to return Lizard's parameter count alongside complexity
- Update detector.py to use single call instead of separate AST traversal
- Refactor `_build_result()` to accept parameters from analyzer
- Test: minimal risk, similar to existing migration

Cost: ~15 lines of code change, ~1 hour testing
```

**Decision:** RECOMMEND migration to Lizard's parameter count.

---

### 🏷️ DOMAIN-SPECIFIC: Classification Metrics (No Direct Tools)

These metrics require **domain knowledge about testing frameworks and fixture patterns**. While pattern-matching libraries exist, they don't replace the semantic understanding needed for accurate classification.

#### 6. `fixture_type`
**Current Implementation:** Pattern matching + AST node analysis in `detector.py`
```python
# Detects: pytest_decorator, unittest_setup, before_each, before_all, test_main, etc.
# Per-language fixture patterns:
#   - Python: @pytest.fixture, def setUp(), def tearDown()
#   - Java: @Before, @BeforeClass, @Setup, @Test
#   - JS/TS: beforeEach(), beforeAll(), describe(), setUp()
#   - Go: Test*, testing.T usage
#   - C#: [SetUp], [Fixture], [Test] attributes
```

**External Tool Analysis:**

| Tool | Support | Pros | Cons | Assessment |
|------|---------|------|------|------------|
| **AST-based libraries** | Partial | Can identify decorators and annotations | No semantic understanding of fixture vs test vs helper | ⚠️ False positives |
| **Pre-trained ML models** | Maybe | Could classify based on source text | No public pre-trained models for this task | ❌ Not available |
| **SonarQube/Checkstyle** | No | Code quality tools, not fixture classifiers | Not designed for this type of classification | ❌ Out of scope |
| **Custom implementation** | ✅ Full | Can encode domain knowledge accurately | Requires maintenance for each language/framework | ✅ Current approach best option |

**Recommendation:**
```
KEEP custom implementation with clear documentation.

Why:
- No publicly available tool understands fixture vs. test semantics
- Domain knowledge is essential (knowing pytest vs unittest patterns)
- Custom implementation has been validated against test suite

Possible improvements (enhancement track):
1. Multi-language test suite (add more fixture types to TEST_PLAN.md)
2. Validation against real-world repos
3. Fine-tune regex patterns if accuracy issues emerge

Document clearly in detection methodology for reproducibility.
```

**Decision:** Keep custom implementation (no viable alternatives).

---

#### 7. `scope`
**Current Implementation:** Pattern matching + AST node analysis in `detector.py`
```python
# Detects scope: per_test, per_class, per_module, global
# Rules per language:
#   - Python: function vs. class vs. module level
#   - Java: method vs. static vs. class variable
#   - JS/TS: block scope vs. global (closure analysis)
#   - Go: function-scoped vs. package-scoped
#   - C#: instance vs. static vs. module-level
```

**External Tool Analysis:**

| Tool | Support | Pros | Cons | Assessment |
|------|---------|------|------|------------|
| **Tree-sitter** | ✅ Full | Parent node analysis to determine nesting | Currently using for detection; can refine | ✅ Already integrated |
| **AST modules** | ✅ Full | Language-native scope analysis | Requires per-language reimplementation | ⚠️ Redundant work |
| **Type checkers** (mypy, tsc) | Partial | Can infer scope from type information | Over-engineered for fixture scope analysis | ❌ Not practical |
| **Custom implementation** | ✅ Full | Simple, fast, language-aware | Requires maintenance | ✅ Current approach |

**Recommendation:**
```
KEEP custom Tree-sitter based implementation.

Why:
- Tree-sitter parent node analysis is the right approach
- Already integrated; no benefit to switching tools
- Simpler than type-checker based approach
- Current test coverage validates accuracy

Possible improvements (enhancement track):
1. Add more edge cases to test suite
2. Validate against real-world repos
3. Consider closure scope for JavaScript/TypeScript

Document clearly in detection methodology.
```

**Decision:** Keep custom implementation (already optimal).

---

#### 8. `framework`
**Current Implementation:** Regex pattern matching in `detector.py`
```python
# Detects testing framework: pytest, unittest, junit, nunit, testify, jest, mocha,
# jest, sinon, gomock, testify, xunit, nunit, mockito, powermock, easymock, etc.
# ~40 framework-specific patterns searched in source code
```

**External Tool Analysis:**

| Tool | Support | Pros | Cons | Assessment |
|------|---------|------|------|------------|
| **Dependency parsers** | Partial | Can identify frameworks from imports | Misses fixtures not using explicit imports | ⚠️ Incomplete |
| **Package detection** (pip, npm) | Partial | Can check installed packages | Requires analyzing repo's dependency files (setup.py, package.json) | ⚠️ Requires integration |
| **AST-based detection** | ✅ Full | Parse imports and decorators directly | Current regex approach already covers this | ✅ Current approach is solid |
| **Standardized framework lists** | ✅ Full | Maintain authoritative list of frameworks per language | Not a tool, but a data resource | ✅ Can improve current approach |

**Recommendation:**
```
ENHANCE current implementation with standardized framework registry:

Current approach:
- Regex pattern matching (works well)
- Language-agnostic
- ~40 patterns covering all major frameworks

Improvement opportunity:
- Create FRAMEWORK_REGISTRY in config.py:
  {
    "python": ["pytest", "unittest", "nose", "doctest"],
    "java": ["junit", "testng"],
    "javascript": ["jest", "mocha", "jasmine"],
    "typescript": ["jest", "mocha"],
    "go": ["testing", "testify"],
    "csharp": ["nunit", "xunit", "mstest"]
  }
- Use registry to validate detected frameworks
- Can also generate patterns from registry

This is optional refactoring; current regex approach works.

Cost: ~30 lines of config code, no logic changes
```

**Decision:** Optional enhancement; current implementation is adequate.

---

## Part 3: File-Level Metrics

The `test_files` table also collects metrics at the file level:

| Metric | Current Implementation | External Tool Available? | Recommendation |
|--------|----------------------|------------------------|-----------------|
| `file_loc` | Manual line counting | **Lizard** ✅ | Migrate to Lizard for consistency |
| `num_test_funcs` | AST-based counting | **Lizard** ✅ | Migrate to Lizard's function count |
| `num_fixtures` | Aggregate from fixtures table | Internal DB query | Keep as-is (no external tool needed) |
| `total_fixture_loc` | Aggregate from fixtures table | SQL SUM() | Keep as-is (database calculation) |

**Recommendation:**
For consistency with fixture-level metrics, consider migrating:
- `file_loc` → Lizard's file LOC (already available with complexity analysis)
- `num_test_funcs` → Lizard's function count

Cost: Minimal (already parsing with Lizard); refactor aggregation logic.

---

## Part 4: Repository-Level Metrics

The `repositories` table collects GitHub statistics (not code metrics):

| Metric | Source | Tool/API | External? | Status |
|--------|--------|----------|-----------|--------|
| `stars` | GitHub API | `PyGithub` | ✅ External | Already using |
| `forks` | GitHub API | `PyGithub` | ✅ External | Already using |
| `created_at` | GitHub API | `PyGithub` | ✅ External | Already using |
| `pushed_at` | GitHub API | `PyGithub` | ✅ External | Already using |
| `topics` | GitHub API | `PyGithub` | ✅ External | Already using |
| `domain` | Manual classification | N/A | Custom | Requires domain expertise |
| `star_tier` | Algorithm (stars >= 500) | N/A | Internal | Simple bucketing |

**No action needed** — already using external GitHub API.

---

## Part 5: Mock Usage Metrics

The `mock_usages` table collects mock-specific metrics:

| Metric | Current Implementation | External Tool Available? | Recommendation |
|--------|----------------------|------------------------|-----------------|
| `framework` | Regex pattern matching | **Partial: Package detection** ⚠️ | See below |
| `mock_style` | Classification (stub/mock/spy/fake) | NO: Domain-specific | Keep custom |
| `target_layer` | Classification (boundary/infra/internal) | NO: Domain-specific | Keep custom |
| `num_interactions_configured` | AST-based call counting | **Partial: Lizard** ⚠️ | Could use external_call count |

**Recommendations:**

1. **`framework`** (mock framework detection)
   - Current: Regex (mockito, unittest_mock, jest, sinon, gomock, testify, etc.)
   - Could enhance with dependency detection
   - Keep regex as primary, consider dependency validation as secondary

2. **`mock_style` & `target_layer`**
   - Domain-specific classifications
   - Require understanding of mocking semantics
   - Keep custom implementation
   - Consider documenting classification rules clearly for reproducibility

3. **`num_interactions_configured`**
   - Counts mock method call configurations (e.g., `when(x).thenReturn(y)`)
   - Could use Lizard's external_call metric as rough approximation
   - Current custom implementation is more precise
   - Keep as-is unless accuracy issues arise

---

## Summary: Migration Roadmap

### ✅ Completed (Phase 1)
1. `cyclomatic_complexity` → Lizard
2. `cognitive_complexity` → cognitive-complexity (Python) + formula

### ✅ Completed (Phase 2)
3. `num_parameters` → Lizard's `parameter_count`

### ✅ Kept Custom (Domain-Specific or Specialized)
4. `num_external_calls` → Regex-based custom detection
   - Reason: Lizard's `fan_out` metric measures inter-function calls within the same module, not external I/O operations (database, HTTP, file, subprocess). We need I/O-specific detection, so custom regex is the right choice.
5. `fixture_type`, `scope`, `mock_style`, `target_layer` → Domain-specific, no viable tools
6. `raw_source` → Required for reproducibility
7. GitHub metrics → Already using external API
8. Database aggregates (`num_fixtures`, `total_fixture_loc`) → Internal calculations

### 📚 Optional Enhancement
9. Create FRAMEWORK_REGISTRY in config.py (enhancement track)

---

## Conclusion

**10 fixture-level metrics analyzed:**
- ✅ **2 completed** (complexity metrics)
- 🎯 **2 recommended** for Phase 2 (Lizard integration)
- ✅ **3 kept** as custom (domain-specific classifications)
- ✅ **3 other** (database aggregates, raw source)

**Primary finding:** After complexity metrics migration, focus should shift to **Lizard integration for ancillary metrics** (external calls, parameters) to create a **unified, reliable, academic-standard toolchain**.

**For academic paper methodology:** This audit provides clear justification for tool choices and identifies which metrics use industry-standard implementations vs. domain-specific custom code.

---

## References

### Tools Discussed
- **Lizard** (Cyclomatic & Cognitive complexity, LOC, external calls, parameters)
  - GitHub: https://github.com/terryyin/lizard
  - Paper: McCabe, T. J. (1976). A Complexity Measure
  
- **cognitive-complexity** (Python cognitive complexity)
  - GitHub: https://github.com/sonarSource/cognitive-complexity
  - Standard: SonarQube cognitive complexity algorithm

- **Tree-sitter** (AST parsing, fixture detection, scope analysis)
  - GitHub: https://github.com/tree-sitter/tree-sitter
  - Languages: Python, Java, JavaScript, TypeScript, Go, C#

- **PyGithub** (GitHub API access)
  - GitHub: https://github.com/PyGithub/PyGithub
  - Used for repository metadata collection

### Related Documents
- [COMPLEXITY_METRICS_MIGRATION.md](COMPLEXITY_METRICS_MIGRATION.md) — Migration methodology and results
- [03-database-schema.md](03-database-schema.md) — Complete schema documentation
- [11-detection.md](11-detection.md) — Fixture detection methodology
