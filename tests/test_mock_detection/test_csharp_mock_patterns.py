"""
Mock detection tests for C# fixtures.

Validates that the extractor correctly identifies mock usage patterns
in C# test fixtures.
"""

import pytest
from ..conftest import (
    extract_and_find_fixtures,
    assert_fixture_detected,
    assert_fixture_not_detected,
    assert_fixture_count,
)


class TestCSharpMoqPatterns:
    """Moq mock patterns"""
    
    def test_moq_setup(self):
        """Moq mock setup in [SetUp] fixture"""
        code = """
using Moq;
using NUnit.Framework;

[TestFixture]
public class UserServiceTests {
    private Mock<IUserRepository> mockRepo;
    
    [SetUp]
    public void Setup() {
        mockRepo = new Mock<IUserRepository>();
        mockRepo.Setup(r => r.GetUser(It.IsAny<int>()))
            .Returns(new User { Id = 1 });
    }
}
"""
        fixture = assert_fixture_detected(code, 'csharp', 'Setup')
        assert fixture.fixture_type == 'nunit_setup'
        assert fixture.num_objects_instantiated >= 1


class TestCSharpNSubstitutePatterns:
    """NSubstitute mock patterns"""
    
    def test_nsubstitute_setup(self):
        """NSubstitute setup in [SetUp]"""
        code = """
using NSubstitute;
using NUnit.Framework;

[TestFixture]
public class UserServiceTests {
    private IUserService mockService;
    
    [SetUp]
    public void Setup() {
        mockService = Substitute.For<IUserService>();
        mockService.GetUser(1).Returns(new User { Id = 1 });
    }
}
"""
        fixture = assert_fixture_detected(code, 'csharp', 'Setup')
        assert fixture.num_objects_instantiated >= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
