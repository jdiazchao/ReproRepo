"""Entry point for rebuilding the crop yield summary pipeline."""

from __future__ import annotations

from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    data_path = root / "data" / "yields.csv"
    if not data_path.exists():
        raise FileNotFoundError("Missing source data: data/yields.csv")

    # TODO: load the CSV, compute per-region weighted summaries, build the
    # global aggregate, and materialize artifacts/yield_report.json. The stdout
    # should mention the best-performing region and the global correlation.
    raise NotImplementedError("Analysis script not implemented yet")


if __name__ == "__main__":
    main()
