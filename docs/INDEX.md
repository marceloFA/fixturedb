# FixtureDB Documentation Index

This folder contains the complete documentation for FixtureDB, organized into sections.

## Getting Started (5 min read)

1. **[What is FixtureDB?](getting-started/01-intro.md)** — Overview, language coverage, and why this dataset matters
2. **[Quick Start](getting-started/06-setup.md)** — Installation and first steps
3. **[Running the Pipeline](getting-started/07-running.md)** — Command reference for all operations

## Documentation by Use Case

### **I want to analyze the data (CSV exports)**
- Start: [Using the Dataset for Research — CSV Exports](usage/09-usage.md#use-case-2-analyzing-csv-exports)
- Reference: [CSV Export Guide](data/14-csv-export-guide.md) — Full column documentation
- How-to: [CSV User Guide](data/15-csv-user-guide.md) — Import & analyze in Excel, pandas, R
- Language-specific data: [Language-Specific Fixture CSV](data/15-language-specific-csv-export.md)

### **I want to query the SQLite database**
- Start: [Using the Dataset for Research — SQLite](usage/09-usage.md#use-case-1-querying-the-sqlite-database)
- Schema: [Database Schema](architecture/03-database-schema.md)
- Advanced: [Data Pipeline Overview](architecture/18-data-pipeline-overview.md)

### **I want to verify or reproduce results**
- How-to: [Reproducing the Paper Corpus](usage/08-reproducing.md)
- Configuration: [Configuration Reference](architecture/10-configuration.md)
- Details: [Fixture Detection Logic](architecture/11-detection.md)

### **I want to understand limitations**
- Overview: [Limitations & Threats to Validity](reference/12-limitations.md)
- Testing: [Testing Strategy](reference/17-testing.md)

### **I want to understand metrics & calculations**
- Guide: [Metrics Reference & Calculation Methodology](architecture/20-metrics-reference.md) — External tools (Lizard, complexipy), custom implementations, reliability assessments, academic references


## All Documentation

### Getting Started
- [What is FixtureDB?](getting-started/01-intro.md)
- [Repository Structure](getting-started/02-repository-structure.md)
- [Setup & Requirements](getting-started/06-setup.md)
- [Running the Pipeline](getting-started/07-running.md)

### Architecture & Technical
- [Database Schema](architecture/03-database-schema.md)
- [Configuration Reference](architecture/10-configuration.md)
- [Fixture Detection Logic](architecture/11-detection.md)
- [Metrics Reference & Calculation Methodology](architecture/20-metrics-reference.md)
- [Data Pipeline Overview](architecture/18-data-pipeline-overview.md)

### Data Collection & Export
- [Data Collection Process](data/04-data-collection.md)
- [Storage & Scale](data/05-storage.md)
- [CSV Export Guide](data/14-csv-export-guide.md)
- [CSV User Guide](data/15-csv-user-guide.md)
- [Language-Specific CSV Export](data/15-language-specific-csv-export.md)

### Usage & Analysis
- [Reproducing Results](usage/08-reproducing.md)
- [Using the Dataset for Research](usage/09-usage.md)
- [Fixture Patterns Reference](usage/16-fixture-patterns-reference.md)

### Reference & Specs
- [Limitations & Validity](reference/12-limitations.md)
- [License](reference/13-license.md)
- [Testing Strategy](reference/17-testing.md)
- [Scientific References](reference/19-references.md)

## Quick Navigation

- **New to FixtureDB?** → [What is FixtureDB?](getting-started/01-intro.md)
- **How do I install?** → [Setup & Requirements](getting-started/06-setup.md)
- **How do I run it?** → [Running the Pipeline](getting-started/07-running.md)
- **Where's the data schema?** → [Database Schema](architecture/03-database-schema.md)
- **How do I analyze CSVs?** → [CSV User Guide](data/15-csv-user-guide.md)
- **How do I query SQLite?** → [Using the Dataset for Research](usage/09-usage.md)
- **What are the limitations?** → [Limitations & Validity](reference/12-limitations.md)

## Citation

FixtureDB: A Multi-Language Dataset of Test Fixture Definitions from Open-Source Software  
João Almeida, Andre Hora  
*ICSME 2026 — Tool Demonstration and Data Showcase Track*  

Dataset: [![DOI](https://zenodo.org/badge/DOI/TODO.svg)](https://doi.org/TODO)

## License

- **Code:** MIT License — See [LICENSE](../LICENSE) or [reference/13-license.md](reference/13-license.md)
- **Dataset:** CC BY 4.0 — See [reference/13-license.md](reference/13-license.md)
