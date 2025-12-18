"""Template entry point for the linear regression reproduction task."""

from __future__ import annotations

import json
from pathlib import Path

import csv


def main() -> None:
    root = Path(__file__).resolve().parent
    data_path = root / "data.csv"
    if not data_path.exists():
        raise FileNotFoundError("data.csv is missing from the workspace")

    # TODO: load the CSV, fit a linear model, generate metrics, and write them
    # to artifacts/metrics.json. The expected stdout should mention RMSE and the
    # Pearson correlation to reassure the research lead that you reproduced the
    # reported numbers.
    raise NotImplementedError("Training script not yet implemented")


if __name__ == "__main__":
    main()
