"""
Shared utilities for FixtureDB EDA plots
"""

import sqlite3
import sys
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent  # Up one level from eda/ to workspace root
DB_PATH = ROOT / "data" / "corpus.db"
DEFAULT_OUT = ROOT / "output" / "eda"

# ---------------------------------------------------------------------------
# Palettes
# Language colours are the single source of truth for language identity.
# They are ONLY used when color = language. Any other categorical dimension
# uses sequential single-hue shades (no independent colour vocabulary).
# ---------------------------------------------------------------------------

LANG_PALETTE = {
    "python": "#4C9BE8",
    "java": "#E8834C",
    "javascript": "#E8C94C",
    "go": "#A04CE8",
    "csharp": "#2ECC71",
}
LANG_ORDER = ["python", "java", "javascript", "go", "csharp"]

STATUS_PALETTE = {
    "discovered": "#B0BEC5",
    "cloned": "#64B5F6",
    "analysed": "#81C784",
    "skipped": "#FFB74D",
    "error": "#E57373",
}

# ---------------------------------------------------------------------------
# Global style
# ---------------------------------------------------------------------------


def setup_style() -> None:
    sns.set_theme(
        style="whitegrid",
        context="paper",
        font="DejaVu Sans",
        rc={
            "figure.facecolor": "#FAFAFA",
            "axes.facecolor": "#FAFAFA",
            "grid.color": "#E8E8E8",
            "grid.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "axes.spines.bottom": True,
            "axes.linewidth": 0.8,
            "xtick.bottom": True,
            "ytick.left": False,
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "legend.frameon": False,
            "figure.dpi": 150,
        },
    )


def save_or_show(fig, name, out_dir, show):
    if show:
        plt.show()
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{name}.png"
        fig.savefig(path, bbox_inches="tight", dpi=180, facecolor=fig.get_facecolor())
        try:
            display = path.relative_to(ROOT)
        except ValueError:
            display = path
        print(f"  ✓ {display}")
    plt.close(fig)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def load_db(db_path):
    if not db_path.exists():
        print(f"[error] Database not found at {db_path}")
        sys.exit(1)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def has_data(conn, table, condition="1=1"):
    try:
        r = conn.execute(f"SELECT COUNT(*) n FROM {table} WHERE {condition}").fetchone()
        return r["n"] > 0
    except Exception:
        return False


def qdf(conn, query):
    df = pd.read_sql_query(query, conn)
    # Normalize language names: combine typescript with javascript
    if "language" in df.columns:
        df["language"] = df["language"].replace("typescript", "javascript")
    return df


def lang_display(lang):
    """Convert language internal name to display name (capitalize + JS+TS)."""
    if lang == "javascript":
        return "JS+TS"
    return lang.capitalize()
