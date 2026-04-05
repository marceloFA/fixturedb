# FixtureDB Documentation Index

This folder contains the complete documentation for FixtureDB, split into dedicated sections.

## Quick links

1. **[What is FixtureDB?](01-intro.md)** — Overview, language coverage, and why this dataset matters
2. **[Repository Structure](02-repository-structure.md)** — Project layout and file organization
3. **[Database Schema](03-database-schema.md)** — Complete ERD and table specifications
4. **[Data Collection Process](04-data-collection.md)** — Five-phase pipeline walkthrough
5. **[Storage and Scale Estimates](05-storage.md)** — Disk usage and database growth
6. **[Setup and Requirements](06-setup.md)** — Installation and dependencies
7. **[Running the Pipeline](07-running.md)** — Command reference for all pipeline operations
8. **[Reproducing the Paper Corpus](08-reproducing.md)** — Exact replication with pinned commits
9. **[Using the Dataset for Research](09-usage.md)** — SQL query examples and data access patterns
10. **[Configuration Reference](10-configuration.md)** — All tunable parameters
11. **[Fixture Detection Logic](11-detection.md)** — Tree-sitter AST and mock detection
12. **[Limitations and Threats to Validity](12-limitations.md)** — Known constraints and validation status
13. **[License](13-license.md)** — MIT (code) and CC BY 4.0 (dataset)
14. **[CSV Export Guide](14-csv-export-guide.md)** — Full column documentation for all exported CSV files
15. **[CSV User Guide for Data Analysis](15-csv-user-guide.md)** — How to import and analyze CSVs in Excel, Python (pandas), and R
16. **[Language-Specific Fixture CSV Export](15-language-specific-csv-export.md)** — Python/Java/JavaScript fixtures for Zenodo
17. **[Testing Strategy & Execution](14-testing.md)** — Test suite overview, categories, and how to run
18. **[Data Pipeline Overview](16-data-pipeline-overview.md)** — System architecture and pipeline orchestration
19. **[Scientific References](19-references.md)** — Papers and works that inform FixtureDB methodology

## Technical Methodology

- **[Complexity Metrics Migration](COMPLEXITY_METRICS_MIGRATION.md)** — Phase 1 & 2 migration to Lizard and cognitive-complexity libraries
- **[Metrics Audit & External Tools](METRICS_AUDIT_AND_EXTERNAL_TOOLS.md)** — Comprehensive analysis of all quantitative metrics and available external tools
- **[Phase 3 Advanced Metrics](17-phase-3-advanced-metrics.md)** — max_nesting_depth, reuse_count, has_teardown_pair, num_contributors

## Getting started

- **New to the project?** Start with [What is FixtureDB?](01-intro.md)
- **Ready to install?** Go to [Setup and Requirements](06-setup.md)
- **Want to run it?** See [Running the Pipeline](07-running.md)
- **Need to query the data?** Check [Using the Dataset for Research](09-usage.md)
- **Want to run the test suite?** See [Testing Strategy & Execution](14-testing.md)

## Paper citation

FixtureDB: A Multi-Language Dataset of Test Fixture Definitions from Open-Source Software  
João Almeida, Andre Hora  
*ICSME 2026 — Tool Demonstration and Data Showcase Track*  
TODO: add DOI once published

Dataset archived on Zenodo at: **TODO: Zenodo DOI**
