"""
GitHub search layer.

Searches the GitHub REST API for repositories matching per-language criteria,
applies exclusion filters, and writes candidate repos to the database.

Usage:
    python -m scripts.collect_repos --language python --max 200
"""

import time
import json
import logging
from datetime import datetime, timedelta

import requests

from corpus.config import (
    GITHUB_TOKEN,
    GITHUB_SEARCH_URL,
    GITHUB_RATE_LIMIT_URL,
    REQUEST_DELAY,
    LANGUAGE_CONFIGS,
    EXCLUSION_KEYWORDS,
    LanguageConfig,
    star_tier,
)
from corpus.db import db_session, upsert_repository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------

def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
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
        logger.info(f"Rate limit low ({remaining} remaining). Sleeping {sleep_secs:.0f}s.")
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
    text = " ".join(topics + [(repo.get("description") or "")])
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


def _build_query(config: LanguageConfig) -> str:
    """
    Build the GitHub search query string for a given language.

    We split the search into date-range buckets to work around the 1,000-result
    cap that GitHub imposes per query. Each bucket covers ~6 months, going back
    far enough to collect repositories created since 2015.
    """
    return (
        f"language:{config.github_language} "
        f"stars:>={config.min_stars} "
        f"fork:false "
        f"is:public"
    )


def collect_repos_for_language(
    language_key: str,
    max_repos: int | None = None,
) -> int:
    """
    Search GitHub for repositories in the given language and persist them
    to the database. Returns the number of new repos written.

    To work around GitHub's 1,000-result cap we bucket by creation date.
    """
    config = LANGUAGE_CONFIGS[language_key]
    max_repos = max_repos or config.target_repos
    written = 0

    # Date buckets: split search into ~6-month windows going back to 2015
    # This is the standard trick to exceed the 1000-result search limit.
    bucket_starts = _generate_date_buckets(
        start="2015-01-01",
        end=datetime.utcnow().strftime("%Y-%m-%d"),
        months=6,
    )

    logger.info(
        f"[{language_key}] Starting collection. Target: {max_repos} repos. "
        f"Buckets: {len(bucket_starts)}"
    )

    for bucket_start, bucket_end in bucket_starts:
        if written >= max_repos:
            break

        base_query = _build_query(config)
        query = f"{base_query} created:{bucket_start}..{bucket_end}"
        page = 1

        while written < max_repos:
            rl = _check_rate_limit()
            _wait_for_rate_limit(rl)

            logger.debug(f"[{language_key}] bucket {bucket_start} page {page}")
            data = _search_page(query, page=page)
            items = data.get("items", [])

            if not items:
                break

            with db_session() as conn:
                for repo in items:
                    if written >= max_repos:
                        break

                    excluded, reason = _is_excluded(repo, config)
                    if excluded:
                        logger.debug(f"  skip {repo['full_name']}: {reason}")
                        continue

                    record = {
                        "github_id":   repo["id"],
                        "full_name":   repo["full_name"],
                        "language":    language_key,
                        "stars":       repo.get("stargazers_count"),
                        "forks":       repo.get("forks_count"),
                        "description": repo.get("description"),
                        "topics":      json.dumps(repo.get("topics", [])),
                        "created_at":  repo.get("created_at"),
                        "pushed_at":   repo.get("pushed_at"),
                        "clone_url":   repo.get("clone_url"),
                        "star_tier":   star_tier(repo.get("stargazers_count") or 0),
                    }
                    upsert_repository(conn, record)
                    written += 1

            page += 1
            # GitHub search allows max 10 pages of 100 = 1000 results per query
            if page > 10:
                break

            time.sleep(REQUEST_DELAY)

        logger.info(f"[{language_key}] After bucket {bucket_start}: {written} repos collected")

    logger.info(f"[{language_key}] Collection complete. Total: {written} repos")
    return written


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
        buckets.append((
            current.strftime(fmt),
            bucket_end.strftime(fmt),
        ))
        current = next_dt

    return buckets


# ---------------------------------------------------------------------------
# Convenience: collect all languages
# ---------------------------------------------------------------------------

def collect_all_languages(max_per_language: int | None = None) -> dict[str, int]:
    results = {}
    for lang in LANGUAGE_CONFIGS:
        count = collect_repos_for_language(lang, max_repos=max_per_language)
        results[lang] = count
    return results