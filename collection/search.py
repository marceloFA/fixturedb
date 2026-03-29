"""
GitHub repository search and discovery layer.

Searches the GitHub REST API for repositories matching per-language criteria,
applies quality filters, and writes candidate repos to the database.

COLLECTION STRATEGIES
=====================

Three strategies are available for discovery, selectable per language:

1. **Star-count sorting (DEFAULT)** — collect in order of popularity
   Most popular repos first (API default sort), maximizing high-quality
   (500+ star) repositories early. Good for rapid core corpus buildup.
   
2. **Stratified/temporal sampling** — collect proportionally from each year
   Avoids temporal bias; represents testing practice evolution rather than
   being skewed toward legacy codebases. Use for diachronic studies.

3. **Chronological (legacy)** — collect oldest-first
   Original approach; no longer recommended due to temporal bias.

FILTERING RULES
===============

Applied at GitHub API level:
  - language: {language}
  - stars: >= min_stars (default 100, can override to 500 for 'core' tier)
  - fork: false (exclude forks)
  - is: public (public repos only)

Applied at metadata level (before DB insert):
  - NOT in EXCLUSION_KEYWORDS (tutorial, demo, homework, etc.)
  - NOT archived (archived:true repos skipped)
  - NOT empty (size > 0)
  - NOT fork (redundant check)

SURVIVAL RATES
==============

Empirically observed discovery → analyzed conversion rates for each language.
Used by the `collect` command to calculate how many repos to search for
to reach a target number of analyzable repos. E.g., if Python has 7.6%
survival rate and we want 400 analyzed repos, we search for ~5,260 repos.

See LANGUAGE_SURVIVAL_RATES in config.py for current per-language rates.
"""

import time
import json
import logging
from datetime import datetime, timedelta

import requests

from collection.config import (
    GITHUB_TOKEN,
    GITHUB_SEARCH_URL,
    GITHUB_RATE_LIMIT_URL,
    REQUEST_DELAY,
    LANGUAGE_CONFIGS,
    EXCLUSION_KEYWORDS,
    LanguageConfig,
    star_tier,
)
from collection.db import db_session, upsert_repository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    if GITHUB_TOKEN:
        session.headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    else:
        logger.warning(
            "No GITHUB_TOKEN found. Unauthenticated requests are rate-limited "
            "to 10 requests/minute for search. Set GITHUB_TOKEN in .env"
        )
    return session


SESSION = _make_session()


# ---------------------------------------------------------------------------
# Rate limit handling
# ---------------------------------------------------------------------------


def _check_rate_limit() -> dict:
    """Return the current rate limit state for the search API."""
    r = SESSION.get(GITHUB_RATE_LIMIT_URL, timeout=10)
    r.raise_for_status()
    return r.json()["resources"]["search"]


def _wait_for_rate_limit(resource: dict) -> None:
    """Sleep until the rate limit resets if we are close to exhausted."""
    remaining = resource.get("remaining", 0)
    if remaining < 3:
        reset_at = resource.get("reset", time.time() + 60)
        sleep_secs = max(reset_at - time.time() + 2, 1)
        logger.info(
            f"Rate limit low ({remaining} remaining). Sleeping {sleep_secs:.0f}s."
        )
        time.sleep(sleep_secs)


# ---------------------------------------------------------------------------
# Repository filtering
# ---------------------------------------------------------------------------


def _is_excluded(repo: dict, config: LanguageConfig) -> tuple[bool, str]:
    """
    Returns (should_exclude, reason).
    Applied before writing to DB — purely metadata-based.
    """
    name = (repo.get("name") or "").lower()
    description = (repo.get("description") or "").lower()
    text = f"{name} {description}"

    for kw in config.exclusion_keywords:
        if kw in text:
            return True, f"exclusion keyword '{kw}'"

    if repo.get("fork"):
        return True, "is a fork"

    if repo.get("archived"):
        return True, "is archived"

    # Require at least some open issues / activity signals
    # (size == 0 usually means an empty or stub repo)
    if repo.get("size", 1) == 0:
        return True, "empty repository"

    return False, ""


def _has_test_indicators(repo: dict, config: LanguageConfig) -> bool:
    """
    Quick heuristic: does the repo description or topics mention testing?
    This is a loose positive signal — we do a hard check after cloning.
    Returning False here is not disqualifying; it just deprioritises the repo.
    """
    topics = repo.get("topics") or []
    text = " ".join(topics + [repo.get("description") or ""])
    test_signals = ["test", "testing", "spec", "tdd", "bdd", "unit"]
    return any(sig in text.lower() for sig in test_signals)


