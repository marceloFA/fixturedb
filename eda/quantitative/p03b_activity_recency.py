"""
FixtureDB — Exploratory Data Analysis
======================================
Repository Activity Recency
"""

import argparse
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from ..eda_common import (
    ROOT, DB_PATH, DEFAULT_OUT,
    LANG_PALETTE, LANG_ORDER,
    setup_style, save_or_show, load_db, has_data, qdf, lang_display
)


def plot_activity_recency(conn, out_dir, show):
    repos = qdf(
        conn,
        """
        SELECT language, pushed_at
        FROM repositories WHERE pushed_at IS NOT NULL
    """,
    )
    if repos.empty:
        print("  [skip] No date data.")
        return

    repos["days_since_push"] = (
        pd.Timestamp.now("UTC") - pd.to_datetime(repos["pushed_at"], errors="coerce")
    ).dt.days.clip(lower=0)

    present = [l for l in LANG_ORDER if l in repos["language"].values]

    fig, ax = plt.subplots(figsize=(10, 5), facecolor="#FAFAFA")

    plot_data = repos[repos["language"].isin(present)].copy()
    plot_data["years_since_push"] = plot_data["days_since_push"] / 365.25

    worst_idx = plot_data.groupby("language")["years_since_push"].idxmax()
    plot_data = plot_data.drop(index=worst_idx).reset_index(drop=True)

    sns.boxplot(
        data=plot_data,
        x="language",
        y="years_since_push",
        order=present,
        palette={l: LANG_PALETTE[l] for l in present},
        showfliers=False,
        linewidth=0.9,
        width=0.5,
        ax=ax,
    )
    ax.set_xticklabels([lang_display(l) for l in present])
    ax.set_xlabel("")
    ax.set_ylabel("Years Since Last Commit Push")
    ax.set_title("How Recently Were Repositories Active?", fontsize=14, fontweight="bold")
    ax.axhline(
        1.0, color="#888", linewidth=0.8, linestyle="--", alpha=0.7, label="1 year ago"
    )
    ax.legend(fontsize=9)

    plt.tight_layout()
    save_or_show(fig, "03b_activity_recency", out_dir, show)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FixtureDB Repository Activity Recency")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Base output directory")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    
    setup_style()
    conn = load_db(args.db)
    plot_activity_recency(conn, Path(args.out) / datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), args.show)
