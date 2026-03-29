"""
FixtureDB — Exploratory Data Analysis
======================================
Pipeline Status Breakdown
"""

import argparse
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from ..eda_common import (
    ROOT, DB_PATH, DEFAULT_OUT,
    STATUS_PALETTE,
    setup_style, save_or_show, load_db, has_data, qdf
)


def plot_pipeline_status(conn, out_dir, show):
    repos = qdf(conn, "SELECT status FROM repositories")
    if repos.empty:
        print("  [skip] No repositories in DB yet.")
        return

    fig, ax = plt.subplots(figsize=(10, 5), facecolor="#FAFAFA")

    status_order = ["analysed", "skipped", "error", "cloned", "discovered"]
    status_counts = repos["status"].value_counts().reindex(status_order, fill_value=0)
    colours = [STATUS_PALETTE[s] for s in status_order]
    raw = [int(status_counts[s]) for s in status_order]

    bars = ax.barh(status_order, raw, color=colours, zorder=3, height=0.55)

    x_max = max(raw) if max(raw) > 0 else 1
    for bar, v in zip(bars, raw):
        label = f"{v:,}" if v > 0 else "—"
        if v > x_max * 0.08:
            ax.text(
                bar.get_width() * 0.97,
                bar.get_y() + bar.get_height() / 2,
                label,
                va="center",
                ha="right",
                fontsize=9,
                fontweight="bold",
                color="white",
            )
        else:
            ax.text(
                x_max * 0.02,
                bar.get_y() + bar.get_height() / 2,
                label,
                va="center",
                ha="left",
                fontsize=9,
                fontweight="bold",
                color="#555",
            )

    ax.set_xlim(0, x_max * 1.05)
    ax.set_xlabel("Repositories")
    ax.set_title("Pipeline Status Breakdown", fontsize=14, fontweight="bold")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))

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
    plot_pipeline_status(conn, Path(args.out) / datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), args.show)