# ---------------------------------------------------------------------------
# Core search
# ---------------------------------------------------------------------------


def _search_page(query: str, page: int, per_page: int = 100) -> dict:
    """Fetch a single page of search results."""
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
        "page": page,
    }
    r = SESSION.get(GITHUB_SEARCH_URL, params=params, timeout=30)

    if r.status_code == 403:
        # Secondary rate limit — back off generously
        retry_after = int(r.headers.get("Retry-After", 60))
        logger.warning(f"Secondary rate limit hit. Sleeping {retry_after}s.")
        time.sleep(retry_after)
        return _search_page(query, page, per_page)

    if r.status_code == 422:
        logger.error(f"GitHub rejected query: {query!r} → {r.json()}")
        return {"items": [], "total_count": 0}

    r.raise_for_status()
    return r.json()


def _build_query(config: LanguageConfig, min_stars: int | None = None) -> str:
    """
    Build the GitHub search query string for a given language.

    We split the search into date-range buckets to work around the 1,000-result
    cap that GitHub imposes per query. Each bucket covers ~6 months, going back
    far enough to collect repositories created since 2015.

    Args:
        config: Language configuration
        min_stars: Minimum stars (overrides config.min_stars). Use for tier-based collection.
    """
    stars_threshold = min_stars or config.min_stars
    return (
        f"language:{config.github_language} "
        f"stars:>={stars_threshold} "
        f"fork:false "
        f"is:public"
    )


def collect_repos_for_language(
    language_key: str,
    max_repos: int | None = None,
    sort_by_stars: bool = True,
    stratified: bool = False,
    min_stars: int | None = None,
) -> int:
    """
    Search GitHub for repositories in the given language and persist them
    to the database. Returns the number of NEW repos written.

    Repos already in the database are skipped for counting purposes
    (their metadata is updated in place). The search continues until
    max_repos genuinely new repos have been inserted, making this function
    safe to call multiple times — each call discovers a new batch.

    Args:
        language_key: Language to collect (e.g., 'python', 'java')
        max_repos: Target total repos.
        sort_by_stars: If True (default), collect repos sorted by star count (most stars first).
                       Maximizes core-tier repos. Overrides stratified.
        stratified: If True, collect repos proportionally from each year (representative sampling).
                    Ignored if sort_by_stars=True.
        min_stars: Minimum stars to filter by (e.g., 500 for core repos).
                   If None, uses config.min_stars.
    """
    config = LANGUAGE_CONFIGS[language_key]
    max_repos = max_repos or config.target_repos

    if sort_by_stars:
        return _collect_repos_by_stars(language_key, config, max_repos, min_stars)
    elif stratified:
        return _collect_repos_stratified(language_key, config, max_repos, min_stars)
    else:
        return _collect_repos_chronological(language_key, config, max_repos, min_stars)


def _collect_repos_by_stars(
    language_key: str,
    config: LanguageConfig,
    max_repos: int,
    min_stars: int | None = None,
) -> int:
    """
    Collect repos sorted by star count (most stars first).

    This is the preferred strategy when you want to maximize high-quality (500+ star)
    repositories. By collecting in order of star count, you get the most popular
    repos first, naturally maximizing the percentage of core-tier repos.

    The GitHub API search already returns results sorted by stars (descending),
    so this approach simply pages through without splitting into date buckets.

    Args:
        language_key: e.g., 'python'
        config: Language configuration
        max_repos: Target total repos
        min_stars: Minimum stars filter (uses config.min_stars if None)
    """
    stars_desc = " (500+ stars)" if min_stars and min_stars >= 500 else ""
    logger.info(
        f"[{language_key}] Starting STAR-COUNT collection{stars_desc}. "
        f"Target: {max_repos} repos. "
        f"Collecting in order of popularity (most stars first) to maximize core-tier repos."
    )

    total_written = 0
    base_query = _build_query(config, min_stars=min_stars)
    page = 1

    while total_written < max_repos:
        rl = _check_rate_limit()
        _wait_for_rate_limit(rl)

        logger.debug(f"[{language_key}] page {page} ({total_written}/{max_repos})")
        data = _search_page(base_query, page=page)
        items = data.get("items", [])

        if not items:
            logger.info(
                f"[{language_key}] No more results at page {page}. "
                f"Stopping. Total: {total_written}/{max_repos}"
            )
            break

        with db_session() as conn:
            for repo in items:
                if total_written >= max_repos:
                    break

                excluded, reason = _is_excluded(repo, config)
                if excluded:
                    logger.debug(f"  skip {repo['full_name']}: {reason}")
                    continue

                record = {
                    "github_id": repo["id"],
                    "full_name": repo["full_name"],
                    "language": language_key,
                    "stars": repo.get("stargazers_count"),
                    "forks": repo.get("forks_count"),
                    "description": repo.get("description"),
                    "topics": json.dumps(repo.get("topics", [])),
                    "created_at": repo.get("created_at"),
                    "pushed_at": repo.get("pushed_at"),
                    "clone_url": repo.get("clone_url"),
                    "star_tier": star_tier(repo.get("stargazers_count") or 0),
                }
                _, is_new = upsert_repository(conn, record)
                if is_new:
                    total_written += 1

        page += 1
        # GitHub API allows up to 34 pages of 100 results = 3400 max per query
        # Stop after 35 pages to stay well within limits
        if page > 35:
            logger.info(
                f"[{language_key}] Reached page limit (35 pages × 100 items = 3500 results). "
                f"Total: {total_written}/{max_repos}. "
                f"If more repos needed, run again — they'll be added in next batch."
            )
            break

        time.sleep(REQUEST_DELAY)

    logger.info(
        f"[{language_key}] Star-count collection complete. Total repos: {total_written}"
    )
    return total_written


