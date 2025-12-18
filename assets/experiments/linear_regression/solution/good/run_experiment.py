"""Finished reproduction for the linear regression benchmark."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, Tuple

from repro_utils.metrics import pearson_r, rmse


def load_series(path: Path) -> Tuple[list[float], list[float]]:
    with path.open() as fh:
        reader = csv.DictReader(fh)
        xs, ys = [], []
        for row in reader:
            xs.append(float(row["x"]))
            ys.append(float(row["y"]))
    return xs, ys


def fit_line(xs: Iterable[float], ys: Iterable[float]) -> tuple[float, float]:
    n = len(xs)
    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_x2 = sum(x * x for x in xs)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    denominator = (n * sum_x2) - (sum_x ** 2)
    if denominator == 0:
        raise ValueError("Degenerate input data")
    slope = ((n * sum_xy) - (sum_x * sum_y)) / denominator
    intercept = (sum_y - (slope * sum_x)) / n
    return slope, intercept


def predict(xs: Iterable[float], slope: float, intercept: float) -> list[float]:
    return [slope * x + intercept for x in xs]


def main() -> None:
    root = Path(__file__).resolve().parent
    data_path = root / "data.csv"
    xs, ys = load_series(data_path)
    slope, intercept = fit_line(xs, ys)
    y_pred = predict(xs, slope, intercept)

    metrics = {
        "slope": round(slope, 4),
        "intercept": round(intercept, 4),
        "pearson_r": round(pearson_r(ys, y_pred), 4),
        "rmse": round(rmse(ys, y_pred), 4),
    }

    artifacts_dir = root / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    metrics_path = artifacts_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n")

    print(f"Slope: {metrics['slope']}")
    print(f"Intercept: {metrics['intercept']}")
    print(f"Pearson R: {metrics['pearson_r']}")
    print(f"RMSE: {metrics['rmse']}")


if __name__ == "__main__":
    main()
