"""
Fixture taxonomy classifier — categorizes fixtures into usage patterns.

Assigns one of eight category labels to each fixture based on:
  - structural metadata (LOC, complexity, num_objects_instantiated, etc.)
  - mock framework usage (from mock_usages table)
  - keywords in raw_source text

Categories (RQ1 taxonomy):
  - data_builder:         constructs/initializes test data
  - service_setup:        wires dependencies and services
  - environment:          manages environment, files, databases
  - resource_management:  handles resource allocation/cleanup
  - mock_setup:           creates mocks, stubs, spies for test isolation
  - state_reset:          resets global/shared state between tests
  - configuration_setup:  configures settings, env vars, feature flags
  - hybrid:               combination of above patterns

Usage:
    from corpus.fixture_classifier import categorize_all
    counts = categorize_all()
"""

import logging
import re
from corpus.db import db_session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword patterns for each category
# ---------------------------------------------------------------------------

CATEGORY_KEYWORDS = {
    "mock_setup": [
        r"\bmock\b",
        r"\bstub\b",
        r"\bspy\b",
        r"\bfake\b",
        r"mockito",
        r"easymock",
        r"unittest_mock",
        r"pytest_mock",
        r"jest\.mock",
        r"jest\.spyOn",
        r"sinon\.stub",
        r"testify",
        r"gomock",
        r"moq",
        r"nsubstitute",
        r"create(Mock|Stub|Spy)",
        r"\.when\(",
        r"\.thenReturn",
        r"\.thenThrow",
        r"\.verify\(",
        r"setupMock",
        r"prepareMock",
    ],
    "data_builder": [
        r"\bcreate\b",
        r"\bbuild\b",
        r"\bconstruct\b",
        r"\bnew \w+\(",
        r"factory",
        r"builder",
        r"fixture",
        r"\.add\(",
        r"\.append\(",
        r"\.put\(",
        r"\.set\(",
        r"testdata",
        r"test_data",
        r"sample",
        r"prepare_data",
        r"create_.*objects?",
        r"build_.*objects?",
    ],
    "service_setup": [
        r"\binject\b",
        r"\bwire\b",
        r"\bbind\b",
        r"\bprovide\b",
        r"dependenc",
        r"container",
        r"registry",
        r"factory\.create",
        r"\.register\(",
        r"\.bind\(",
        r"setUp.*service",
        r"setupModule",
        r"initializeService",
    ],
    "environment": [
        r"\bfile\b",
        r"\bfolder\b",
        r"\bdirectory\b",
        r"\bdatabase\b",
        r"\bdb\b",
        r"\btemp\b",
        r"\btmp\b",
        r"\bpath\b",
        r"tempfile",
        r"tempdir",
        r"tmpdir",
        r"sqlite",
        r"connection",
        r"\.create\(\)",
        r"\.mkdir\(",
        r"\.chdir\(",
        r"os\.",
        r"tempfile\.",
        r"pathlib\.",
        r"filesystem",
    ],
    "resource_management": [
        r"\bopen\(",
        r"\bclose\(",
        r"\bconnect\(",
        r"\bdisconnect\(",
        r"\bacquire\(",
        r"\brelease\(",
        r"\byield\b",
        r"\bwith\b",
        r"context_?manager",
        r"transaction",
        r"cleanup",
        r"teardown",
        r"shutdown",
        r"\.close\(\)",
        r"finally:",
    ],
    "state_reset": [
        r"\breset\b",
        r"\bclear\b",
        r"\bclean\b",
        r"\brestore\b",
        r"\bflush\b",
        r"\btruncate\b",
        r"reset.*state",
        r"clear.*cache",
        r"clear.*data",
        r"cleanup",
        r"\.reset\(",
        r"\.clear\(",
        r"\.flush\(",
        r"deleteAll",
        r"drop_all",
    ],
    "configuration_setup": [
        r"\bconfig\b",
        r"\bsetting\b",
        r"\benv\b",
        r"\bfeature\b",
        r"\bflag\b",
        r"\bproperty\b",
        r"\bconfigur",
        r"environment_?variable",
        r"os\.environ",
        r"dotenv",
        r"config\.set",
        r"setProperty",
        r"setEnvironment",
        r"setup.*configuration",
        r"initialize.*config",
        r"set.*flag",
        r"enable.*feature",
    ],
}