def _collect_repos_stratified(
    language_key: str,
    config: LanguageConfig,
    max_repos: int,
    min_stars: int | None = None,
) -> int:
    """
    Collect repos proportionally from each year to avoid temporal bias.

    This ensures the corpus represents the evolution of testing practices
    rather than being skewed toward legacy codebases.

    For example: 1500 repos × 10 years = 150 repos per year

    Args:
        language_key: e.g., 'python'
        config: Language configuration
        max_repos: Target total repos
        min_stars: Minimum stars filter (uses config.min_stars if None)
    """
    bucket_starts = _generate_date_buckets(
        start="2015-01-01",
        end=datetime.utcnow().strftime("%Y-%m-%d"),
        months=12,  # 1 year per bucket for stratification
    )

    num_years = len(bucket_starts)
    repos_per_year = max_repos // num_years if num_years > 0 else max_repos
    remaining_repos = max_repos % num_years  # Distribute remainder

    total_written = 0

    stars_desc = " (500+ stars)" if min_stars and min_stars >= 500 else ""
    logger.info(
        f"[{language_key}] Starting STRATIFIED collection{stars_desc}. "
        f"Target: {max_repos} repos ({repos_per_year} per year × {num_years} years, +{remaining_repos} remainder). "
        f"This ensures balanced temporal representation."
    )

    for idx, (bucket_start, bucket_end) in enumerate(bucket_starts):
        # Allocate more repos to later years to use remainder
        target_for_year = repos_per_year + (
            1 if idx >= (num_years - remaining_repos) else 0
        )
        year_written = 0

        base_query = _build_query(config, min_stars=min_stars)
        query = f"{base_query} created:{bucket_start}..{bucket_end}"
        page = 1

        while year_written < target_for_year:
            rl = _check_rate_limit()
            _wait_for_rate_limit(rl)

            logger.debug(
                f"[{language_key}] {bucket_start} page {page} ({year_written}/{target_for_year})"
            )
            data = _search_page(query, page=page)
            items = data.get("items", [])

            if not items:
                break

            with db_session() as conn:
                for repo in items:
                    if year_written >= target_for_year:
                        break

                    excluded, reason = _is_excluded(repo, config)
                    if excluded:
                        logger.debug(f"  skip {repo['full_name']}: {reason}")
                        continue

                    record = {
                        "github_id": repo["id"],
                        "full_name": repo["full_name"],
                        "language": language_key,
                        "stars": repo.get("stargazers_count"),
                        "forks": repo.get("forks_count"),
                        "description": repo.get("description"),
                        "topics": json.dumps(repo.get("topics", [])),
                        "created_at": repo.get("created_at"),
                        "pushed_at": repo.get("pushed_at"),
                        "clone_url": repo.get("clone_url"),
                        "star_tier": star_tier(repo.get("stargazers_count") or 0),
                    }
                    _, is_new = upsert_repository(conn, record)
                    if is_new:
                        year_written += 1
                        total_written += 1

            page += 1
            if page > 10:
                break

            time.sleep(REQUEST_DELAY)

        logger.info(
            f"[{language_key}] Year {bucket_start}: {year_written}/{target_for_year} repos. "
            f"Total: {total_written}/{max_repos}"
        )

    logger.info(
        f"[{language_key}] Stratified collection complete. "
        f"Total repos: {total_written} (balanced across {num_years} years)"
    )
    return total_written


