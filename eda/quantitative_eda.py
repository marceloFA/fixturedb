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

from eda_common import load_db, setup_style

# Import plot functions from quantitative submodule
from quantitative.p01_corpus_composition import plot_corpus_composition
from quantitative.p02_star_distribution import plot_star_distribution
from quantitative.p03_age_and_activity import plot_age_and_activity
from quantitative.p05_stars_vs_forks import plot_fork_star_ratio
from quantitative.p06_fixture_overview import plot_fixture_overview
from quantitative.p07_mock_prevalence import plot_mock_prevalence

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
        ("Corpus Composition", plot_corpus_composition),
        ("Star Distribution", plot_star_distribution),
        ("Age & Activity", plot_age_and_activity),
        ("Stars vs Forks", plot_fork_star_ratio),
        ("Fixture Overview", plot_fixture_overview),
        ("Mock Prevalence", plot_mock_prevalence),
    ]

    for name, fn in plots:
        print(f"[{name}]")
        fn(conn, out_dir, args.show)

    conn.close()
    print("\n✓ Done")


if __name__ == "__main__":
    main()
