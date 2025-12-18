"""Reference implementation for the crop yield reproduction task."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from repro_utils.metrics import pearson_r


Record = Dict[str, float]


def load_rows(path: Path) -> List[Record]:
    with path.open() as fh:
        reader = csv.DictReader(fh)
        rows = []
        for row in reader:
            rows.append(
                {
                    "region": row["region"],
                    "area": float(row["area_ha"]),
                    "yield": float(row["yield_t_per_ha"]),
                    "rain": float(row["rain_mm"]),
                }
            )
        return rows


def weighted_mean(values: List[float], weights: List[float]) -> float:
    total = sum(weights)
    if total == 0:
        raise ValueError("Weights must sum to a positive value")
    return sum(v * w for v, w in zip(values, weights)) / total


def weighted_std(values: List[float], weights: List[float], mean_value: float) -> float:
    total = sum(weights)
    return (sum(w * (v - mean_value) ** 2 for v, w in zip(values, weights)) / total) ** 0.5


def summarize_region(rows: List[Record]) -> Dict[str, float]:
    areas = [row["area"] for row in rows]
    yields = [row["yield"] for row in rows]
    rains = [row["rain"] for row in rows]
    mean_yield = weighted_mean(yields, areas)
    return {
        "mean_yield": round(mean_yield, 3),
        "yield_std": round(weighted_std(yields, areas, mean_yield), 3),
        "rainfall_corr": round(pearson_r(rains, yields), 3),
        "total_area": int(sum(areas)),
    }


def build_report(rows: List[Record]) -> Dict[str, object]:
    region_rows: Dict[str, List[Record]] = defaultdict(list)
    for row in rows:
        region_rows[row["region"]].append(row)
    regions = {name: summarize_region(entries) for name, entries in region_rows.items()}
    best_region = max(regions.items(), key=lambda item: item[1]["mean_yield"])[0]
    rains = [row["rain"] for row in rows]
    yields = [row["yield"] for row in rows]
    report = {
        "regions": regions,
        "global": {
            "mean_yield": round(
                weighted_mean([row["yield"] for row in rows], [row["area"] for row in rows]), 3
            ),
            "total_area": int(sum(row["area"] for row in rows)),
            "best_region": best_region,
            "rainfall_corr": round(pearson_r(rains, yields), 3),
            "sample_count": len(rows),
        },
    }
    return report


def print_summary(report: Dict[str, object]) -> None:
    print("Region      Mean Yield  Corr(rain,yield)")
    print("----------------------------------------")
    for region, stats in sorted(report["regions"].items()):
        print(
            f"{region:<10} {stats['mean_yield']:.3f} t/ha    "
            f"{stats['rainfall_corr']:+.3f}"
        )
    global_info = report["global"]
    print(f"Best region: {global_info['best_region']}")
    print(f"Global correlation: {global_info['rainfall_corr']:+.3f}")


def main() -> None:
    root = Path(__file__).resolve().parent
    rows = load_rows(root / "data" / "yields.csv")
    report = build_report(rows)
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "yield_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print_summary(report)


if __name__ == "__main__":
    main()
