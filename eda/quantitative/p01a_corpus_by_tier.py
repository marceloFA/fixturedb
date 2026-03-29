"""
FixtureDB — Exploratory Data Analysis
======================================
Repos by Language & Star Tier
"""

import argparse
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from ..eda_common import (
    ROOT, DB_PATH, DEFAULT_OUT,
    LANG_PALETTE, LANG_ORDER,
    setup_style, save_or_show, load_db, has_data, qdf, lang_display
)


def plot_corpus_by_tier(conn, out_dir, show):
    repos = qdf(conn, "SELECT language, star_tier FROM repositories")
    if repos.empty:
        print("  [skip] No repositories in DB yet.")
        return

    present = [l for l in LANG_ORDER if l in repos["language"].values]

    fig, ax = plt.subplots(figsize=(10, 5), facecolor="#FAFAFA")
    fig.suptitle("Repositories by Language & Star Tier", fontsize=14, fontweight="bold", y=1.02)

    tier_alpha = {"core": 1.0, "extended": 0.40}
    tier_label = {"core": "≥500 stars (core)", "extended": "100–499 stars (extended)"}
    tier_order = ["core", "extended"]

    bottoms = [0] * len(present)
    for tier in tier_order:
        vals = [
            int(repos.query("language==@lang and star_tier==@tier").shape[0])
            for lang in present
        ]
        for i, (lang, v) in enumerate(zip(present, vals)):
            colour = LANG_PALETTE[lang]
            bar = ax.bar(
                i,
                v,
                bottom=bottoms[i],
                width=0.6,
                color=colour,
                alpha=tier_alpha[tier],
                zorder=3,
                label=tier_label[tier] if i == 0 else "_nolegend_",
            )
            if v > 0:
                ax.text(
                    i,
                    bottoms[i] + v / 2,
                    str(v),
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white",
                    fontweight="bold",
                )
        bottoms = [b + v for b, v in zip(bottoms, vals)]

    import matplotlib.patches as mpatches

    lang_handles = [
        mpatches.Patch(color=LANG_PALETTE[l], label=lang_display(l)) for l in present
    ]
    tier_handles = [
        mpatches.Patch(color="#888888", alpha=tier_alpha[t], label=tier_label[t])
        for t in tier_order
    ]
    ax.legend(
        handles=lang_handles + tier_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=4,
        fontsize=8,
    )
    ax.set_xticks(range(len(present)))
    ax.set_xticklabels([lang_display(l) for l in present])
    ax.set_ylabel("Repositories")
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    plt.tight_layout()
    save_or_show(fig, "01a_corpus_by_tier", out_dir, show)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FixtureDB Corpus by Tier")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Base output directory")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    
    setup_style()
    conn = load_db(args.db)
    plot_corpus_by_tier(conn, Path(args.out) / datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), args.show)
