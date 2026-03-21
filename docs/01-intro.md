# What is FixtureDB?

FixtureDB is a structured dataset of **test fixture definitions** extracted
from open-source software repositories on GitHub across five language variants:
Python, Java, JavaScript, TypeScript, and Go.

A *test fixture* is any code that prepares or tears down state before or after
a test runs. Each ecosystem has its own idiom:

| Language       | Fixture mechanisms covered |
|----------------|---------------------------|
| Python         | `@pytest.fixture` (all scopes), `setUp`/`tearDown`/`setUpClass`/`tearDownClass` (unittest) |
| Java           | `@Before`, `@BeforeClass` (JUnit 4), `@BeforeEach`, `@BeforeAll` (JUnit 5), and `After` counterparts |
| JavaScript     | `beforeEach`, `beforeAll`, `before`, `afterEach`, `afterAll` (Jest, Mocha, Jasmine, Vitest) |
| TypeScript     | Same as JavaScript |
| Go             | `TestMain`, helper functions called from ≥ 2 `TestXxx` functions in the same file |

For each fixture definition the dataset records structural metadata (size,
complexity, scope, type), and for each mock call found inside a fixture it
records the framework used and the mocked target identifier.

## Why this dataset matters

Prior empirical work on fixtures (TestHound, TestEvoHound) and on mocking
(Mostafa & Wang 2014, Spadini et al. 2017, Chaker et al. 2024) is exclusively
Java-based. FixtureDB is the first cross-language resource that treats the
fixture as its primary unit of analysis, enabling research that was previously
impossible.
