#!/usr/bin/env python3
"""
fixture-corpus — corpus collection pipeline CLI

Commands
--------
  init          Initialise the SQLite database
  search        Search GitHub and write candidate repos to DB
  clone         Clone repos in 'discovered' status
  extract       Extract fixtures from repos in 'cloned' status
  run           Run the full pipeline end-to-end
  stats         Print current corpus statistics

Examples
--------
  # Full pipeline for Python only, 50 repos
  python pipeline.py run --language python --max 50

  # Search phase only, all languages
  python pipeline.py search --max 200

  # Check what we have so far
  python pipeline.py stats
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent))

from corpus.config import (
    LANGUAGE_CONFIGS,
    CLONE_BATCH_SIZE,
    DISCOVERY_SURVIVAL_RATE,
    DISCOVERY_SAFETY_BUFFER,
    MAX_DISCOVERIES_PER_ITERATION,
    MAX_REPOS_PER_ITERATION,
    LANGUAGE_SURVIVAL_RATES,
)
from corpus.db import (
    initialise_db,
    db_is_initialised,
    db_session,
    get_corpus_stats,
    get_analyzed_count_by_language,
    get_analyzed_count_for_language,
    get_discovered_count_for_language,
    get_survival_rate_for_language,
)
from corpus.search import collect_repos_for_language, collect_all_languages
from corpus.cloner import clone_pending_repos, cleanup_stale_clones
from corpus.extractor import extract_all_cloned
from corpus.classifier import classify_all
from corpus.fixture_classifier import categorize_all
from corpus.exporter import export_dataset
from corpus.validator import generate_sample, compute_metrics

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/pipeline.log"),
    ],
)
logger = logging.getLogger("pipeline")


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_init(args):
    initialise_db()
    print("✓ Database initialised.")


def cmd_search(args):
    language = args.language
    max_repos = args.max
    sort_by_stars = not getattr(args, "stratified", False)  # Default to True unless --stratified is passed
    stratified = getattr(args, "stratified", False)

    if language:
        if language not in LANGUAGE_CONFIGS:
            print(
                f"Unknown language '{language}'. "
                f"Choose from: {list(LANGUAGE_CONFIGS)}"
            )
            sys.exit(1)
        count = collect_repos_for_language(language, max_repos=max_repos, sort_by_stars=sort_by_stars, stratified=stratified)
        print(f"✓ {count} repos discovered for {language}")
    else:
        results = collect_all_languages(max_per_language=max_repos, sort_by_stars=sort_by_stars, stratified=stratified)
        for lang, count in results.items():
            print(f"  {lang:12s}: {count} repos")



def cmd_cleanup(args):
    dry_run = getattr(args, "dry_run", False)
    counts = cleanup_stale_clones(dry_run=dry_run)
    verb = "Would remove" if dry_run else "Removed"
    print(f"✓ Cleanup done.")
    print(f"  {verb} {counts['removed']} stale clone(s)")
    print(f"  {verb} {counts['orphaned']} orphaned clone(s)")
    print(f"  Kept {counts['kept']} valid clone(s) (awaiting extraction)")


def cmd_clone(args):
    # batch=None means "process all pending repos"
    # batch=N means "process at most N repos this run" (incremental mode)
    batch = getattr(args, "batch", None)
    summary = clone_pending_repos(
        language=args.language,
        batch_size=batch,
    )
    print(f"✓ Clone batch done: {summary}")


def cmd_extract(args, target_analyzed: int | None = None):
    """Extract fixtures from cloned repos, optionally stopping early when target is reached."""
    totals = extract_all_cloned(language=args.language, target_analyzed=target_analyzed)
    early_stopped = totals.pop("early_stopped", False)
    print(f"✓ Extraction done: {totals} (early_stopped={early_stopped})")
    return early_stopped


def cmd_run(args):
    """Run all phases sequentially."""
    print("── Phase 0: Initialise ─────────────────────────────")
    if db_is_initialised():
        print("  Database already initialised — skipping.")
    else:
        cmd_init(args)

    print("\n── Phase 1: Search GitHub ──────────────────────────")
    cmd_search(args)

    print("\n── Phase 2: Clone repositories ─────────────────────")
    # Override batch to None so ALL discovered repos are cloned, not just
    # the default batch of 50. The --batch flag on `run` is intentionally
    # removed — use `clone --batch N` for incremental operation instead.
    args.batch = None
    cmd_clone(args)

    print("\n── Phase 3: Extract fixtures ───────────────────────")
    cmd_extract(args)

    print("\n── Phase 4: Classify domains ───────────────────────")
    args.overwrite = False
    cmd_classify(args)

    print("\n── Phase 5: Categorize fixtures ────────────────────")
    args.overwrite = False
    cmd_categorize(args)

    print("\n── Done ─────────────────────────────────────────────")
    cmd_stats(args)


def cmd_classify(args):
    counts = classify_all(overwrite=args.overwrite)
    print(f"✓ Domain classification done: {counts}")


def cmd_categorize(args):
    counts = categorize_all(overwrite=args.overwrite)
    print(f"✓ Fixture categorization done: {counts}")


def cmd_collect(args):
    """
    Automated collection for a single language until target analyzed repos reached.
    
    This command loops: search → clone → extract until the target count of
    successfully analyzed repos (status='analysed') is reached for the language.
    
    Recommended usage:
      python pipeline.py collect --language python --target 1500
      python pipeline.py collect --language java --target 1500
    """
    language = args.language
    target_analyzed = args.target
    
    if not language:
        print("ERROR: --language is required for collect command")
        sys.exit(1)
    
    if language not in LANGUAGE_CONFIGS:
        print(f"Unknown language '{language}'. Choose from: {list(LANGUAGE_CONFIGS)}")
        sys.exit(1)
    
    if not target_analyzed or target_analyzed < 1:
        print("ERROR: --target must be a positive integer")
        sys.exit(1)
    
    stratified = getattr(args, "stratified", False)
    
    # Initialize DB if needed
    if not db_is_initialised():
        print("── Initializing database ──")
        cmd_init(args)
    
    iteration = 0
    while True:
        iteration += 1
        
        with db_session() as conn:
            current_analyzed = get_analyzed_count_for_language(conn, language)
        
        print(f"\n{'='*60}")
        print(f"Collection Iteration {iteration} for {language}")
        print(f"  Current analyzed repos: {current_analyzed}/{target_analyzed}")
        print(f"{'='*60}")
        
        if current_analyzed >= target_analyzed:
            print(f"\n✓ TARGET REACHED: {language} has {current_analyzed} analyzed repos (≥{target_analyzed})")
            break
        
        # Check if there are already discovered repos waiting to be cloned
        with db_session() as conn:
            pending_discovered = get_discovered_count_for_language(conn, language)
        
        needed = target_analyzed - current_analyzed
        
        print(f"\n  Repos still needed: {needed}")
        print(f"  Pending discovered repos waiting: {pending_discovered}")
        
        if pending_discovered > 0:
            print(f"\n  → Processing {pending_discovered} pending discovered repos (skipping new search)...")
        else:
            # Only search if no pending repos
            # Get language-specific survival rate (from observed data or config)
            with db_session() as conn:
                observed_rate = get_survival_rate_for_language(conn, language)
                total_discovered = get_discovered_count_for_language(conn, language) + get_analyzed_count_for_language(conn, language)
            
            # Use observed rate if we have enough data (>20 discovered repos), else use config estimate
            if observed_rate > 0 and total_discovered >= 20:
                survival_rate = observed_rate
                rate_source = f"observed ({total_discovered} repos)"
            else:
                survival_rate = LANGUAGE_SURVIVAL_RATES.get(language, DISCOVERY_SURVIVAL_RATE)
                rate_source = "config estimate"
            
            # Based on empirical survival rate, calculate required discoveries
            # Apply safety buffer to account for estimation variability
            discoveries_needed = max(1, int(needed / survival_rate * DISCOVERY_SAFETY_BUFFER))
            # Cap discovery to match the cloning/extraction cap per iteration
            discover_target = min(discoveries_needed, MAX_REPOS_PER_ITERATION)
            
            print(f"  Discovery survival rate: {survival_rate*100:.1f}% ({rate_source})")
            print(f"  Safety buffer: {DISCOVERY_SAFETY_BUFFER:.0%}")
            print(f"  Calculated discoveries needed (with buffer): {discoveries_needed}")
            print(f"  Will discover this iteration: {discover_target} (capped at {MAX_DISCOVERIES_PER_ITERATION})")
            
            print(f"\n  → Searching for ~{discover_target} more repos (to reach analyzed target)...")
            args.max = discover_target
            args.stratified = stratified
            cmd_search(args)
        
        print(f"\n  → Cloning discovered repos (capped at {MAX_REPOS_PER_ITERATION} per iteration)...")
        args.batch = MAX_REPOS_PER_ITERATION  # cap repos per iteration
        cmd_clone(args)
        
        print(f"\n  → Extracting fixtures from cloned repos...")
        early_stopped = cmd_extract(args, target_analyzed=target_analyzed)
        
        # If we hit target during extraction, stop searching for more repos
        if early_stopped:
            print(f"\n  ✓ Target {target_analyzed} analyzed repos reached during extraction.")
            print(f"  Stopping collection loop.")
            break
    
    # Classify and categorize all extracted repos (once, after all iterations)
    print(f"\n  → Classifying domains for all extracted repos...")
    args.overwrite = False
    cmd_classify(args)
    
    print(f"\n  → Categorizing fixtures...")
    args.overwrite = False
    cmd_categorize(args)
    
    print(f"\n{'='*60}")
    print(f"Final status for {language}:")
    with db_session() as conn:
        analyzed = get_analyzed_count_for_language(conn, language)
        stats = get_corpus_stats(conn)
    
    print(f"  Analyzed repos: {analyzed}")
    print(f"  Total fixtures: {stats.get('fixtures', 0)}")
    print(f"  Total test files: {stats.get('test_files', 0)}")
    print(f"{'='*60}\n")


def cmd_export(args):
    zip_path = export_dataset(
        version=args.version,
        include_raw_source=args.include_source,
    )
    print(f"✓ Dataset exported to: {zip_path}")


def cmd_validate(args):
    if args.compute:
        from pathlib import Path

        results = compute_metrics(Path(args.compute))
        if results:
            print("✓ Metrics computed. See output above.")
    else:
        out = generate_sample(n_per_language=args.sample)
        if out:
            print(f"✓ Sample written to: {out}")


def cmd_stats(args):
    with db_session() as conn:
        stats = get_corpus_stats(conn)

    col_w = 22
    print(f"\n{'Corpus statistics':─<45}")
    status_keys = [
        "repos_discovered",
        "repos_cloned",
        "repos_analysed",
        "repos_skipped",
        "repos_error",
    ]
    for k in status_keys:
        label = k.replace("_", " ").capitalize()
        print(f"  {label:<{col_w}} {stats.get(k, 0):>8,}")
    print()
    for k in ("test_files", "fixtures", "mock_usages"):
        label = k.replace("_", " ").capitalize()
        print(f"  {label:<{col_w}} {stats.get(k, 0):>8,}")
    print()


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fixture corpus collection pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    sub.add_parser("init", help="Initialise the database")

    # search
    p_search = sub.add_parser("search", help="Search GitHub for repos")
    p_search.add_argument(
        "--language",
        choices=list(LANGUAGE_CONFIGS),
        help="Limit to one language (default: all)",
    )
    p_search.add_argument(
        "--max", type=int, default=None, help="Max repos per language"
    )
    p_search.add_argument(
        "--stratified",
        action="store_true",
        dest="stratified",
        help="Collect repos proportionally from each year (balanced sampling). Default: sort by star count (most stars first).",
    )

    # clone
    p_clone = sub.add_parser("clone", help="Clone discovered repos")
    p_clone.add_argument("--language", choices=list(LANGUAGE_CONFIGS))
    p_clone.add_argument(
        "--batch",
        type=int,
        default=CLONE_BATCH_SIZE,
        help="Max repos to clone in this run",
    )

    # extract
    p_extract = sub.add_parser("extract", help="Extract fixtures from cloned repos")
    p_extract.add_argument("--language", choices=list(LANGUAGE_CONFIGS))

    # run
    p_run = sub.add_parser("run", help="Run full pipeline end-to-end")
    p_run.add_argument(
        "--language", choices=list(LANGUAGE_CONFIGS), help="Limit to one language"
    )
    p_run.add_argument(
        "--max", type=int, default=None, help="Max repos per language to search"
    )
    p_run.add_argument(
        "--stratified",
        action="store_true",
        dest="stratified",
        help="Collect repos proportionally from each year (balanced sampling). Default: sort by star count (most stars first).",
    )

    # collect
    p_collect = sub.add_parser(
        "collect",
        help="Automated collection for one language until target analyzed repos reached",
    )
    p_collect.add_argument(
        "--language",
        choices=list(LANGUAGE_CONFIGS),
        required=True,
        help="Language to collect",
    )
    p_collect.add_argument(
        "--target",
        type=int,
        required=True,
        help="Target number of successfully analyzed repos (gold standard, post-filtering)",
    )
    p_collect.add_argument(
        "--stratified",
        action="store_true",
        dest="stratified",
        help="Collect repos proportionally from each year (balanced sampling). Default: sort by star count (most stars first).",
    )

    # cleanup
    p_cleanup = sub.add_parser(
        "cleanup", help="Remove stale clone directories from interrupted runs"
    )
    p_cleanup.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without deleting anything",
    )

    # classify
    p_classify = sub.add_parser("classify", help="Label repo domains (web/cli/data/…)")
    p_classify.add_argument(
        "--overwrite", action="store_true", help="Re-classify already-labelled repos"
    )

    # categorize
    p_categorize = sub.add_parser("categorize", help="Categorize fixtures by usage pattern (data_builder/service_setup/…)")
    p_categorize.add_argument(
        "--overwrite", action="store_true", help="Re-categorize already-categorized fixtures"
    )

    # export
    p_export = sub.add_parser("export", help="Export dataset for Zenodo deposit")
    p_export.add_argument(
        "--version", default="1.0", help="Version string (default: 1.0)"
    )
    p_export.add_argument(
        "--include-source",
        action="store_true",
        help="Include raw_source column in fixtures CSV",
    )

    # validate
    p_validate = sub.add_parser(
        "validate", help="Sample fixtures for manual precision/recall validation"
    )
    p_validate.add_argument(
        "--sample",
        type=int,
        default=50,
        help="Fixtures to sample per language (default: 50)",
    )
    p_validate.add_argument(
        "--compute",
        metavar="CSV",
        help="Path to a completed validation CSV — compute metrics",
    )

    # stats
    sub.add_parser("stats", help="Print corpus statistics")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

COMMAND_MAP = {
    "init": cmd_init,
    "search": cmd_search,
    "clone": cmd_clone,
    "extract": cmd_extract,
    "cleanup": cmd_cleanup,
    "classify": cmd_classify,
    "categorize": cmd_categorize,
    "collect": cmd_collect,
    "export": cmd_export,
    "validate": cmd_validate,
    "run": cmd_run,
    "stats": cmd_stats,
}

if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    COMMAND_MAP[args.command](args)
