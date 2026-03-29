"""
FixtureDB — Exploratory Data Analysis
======================================
Mock Styles & Techniques
"""

import argparse
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from ..eda_common import (
    ROOT, DB_PATH, DEFAULT_OUT,
    LANG_PALETTE, LANG_ORDER,
    setup_style, save_or_show, load_db, has_data, qdf, lang_display
)


def plot_mock_styles(conn, out_dir, show):
    if not has_data(conn, "mock_usages"):
        print("  [skip] No mock data yet. Run `python pipeline.py extract`.")
        return

    mock_styles = qdf(
        conn,
        """
        SELECT m.mock_style, r.language, COUNT(*) as count
        FROM mock_usages m
        JOIN repositories r ON m.repo_id = r.id
        WHERE r.status = 'analysed' AND m.mock_style IS NOT NULL
        GROUP BY r.language, m.mock_style
    """,
    )
    
    if mock_styles.empty:
        print("  [skip] No mock style data yet (run full pipeline to extract).")
        return

    fixtures = qdf(
        conn,
        """
        SELECT r.language
        FROM fixtures f
        JOIN repositories r ON f.repo_id = r.id
        WHERE r.status = 'analysed'
    """,
    )
    present = [l for l in LANG_ORDER if l in fixtures["language"].values]

    fig, ax = plt.subplots(figsize=(12, 5), facecolor="#FAFAFA")

    style_pivot = (
        mock_styles[mock_styles["language"].isin(present)]
        .pivot(index="language", columns="mock_style", values="count")
        .reindex(present)
        .fillna(0)
    )
    style_pct = style_pivot.div(style_pivot.sum(axis=1), axis=0) * 100
    styles = list(style_pct.columns)
    
    style_colors = {
        "mock": "#FF6B6B",
        "stub": "#4ECDC4",
        "spy": "#FFE66D",
        "fake": "#95E1D3",
    }
    
    y_pos = range(len(present))
    for i, lang in enumerate(present):
        left = 0.0
        for style in styles:
            w = style_pct.loc[lang, style]
            color = style_colors.get(style, "#CCCCCC")
            if w > 0:
                ax.barh(i, w, left=left, color=color, height=0.55, zorder=3)
                if w > 5:
                    ax.text(
                        left + w / 2,
                        i,
                        style.capitalize(),
                        ha="center",
                        va="center",
                        fontsize=9,
                        color="white" if style != "spy" else "#333",
                        fontweight="bold",
                    )
            left += w
    
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels([lang_display(l) for l in present])
    ax.set_xlabel("Distribution of mock techniques (%)")
    ax.set_xlim(0, 105)
    ax.set_title("What Mock Techniques Do Developers Prefer?", fontsize=14, fontweight="bold")

    plt.tight_layout()
    save_or_show(fig, "07c_mock_styles", out_dir, show)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FixtureDB Mock Styles & Techniques")
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Base output directory")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    
    setup_style()
    conn = load_db(args.db)
    plot_mock_styles(conn, Path(args.out) / datetime.now().strftime("%Y-%m-%d_%H-%M-%S"), args.show)
