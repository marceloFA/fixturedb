"""
FixtureDB — Exploratory Data Analysis
======================================
Individual plot script.
"""

import argparse
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

from eda_common import (
    ROOT, DB_PATH, DEFAULT_OUT,
    LANG_PALETTE, LANG_ORDER, STATUS_PALETTE,
    setup_style, save_or_show, load_db, has_data, qdf, lang_display
)

# -----------
# FIXTURE OVERVIEW
# -----------


def plot_fixture_overview(conn, out_dir, show):
    if not has_data(conn, "fixtures"):
        print("  [skip] No fixture data yet. Run `python pipeline.py extract`.")
        return

    fixtures = qdf(
        conn,
        """
        SELECT f.fixture_type, r.language, r.full_name
        FROM fixtures f
        JOIN repositories r ON f.repo_id = r.id
        WHERE r.status = 'analysed'
    """,
    )
    if fixtures.empty:
        print("  [skip] Fixture table is empty.")
        return

    present = [l for l in LANG_ORDER if l in fixtures["language"].values]

    fig, axes = plt.subplots(1, 2, figsize=(15, 5), facecolor="#FAFAFA")
    fig.suptitle("Fixture Overview", fontsize=14, fontweight="bold", y=1.02)

    # ── 6a: fixture count per repo — ridge plot (log scale) ───────────────────
    ax = axes[0]
    per_repo = (
        fixtures.groupby(["language", "full_name"])
        .size()
        .reset_index(name="fixture_count")
    )
    per_repo = per_repo[per_repo["language"].isin(present)]
    per_repo["fixture_count"] = per_repo["fixture_count"].clip(lower=1)
    per_repo["log_count"] = np.log10(per_repo["fixture_count"])

    # Ridge plot: one density curve per language
    from scipy import stats
    
    x_range = np.logspace(
        np.log10(per_repo["fixture_count"].min()),
        np.log10(per_repo["fixture_count"].max()),
        200
    )
    x_log = np.log10(x_range)
    
    y_offset = 0
    for i, lang in enumerate(present):
        sub = per_repo[per_repo["language"] == lang]["log_count"].values
        if len(sub) > 1:
            kde = stats.gaussian_kde(sub, bw_method=0.15)
            density = kde(x_log)
            # Normalize density for stacking
            density = density / density.max() * 0.8
            
            # Fill area under curve
            ax.fill_between(
                x_range,
                y_offset,
                y_offset + density,
                color=LANG_PALETTE[lang],
                alpha=0.7,
                label=lang_display(lang),
                zorder=len(present) - i,
            )
            # Edge line
            ax.plot(
                x_range,
                y_offset + density,
                color=LANG_PALETTE[lang],
                linewidth=1.2,
                zorder=len(present) - i + 1,
            )
            y_offset += 1
    
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: str(int(v)) if v >= 1 else "")
    )
    ax.set_xlabel("Fixtures per Repository (log scale)")
    ax.set_ylabel("Language (density, offset)")
    ax.set_title("How Many Fixtures Does Each Repo Have?\n(ridge plot, log scale)")
    ax.set_yticks([])
    ax.legend(fontsize=9, loc="upper right")

    # ── 6b: fixture type breakdown — single-hue heatmap ──────────────────────
    ax2 = axes[1]
    type_counts = (
        fixtures[fixtures["language"].isin(present)]
        .groupby(["language", "fixture_type"])
        .size()
        .reset_index(name="n")
    )
    pivot = (
        type_counts.pivot(index="language", columns="fixture_type", values="n")
        .reindex(present)
        .fillna(0)
    )
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100

    annot = np.empty(pivot_pct.shape, dtype=object)
    for i, lang in enumerate(present):
        for j, ftype in enumerate(pivot_pct.columns):
            annot[i, j] = f"{pivot_pct.iloc[i, j]:.0f}%"

    sns.heatmap(
        pivot_pct,
        annot=annot,
        fmt="",
        cmap="YlOrBr",
        linewidths=0.4,
        linecolor="#E0E0E0",
        cbar_kws={"label": "% of language fixtures"},
        annot_kws={"size": 8},
        ax=ax2,
    )
    ax2.set_title(
        "Fixture Type Breakdown per Language\n" "(% share of each detection pattern)"
    )
    ax2.set_yticklabels([lang_display(l) for l in present], rotation=0)
    ax2.set_xticklabels(
        [c.replace("_", "\n") for c in pivot_pct.columns],
        rotation=30,
        ha="right",
        fontsize=8,
    )
    ax2.set_xlabel("")
    ax2.set_ylabel("")

    plt.tight_layout()
    save_or_show(fig, "06_fixture_overview", out_dir, show)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FixtureDB Fixture Overview")
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

    conn = load_db(Path(args.db))
    setup_style()
    
    print(f"\n[Fixture Overview]")
    plot_fixture_overview(conn, out_dir, args.show)
    
    conn.close()
    print("Done\n")
