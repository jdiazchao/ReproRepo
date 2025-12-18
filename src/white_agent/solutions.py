from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Dict

from src.reproduction import list_experiments


SOLUTIONS_ROOT = Path(__file__).resolve().parents[2] / "assets" / "experiments"
GLOBAL_VARIANT = os.getenv("WHITE_AGENT_VARIANT", "good")


def _load_submission(base: Path) -> Dict[str, object]:
    with (base / "submission.json").open() as fh:
        payload = json.load(fh)
    files = []
    for entry in payload.get("files", []):
        source = entry.get("source")
        if source:
            entry = {
                "path": entry["path"],
                "content": (base / source).read_text(),
            }
        files.append(entry)
    payload["files"] = files
    return payload


def _load_solution_variants(exp_id: str) -> Dict[str, Dict[str, object]]:
    base = SOLUTIONS_ROOT / exp_id / "solution"
    if not base.exists():
        raise FileNotFoundError(f"No solution folder for {exp_id}")
    variant_dirs = [path for path in base.iterdir() if path.is_dir()]
    if not variant_dirs:
        return {"default": _load_submission(base)}
    payloads = {}
    for variant_dir in variant_dirs:
        payloads[variant_dir.name] = _load_submission(variant_dir)
    return payloads


_SOLUTIONS = {exp_id: _load_solution_variants(exp_id) for exp_id in list_experiments()}


def _choose_variant(exp_id: str, catalog: Dict[str, Dict[str, object]], variant: str | None) -> str:
    requested = (variant or GLOBAL_VARIANT or "").strip().lower()
    if requested == "random":
        return random.choice(list(catalog.keys()))
    if requested in catalog:
        return requested
    if "good" in catalog:
        return "good"
    # gracefully fall back to the first available option
    return next(iter(catalog.keys()))


def get_solution(exp_id: str, variant: str | None = None) -> Dict[str, object]:
    if exp_id not in _SOLUTIONS:
        raise KeyError(f"No canned solution for {exp_id}")
    catalog = _SOLUTIONS[exp_id]
    chosen_variant = _choose_variant(exp_id, catalog, variant)
    payload = catalog[chosen_variant]
    payload.setdefault("variant", chosen_variant)
    return payload