# ---------------------------------------------------------------------------
# Categorization logic
# ---------------------------------------------------------------------------


def _classify_fixture(
    fixture_id: int,
    fixture_type: str,
    scope: str,
    loc: int,
    cyclomatic_complexity: int,
    num_objects_instantiated: int,
    num_external_calls: int,
    num_parameters: int,
    has_yield: int,
    raw_source: str,
    mock_count: int,
) -> str:
    """
    Categorize a single fixture using heuristics based on structure and content.
    Returns one of the category labels.
    """
    if not raw_source:
        return "hybrid"  # default if no source available

    source_lower = raw_source.lower()
    matched_categories = set()

    # 1. Check keyword patterns in raw_source
    for category, keywords in CATEGORY_KEYWORDS.items():
        for pattern in keywords:
            if re.search(pattern, source_lower, re.IGNORECASE):
                matched_categories.add(category)
                break

    # 2. Check for mocks in mock_usages table
    if mock_count > 0:
        matched_categories.add("mock_setup")

    # 3. Structural heuristics
    if num_parameters >= 2:
        matched_categories.add("service_setup")
    if num_objects_instantiated >= 3:
        matched_categories.add("data_builder")
    if num_external_calls >= 2:
        matched_categories.add("environment")
    if has_yield == 1:
        matched_categories.add("resource_management")

    # 4. Scope-based hints
    if scope in ("per_module", "global"):
        matched_categories.add("state_reset")

    # 5. Complexity heuristics
    if cyclomatic_complexity >= 3:
        # More complex fixtures often do multiple things
        if len(matched_categories) == 0:
            matched_categories.add("hybrid")

    # Decision logic: pick single best category or "hybrid"
    if len(matched_categories) == 0:
        return "hybrid"
    elif len(matched_categories) == 1:
        return list(matched_categories)[0]
    else:
        # Multiple categories matched -> check for dominance
        # If mock_setup is strong (lots of mock calls), it wins
        if mock_count >= 2 and "mock_setup" in matched_categories:
            return "mock_setup"
        # If it looks like a builder (lots of object instantiation), it wins
        if num_objects_instantiated >= 5 and "data_builder" in matched_categories:
            return "data_builder"
        # Otherwise, it's genuinely hybrid
        return "hybrid"


def categorize_all(overwrite: bool = False) -> dict[str, int]:
    """
    Categorize all fixtures that have no category label yet.
    If overwrite=True, re-categorize all fixtures including already-categorized ones.
    Returns a count dict {category: n}.
    """
    counts: dict[str, int] = {}

    with db_session() as conn:
        if overwrite:
            query = """
                SELECT f.id, f.fixture_type, f.scope, f.loc, f.cyclomatic_complexity,
                       f.num_objects_instantiated, f.num_external_calls, f.num_parameters,
                       f.has_yield, f.raw_source, COALESCE(COUNT(m.id), 0) as mock_count
                FROM fixtures f
                LEFT JOIN mock_usages m ON f.id = m.fixture_id
                GROUP BY f.id
            """
        else:
            query = """
                SELECT f.id, f.fixture_type, f.scope, f.loc, f.cyclomatic_complexity,
                       f.num_objects_instantiated, f.num_external_calls, f.num_parameters,
                       f.has_yield, f.raw_source, COALESCE(COUNT(m.id), 0) as mock_count
                FROM fixtures f
                LEFT JOIN mock_usages m ON f.id = m.fixture_id
                WHERE f.category IS NULL
                GROUP BY f.id
            """
        
        rows = conn.execute(query).fetchall()
        logger.info(f"Categorizing {len(rows)} fixtures …")

        for row in rows:
            category = _classify_fixture(
                fixture_id=row["id"],
                fixture_type=row["fixture_type"],
                scope=row["scope"],
                loc=row["loc"],
                cyclomatic_complexity=row["cyclomatic_complexity"],
                num_objects_instantiated=row["num_objects_instantiated"],
                num_external_calls=row["num_external_calls"],
                num_parameters=row["num_parameters"],
                has_yield=row["has_yield"],
                raw_source=row["raw_source"],
                mock_count=row["mock_count"],
            )
            conn.execute(
                "UPDATE fixtures SET category = ? WHERE id = ?",
                (category, row["id"]),
            )
            counts[category] = counts.get(category, 0) + 1

    logger.info(f"Fixture categorization done: {counts}")
    return counts
