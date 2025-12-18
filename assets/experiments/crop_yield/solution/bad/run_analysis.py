"""Deliberately weak crop yield baseline.

This script ignores planted area weighting and never computes correlations.
It exists so the evaluator can observe a failing submission.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


def load_rows(path: Path):
    with path.open() as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def average(values):
    return sum(values) / len(values)


def summarize_region(rows):
    yields = [float(row["yield_t_per_ha"]) for row in rows]
    return {
        "mean_yield": round(average(yields), 2),
        "total_area": sum(int(row["area_ha"]) for row in rows),
        # Missing std + correlation on purpose.
    }


def main() -> None:
    root = Path(__file__).resolve().parent
    rows = load_rows(root / "data" / "yields.csv")
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["region"]].append(row)
    summary = {region: summarize_region(entries) for region, entries in grouped.items()}
    best_region = max(summary.items(), key=lambda item: item[1]["mean_yield"])[0]
    global_report = {
        "mean_yield": round(average([float(row["yield_t_per_ha"]) for row in rows]), 2),
        "total_area": sum(int(row["area_ha"]) for row in rows),
        "best_region": best_region,
        # Missing correlation + sample count.
    }

    report = {"regions": summary, "global": global_report}
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "yield_report.json").write_text(json.dumps(report, indent=2) + "\n")

    print("Region average yields (simple mean)")
    for region, stats in summary.items():
        print(f"{region}: {stats['mean_yield']} t/ha (area {stats['total_area']})")
    print(f"Best guess: {best_region}")


if __name__ == "__main__":
    main()
