"""Skeleton entry point for the climate summary reproduction task."""

from __future__ import annotations

from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    if not data_dir.exists():
        raise FileNotFoundError("The data directory is missing")

    # TODO: load the JSON records, aggregate per-station metrics, and write the
    # results to artifacts/summary.json. The evaluator expects human-readable
    # stdout so they can compare with the paper's appendix.
    raise NotImplementedError("Pipeline has not been implemented yet")


if __name__ == "__main__":
    main()
