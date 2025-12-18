"""Reference implementation for the microbial growth kinetics benchmark."""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


Record = Dict[str, float]


def load_records(path: Path) -> List[Record]:
    with path.open() as fh:
        reader = csv.DictReader(fh)
        rows = []
        for row in reader:
            rows.append(
                {
                    "strain": row["strain"],
                    "time": float(row["time_hr"]),
                    "od": float(row["od600"]),
                }
            )
        return rows


def fit_line(xs: List[float], ys: List[float]) -> Tuple[float, float]:
    n = len(xs)
    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_x2 = sum(x * x for x in xs)
    denominator = n * sum_x2 - sum_x**2
    if denominator == 0:
        raise ValueError("Degenerate timeseries")
    slope = (n * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


def summarize_strain(records: List[Record]) -> Dict[str, float]:
    times = [record["time"] for record in records]
    log_od = [math.log(record["od"]) for record in records]
    slope, intercept = fit_line(times, log_od)
    preds = [slope * t + intercept for t in times]
    mean = sum(log_od) / len(log_od)
    ss_res = sum((obs - pred) ** 2 for obs, pred in zip(log_od, preds))
    ss_tot = sum((obs - mean) ** 2 for obs in log_od)
    r2 = 1 - (ss_res / ss_tot)
    doubling = math.log(2) / slope
    return {
        "growth_rate": round(slope, 4),
        "intercept": round(intercept, 4),
        "doubling_time": round(doubling, 4),
        "r2": round(r2, 4),
    }


def build_report(records: List[Record]) -> Dict[str, object]:
    grouped: Dict[str, List[Record]] = defaultdict(list)
    for record in records:
        grouped[record["strain"]].append(record)
    strain_stats = {name: summarize_strain(rows) for name, rows in grouped.items()}
    fastest = min(strain_stats.items(), key=lambda item: item[1]["doubling_time"])[0]
    mean_doubling = sum(stats["doubling_time"] for stats in strain_stats.values()) / len(
        strain_stats
    )
    mean_r2 = sum(stats["r2"] for stats in strain_stats.values()) / len(strain_stats)
    return {
        "strains": strain_stats,
        "global": {
            "fastest_strain": fastest,
            "mean_doubling_time": round(mean_doubling, 4),
            "mean_r2": round(mean_r2, 4),
        },
    }


def print_summary(report: Dict[str, object]) -> None:
    print("Strain    Rate  Doubling (h)  R^2")
    print("---------------------------------")
    for strain, stats in sorted(report["strains"].items()):
        print(
            f"{strain:<8} {stats['growth_rate']:.4f}   "
            f"{stats['doubling_time']:.2f}        {stats['r2']:.4f}"
        )
    global_stats = report["global"]
    print(f"Fastest strain: {global_stats['fastest_strain']}")
    print(f"Mean doubling time: {global_stats['mean_doubling_time']:.2f} h")


def main() -> None:
    root = Path(__file__).resolve().parent
    records = load_records(root / "data" / "growth.csv")
    report = build_report(records)
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "growth_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print_summary(report)


if __name__ == "__main__":
    main()
