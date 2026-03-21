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

from corpus.config import LANGUAGE_CONFIGS, CLONE_BATCH_SIZE
from corpus.db import initialise_db, db_session, get_corpus_stats
from corpus.search import collect_repos_for_language, collect_all_languages
from corpus.cloner import clone_pending_repos
from corpus.extractor import extract_all_cloned
from corpus.classifier import classify_all
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

    if language:
        if language not in LANGUAGE_CONFIGS:
            print(f"Unknown language '{language}'. "
                  f"Choose from: {list(LANGUAGE_CONFIGS)}")
            sys.exit(1)
        count = collect_repos_for_language(language, max_repos=max_repos)
        print(f"✓ {count} repos discovered for {language}")
    else:
        results = collect_all_languages(max_per_language=max_repos)
        for lang, count in results.items():
            print(f"  {lang:12s}: {count} repos")


def cmd_clone(args):
    # batch=None means "process all pending repos"
    # batch=N means "process at most N repos this run" (incremental mode)
    batch = getattr(args, "batch", None)
    summary = clone_pending_repos(
        language=args.language,
        batch_size=batch,
    )
    print(f"✓ Clone batch done: {summary}")


def cmd_extract(args):
    totals = extract_all_cloned(language=args.language)
    print(f"✓ Extraction done: {totals}")


def cmd_run(args):
    """Run all phases sequentially."""
    print("── Phase 0: Initialise ─────────────────────────────")
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

    print("\n── Done ─────────────────────────────────────────────")
    cmd_stats(args)


def cmd_classify(args):
    counts = classify_all(overwrite=args.overwrite)
    print(f"✓ Domain classification done: {counts}")


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
    status_keys = ["repos_discovered", "repos_cloned",
                   "repos_analysed", "repos_skipped", "repos_error"]
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
    p_search.add_argument("--language", choices=list(LANGUAGE_CONFIGS),
                          help="Limit to one language (default: all)")
    p_search.add_argument("--max", type=int, default=None,
                          help="Max repos per language")

    # clone
    p_clone = sub.add_parser("clone", help="Clone discovered repos")
    p_clone.add_argument("--language", choices=list(LANGUAGE_CONFIGS))
    p_clone.add_argument("--batch", type=int, default=CLONE_BATCH_SIZE,
                         help="Max repos to clone in this run")

    # extract
    p_extract = sub.add_parser("extract", help="Extract fixtures from cloned repos")
    p_extract.add_argument("--language", choices=list(LANGUAGE_CONFIGS))

    # run
    p_run = sub.add_parser("run", help="Run full pipeline end-to-end")
    p_run.add_argument("--language", choices=list(LANGUAGE_CONFIGS),
                       help="Limit to one language")
    p_run.add_argument("--max", type=int, default=None,
                       help="Max repos per language to search")

    # classify
    p_classify = sub.add_parser("classify", help="Label repo domains (web/cli/data/…)")
    p_classify.add_argument("--overwrite", action="store_true",
                            help="Re-classify already-labelled repos")

    # export
    p_export = sub.add_parser("export", help="Export dataset for Zenodo deposit")
    p_export.add_argument("--version", default="1.0", help="Version string (default: 1.0)")
    p_export.add_argument("--include-source", action="store_true",
                          help="Include raw_source column in fixtures CSV")

    # validate
    p_validate = sub.add_parser("validate",
                                 help="Sample fixtures for manual precision/recall validation")
    p_validate.add_argument("--sample", type=int, default=50,
                             help="Fixtures to sample per language (default: 50)")
    p_validate.add_argument("--compute", metavar="CSV",
                             help="Path to a completed validation CSV — compute metrics")

    # stats
    sub.add_parser("stats", help="Print corpus statistics")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

COMMAND_MAP = {
    "init":     cmd_init,
    "search":   cmd_search,
    "clone":    cmd_clone,
    "extract":  cmd_extract,
    "classify": cmd_classify,
    "export":   cmd_export,
    "validate": cmd_validate,
    "run":      cmd_run,
    "stats":    cmd_stats,
}

if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    COMMAND_MAP[args.command](args)
