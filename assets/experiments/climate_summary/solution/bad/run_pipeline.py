"""Flawed implementation of the climate summary task.

This version intentionally ignores sample weighting and omits the overall
aggregate so evaluators can observe failure handling.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


Record = Dict[str, float]


def load_records(path: Path) -> List[Record]:
    with path.open() as fh:
        return json.load(fh)


def summarize_group(records: List[Record]) -> Dict[str, float]:
    # BUG: averages without considering sample counts.
    temps = [r["temp_c"] for r in records]
    hums = [r["humidity"] for r in records]
    mean_temp = sum(temps) / len(temps)
    mean_hum = sum(hums) / len(hums)
    return {
        "mean_temp_c": round(mean_temp, 1),
        "mean_humidity": round(mean_hum, 2),
        "total_samples": sum(int(r["samples"]) for r in records),
    }


def build_summary(records: List[Record]) -> Dict[str, Dict[str, float]]:
    groups: Dict[str, List[Record]] = defaultdict(list)
    for record in records:
        groups[record["station"]].append(record)
    return {station: summarize_group(rows) for station, rows in groups.items()}


def main() -> None:
    root = Path(__file__).resolve().parent
    data_path = root / "data" / "records.json"
    summary = build_summary(load_records(data_path))

    artifacts_dir = root / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    print("Mean temp stats (unweighted)")
    print(f"Stations processed: {len(summary)}")


if __name__ == "__main__":
    main()
