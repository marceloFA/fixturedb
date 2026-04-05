"""
FixtureDB — Exploratory Data Analysis
======================================
Pipeline Status Breakdown
"""

import argparse
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from ..eda_common import (
    ROOT,
    DB_PATH,
    DEFAULT_OUT,
    STATUS_PALETTE,
    setup_style,
    save_or_show,
    load_db,
    has_data,
    qdf,
)


def plot_pipeline_status(conn, out_dir, show):
    repos = qdf(conn, "SELECT status FROM repositories")
    if repos.empty:
        print("  [skip] No repositories in DB yet.")
        return

    fig, ax = plt.subplots(figsize=(12, 6), facecolor="#FAFAFA")

    status_order = ["analysed", "skipped", "error", "cloned", "discovered"]
    status_counts = repos["status"].value_counts().reindex(status_order, fill_value=0)
    colours = [STATUS_PALETTE[s] for s in status_order]
    raw = [int(status_counts[s]) for s in status_order]
    total = sum(raw)

    # Filter out zero-count statuses for cleaner pie chart
    nonzero_statuses = []
    nonzero_counts = []
    nonzero_colours = []
    for status, count, color in zip(status_order, raw, colours):
        if count > 0:
            nonzero_statuses.append(status)
            nonzero_counts.append(count)
            nonzero_colours.append(color)

    # Create pie chart with counts in legend
    wedges, texts, autotexts = ax.pie(
        nonzero_counts,
        labels=None,
        colors=nonzero_colours,
        autopct="%1.1f%%",
        startangle=90,
        textprops={"fontsize": 10, "fontweight": "bold"},
    )

    # Make percentage text white and readable
    for autotext in autotexts:
        autotext.set_color("white")
        autotext.set_fontsize(10)
        autotext.set_fontweight("bold")

    # Create legend with status names and counts, plus total
    legend_labels = [
        f"{status.capitalize()}\n(n={count:,})"
        for status, count in zip(nonzero_statuses, nonzero_counts)
    ]

    # Add legend with wedges
    legend = ax.legend(
        wedges, legend_labels, fontsize=11, loc="center left", bbox_to_anchor=(1, 0.5)
    )

    # Add total text below legend
    fig.text(0.72, 0.08, f"Total: {total:,} repos", fontsize=11, fontweight="bold")

    ax.set_title("Pipeline Status Breakdown", fontsize=14, fontweight="bold", pad=20)

    plt.tight_layout()
    save_or_show(fig, "01b_pipeline_status", out_dir, show)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FixtureDB Pipeline Status Breakdown")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Base output directory")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    setup_style()
    conn = load_db(args.db)
    plot_pipeline_status(
        conn, Path(args.out) / datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), args.show
    )