def _collect_repos_chronological(
    language_key: str,
    config: LanguageConfig,
    max_repos: int,
    min_stars: int | None = None,
) -> int:
    """
    Collect repos chronologically (oldest first) until max_repos is reached.

    This is the original behavior. WARNING: Prone to temporal bias since
    it stops once max_repos is collected, typically resulting in mostly
    2015-2017 repos. Use stratified=True for better representativeness.

    Args:
        language_key: e.g., 'python'
        config: Language configuration
        max_repos: Target total repos
        min_stars: Minimum stars filter (uses config.min_stars if None)
    """
    bucket_starts = _generate_date_buckets(
        start="2015-01-01",
        end=datetime.utcnow().strftime("%Y-%m-%d"),
        months=6,
    )

    stars_desc = " (500+ stars)" if min_stars and min_stars >= 500 else ""
    logger.info(
        f"[{language_key}] Starting CHRONOLOGICAL collection{stars_desc} (legacy mode). "
        f"Target: {max_repos} NEW repos. Buckets: {len(bucket_starts)}. "
        f"⚠ WARNING: This may bias toward older repos. Consider stratified=True."
    )

    new_written = 0

    for bucket_start, bucket_end in bucket_starts:
        if new_written >= max_repos:
            break

        base_query = _build_query(config, min_stars=min_stars)
        query = f"{base_query} created:{bucket_start}..{bucket_end}"
        page = 1

        while new_written < max_repos:
            rl = _check_rate_limit()
            _wait_for_rate_limit(rl)

            logger.debug(f"[{language_key}] bucket {bucket_start} page {page}")
            data = _search_page(query, page=page)
            items = data.get("items", [])

            if not items:
                break

            with db_session() as conn:
                for repo in items:
                    if new_written >= max_repos:
                        break

                    excluded, reason = _is_excluded(repo, config)
                    if excluded:
                        logger.debug(f"  skip {repo['full_name']}: {reason}")
                        continue

                    record = {
                        "github_id": repo["id"],
                        "full_name": repo["full_name"],
                        "language": language_key,
                        "stars": repo.get("stargazers_count"),
                        "forks": repo.get("forks_count"),
                        "description": repo.get("description"),
                        "topics": json.dumps(repo.get("topics", [])),
                        "created_at": repo.get("created_at"),
                        "pushed_at": repo.get("pushed_at"),
                        "clone_url": repo.get("clone_url"),
                        "star_tier": star_tier(repo.get("stargazers_count") or 0),
                    }
                    _, is_new = upsert_repository(conn, record)
                    if is_new:
                        new_written += 1

            page += 1
            if page > 10:
                break

            time.sleep(REQUEST_DELAY)

        logger.info(
            f"[{language_key}] After bucket {bucket_start}: "
            f"{new_written} new repos collected"
        )

    logger.info(
        f"[{language_key}] Chronological collection complete. New repos: {new_written}"
    )
    return new_written


# ---------------------------------------------------------------------------
# Date bucket generator
# ---------------------------------------------------------------------------


def _generate_date_buckets(
    start: str, end: str, months: int = 6
) -> list[tuple[str, str]]:
    """
    Split [start, end] into overlapping date buckets of `months` months each.
    Returns a list of (bucket_start, bucket_end) string pairs in ISO format.
    """
    fmt = "%Y-%m-%d"
    current = datetime.strptime(start, fmt)
    end_dt = datetime.strptime(end, fmt)
    buckets = []

    while current < end_dt:
        # Approximate month arithmetic
        next_dt = current + timedelta(days=months * 30)
        bucket_end = min(next_dt, end_dt)
        buckets.append(
            (
                current.strftime(fmt),
                bucket_end.strftime(fmt),
            )
        )
        current = next_dt

    return buckets


# ---------------------------------------------------------------------------
# Convenience: collect all languages
# ---------------------------------------------------------------------------


def collect_all_languages(
    max_per_language: int | None = None,
    sort_by_stars: bool = True,
    stratified: bool = False,
) -> dict[str, int]:
    results = {}
    for lang in LANGUAGE_CONFIGS:
        count = collect_repos_for_language(
            lang,
            max_repos=max_per_language,
            sort_by_stars=sort_by_stars,
            stratified=stratified,
        )
        results[lang] = count
    return results
