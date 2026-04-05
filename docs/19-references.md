# References

This document lists scientific papers referenced in the FixtureDB project. These works inform our approach to fixture detection, test quality assessment, and empirical analysis of testing practices across multiple programming languages.

---

## Where These References Are Used

Our design decisions are grounded in empirical software engineering practice:

- **Repository Selection** ([docs/10-configuration.md](10-configuration.md), [docs/04-data-collection.md](04-data-collection.md)): The 500-star threshold for the `core` tier and 100-star minimum follow established conventions from large-scale empirical studies (Hamster; Pan et al., 2025).
- **Quality Filters** ([docs/10-configuration.md](10-configuration.md)): The MIN_TEST_FILES = 5 threshold is grounded in observations about test project characteristics (Ahmed et al., 2025).
- **Sampling Bias Analysis** ([docs/12-limitations.md](12-limitations.md)): We compare our methodology to Hamster's approach to managing star-based sampling bias.
- **Complexity Metrics** ([docs/COMPLEXITY_METRICS_MIGRATION.md](COMPLEXITY_METRICS_MIGRATION.md)): While cognitive complexity was designed for production code, we acknowledge recent work (Ouédraogo et al., 2025) on test-specific complexity metrics that suggests future refinements.
- **Empirical Methods** ([docs/METRICS_AUDIT_AND_EXTERNAL_TOOLS.md](METRICS_AUDIT_AND_EXTERNAL_TOOLS.md)): Large-scale studies (Pan et al., 2025; Ahmed et al., 2025) motivate our comprehensive quantitative characterization approach.

---

## Test Fixtures & Mocking Practices

### Challenges in Test Mocking

Ahmed, M., Islam Opu, M. N., Roy, C., Islam Suhi, S., & Chowdhury, S. (2025).  
**Exploring Challenges in Test Mocking: Developer Questions and Insights from StackOverflow**.  
*arXiv:2505.08300* [cs.SE]

> Investigates common challenges developers face when designing mock objects, based on real developer discussions from StackOverflow. Provides empirical evidence of mocking pain points that motivate the need for systematic fixture collection.

---

### Over-Mocking in Generated Tests

Hora, A., & Robbes, R. (2026).  
**Are Coding Agents Generating Over-Mocked Tests? An Empirical Study**.  
*Proceedings of the 2026 IEEE/ACM International Conference on Mining Software Repositories (MSR 2026)*.

> Examines whether AI-generated tests tend to mock more extensively than human developers, highlighting the gap between human and LLM testing practices. Relevant for understanding fixture usage patterns across different test authorship contexts.

---

## Code Evolution & Repository Analysis

### GitEvo: Evolution Analysis for Git Repositories

Hora, A. (2026).  
**GitEvo: Code Evolution Analysis for Git Repositories**.  
*Proceedings of the 2026 IEEE/ACM International Conference on Mining Software Repositories (MSR 2026)*.

> A tool and methodology for analyzing code evolution across Git repositories, providing infrastructure for longitudinal studies of software orga nization patterns and testing practices.

---

## Test Code Complexity Metrics

### Cognitive Complexity for Unit Tests

Ouédraogo, W. C., Li, Y., Dang, X., Zhou, X., Koyuncu, A., Klein, J., Lo, D., & Bissyandé, T. F. (2025).  
**Rethinking Cognitive Complexity for Unit Tests: Toward a Readability-Aware Metric Grounded in Developer Perception**.  
*Proceedings of the 2025 International Conference on Software Maintenance and Evolution (ICSME 2025), New Ideas and Emerging Results (NIER) Track*.  
*arXiv:2506.06764* [cs.SE]

> Proposes CCTR, a test-aware cognitive complexity metric tailored for unit tests that accounts for assertion density, annotation roles, and test composition patterns. Demonstrates that traditional complexity metrics (e.g., SonarSource's Cognitive Complexity) inadequately capture test code structure. Directly informs our fixture complexity analysis methodology.

---

### Removing Unnecessary Test Stubs

Li, M., & Fazzini, M. (2024).  
**Automatically Removing Unnecessary Stubbings from Test Suites**.  
*arXiv:2407.20924* [cs.SE]

> Addresses test fixture maintenance through automatic detection of over-stubbed test cases, providing techniques for identifying redundant mock setup code. Relevant to understanding fixture necessity and scope.

---

## Large-Scale Test Characterization

### Hamster: Developer-Written Test Characterization

Pan, R., Stennett, T., Pavuluri, R., Levin, N., Orso, A., & Sinha, S. (2025).  
**Hamster: A Large-Scale Study and Characterization of Developer-Written Tests**.  
*arXiv:2509.26204* [cs.SE]

> A comprehensive empirical study characterizing properties of developer-written unit tests at scale, including test structure, fixture usage, and assertion patterns. Provides comparative context for FixtureDB findings.

---

## General Software Engineering Empirical Studies

### Empirical Software Engineering Journal

Springer *Empirical Software Engineering* (EMSE) is a primary venue for empirical studies in software engineering. The following papers in this journal inform our empirical methodology:

- **DOI: 10.1007/s10664-023-10410-y** (2023)
  - See [docs/06-setup.md](docs/06-setup.md) for methodological details
  
- **DOI: 10.1007/s10664-018-9663-0** (2018)
  - Foundational empirical methods in software engineering

---

## Mining Software Repositories

### MSR Conference Series

The Mining Software Repositories (MSR) conference has been a primary venue for work on analyzing software repositories at scale.

- **MSR 2017** — Foundational work on repository analysis techniques
  - *See papers/msr2017b.pdf for details*

---

## Citation Guidance

If you use FixtureDB in your research, please cite the following paper:

```bibtex
@inproceedings{Almeida2026,
  author = {Almeida, Jo\u00e3o and Hora, Andre},
  title = {FixtureDB: A Multi-Language Dataset of Test Fixture Definitions from Open-Source Software},
  booktitle = {Proceedings of the 2026 IEEE/ACM International Conference on Software Maintenance and Evolution (ICSME 2026)},
  year = {2026},
  note = {Tool Demonstration and Data Showcase Track}
}
```

---

## Paper Collection

All referenced papers are available in the [papers/](../papers/) folder for offline access. Metadata and full citations are maintained in this document and in `.bib` format (when applicable).

