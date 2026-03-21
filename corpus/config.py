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
CLONES_DIR = ROOT_DIR / "clones"          # temporary, deleted after extraction
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

    name: str                          # human-readable
    github_language: str               # label used by GitHub search API
    min_stars: int = 100
    target_repos: int = 1000           # how many repos to collect

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

STAR_TIER_CORE_THRESHOLD = 500   # 'core'     — directly comparable to Hamster
# repos with stars in [MIN_STARS, 499] are tagged 'extended'


def star_tier(stars: int) -> str:
    """Return the tier label for a given star count."""
    return "core" if stars >= STAR_TIER_CORE_THRESHOLD else "extended"


EXCLUSION_KEYWORDS = [
    "tutorial", "course", "homework", "exercise", "demo", "example",
    "sample", "workshop", "bootcamp", "learning", "practice", "beginner",
    "awesome-", "cheatsheet", "interview", "leetcode", "hackerrank",
]

# ---------------------------------------------------------------------------
# Per-language targets
#
# target_repos is the search-phase ceiling.  Expected survival after quality
# filters (min test files + min commits) is ~50–70%, so searching for 1,000
# should yield ~600–700 analysed repos per language — a corpus size that
# stands well in a Data Showcase abstract and allows meaningful stratification.
#
# JavaScript is slightly lower because many JS repos are frontend-only and
# yield few or no fixture definitions.
# ---------------------------------------------------------------------------

LANGUAGE_CONFIGS = {
    "python": LanguageConfig(
        name="Python",
        github_language="Python",
        min_stars=100,
        target_repos=1000,
        test_path_patterns=["test/", "tests/", "testing/", "test_", "conftest"],
        test_file_suffixes=["test_.py", "_test.py", "_tests.py"],
    ),
    "java": LanguageConfig(
        name="Java",
        github_language="Java",
        min_stars=100,
        target_repos=1000,
        test_path_patterns=["src/test/", "test/", "tests/"],
        test_file_suffixes=["Test.java", "Tests.java", "IT.java", "Spec.java"],
    ),
    "javascript": LanguageConfig(
        name="JavaScript",
        github_language="JavaScript",
        min_stars=100,
        target_repos=800,
        test_path_patterns=["__tests__/", "test/", "tests/", "spec/"],
        test_file_suffixes=[".test.js", ".spec.js", "test.js", ".test.jsx", ".spec.jsx", ".test.mjs", ".spec.mjs"],
    ),
    "typescript": LanguageConfig(
        name="TypeScript",
        github_language="TypeScript",
        min_stars=100,
        target_repos=600,
        test_path_patterns=["__tests__/", "test/", "tests/", "spec/"],
        test_file_suffixes=[".test.ts", ".spec.ts", "test.ts", ".test.tsx", ".spec.tsx", ".test.mts", ".spec.mts"],
    ),
    "go": LanguageConfig(
        name="Go",
        github_language="Go",
        min_stars=100,
        target_repos=600,
        test_path_patterns=["test/", "tests/", "_test.go"],
        test_file_suffixes=["_test.go"],
    ),
}

# Minimum thresholds applied after cloning
MIN_TEST_FILES = 5          # repos with fewer test files are dropped
MIN_COMMITS = 50            # repos with fewer commits are dropped
MIN_FIXTURES_FOUND = 1      # repos where we detect zero fixtures are dropped

# Maximum repos to clone in a single run (useful for incremental collection)
CLONE_BATCH_SIZE = 50

# Number of parallel clone workers
CLONE_WORKERS = 10