"""
Manual validation scaffold.

Samples N fixtures per language from the database and exports them to a CSV
that you fill in manually (column: `is_true_fixture`, values: 1 or 0).

After filling in the CSV, run with --compute to calculate precision/recall.

Usage:
    # Step 1 — generate the sample
    python pipeline.py validate --sample 50

    # Step 2 — open validation/sample_<timestamp>.csv in a spreadsheet,
    #           read each raw_source, and set is_true_fixture to 1 or 0

    # Step 3 — compute precision/recall
    python pipeline.py validate --compute validation/sample_<timestamp>.csv
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from corpus.config import DB_PATH, ROOT_DIR

logger = logging.getLogger(__name__)

VALIDATION_DIR = ROOT_DIR / "validation"
VALIDATION_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------

def generate_sample(n_per_language: int = 50) -> Path:
    """
    Draw a stratified random sample of n_per_language fixtures per language.
    Exports to a CSV with an empty `is_true_fixture` column for manual review.
    Returns the CSV path.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    languages = [r[0] for r in conn.execute(
        "SELECT DISTINCT language FROM repositories WHERE status='analysed'"
    ).fetchall()]

    if not languages:
        logger.error("No analysed repositories found. Run extraction first.")
        conn.close()
        return None

    frames = []
    for lang in languages:
        rows = conn.execute("""
            SELECT
                f.id            AS fixture_id,
                r.language,
                r.full_name     AS repo,
                tf.relative_path AS file_path,
                f.fixture_type,
                f.name          AS fixture_name,
                f.start_line,
                f.loc,
                f.raw_source
            FROM fixtures f
            JOIN test_files tf   ON f.file_id  = tf.id
            JOIN repositories r  ON f.repo_id  = r.id
            WHERE r.language = ? AND r.status = 'analysed'
            ORDER BY RANDOM()
            LIMIT ?
        """, (lang, n_per_language)).fetchall()

        if not rows:
            logger.warning(f"No fixtures found for language: {lang}")
            continue

        df = pd.DataFrame([dict(r) for r in rows])
        frames.append(df)
        logger.info(f"  {lang}: sampled {len(df)} fixtures")

    conn.close()

    if not frames:
        logger.error("No fixtures to sample.")
        return None

    sample = pd.concat(frames, ignore_index=True)

    # Add the manual labeling column
    sample["is_true_fixture"] = ""   # reviewer fills: 1 = correct, 0 = false positive
    sample["reviewer_notes"] = ""    # optional free-text notes

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = VALIDATION_DIR / f"sample_{timestamp}.csv"
    sample.to_csv(out_path, index=False)

    logger.info(f"\nValidation sample written to: {out_path}")
    logger.info(
        "Instructions:\n"
        "  1. Open the CSV in a spreadsheet editor.\n"
        "  2. Read each 'raw_source' value.\n"
        "  3. Set 'is_true_fixture' to 1 (true fixture) or 0 (false positive).\n"
        "  4. Run: python pipeline.py validate --compute <path_to_csv>"
    )
    return out_path


# ---------------------------------------------------------------------------
# Precision / recall computation
# ---------------------------------------------------------------------------

def compute_metrics(csv_path: Path) -> dict:
    """
    Read a completed validation CSV and compute precision per language.

    Note: We compute precision (TP / (TP + FP)) from the sample.
    Recall requires knowing the false negatives, which requires a separate
    manual pass over raw test files to count missed fixtures.
    Report precision from this function; note recall limitation in the paper.
    """
    df = pd.read_csv(csv_path)

    required_cols = {"language", "is_true_fixture"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    # Drop rows not yet labelled
    labelled = df[df["is_true_fixture"].isin([0, 1, "0", "1"])]
    labelled = labelled.copy()
    labelled["is_true_fixture"] = labelled["is_true_fixture"].astype(int)

    total_labelled = len(labelled)
    if total_labelled == 0:
        logger.error("No labelled rows found. Fill in is_true_fixture before computing.")
        return {}

    results = {}
    print(f"\nValidation results from: {csv_path.name}")
    print(f"Total labelled: {total_labelled}\n")
    print(f"{'Language':<14} {'Sampled':>8} {'True':>8} {'False+':>8} {'Precision':>10}")
    print("-" * 52)

    for lang, group in labelled.groupby("language"):
        tp = (group["is_true_fixture"] == 1).sum()
        fp = (group["is_true_fixture"] == 0).sum()
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        results[lang] = {
            "sampled": len(group),
            "true_positives": int(tp),
            "false_positives": int(fp),
            "precision": round(precision, 3),
        }
        print(f"{lang:<14} {len(group):>8} {tp:>8} {fp:>8} {precision:>9.1%}")

    overall_tp = sum(r["true_positives"] for r in results.values())
    overall_fp = sum(r["false_positives"] for r in results.values())
    overall_p  = overall_tp / (overall_tp + overall_fp) if (overall_tp + overall_fp) > 0 else 0.0
    print("-" * 52)
    print(f"{'Overall':<14} {total_labelled:>8} {overall_tp:>8} {overall_fp:>8} "
          f"{overall_p:>9.1%}")

    print(
        "\nNote: This script measures precision only. "
        "Recall requires a separate manual pass to count missed fixtures.\n"
        "For the paper, report precision here and note the recall limitation."
    )
    return results