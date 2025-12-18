"""Purposefully flawed microbial growth submission."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


def load_rows(path: Path):
    with path.open() as fh:
        return list(csv.DictReader(fh))


def simple_fit(times, values):
    # Treat OD as linear rather than exponential growth.
    n = len(times)
    sum_x = sum(times)
    sum_y = sum(values)
    sum_xy = sum(x * y for x, y in zip(times, values))
    sum_x2 = sum(x * x for x in times)
    denom = n * sum_x2 - sum_x**2
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


def summarize(records):
    times = [float(row["time_hr"]) for row in records]
    ods = [float(row["od600"]) for row in records]
    slope, intercept = simple_fit(times, ods)
    return {
        "linear_rate": round(slope, 3),
        "intercept": round(intercept, 3),
        # Missing doubling time and R^2 entirely.
    }


def main() -> None:
    root = Path(__file__).resolve().parent
    rows = load_rows(root / "data" / "growth.csv")
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["strain"]].append(row)
    stats = {strain: summarize(records) for strain, records in grouped.items()}
    fastest = max(stats.items(), key=lambda item: item[1]["linear_rate"])[0]
    report = {
        "strains": stats,
        "global": {
            "fastest_strain": fastest,
            "mean_rate": round(sum(s["linear_rate"] for s in stats.values()) / len(stats), 3),
        },
    }
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "growth_report.json").write_text(json.dumps(report, indent=2) + "\n")

    print("Linear OD slopes (incorrect model)")
    for strain, data in stats.items():
        print(f"{strain}: {data['linear_rate']} per hour")
    print(f"Claimed fastest strain: {fastest}")


if __name__ == "__main__":
    main()
