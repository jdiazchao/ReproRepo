from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: Path):
    with path.open() as fh:
        return json.load(fh)


def _build_manifest(base_dir: Path) -> List[str]:
    manifest: List[str] = []
    for path in sorted(base_dir.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(base_dir)
        manifest.append(str(rel))
    return manifest


def _preview_file(path: Path, max_chars: int = 600) -> str:
    content = path.read_text()
    if len(content) <= max_chars:
        return content
    return content[: max_chars - 3] + "..."


@dataclass
class ArtifactExpectation:
    path: str
    kind: str  # e.g. "json"
    expected: object
    tolerance: float | None = None


@dataclass
class CommandExpectation:
    description: str
    expected_stdout: Sequence[str] = field(default_factory=list)
    artifacts: Sequence[ArtifactExpectation] = field(default_factory=list)


@dataclass
class ExperimentSpec:
    id: str
    title: str
    summary: str
    workspace_template: Path
    expected_dir: Path
    request_notes: str
    dependencies: Sequence[Path]
    commands: Sequence[CommandExpectation]
    review_targets: Sequence[str]
    score_guidance: str = ""

    def readme(self) -> str:
        readme_path = self.workspace_template / "README.md"
        if readme_path.exists():
            return readme_path.read_text().strip()
        return "README not available for this experiment."

    def repo_manifest(self) -> List[str]:
        return _build_manifest(self.workspace_template)

    def contract_payload(self) -> Dict[str, object]:
        previews = []
        for candidate in ("run_experiment.py", "run_pipeline.py"):
            preview_path = self.workspace_template / candidate
            if preview_path.exists():
                previews.append(
                    {
                        "path": candidate,
                        "preview": _preview_file(preview_path),
                    }
                )
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "notes": self.request_notes,
            "readme": self.readme(),
            "manifest": self.repo_manifest(),
            "file_previews": previews,
            "score_guidance": self.score_guidance,
            "expected_artifacts": [
                asdict(artifact)
                for cmd in self.commands
                for artifact in cmd.artifacts
            ],
        }


def _specs() -> Dict[str, ExperimentSpec]:
    shared_lib = PROJECT_ROOT / "assets" / "shared_libs" / "repro_utils"

    experiments_root = PROJECT_ROOT / "assets" / "experiments"

    linear_expected = _load_json(
        PROJECT_ROOT
        / "assets"
        / "experiments"
        / "linear_regression"
        / "expected"
        / "metrics.json"
    )
    climate_expected = _load_json(
        PROJECT_ROOT
        / "assets"
        / "experiments"
        / "climate_summary"
        / "expected"
        / "summary.json"
    )
    crop_expected = _load_json(
        experiments_root / "crop_yield" / "expected" / "yield_report.json"
    )
    growth_expected = _load_json(
        experiments_root / "microbial_growth" / "expected" / "growth_report.json"
    )

    linear_spec = ExperimentSpec(
        id="linear_regression",
        title="Linear Regression Recovery",
        summary=(
            "Rebuild the missing training script so the repo can fit a noisy "
            "linear model and report regression metrics."
        ),
        workspace_template=experiments_root / "linear_regression" / "workspace",
        expected_dir=experiments_root / "linear_regression" / "expected",
        request_notes=(
            "Only the README and raw data are available. The regression script "
            "and artifacts folder must be recreated by the white agent."
        ),
        dependencies=[shared_lib],
        commands=[
            CommandExpectation(
                description="Fit the linear model and emit metrics",
                expected_stdout=[
                    "Slope:",
                    "Intercept:",
                    "Pearson R:",
                    "RMSE:",
                ],
                artifacts=[
                    ArtifactExpectation(
                        path="artifacts/metrics.json",
                        kind="json",
                        expected=linear_expected,
                        tolerance=0.02,
                    )
                ],
            )
        ],
        review_targets=["run_experiment.py"],
        score_guidance="Use RMSE or Pearson correlation from metrics.json; prioritize RMSE.",
    )

    climate_spec = ExperimentSpec(
        id="climate_summary",
        title="Regional Climate Summary",
        summary=(
            "Aggregate weighted climate statistics per station and provide a "
            "concise textual report plus machine-readable JSON."
        ),
        workspace_template=experiments_root / "climate_summary" / "workspace",
        expected_dir=experiments_root / "climate_summary" / "expected",
        request_notes=(
            "The orchestration script is missing. Build the reporting pipeline "
            "and keep the summary logic modular."
        ),
        dependencies=[shared_lib],
        commands=[
            CommandExpectation(
                description="Compute per-station summaries",
                expected_stdout=[
                    "Mean temp",
                    "Stations processed",
                ],
                artifacts=[
                    ArtifactExpectation(
                        path="artifacts/summary.json",
                        kind="json",
                        expected=climate_expected,
                        tolerance=0.05,
                    )
                ],
            )
        ],
        review_targets=["run_pipeline.py"],
        score_guidance="Focus on aggregated mean temperature/humidity from overall summary.",
    )

    crop_spec = ExperimentSpec(
        id="crop_yield",
        title="High-Altitude Crop Yield Study",
        summary=(
            "Recreate the weighted aggregation pipeline that reports per-region "
            "yield statistics and rainfall correlations."
        ),
        workspace_template=experiments_root / "crop_yield" / "workspace",
        expected_dir=experiments_root / "crop_yield" / "expected",
        request_notes=(
            "Data includes planted area and rainfall columns. Use area-weighted "
            "averages and include a global summary that highlights the best region."
        ),
        dependencies=[shared_lib],
        commands=[
            CommandExpectation(
                description="Compute weighted yield summaries",
                expected_stdout=[
                    "Region",
                    "Best region",
                    "Global correlation",
                ],
                artifacts=[
                    ArtifactExpectation(
                        path="artifacts/yield_report.json",
                        kind="json",
                        expected=crop_expected,
                        tolerance=0.02,
                    )
                ],
            )
        ],
        review_targets=["run_analysis.py"],
        score_guidance="Prefer the rainfall correlation and best-region accuracy.",
    )

    growth_spec = ExperimentSpec(
        id="microbial_growth",
        title="Microbial Growth Kinetics",
        summary=(
            "Fit log-linear models per strain to recover growth rates, "
            "doubling times, and R^2 values before ranking strains."
        ),
        workspace_template=experiments_root / "microbial_growth" / "workspace",
        expected_dir=experiments_root / "microbial_growth" / "expected",
        request_notes=(
            "Only OD600 readings remain. Rebuild the fitting script and emit "
            "growth_report.json with per-strain metrics and an overall section."
        ),
        dependencies=[],
        commands=[
            CommandExpectation(
                description="Estimate growth rates",
                expected_stdout=[
                    "Strain",
                    "Fastest strain",
                    "Mean doubling time",
                ],
                artifacts=[
                    ArtifactExpectation(
                        path="artifacts/growth_report.json",
                        kind="json",
                        expected=growth_expected,
                        tolerance=0.02,
                    )
                ],
            )
        ],
        review_targets=["run_analysis.py"],
        score_guidance="Prioritize doubling-time accuracy; R^2 serves as a tiebreaker.",
    )

    return {spec.id: spec for spec in (linear_spec, climate_spec, crop_spec, growth_spec)}


_EXPERIMENT_SPECS = _specs()


def list_experiments() -> Sequence[str]:
    return list(_EXPERIMENT_SPECS.keys())


def get_experiment_spec(exp_id: str) -> ExperimentSpec:
    if exp_id not in _EXPERIMENT_SPECS:
        raise KeyError(f"Unknown experiment id: {exp_id}")
    return _EXPERIMENT_SPECS[exp_id]
