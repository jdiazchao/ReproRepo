"""Intentionally flawed linear regression reproduction.

This variant ignores the intercept term and relies on a naïve slope estimate.
It is useful for validating that the green agent can flag poor submissions.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


def load_pairs(path: Path) -> tuple[list[float], list[float]]:
    with path.open() as fh:
        reader = csv.DictReader(fh)
        xs, ys = [], []
        for row in reader:
            xs.append(float(row["x"]))
            ys.append(float(row["y"]))
    return xs, ys


def naive_fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    # Broken assumption: forces the regression through the origin and uses a
    # simplistic slope estimate.
    slope = sum(ys) / sum(xs)
    intercept = 0.0
    return slope, intercept


def compute_metrics(xs: list[float], ys: list[float], slope: float, intercept: float):
    preds = [slope * x + intercept for x in xs]
    mean_y = sum(ys) / len(ys)
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - p) ** 2 for y, p in zip(ys, preds))
    rmse = (ss_res / len(ys)) ** 0.5
    pearson_r = 1 - (ss_res / ss_tot) if ss_tot else 0.0
    return {
        "slope": round(slope, 2),
        "intercept": round(intercept, 2),
        "pearson_r": round(pearson_r, 4),
        "rmse": round(rmse, 2),
    }


def main() -> None:
    root = Path(__file__).resolve().parent
    data_path = root / "data.csv"
    xs, ys = load_pairs(data_path)
    slope, intercept = naive_fit(xs, ys)
    metrics = compute_metrics(xs, ys, slope, intercept)

    artifacts_dir = root / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

    print(f"Slope (naive): {metrics['slope']}")
    print(f"Intercept (forced zero): {metrics['intercept']}")
    print(f"Pearson R-ish: {metrics['pearson_r']}")
    print(f"RMSE-ish: {metrics['rmse']}")


if __name__ == "__main__":
    main()
