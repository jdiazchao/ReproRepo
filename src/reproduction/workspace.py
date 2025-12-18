from __future__ import annotations

import asyncio
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence

from .experiments import ArtifactExpectation, CommandExpectation, ExperimentSpec, PROJECT_ROOT


RUN_ROOT = PROJECT_ROOT / ".tmp" / "repro_runs"
RUN_ROOT.mkdir(parents=True, exist_ok=True)


@dataclass
class CommandResult:
    command: Sequence[str]
    returncode: int
    stdout: str
    stderr: str
    duration: float
    checks: List[Dict[str, object]] = field(default_factory=list)


@dataclass
class ArtifactResult:
    path: str
    success: bool
    details: str
    actual_path: Path


class WorkspaceManager:
    def __init__(self, spec: ExperimentSpec):
        self.spec = spec
        self.workspace_path = Path(
            tempfile.mkdtemp(prefix=f"{spec.id}_", dir=RUN_ROOT)
        )
        shutil.copytree(
            spec.workspace_template, self.workspace_path, dirs_exist_ok=True
        )
        self._extra_pythonpaths = [str(dep) for dep in spec.dependencies]

    def apply_submission(self, files: Sequence[Dict[str, str]]) -> List[str]:
        created_files: List[str] = []
        for file_entry in files:
            rel_path = file_entry["path"]
            content = file_entry["content"]
            target_path = self.workspace_path / rel_path
            if not target_path.resolve().is_relative_to(self.workspace_path):
                raise ValueError(f"File path escapes workspace: {rel_path}")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content)
            created_files.append(rel_path)
        return created_files

    def _command_env(self) -> Dict[str, str]:
        env = os.environ.copy()
        pythonpath = env.get("PYTHONPATH", "")
        extra = os.pathsep.join(self._extra_pythonpaths)
        if pythonpath:
            env["PYTHONPATH"] = pythonpath + os.pathsep + extra
        else:
            env["PYTHONPATH"] = extra
        return env

    async def run_commands(
        self, submissions: Sequence[Sequence[str]], expectations: Sequence[CommandExpectation]
    ) -> List[CommandResult]:
        results: List[CommandResult] = []
        env = self._command_env()
        for idx, command in enumerate(submissions):
            expectation = expectations[min(idx, len(expectations) - 1)]
            result = await self._run_single(command, env, expectation)
            results.append(result)
        return results

    async def _run_single(
        self,
        command: Sequence[str],
        env: Dict[str, str],
        expectation: CommandExpectation,
    ) -> CommandResult:
        def _execute():
            start = time.time()
            proc = subprocess.run(
                command,
                cwd=self.workspace_path,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            return proc, time.time() - start

        proc, duration = await asyncio.to_thread(_execute)
        checks = []
        stdout = proc.stdout
        for snippet in expectation.expected_stdout:
            checks.append(
                {
                    "type": "stdout_contains",
                    "snippet": snippet,
                    "passed": snippet in stdout,
                }
            )
        return CommandResult(
            command=command,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=proc.stderr,
            duration=duration,
            checks=checks,
        )

    def evaluate_artifacts(self) -> List[ArtifactResult]:
        results: List[ArtifactResult] = []
        for cmd in self.spec.commands:
            for expectation in cmd.artifacts:
                result = self._check_artifact(expectation)
                results.append(result)
        return results

    def _check_artifact(self, expectation: ArtifactExpectation) -> ArtifactResult:
        target = self.workspace_path / expectation.path
        if not target.exists():
            return ArtifactResult(
                path=expectation.path,
                success=False,
                details="Artifact missing",
                actual_path=target,
            )
        if expectation.kind == "json":
            with target.open() as fh:
                actual = json.load(fh)
            success, details = _compare_values(
                expectation.expected, actual, expectation.tolerance
            )
        else:
            success = target.read_text().strip() == str(expectation.expected).strip()
            details = "Exact match" if success else "Content mismatch"
        return ArtifactResult(
            path=expectation.path,
            success=success,
            details=details,
            actual_path=target,
        )


def _compare_values(expected, actual, tolerance: float | None):
    mismatches: List[str] = []

    def _recurse(exp, act, path: str):
        if isinstance(exp, dict):
            if not isinstance(act, dict):
                mismatches.append(f"{path} expected dict, got {type(act).__name__}")
                return
            for key in exp:
                new_path = f"{path}.{key}" if path else key
                if key not in act:
                    mismatches.append(f"{new_path} missing from output")
                    continue
                _recurse(exp[key], act[key], new_path)
        elif isinstance(exp, list):
            if not isinstance(act, list):
                mismatches.append(f"{path} expected list, got {type(act).__name__}")
                return
            if len(exp) != len(act):
                mismatches.append(f"{path} length mismatch ({len(exp)} != {len(act)})")
            for idx, (exp_item, act_item) in enumerate(zip(exp, act)):
                new_path = f"{path}[{idx}]"
                _recurse(exp_item, act_item, new_path)
        elif isinstance(exp, (int, float)):
            if not isinstance(act, (int, float)):
                mismatches.append(f"{path} expected numeric value, got {act}")
                return
            allowed = tolerance if tolerance is not None else 0.0
            if not math.isclose(exp, act, rel_tol=allowed, abs_tol=allowed):
                mismatches.append(f"{path} expected {exp} ±{allowed}, got {act}")
        else:
            if exp != act:
                mismatches.append(f"{path} expected {exp}, got {act}")

    _recurse(expected, actual, path="")
    return not mismatches, "; ".join(mismatches) or "Match"
