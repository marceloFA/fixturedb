"""
FixtureDB — Exploratory Data Analysis
======================================
Complexity Metrics: Cyclomatic vs Cognitive Complexity
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

from ..eda_common import (
    LANG_PALETTE,
    LANG_ORDER,
    setup_style,
    save_or_show,
    load_db,
    has_data,
    qdf,
    lang_display,
    DB_PATH,
    DEFAULT_OUT,
)


def plot_complexity_metrics(conn, out_dir, show):
    """Compare cyclomatic vs cognitive complexity across languages."""
    if not has_data(conn, "fixtures"):
        print("  [skip] No fixture data yet. Run `python pipeline.py extract`.")
        return

    fixtures = qdf(
        conn,
        """
        SELECT r.language, f.cyclomatic_complexity, f.cognitive_complexity, f.loc
        FROM fixtures f
        JOIN repositories r ON f.repo_id = r.id
        WHERE r.status = 'analysed'
          AND f.cyclomatic_complexity > 0
          AND f.cognitive_complexity > 0
    """,
    )

    if fixtures.empty:
        print("  [skip] No complexity data.")
        return

    present = [l for l in LANG_ORDER if l in fixtures["language"].unique()]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), facecolor="#FAFAFA")
    axes = axes.flatten()

    # Panel 1: Cyclomatic Complexity Distribution
    ax = axes[0]
    for lang in present:
        data = fixtures[fixtures["language"] == lang]["cyclomatic_complexity"].values
        # Clip extreme outliers for better visualization
        data_clipped = np.clip(data, 0, np.percentile(data, 95))
        ax.hist(
            data_clipped,
            bins=25,
            alpha=0.6,
            label=lang_display(lang),
            color=LANG_PALETTE[lang],
            edgecolor="black",
            linewidth=0.5,
        )
    ax.set_xlabel("Cyclomatic Complexity", fontsize=11)
    ax.set_ylabel("Count", fontsize=11)
    ax.set_title("(a) Cyclomatic Complexity Distribution", fontsize=12, fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.3, linestyle="--")

    # Panel 2: Cognitive Complexity Distribution
    ax = axes[1]
    for lang in present:
        data = fixtures[fixtures["language"] == lang]["cognitive_complexity"].values
        data_clipped = np.clip(data, 0, np.percentile(data, 95))
        ax.hist(
            data_clipped,
            bins=25,
            alpha=0.6,
            label=lang_display(lang),
            color=LANG_PALETTE[lang],
            edgecolor="black",
            linewidth=0.5,
        )
    ax.set_xlabel("Cognitive Complexity", fontsize=11)
    ax.set_ylabel("Count", fontsize=11)
    ax.set_title("(b) Cognitive Complexity Distribution", fontsize=12, fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.3, linestyle="--")

    # Panel 3: Scatter plot - Cyclomatic vs Cognitive
    ax = axes[2]
    for lang in present:
        sub = fixtures[fixtures["language"] == lang]
        # Sample if too many points
        if len(sub) > 5000:
            sub = sub.sample(5000, random_state=42)
        ax.scatter(
            sub["cyclomatic_complexity"],
            sub["cognitive_complexity"],
            alpha=0.4,
            s=30,
            color=LANG_PALETTE[lang],
            label=lang_display(lang),
        )
    ax.set_xlabel("Cyclomatic Complexity", fontsize=11)
    ax.set_ylabel("Cognitive Complexity", fontsize=11)
    ax.set_title("(c) Cyclomatic vs Cognitive (sample)", fontsize=12, fontweight="bold")
    ax.legend(fontsize=10, loc="upper left")
    ax.grid(alpha=0.3, linestyle="--")
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 30)

    # Panel 4: Box plots side-by-side
    ax = axes[3]
    x_pos = np.arange(len(present))
    width = 0.35

    cyc_data = [
        fixtures[fixtures["language"] == l]["cyclomatic_complexity"].values for l in present
    ]
    cog_data = [
        fixtures[fixtures["language"] == l]["cognitive_complexity"].values for l in present
    ]

    bp1 = ax.boxplot(
        cyc_data,
        positions=x_pos - width / 2,
        widths=width,
        patch_artist=True,
        labels=[""] * len(present),
    )
    bp2 = ax.boxplot(
        cog_data,
        positions=x_pos + width / 2,
        widths=width,
        patch_artist=True,
        labels=[""] * len(present),
    )

    for patch in bp1["boxes"]:
        patch.set_facecolor("#A0A0A0")
        patch.set_alpha(0.7)
    for patch in bp2["boxes"]:
        patch.set_facecolor("#4488CC")
        patch.set_alpha(0.7)

    ax.set_xticks(x_pos)
    ax.set_xticklabels([lang_display(l) for l in present])
    ax.set_ylabel("Complexity Score", fontsize=11)
    ax.set_title("(d) Complexity Comparison by Language", fontsize=12, fontweight="bold")
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_ylim(0, 15)

    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#A0A0A0", alpha=0.7, label="Cyclomatic"),
        Patch(facecolor="#4488CC", alpha=0.7, label="Cognitive"),
    ]
    ax.legend(handles=legend_elements, fontsize=10, loc="upper right")

    fig.suptitle(
        "Fixture Complexity Metrics: Cyclomatic vs Cognitive",
        fontsize=14,
        fontweight="bold",
        y=0.995,
    )

    plt.tight_layout()
    save_or_show(fig, "04d_complexity_metrics", out_dir, show)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FixtureDB Complexity Metrics")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    setup_style()
    conn = load_db(args.db)
    plot_complexity_metrics(conn, args.out if not args.show else None, args.show)
    conn.close()
