"""
Central configuration for the fixture corpus collection pipeline.
Edit this file to tune search parameters before a collection run.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).parent.parent
CLONES_DIR = ROOT_DIR / "clones"  # temporary, deleted after extraction
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "corpus.db"
LOGS_DIR = ROOT_DIR / "logs"

for _d in (CLONES_DIR, DATA_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")  # set in .env
GITHUB_API_BASE = "https://api.github.com"
GITHUB_SEARCH_URL = f"{GITHUB_API_BASE}/search/repositories"
GITHUB_RATE_LIMIT_URL = f"{GITHUB_API_BASE}/rate_limit"

# Pause between paginated requests to stay well within rate limits (seconds)
REQUEST_DELAY = 2.0

# ---------------------------------------------------------------------------
# Repository search filters
# ---------------------------------------------------------------------------


@dataclass
class LanguageConfig:
    """Per-language search and detection configuration."""

    name: str  # human-readable
    github_language: str  # label used by GitHub search API
    min_stars: int = 100
    target_repos: int = 1000  # target count of final analyzed repos (with >=1 fixture extracted)

    # Paths that signal "this is a test file"
    test_path_patterns: list[str] = field(default_factory=list)

    # File name suffixes that signal a test file
    test_file_suffixes: list[str] = field(default_factory=list)

    # Keywords whose presence in repo name/description signals a non-research repo
    exclusion_keywords: list[str] = field(default_factory=lambda: EXCLUSION_KEYWORDS)


# ---------------------------------------------------------------------------
# Star tier thresholds
#
# Repos are tagged at collection time as 'core' (≥500 stars, comparable to
# Hamster's selection criterion) or 'extended' (100–499 stars, adds diversity).
# Both tiers are collected; analyses can be stratified or filtered by tier.
#
# Literature reference:
#   Hamster (arXiv:2509.26204) uses ≥500 stars + organisational ownership.
#   Studies using ≥1000 stars claim "influential project" comparability.
#   The 100-star floor is the common quality minimum in MSR work.
# ---------------------------------------------------------------------------

STAR_TIER_CORE_THRESHOLD = 500  # 'core', directly comparable to Hamster
# repos with stars in [MIN_STARS, 499] are tagged 'extended'


def star_tier(stars: int) -> str:
    """Return the tier label for a given star count."""
    return "core" if stars >= STAR_TIER_CORE_THRESHOLD else "extended"


EXCLUSION_KEYWORDS = [
    "tutorial",
    "course",
    "homework",
    "exercise",
    "demo",
    "example",
    "sample",
    "workshop",
    "bootcamp",
    "learning",
    "practice",
    "beginner",
    "awesome-",
    "cheatsheet",
    "interview",
    "leetcode",
    "hackerrank",
]

# ---------------------------------------------------------------------------
# Per-language targets
#
# target_repos is the gold-standard final count: repositories with status='analysed'
# AND at least one extracted fixture. The `collect` command loops until this target
# is reached for each language.
#
# JavaScript and TypeScript targets are lower because many such repos are
# frontend-only and yield few or no fixture definitions.
# ---------------------------------------------------------------------------

LANGUAGE_CONFIGS = {
    "python": LanguageConfig(
        name="Python",
        github_language="Python",
        min_stars=100,
        target_repos=400,
        test_path_patterns=["test/", "tests/", "testing/", "test_", "conftest"],
        test_file_suffixes=["test_.py", "_test.py", "_tests.py"],
    ),
    "java": LanguageConfig(
        name="Java",
        github_language="Java",
        min_stars=100,
        target_repos=400,
        test_path_patterns=["src/test/", "test/", "tests/"],
        test_file_suffixes=["Test.java", "Tests.java", "IT.java", "Spec.java"],
    ),
    "javascript": LanguageConfig(
        name="JavaScript",
        github_language="JavaScript",
        min_stars=100,
        target_repos=250,
        test_path_patterns=["__tests__/", "test/", "tests/", "spec/"],
        test_file_suffixes=[
            ".test.js",
            ".spec.js",
            "test.js",
            ".test.jsx",
            ".spec.jsx",
            ".test.mjs",
            ".spec.mjs",
        ],
    ),
    "typescript": LanguageConfig(
        name="TypeScript",
        github_language="TypeScript",
        min_stars=100,
        target_repos=150,
        test_path_patterns=["__tests__/", "test/", "tests/", "spec/"],
        test_file_suffixes=[
            ".test.ts",
            ".spec.ts",
            "test.ts",
            ".test.tsx",
            ".spec.tsx",
            ".test.mts",
            ".spec.mts",
        ],
    ),
    "go": LanguageConfig(
        name="Go",
        github_language="Go",
        min_stars=100,
        target_repos=400,
        test_path_patterns=["test/", "tests/", "_test.go"],
        test_file_suffixes=["_test.go"],
    ),
    "csharp": LanguageConfig(
        name="C#",
        github_language="C#",
        min_stars=100,
        target_repos=300,
        test_path_patterns=["tests/", "test/", "Tests/", "Test/"],
        test_file_suffixes=[
            "Tests.cs",
            ".Tests.cs",
            "_Tests.cs",
            "Test.cs",
            "_Test.cs",
        ],
    ),
}

# Minimum thresholds applied after cloning
MIN_TEST_FILES = 5  # repos with fewer test files are dropped
MIN_COMMITS = 100  # repos with fewer commits are dropped
MIN_FIXTURES_FOUND = 1  # repos where we detect zero fixtures are dropped

# Per-language survival rates (discovered → analyzed with fixtures)
# These are empirically observed rates used to calculate discovery estimates.
# They are updated as we collect data for each language.
# Format: {language: survival_rate}
LANGUAGE_SURVIVAL_RATES = {
    "python": 0.076,  # 7.6% actual from completed collection
    "java": 0.15,     # estimate (Java typically has higher survival)
    "go": 0.09,       # estimate
    "csharp": 0.10,   # estimate
    "javascript": 0.08,  # estimate
    "typescript": 0.08,  # estimate
}

# Discovery and collection tuning
DISCOVERY_SURVIVAL_RATE = 0.09  # fallback/default if language not in LANGUAGE_SURVIVAL_RATES
DISCOVERY_SAFETY_BUFFER = 1.25  # 25% buffer to reduce iterations
MAX_DISCOVERIES_PER_ITERATION = 3000  # cap to manage disk space
MAX_REPOS_PER_ITERATION = 500  # max repos (discovered + cloned + extracted) per collection iteration

# Maximum repos to clone in a single run (useful for incremental collection)
CLONE_BATCH_SIZE = 50

# Number of parallel clone workers
CLONE_WORKERS = 12

# Number of parallel extraction workers (balanced for SQLite single-writer limit)
# SQLite has a single-writer limitation; only one transaction can write at a time.
# With 20-retry aggressive backoff policy, 3 workers is safe and provides good parallelism
# without excessive lock contention. Going above 4 causes diminishing returns.
EXTRACT_WORKERS = 3

# Maximum time to spend extracting fixtures from a single test file (seconds)
# Files that exceed this timeout are skipped to prevent pathological cases
# (e.g., minified code, massive auto-generated test files, etc.)
FILE_EXTRACTION_TIMEOUT = 300  # 5 minutes
