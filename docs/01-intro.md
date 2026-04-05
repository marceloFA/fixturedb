# What is FixtureDB?

FixtureDB is a structured dataset of **test fixture definitions** extracted
from open-source software repositories on GitHub across four languages:
Python, Java, JavaScript, and TypeScript.

A *test fixture* is any code that prepares or tears down state before or after
a test runs. Each ecosystem has its own idiom:

| Language       | Fixture mechanisms covered |
|----------------|----------------------------|
| Python         | `@pytest.fixture` (all scopes), `setUp`/`tearDown`/`setUpClass`/`tearDownClass` (unittest) |
| Java           | `@Before`, `@BeforeClass` (JUnit 4), `@BeforeEach`, `@BeforeAll` (JUnit 5), and `After` counterparts |
| JavaScript     | `beforeEach`, `beforeAll`, `before`, `afterEach`, `afterAll` (Jest, Mocha, Jasmine, Vitest) |
| TypeScript     | Same as JavaScript |



For each fixture definition the dataset records structural metadata (size,
complexity, scope, type), and for each mock call found inside a fixture it
records the framework used and the mocked target identifier.

## Why this dataset matters

Prior empirical work on fixtures (TestHound, TestEvoHound) has been exclusively Java-based. Meanwhile, large-scale empirical studies of test suites (Hamster; Pan et al., 2025) and test mocking practices reveal widespread challenges with fixture design and mock usage across languages (Ahmed et al., 2025). FixtureDB is the first cross-language resource that treats the fixture as its primary unit of analysis, enabling research that was previously impossible and directly addressing the multi-language gap in testing empirics.

## Dataset Composition

FixtureDB comprises:

- **Public CSV exports** (`fixtures.csv`, `mock_usages.csv`, language-specific CSVs)  
  Contains **quantitative metrics only**: structure (LOC, complexity, scope, type), mock framework detection
- **Full SQLite database** (`fixturedb.sqlite`)  
  Includes the complete dataset plus internal infrastructure for reproducibility and future research
- **Repository metadata**: GitHub stars, forks, contributor count, creation date, domain classification

The **public CSV exports are the primary analysis format** for this paper. They contain all quantitative fixture characteristics needed for cross-language empirical studies. The SQLite database is provided for transparency and reproducibility, allowing researchers to query the complete dataset and verify extraction decisions.
