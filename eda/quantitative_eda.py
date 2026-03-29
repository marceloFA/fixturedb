"""
FixtureDB — Quantitative EDA
============================
Analysis-ready statistical plots for publication in ICSME Data Showcase track.

Only includes purely quantitative and statistical results that do not depend
on subjective interpretation of the data.

Usage:
    python quantitative_eda.py                    # all plots → output/eda/<timestamp>/
    python quantitative_eda.py --out figures/     # custom base output directory
    python quantitative_eda.py --show             # display interactively instead of saving
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from .eda_common import load_db, setup_style

# Import plot functions from quantitative submodule
from .quantitative.p01a_corpus_by_tier import plot_corpus_by_tier
from .quantitative.p01b_pipeline_status import plot_pipeline_status
from .quantitative.p02_star_distribution import plot_star_distribution
from .quantitative.p03a_creation_timeline import plot_creation_timeline
from .quantitative.p03b_activity_recency import plot_activity_recency
from .quantitative.p05_stars_vs_forks import plot_fork_star_ratio
from .quantitative.p06a_fixtures_per_repo import plot_fixtures_per_repo
from .quantitative.p06b_fixture_scope import plot_fixture_scope
from .quantitative.p07a_mock_adoption import plot_mock_adoption
from .quantitative.p07b_framework_diversity import plot_framework_diversity
from .quantitative.p07c_mock_styles import plot_mock_styles

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "corpus.db"
DEFAULT_OUT = ROOT / "output" / "eda" / "quantitative"


def main():
    parser = argparse.ArgumentParser(
        description="FixtureDB Quantitative EDA — ICSME Data Showcase Track"
    )
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Base output directory")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    if args.show:
        out_dir = None
    else:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_dir = Path(args.out) / ts
        out_dir.mkdir(parents=True, exist_ok=True)
        latest = Path(args.out) / "latest"
        if latest.exists() or latest.is_symlink():
            latest.unlink()
        try:
            latest.symlink_to(ts)
        except (OSError, NotImplementedError):
            pass

    conn = load_db(Path(args.db))
    setup_style()

    total = pd.read_sql_query("SELECT COUNT(*) n FROM repositories", conn).iloc[0]["n"]
    analysed = pd.read_sql_query(
        "SELECT COUNT(*) n FROM repositories WHERE status='analysed'", conn
    ).iloc[0]["n"]
    
    print(f"\nFixtureDB Quantitative EDA — {int(total):,} repos  ({int(analysed):,} analysed)")
    print(f"Track: ICSME Data Showcase (no subjective interpretation)")
    print(f"Output → {out_dir or 'screen'}\n")

    # Quantitative plots only (no subjectivity bias)
    plots = [
        ("Corpus by Tier", plot_corpus_by_tier),
        ("Pipeline Status", plot_pipeline_status),
        ("Star Distribution", plot_star_distribution),
        ("Creation Timeline", plot_creation_timeline),
        ("Activity Recency", plot_activity_recency),
        ("Stars vs Forks", plot_fork_star_ratio),
        ("Fixtures per Repo", plot_fixtures_per_repo),
        ("Fixture Scope", plot_fixture_scope),
        ("Mock Adoption", plot_mock_adoption),
        ("Framework Diversity", plot_framework_diversity),
        ("Mock Styles", plot_mock_styles),
    ]

    for name, fn in plots:
        print(f"[{name}]")
        fn(conn, out_dir, args.show)

    conn.close()
    print("\n✓ Done")


if __name__ == "__main__":
    main()
