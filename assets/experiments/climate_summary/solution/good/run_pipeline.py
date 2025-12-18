"""Implementation of the climate summary reproduction task."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from repro_utils.metrics import weighted_mean_std


Record = Dict[str, float]


def load_records(data_path: Path) -> List[Record]:
    with data_path.open() as fh:
        return json.load(fh)


def summarize_station(records: List[Record]) -> Dict[str, float]:
    temps = [record["temp_c"] for record in records]
    hums = [record["humidity"] for record in records]
    weights = [int(record["samples"]) for record in records]
    mean_temp, temp_std = weighted_mean_std(temps, weights)
    mean_hum, hum_std = weighted_mean_std(hums, weights)
    return {
        "mean_temp_c": round(mean_temp, 2),
        "temp_std": round(temp_std, 2),
        "mean_humidity": round(mean_hum, 2),
        "humidity_std": round(hum_std, 2),
        "total_samples": sum(weights),
    }


def build_summary(records: List[Record]) -> Dict[str, Dict[str, float]]:
    groups: Dict[str, List[Record]] = defaultdict(list)
    for record in records:
        groups[record["station"]].append(record)
    summary = {station: summarize_station(rows) for station, rows in groups.items()}
    overall = summarize_station(records)
    summary["overall"] = overall
    return summary


def main() -> None:
    root = Path(__file__).resolve().parent
    data_path = root / "data" / "records.json"
    records = load_records(data_path)
    summary = build_summary(records)

    artifacts_dir = root / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    summary_path = artifacts_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    overall = summary["overall"]
    print(
        "Mean temp: {mean_temp_c}°C (σ={temp_std}), humidity {mean_humidity}"
        .format(**overall)
    )
    print(f"Stations processed: {len(summary) - 1}")


if __name__ == "__main__":
    main()
