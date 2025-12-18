from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from .experiments import PROJECT_ROOT


LOG_ROOT = PROJECT_ROOT / "logs" / "experiments"
LOG_ROOT.mkdir(parents=True, exist_ok=True)


def log_experiment_result(experiment_id: str, payload: Dict[str, Any]) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = LOG_ROOT / f"{experiment_id}_{timestamp}.json"
    serializable = json.dumps(payload, indent=2, default=str)
    path.write_text(serializable + "\n")
    return path
