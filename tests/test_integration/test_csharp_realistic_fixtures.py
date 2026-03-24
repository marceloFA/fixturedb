"""
Integration tests for C# fixture extraction on realistic code.

Tests extraction on actual test files with multiple fixtures,
inheritance hierarchies, and real-world patterns from popular C# frameworks.
"""

import pytest
from ..conftest import (
    extract_and_find_fixtures,
    assert_fixture_detected,
    assert_fixture_count,
)


class TestCSharpxUnitFixtures:
    """Integration tests using xUnit patterns"""
    
    def test_xunit_with_collection_fixtures(self):
        """xUnit test class with collection fixtures"""
        code = """
using Xunit;
using Moq;

public class DatabaseFixture : IAsyncLifetime {
    private readonly IDatabase _db;
    
    public DatabaseFixture() {
        _db = new TestDatabase();
    }
    
    public async Task InitializeAsync() {
        await _db.Initialize();
        await _db.Migrate();
    }
    
    public async Task DisposeAsync() {
        await _db.Cleanup();
        _db.Dispose();
    }
}

[CollectionDefinition("Database collection")]
public class DatabaseCollection : ICollectionFixture<DatabaseFixture> {
}

[Collection("Database collection")]
public class UserRepositoryTests {
    private readonly DatabaseFixture _fixture;
    private readonly Mock<ILogger> _mockLogger;
    
    public UserRepositoryTests(DatabaseFixture fixture) {
        _fixture = fixture;
        _mockLogger = new Mock<ILogger>();
    }
}
"""
        assert_fixture_detected(code, 'csharp', 'InitializeAsync')
        assert_fixture_detected(code, 'csharp', 'DisposeAsync')


class TestCSharpNUnitFixtures:
    """Integration tests using NUnit patterns"""
    
    def test_nunit_with_inheritance(self):
        """NUnit test with inheritance hierarchy"""
        code = """
using NUnit.Framework;

[TestFixture]
public abstract class BaseRepositoryTests {
    protected IRepository Repository;
    protected TestDatabase TestDb;
    
    [OneTimeSetUp]
    public void OneTimeSetUp() {
        TestDb = new TestDatabase();
    }
    
    [SetUp]
    public virtual void Setup() {
        Repository = new Repository(TestDb.GetConnection());
    }
    
    [TearDown]
    public virtual void TearDown() {
        TestDb.ClearData();
    }
    
    [OneTimeTearDown]
    public void OneTimeTearDown() {
        TestDb.Dispose();
    }
}

[TestFixture]
public class UserRepositoryTests : BaseRepositoryTests {
    [SetUp]
    public override void Setup() {
        base.Setup();
        ((UserRepository)Repository).Seed();
    }
}
"""
        assert_fixture_detected(code, 'csharp', 'OneTimeSetUp')
        assert_fixture_detected(code, 'csharp', 'Setup')
        assert_fixture_detected(code, 'csharp', 'TearDown')
        assert_fixture_detected(code, 'csharp', 'OneTimeTearDown')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
