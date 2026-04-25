# Fixture Patterns Reference

**Document Purpose:** Comprehensive catalog of all fixture types detected across all supported languages and frameworks. Provides examples, patterns, and classification criteria for fixture detection in the FixtureDB.

**Status:** Complete reference with BDD and Spring enhancements  

**Languages:** Python, Java, JavaScript, TypeScript, C#

---

## Table of Contents

1. [Quick Lookup](#quick-lookup)
2. [Python Fixtures](#python-fixtures)
3. [Java Fixtures](#java-fixtures)
4. [JavaScript/TypeScript Fixtures](#javascripttypescript-fixtures)
5. [C# Fixtures](#c-fixtures)
6. [BDD Frameworks](#bdd-frameworks)
7. [Spring Framework](#spring-framework)
8. [Fixture Relationships](#fixture-relationships)
9. [Detection Methodology](#detection-methodology)

---

## Quick Lookup

| Framework | Language | Fixture Type | Pattern | Scope |
|-----------|----------|--------------|---------|-------|
| pytest | Python | pytest_decorator | `@pytest.fixture` | per_test, per_class, per_module, global |
| unittest | Python | unittest_setup | `def setUp/tearDown/setUpClass/tearDownClass` | per_test, per_class, per_module |
| nose | Python | nose_fixture | `def setup/teardown/setup_module/teardown_module` | per_test, per_module |
| behave | Python | behave_given/when/then/step | `@given/@when/@then/@step(...)` | per_test |
| JUnit 3 | Java | junit3_setup/junit3_teardown | `def setUp()/tearDown()` | per_test |
| JUnit 4 | Java | junit4_before/after/before_class/after_class | `@Before/@After/@BeforeClass/@AfterClass` | per_test, per_class |
| JUnit 5 | Java | junit5_before_each/after_each/before_all/after_all | `@BeforeEach/@AfterEach/@BeforeAll/@AfterAll` | per_test, per_class |
| TestNG | Java | testng_before_method/after_method/before_class/after_class | `@BeforeMethod/@AfterMethod/@BeforeClass/@AfterClass` | per_test, per_class |
| Cucumber | Java | cucumber_given/when/then/and/but | `@Given/@When/@Then/@And/@But(...)` | per_test |
| Spring | Java | spring_bean/spring_test_config | `@Bean/@TestConfiguration` | per_class |
| Jest/Mocha/Jasmine/Vitest | JavaScript | before_each/after_each/before_all/after_all | `beforeEach/afterEach/beforeAll/afterAll(...)` | per_test, per_class |
| Mocha | JavaScript | mocha_before/mocha_after | `before/after(...)` | per_test |
| AVA | JavaScript/TypeScript | ava_before/after/serial_before/serial_after | `test.before/.after/.serial.before/.serial.after(...)` | per_test, per_class |
| NUnit | C# | nunit_setup/nunit_teardown | `[SetUp]/[TearDown]` | per_test |
| xUnit | C# | xunit_constructor/xunit_dispose | `Constructor/IDisposable` | per_test, per_class |

---

## Python Fixtures

### pytest Fixtures

**Type:** `pytest_decorator`  
**Framework:** pytest  
**Pattern:** Decorated function with `@pytest.fixture`

```python
# Basic fixture
@pytest.fixture
def my_fixture():
    """Setup code here"""
    yield value
    """Teardown code here"""

# Fixture with scope
@pytest.fixture(scope="module")
def db_connection():
    conn = connect()
    yield conn
    conn.close()

# Parametrized fixture
@pytest.fixture(params=[1, 2, 3])
def param_fixture(request):
    return request.param
```

**Scope Mapping:**
- `scope="function"` → per_test
- `scope="class"` → per_class
- `scope="module"` → per_module
- `scope="session"` → global
- Default (no args) → per_test

**Detection Logic:**
1. Find `decorated_definition` node
2. Check for `fixture` keyword AND `pytest` keyword in decorator text
3. Extract scope from `scope="..."` parameter if present

---

### unittest Fixtures

**Type:** `unittest_setup`  
**Framework:** unittest  
**Pattern:** Method names: `setUp`, `tearDown`, `setUpClass`, `tearDownClass`, `setUpModule`, `tearDownModule`

```python
class MyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Class-level setup (runs once before all tests)"""
        cls.resource = setup_expensive_resource()
    
    def setUp(self):
        """Per-test setup (runs before each test)"""
        self.value = 42
    
    def tearDown(self):
        """Per-test cleanup (runs after each test)"""
        self.value = None
    
    def test_something(self):
        assert self.value == 42

def setUpModule():
    """Module-level setup (runs once at module start)"""
    global module_state
    module_state = initialize()
```

**Scope Mapping:**
- `setUp/tearDown` → per_test
- `setUpClass/tearDownClass` → per_class
- `setUpModule/tearDownModule` → per_module

**Detection Logic:**
1. Find `function_definition` nodes
2. Extract function name from `name` field
3. Check if name matches `setUp*` or `tearDown*` patterns

---

### nose Fixtures

**Type:** `nose_fixture`  
**Framework:** nose, nose2  
**Pattern:** Module-level or class-level functions: `setup`, `teardown`, `setup_module`, `teardown_module`, `setup_package`, `teardown_package`

```python
# Module-level setup/teardown
def setup_module():
    """Run once at module start"""
    global state
    state = init()

def teardown_module():
    """Run once at module end"""
    cleanup(state)

# Package-level setup/teardown
def setup_package():
    """Run once at package start"""
    pass

def teardown_package():
    """Run once at package end"""
    pass

# Class-level setup/teardown
class TestMyClass:
    def setup(self):
        """Per-test setup"""
        pass
    
    def teardown(self):
        """Per-test cleanup"""
        pass
    
    def test_something(self):
        pass
```

**Scope Mapping:**
- `setup/teardown` → per_test
- `setup_module/teardown_module` → per_module
- `setup_package/teardown_package` → per_module

**Detection Logic:**
1. Find `function_definition` nodes
2. Extract function name
3. Check if name matches `setup*` or `teardown*` patterns

---

### Behave (BDD) Fixtures

**Type:** `behave_given`, `behave_when`, `behave_then`, `behave_step`  
**Framework:** behave  
**Pattern:** Function decorated with `@given(...)`, `@when(...)`, `@then(...)`, `@step(...)`

```python
from behave import given, when, then, step

@given('a user is logged in')
def step_given_user_logged_in(context):
    context.user = User.login('john', 'password')
    assert context.user is not None

@when('the user clicks the logout button')
def step_when_logout(context):
    context.user.logout()

@then('the user is redirected to login page')
def step_then_redirected(context):
    assert context.current_page == 'login'

@step('the system shows an error message')
def step_system_error(context):
    assert context.error_visible
```

**Scope:** Always per_test (each step is part of a scenario execution)

**Detection Logic:**
1. Find `decorated_definition` with `function_definition`
2. Check for decorator matching `@(given|when|then|step)\s*\(`
3. Map to appropriate fixture_type

---

## Java Fixtures

### JUnit 3 (Legacy)

**Type:** `junit3_setup`, `junit3_teardown`  
**Framework:** JUnit 3  
**Pattern:** Method names in TestCase subclass: `setUp()`, `tearDown()`

```java
import junit.framework.TestCase;

public class MyTest extends TestCase {
    private Resource resource;
    
    /**
     * Called before each test method (per_test scope)
     */
    public void setUp() throws Exception {
        super.setUp();
        resource = new Resource();
    }
    
    /**
     * Called after each test method (per_test scope)
     */
    public void tearDown() throws Exception {
        resource.close();
        super.tearDown();
    }
    
    public void testSomething() {
        assertNotNull(resource);
    }
}
```

**Scope:** Always per_test

**Detection Logic:**
1. Find `method_declaration` nodes
2. Extract method name
3. If name is `setUp` or `tearDown`, match as junit3

---

### JUnit 4

**Type:** `junit4_before`, `junit4_after`, `junit4_before_class`, `junit4_after_class`  
**Framework:** JUnit 4  
**Pattern:** Methods annotated with `@Before`, `@After`, `@BeforeClass`, `@AfterClass`

```java
import org.junit.Before;
import org.junit.After;
import org.junit.BeforeClass;
import org.junit.AfterClass;
import org.junit.Test;

public class MyTest {
    private static Resource sharedResource;
    private Resource perTestResource;
    
    @BeforeClass
    public static void setupClass() {
        // Runs once before all tests in this class
        sharedResource = new Resource();
    }
    
    @Before
    public void setup() throws Exception {
        // Runs before each test method
        perTestResource = new Resource();
    }
    
    @After
    public void teardown() throws Exception {
        // Runs after each test method
        perTestResource.close();
    }
    
    @AfterClass
    public static void teardownClass() {
        // Runs once after all tests in this class
        sharedResource.close();
    }
    
    @Test
    public void testSomething() {
        assertNotNull(perTestResource);
    }
}
```

**Scope Mapping:**
- `@Before` → per_test
- `@After` → per_test
- `@BeforeClass` → per_class
- `@AfterClass` → per_class

**Detection Logic:**
1. Find `method_declaration` nodes
2. Scan for `modifiers` child with annotations
3. Extract annotation name (`@Before`, etc.)
4. Look up in JUNIT_FIXTURE_ANNOTATIONS dict

---

### JUnit 5 (Jupiter)

**Type:** `junit5_before_each`, `junit5_after_each`, `junit5_before_all`, `junit5_after_all`  
**Framework:** JUnit 5  
**Pattern:** Methods annotated with `@BeforeEach`, `@AfterEach`, `@BeforeAll`, `@AfterAll`

```java
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;

public class MyTest {
    @BeforeAll
    static void setupOnce() {
        // Runs once before all tests
        System.out.println("Suite setup");
    }
    
    @BeforeEach
    void setUp() {
        // Runs before each test
        System.out.println("Test setup");
    }
    
    @AfterEach
    void tearDown() {
        // Runs after each test
        System.out.println("Test teardown");
    }
    
    @AfterAll
    static void tearDownOnce() {
        // Runs once after all tests
        System.out.println("Suite teardown");
    }
    
    @Test
    void testSomething() {
        // test code
    }
}
```

**Scope Mapping:**
- `@BeforeEach` → per_test
- `@AfterEach` → per_test
- `@BeforeAll` → per_class
- `@AfterAll` → per_class

---

### TestNG

**Type:** `testng_before_method`, `testng_after_method`, `testng_before_class`, `testng_after_class`, `testng_data_provider`  
**Framework:** TestNG  
**Pattern:** Methods annotated with TestNG annotations

```java
import org.testng.annotations.BeforeMethod;
import org.testng.annotations.AfterMethod;
import org.testng.annotations.BeforeClass;
import org.testng.annotations.AfterClass;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

public class MyTest {
    @BeforeClass
    public void setupClass() {
        // Class-level setup
    }
    
    @BeforeMethod
    public void setup() {
        // Per-test setup
    }
    
    @DataProvider(name = "testData")
    public Object[][] dataProvider() {
        // Returns data for parametrized tests
        return new Object[][] {
            {1, 2},
            {3, 4}
        };
    }
    
    @Test(dataProvider = "testData")
    public void testWithData(int a, int b) {
        // Test using data from provider
    }
    
    @AfterMethod
    public void teardown() {
        // Per-test cleanup
    }
    
    @AfterClass
    public void teardownClass() {
        // Class-level cleanup
    }
}
```

**Scope Mapping:**
- `@BeforeMethod` → per_test
- `@AfterMethod` → per_test
- `@BeforeClass` → per_class
- `@AfterClass` → per_class
- `@DataProvider` → per_test

---

### Cucumber (BDD)

**Type:** `cucumber_given`, `cucumber_when`, `cucumber_then`, `cucumber_and`, `cucumber_but`  
**Framework:** Cucumber (for Java)  
**Pattern:** Methods annotated with `@Given(...)`, `@When(...)`, `@Then(...)`

```java
import io.cucumber.java.en.Given;
import io.cucumber.java.en.When;
import io.cucumber.java.en.Then;

public class LoginStepDefinitions {
    private User user;
    private Application app;
    
    @Given("a user with username {string} and password {string}")
    public void givenUser(String username, String password) {
        user = new User(username, password);
    }
    
    @When("the user logs in")
    public void whenUserLogsIn() {
        app.login(user.username, user.password);
    }
    
    @Then("the user should be authenticated")
    public void thenUserAuthenticated() {
        assert app.isAuthenticated(user);
    }
    
    @And("the dashboard should be displayed")
    public void andDashboardDisplayed() {
        assert app.getDashboard() != null;
    }
    
    @But("no error message should appear")
    public void butNoErrorMessage() {
        assert !app.hasError();
    }
}
```

**Scope:** Always per_test (each step definition is evaluated per scenario)

**Gherkin Feature Files (Content, not Fixture Type):**
```gherkin
Feature: User Login
  Scenario: Valid credentials
    Given a user with username "john" and password "secret"
    When the user logs in
    Then the user should be authenticated
    And the dashboard should be displayed
    But no error message should appear
```

---

### Spring Framework

**Type:** `spring_bean`, `spring_test_config`  
**Framework:** Spring, Spring Boot Test  
**Pattern:** Methods annotated with `@Bean`, `@TestConfiguration`

```java
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

@SpringBootTest
public class MyApplicationTest {
    
    @TestConfiguration
    static class TestConfig {
        
        @Bean
        public UserRepository userRepository() {
            // Create a test-specific bean
            return new InMemoryUserRepository();
        }
        
        @Bean
        public EmailService emailService() {
            // Create a mock or stub email service
            return mock(EmailService.class);
        }
    }
    
    @Autowired
    private UserRepository userRepository;
    
    @Autowired
    private EmailService emailService;
    
    @Test
    public void testUserCreation() {
        // Test using injected beans
        User user = userRepository.save(new User("john"));
        emailService.sendWelcomeEmail(user);
    }
}
```

**Scope:**
- `@Bean` → per_class (bean is created once per test class)
- `@TestConfiguration` → per_class (configuration applies to entire test class)

---

## JavaScript/TypeScript Fixtures

### Jest/Jasmine/Jest/Vitest (Standard Hooks)

**Type:** `before_each`, `after_each`, `before_all`, `after_all`  
**Frameworks:** Jest, Jasmine, Vitest  
**Pattern:** Hook functions: `beforeEach()`, `afterEach()`, `beforeAll()`, `afterAll()`

```javascript
describe('User Service', () => {
    let userService;
    let database;
    
    // Runs once before all tests in this suite
    beforeAll(() => {
        database = new Database();
        database.connect();
    });
    
    // Runs before each test
    beforeEach(() => {
        userService = new UserService(database);
        jest.clearAllMocks();
    });
    
    // Runs after each test
    afterEach(() => {
        userService = null;
    });
    
    // Runs once after all tests in this suite
    afterAll(() => {
        database.disconnect();
    });
    
    test('should create user', () => {
        const user = userService.create('john');
        expect(user.name).toBe('john');
    });
});
```

**Scope Mapping:**
- `beforeEach` → per_test
- `afterEach` → per_test
- `beforeAll` → per_class
- `afterAll` → per_class

**Detection Logic:**
1. Find `call_expression` nodes
2. Extract function name from `function` child
3. Check if matches standard hook names in JS_FIXTURE_CALLS

---

### Mocha (Ambiguous Hooks)

**Type:** `mocha_before`, `mocha_after`  
**Framework:** Mocha  
**Pattern:** `before()`, `after()` (ambiguous scope)

```javascript
describe('User API', () => {
    // Ambiguous scope: could be per-test or per-suite depending on nesting
    before(async () => {
        // Called before the suite runs
        await setupDatabase();
    });
    
    after(async () => {
        // Called after the suite runs
        await teardownDatabase();
    });
    
    it('should list users', async () => {
        const users = await api.getUsers();
        expect(users).toHaveLength(3);
    });
});
```

**Scope Mapping:**
- `before` → per_test (default, but context-dependent: could be per_class if outside nested describe)
- `after` → per_test (default, but context-dependent)

**Detection Note:** These hooks can have per-test or per-class semantics depending on nesting level. Current detector defaults to per_test for conservative accuracy.

---

### AVA

**Type:** `ava_before`, `ava_after`, `ava_serial_before`, `ava_serial_after`  
**Framework:** AVA  
**Pattern:** `test.before(...)`, `test.after(...)`, `test.serial.before(...)`, `test.serial.after(...)`

```javascript
import test from 'ava';

// Serial (per_test) before: runs before each test
test.serial.before(t => {
    t.context.db = new Database();
});

// Concurrent (per_class) after: runs after all tests
test.after(t => {
    t.context.db.close();
});

test.serial('database operations', t => {
    const result = t.context.db.query('SELECT 1');
    t.is(result, 1);
});
```

**Scope Mapping:**
- `test.before` → per_class
- `test.after` → per_class
- `test.serial.before` → per_test
- `test.serial.after` → per_test

**Detection Logic:**
1. Find `call_expression` nodes
2. Extract member access pattern: `test.before`, `test.serial.before`, etc.
3. Look up in AVA_FIXTURE_PATTERNS

---

## C# Fixtures

### NUnit

**Type:** `nunit_setup`, `nunit_teardown`  
**Framework:** NUnit  
**Pattern:** Methods annotated with `[SetUp]`, `[TearDown]`, `[OneTimeSetUp]`, `[OneTimeTearDown]`

```c#
using NUnit.Framework;

[TestFixture]
public class MyTest {
    private Resource resource;
    
    [OneTimeSetUp]
    public void OneTimeSetup() {
        // Runs once per test class
    }
    
    [SetUp]
    public void Setup() {
        // Runs before each test
        resource = new Resource();
    }
    
    [TearDown]
    public void TearDown() {
        // Runs after each test
        resource.Dispose();
    }
    
    [OneTimeTearDown]
    public void OneTimeTearDown() {
        // Runs once after all tests
    }
    
    [Test]
    public void TestSomething() {
        Assert.IsNotNull(resource);
    }
}
```

---

### xUnit

**Type:** `xunit_constructor`, `xunit_dispose`  
**Framework:** xUnit.NET  
**Pattern:** Constructor for setup, IDisposable for teardown

```c#
public class MyTest : IDisposable {
    private readonly Database db;
    
    // Runs before each test (constructor)
    public MyTest() {
        db = new Database();
        db.Connect();
    }
    
    // Runs after each test (Dispose)
    public void Dispose() {
        db.Disconnect();
    }
    
    [Fact]
    public void TestSomething() {
        var result = db.Query("SELECT 1");
        Assert.Equal(1, result);
    }
}
```

---

## BDD Frameworks

### Feature: BDD-Style Testing

BDD (Behavior-Driven Development) frameworks structure tests around human-readable scenarios describing desired behavior.

**Supported Frameworks:**

1. **Behave** (Python)
   - Step definitions: `@given`, `@when`, `@then`, `@step`
   - Feature files: `.feature` files with Gherkin syntax
   - Scope: per_test (each step is part of a scenario)

2. **Cucumber** (Java, JavaScript)
   - Step definitions: `@Given`, `@When`, `@Then`, `@And`, `@But`
   - Feature files: `.feature` files with Gherkin syntax
   - Scope: per_test (each step definition runs as part of scenario execution)

3. **SpecFlow** (C#)
   - Step binding attributes: `[Given]`, `[When]`, `[Then]`
   - Feature files: `.feature` files (similar to Gherkin)
   - Scope: per_test

**Example BDD Test Flow:**
```
Feature: User Login          ← Feature file
  Scenario: Valid login      ← Scenario (test)
    Given a user exists      ← Step definition 1 (behave_given)
    When user logs in        ← Step definition 2 (behave_when)
    Then user is authenticated ← Step definition 3 (behave_then)
```

**Detection Strategy:**
- BDD fixtures are detected by decorator patterns: `@given(...)`, `@when(...)`, `@then(...)`
- Each step definition is a separate fixture_type
- Scope is always per_test (steps are evaluated during scenario execution)
- Framework detection: identify which BDD tool based on import statements

---

## Spring Framework

### Feature: Spring Dependency Injection & Configuration

Spring provides test fixtures via configuration classes and bean factories.

**Key Annotations:**

1. **@TestConfiguration** — Test-specific bean definitions
   ```java
   @TestConfiguration
   public class MockConfig {
       @Bean
       public UserService userService() {
           return mock(UserService.class);
       }
   }
   ```

2. **@Bean** — Factory method for bean creation
   ```java
   @Bean
   public Database database() {
       return new InMemoryDatabase();
   }
   ```

3. **@MockBean** — Mock bean injection
   ```java
   @SpringBootTest
   public class MyTest {
       @MockBean
       private UserRepository repo;
   }
   ```

4. **@SpyBean** — Spy on real beans
   ```java
   @SpringBootTest
   public class MyTest {
       @SpyBean
       private UserService service;
   }
   ```

**Scope:**
- Spring fixtures are per_class (configuration applies to entire test class)
- Dependencies injected via @Autowired are created per-class

**Detection Strategy:**
- Detect `@Bean` and `@TestConfiguration` annotations in method declarations
- Look for classes nested inside test classes (inner @TestConfiguration classes)
- Scope: always per_class

---

## Fixture Relationships

### Fixture Dependency Tracking

Fixture relationships capture how fixtures depend on each other:

```
Example: pytest fixture dependency

@pytest.fixture(scope="session")
def database():
    db = Database.open()
    yield db
    db.close()

@pytest.fixture
def user(database):  # ← depends on 'database' fixture
    user = User.create(database)
    yield user
    user.delete()

def test_user_profile(user):  # ← depends on 'user' fixture
    assert user.id is not None
```

**Relationship Types:**

1. **Direct Dependency** — Fixture A requires Fixture B as a parameter
   ```python
   def fixture_a(fixture_b):  # A depends on B
       pass
   ```

2. **Scope Hierarchy** — Broader-scope fixtures enable narrower-scope fixtures
   ```python
   @pytest.fixture(scope="module")
   def module_db():  # Broader scope
       pass
   
   @pytest.fixture(scope="function")
   def test_db(module_db):  # Narrower scope depends on broader
       pass
   ```

3. **Framework Nesting** — Describe blocks nest beforeEach hooks
   ```javascript
   describe("outer", () => {
       beforeAll(() => setup1());
       
       describe("inner", () => {
           beforeAll(() => setup2());  // setup2 runs after outer setup1
       });
   });
   ```

**Future Enhancement:**
The FixtureDB can track fixture relationships to:
- Build fixture dependency graphs
- Analyze fixture initialization order
- Detect circular dependencies
- Optimize fixture reuse

---

## Detection Methodology

### General Detection Algorithm

```
For each source file:
  1. Parse tree-sitter AST
  2. Traverse all nodes
  3. For each node type:
     a. Check language-specific patterns
     b. Match against fixture type registry
     c. Extract metadata (line numbers, scope, etc.)
     d. Run complexity analysis (Lizard, cognitive-complexity)
     e. Create FixtureResult
```

### Language-Specific Strategies

**Python:**
- Decorated functions: `@pytest.fixture`, `@given`, `@when`, `@then`
- Method names: `setUp`, `tearDown`, `setup_method`, `setup_module`
- Check for `decorated_definition` and `function_definition` nodes

**Java:**
- Annotations: `@Before`, `@After`, `@BeforeEach`, `@AfterEach`, `@Given`, `@When`, `@Then`
- Method names for JUnit 3: `setUp`, `tearDown`
- Check for `method_declaration` with `modifiers` containing annotations

**JavaScript/TypeScript:**
- Function calls: `beforeEach()`, `beforeAll()`, `test.before()`, etc.
- Member expressions: `test.serial.before()`
- Decorators (TypeScript): `@Before`, `@After`
- Check for `call_expression` with matching function names

**C#:**
- Attributes: `[SetUp]`, `[TearDown]`, `[OneTimeSetUp]`, `[OneTimeTearDown]`
- Constructor/Dispose pattern for xUnit
- Check for `method_declaration` with attributes

### Accuracy Considerations

**High Confidence:**
- Explicit decorators/annotations (`@pytest.fixture`, `@Before`, `@Given`)
- Standard method names (`setUp`, `tearDown`, `beforeEach`, `afterEach`)
- Direct framework imports

**Medium Confidence:**
- Mocha `before/after` (ambiguous scope: detection defaults to per_test)
- Spring @Bean (could be test fixture or production fixture)

**Lower Confidence:**
- Custom fixture patterns (not in standard list)
- Framework detection without explicit imports
- Fixture type inference from context alone

### Known Limitations

1. **Gherkin Feature Files:** Not yet detected (only step definitions)
2. **Dynamic Fixtures:** Fixtures created at runtime without explicit definition
3. **Inheritance-based Fixtures:** Base test classes with inherited fixtures
4. **Framework Disambiguation:** Some annotations appear in multiple frameworks
5. **Custom Frameworks:** Non-standard fixture patterns not covered by detection rules

### Future Improvements

1. **BDD Feature File Detection**
   - Parse `.feature` files with Gherkin syntax
   - Extract scenarios as test cases
   - Link to corresponding step definitions

2. **Inheritance Tracking**
   - Follow class hierarchy to find inherited fixtures
   - Track fixture scope propagation through inheritance

3. **Fixture Relationship Graphs**
   - Build dependency graph of fixture relationships
   - Detect circular dependencies and initialization order issues
   - Analyze fixture re-use patterns

4. **Pattern Registry**
   - Expand FRAMEWORK_REGISTRY to include fixture patterns
   - Generate detection patterns from registry (code-first instead of pattern-first)
   - Allow user-defined custom fixture patterns

5. **Enhanced Spring Support**
   - Detect `@MockBean` and `@SpyBean` fixtures
   - Track Spring context creation and injection
   - Link fixtures to their @Configuration classes

---

## References

### Pytest Documentation
- [pytest Fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [Fixture Scopes](https://docs.pytest.org/en/stable/how-to-fixtures.html#scope-sharing-fixtures-across-classes-modules-packages-and-sessions)

### JUnit Documentation
- [JUnit 4 Annotations](https://junit.org/junit4/javadoc/latest/org/junit/package-summary.html)
- [JUnit 5 Annotations](https://junit.org/junit5/docs/current/user-guide/#writing-tests-annotations)

### Other Frameworks
- [TestNG](https://testng.org/doc/)
- [Jest](https://jestjs.io/docs/setup-teardown)
- [Mocha](https://mochajs.org/#hooks)
- [AVA](https://github.com/avajs/ava#test-execution)
- [Behave](https://behave.readthedocs.io/)
- [Cucumber](https://cucumber.io/docs/gherkin/)

