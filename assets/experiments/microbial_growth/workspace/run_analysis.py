"""Placeholder script for the microbial growth kinetics reproduction."""

from __future__ import annotations

from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    data_path = root / "data" / "growth.csv"
    if not data_path.exists():
        raise FileNotFoundError("growth.csv is missing; rerun data collection")

    # TODO: build the exponential fit per strain, compute R^2 / doubling time,
    # print a comparison table, and write artifacts/growth_report.json.
    raise NotImplementedError("Growth analysis not yet implemented")


if __name__ == "__main__":
    main()
