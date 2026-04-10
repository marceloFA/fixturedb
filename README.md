# FixtureDB — Corpus Collection Pipeline

[![Tests & Coverage](https://github.com/joao-almeida/icsme-nier-2026/actions/workflows/coverage.yml/badge.svg)](https://github.com/joao-almeida/icsme-nier-2026/actions/workflows/coverage.yml)
![Coverage](./.github/coverage.svg)

Replication package for the paper:

> **FixtureDB: A Multi-Language Dataset of Test Fixture Definitions from Open-Source Software**  
> João Almeida, Andre Hora  
> *ICSME 2026 — Tool Demonstration and Data Showcase Track*  
> TODO: add DOI once published

This repository contains the extraction pipeline that builds FixtureDB.
The dataset itself (SQLite database + CSV exports) is archived separately
on Zenodo at **TODO: Zenodo DOI**.

## Dataset Collection Details

| Property | Value |
|----------|-------|
| **Collection Period** | April 1–2, 2026 |
| **GitHub API Version** | v3 REST API |
| **Tree-sitter Grammar** | v0.21.0+ (Python, Java, JavaScript, TypeScript) |
| **Complexity Tool** | Lizard v1.21.0+ |
| **Cognitive Complexity** | complexipy v5.0.0+ |
| **Python Version** | 3.8+ (see requirements.txt) |

For exact tool versions and reproducibility details, see [docs/04-data-collection.md](docs/04-data-collection.md).

---

## Documentation

Complete documentation has been organized into dedicated files in the [docs/](docs/) folder:

| Document | Purpose |
|----------|---------|
| [docs/INDEX.md](docs/INDEX.md) | **Start here** — overview and quick navigation |
| [docs/01-intro.md](docs/01-intro.md) | What is FixtureDB and why it matters |
| [docs/02-repository-structure.md](docs/02-repository-structure.md) | Project layout and organization |
| [docs/03-database-schema.md](docs/03-database-schema.md) | Complete ERD and table specifications |
| [docs/04-data-collection.md](docs/04-data-collection.md) | Five-phase pipeline walkthrough |
| [docs/05-storage.md](docs/05-storage.md) | Disk usage and database growth |
| [docs/06-setup.md](docs/06-setup.md) | Installation and dependencies |
| [docs/07-running.md](docs/07-running.md) | Command reference for pipeline operations |
| [docs/08-reproducing.md](docs/08-reproducing.md) | Exact corpus replication with pinned commits |
| [docs/09-usage.md](docs/09-usage.md) | SQL query examples and data access |
| [docs/10-configuration.md](docs/10-configuration.md) | All tunable parameters |
| [docs/11-detection.md](docs/11-detection.md) | Tree-sitter AST and mock detection |
| [docs/12-limitations.md](docs/12-limitations.md) | Known constraints and validation status |
| [docs/13-license.md](docs/13-license.md) | MIT (code) and CC BY 4.0 (dataset) |
| [docs/14-criteria-tracking.md](docs/14-criteria-tracking.md) | Research question tracking |
| [docs/15-csv-user-guide.md](docs/15-csv-user-guide.md) | CSV exports for non-SQL users |
| [docs/18-example-analyses.md](docs/18-example-analyses.md) | 5 research questions with findings |

## Quick start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up your GitHub token
cp .env.example .env
# Edit .env and add your GITHUB_TOKEN

# Initialize the database
python pipeline.py init

# Run the full pipeline (all languages)
python pipeline.py run
```

For detailed setup, see [docs/06-setup.md](docs/06-setup.md).

## What is FixtureDB?

FixtureDB is a structured dataset of **test fixture definitions** extracted from
open-source software repositories on GitHub across **Python, Java, JavaScript,
and TypeScript**.

A *test fixture* is any code that prepares or tears down state before or after a test runs.
For each fixture, the dataset records structural metadata (size, complexity, scope, type)
and mock framework usage.

**Why it matters:** Prior empirical work on fixtures is exclusively Java-based. FixtureDB is the
first cross-language resource treating the fixture as its primary unit of analysis.

See [docs/01-intro.md](docs/01-intro.md) for the full overview.

### Data Quality & Testing

FixtureDB focuses exclusively on **quantitative, objective aspects** of test fixtures:

- **Framework Detection**: Syntactically unambiguous markers only (decorators, annotations, attributes)
  - Python: `@pytest.fixture`, `setUp()`/`tearDown()` methods
  - Java: `@Before`/`@After` annotations
  - JavaScript/TypeScript: Mocha/Jest `beforeEach()`/`afterEach()` and related patterns

- **Structural Metrics**: Lines of code, cyclomatic complexity, parameter counts, fixture type/scope
- **Mock Framework Usage**: Detection of mock object patterns within fixture code

**CSV exports** contain quantitative metrics. The SQLite database includes additional internal infrastructure for reproducibility and future research.

All fixture detectors include **comprehensive unit tests** ([tests/test_framework_detection.py](tests/test_framework_detection.py)) verifying:
- Correct framework identification across supported languages
- AST-based detection accuracy
- Cross-language consistency

See [docs/11-detection.md](docs/11-detection.md) for technical details on detection algorithms.

---

## Exploratory Data Analysis (EDA)

The following visualizations provide an overview of the FixtureDB corpus:

### Corpus Composition

**Repository Distribution and Pipeline Status**

![Repositories by Tier](docs/plots/01a_corpus_by_tier.png)

![Pipeline Status](docs/plots/01b_pipeline_status.png)

### Repository Timeline & Activity

**Creation Timeline and Activity Patterns**

![Repository Creation Timeline](docs/plots/02a_creation_timeline.png)

![Repository Recent Activity](docs/plots/02b_activity_recency.png)

### Fixture Overview

**Fixture Distribution and Scope Patterns**

![Fixture Distribution per Repository](docs/plots/03a_fixtures_per_repo.png)

![Fixture Scope Distribution](docs/plots/03b_fixture_scope.png)

### Mocking Practices

**Mock Usage and Framework Diversity**

![Mock Adoption Rate](docs/plots/04a_mock_adoption.png)

![Mocking Framework Usage](docs/plots/04b_framework_diversity.png)

### Fixture Complexity Analysis

**Nesting, Reuse, and Complexity Patterns**

![Fixture Nesting Depth Distribution](docs/plots/05a_nesting_depth.png)

![Nesting vs Complexity Correlation](docs/plots/05b_nesting_complexity_correlation.png)

![Fixture Reuse Patterns](docs/plots/05c_fixture_reuse_distribution.png)

![Reuse vs Complexity Correlation](docs/plots/05d_reuse_complexity_correlation.png)

![Teardown Adoption Rate](docs/plots/05e_teardown_adoption.png)