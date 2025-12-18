from __future__ import annotations

import json
import os
import textwrap
import time
from dataclasses import dataclass
from typing import Dict, List, Sequence

import tomllib
import dotenv
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, Message, SendMessageSuccessResponse
from a2a.utils import get_text_parts, new_agent_text_message

from src.my_util import my_a2a, parse_tags
from src.reproduction import (
    WorkspaceManager,
    get_experiment_spec,
    review_code_quality,
    score_with_llm,
    log_experiment_result,
)

dotenv.load_dotenv()


class ConsolePalette:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    INFO = "\033[36m"
    SUCCESS = "\033[32m"
    WARNING = "\033[33m"
    ERROR = "\033[31m"
    CODE = "\033[35m"
    RESULT = "\033[93m"


def log_status(label: str, message: str, color: str = ConsolePalette.INFO) -> None:
    prefix = f"[{label}]".ljust(18)
    print(f"{color}{prefix}{ConsolePalette.RESET} {message}")


def _trim_block(text: str, max_lines: int = 6, max_chars: int = 120) -> str:
    lines = [line.rstrip() for line in text.strip().splitlines()]
    if not lines:
        return "<empty>"
    if len(lines) > max_lines:
        lines = lines[:max_lines] + ["..."]
    return "\n".join(line[:max_chars] for line in lines)


def log_code_preview(path: str, content: str) -> None:
    snippet = _trim_block(content, max_lines=5, max_chars=140)
    log_status("file", path, ConsolePalette.CODE)
    body = textwrap.indent(snippet, "    ")
    print(f"{ConsolePalette.CODE}{body}{ConsolePalette.RESET}")


def log_text_block(label: str, text: str, color: str = ConsolePalette.DIM) -> None:
    snippet = _trim_block(text, max_lines=8, max_chars=160)
    log_status(label, "", color)
    body = textwrap.indent(snippet, "    ")
    print(f"{color}{body}{ConsolePalette.RESET}")


def load_agent_card_toml(agent_name: str) -> Dict[str, object]:
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, f"{agent_name}.toml"), "rb") as fh:
        return tomllib.load(fh)


@dataclass
class ExperimentEvaluation:
    id: str
    status: str
    workspace: str
    files_written: List[str]
    command_results: List[Dict[str, object]]
    artifact_results: List[Dict[str, object]]
    reviews: List[Dict[str, object]]
    score: Dict[str, object]
    log_path: str
    notes: str
    variant: str = "unspecified"
    attempt: int = 1


async def request_white_agent_submission(
    white_agent_url: str,
    experiment_ids: Sequence[str],
    solution_variant: str | None = None,
    experiment_variants: Dict[str, str] | None = None,
    experiment_feedback: Dict[str, str] | None = None,
) -> Dict[str, object]:
    specs = [get_experiment_spec(exp_id) for exp_id in experiment_ids]
    experiment_variants = experiment_variants or {}
    experiment_feedback = experiment_feedback or {}
    experiments_payload = []
    for spec in specs:
        contract = spec.contract_payload()
        if spec.id in experiment_variants:
            contract["variant"] = experiment_variants[spec.id]
        if spec.id in experiment_feedback:
            contract["feedback"] = experiment_feedback[spec.id]
        experiments_payload.append(contract)
    request_payload = {
        "objective": (
            "Reproduce the toy experiments as if they were public research "
            "repositories. Fill in the missing code, resolve dependencies, "
            "and describe how to run the experiments. Return JSON describing "
            "the files you created and the commands to execute."
        ),
        "response_contract": {
            "fields": {
                "experiments": (
                    "Array of objects with keys id, files (path+content), "
                    "commands (list of argv arrays), and optional notes."
                )
            },
            "wrapping": "<submission>{...}</submission>",
        },
        "experiments": experiments_payload,
    }
    if solution_variant:
        request_payload["solution_variant"] = solution_variant
    message = f"""
You are the white evaluation agent. Provide runnable code and instructions
for each experiment below. Respond with a JSON payload wrapped in
<submission>...</submission>.

<experiment_request>
{json.dumps(request_payload, indent=2)}
</experiment_request>
    """.strip()

    response = await my_a2a.send_message(white_agent_url, message)
    return parse_submission_payload(response)


def parse_submission_payload(response) -> Dict[str, object]:
    root = response.root
    assert isinstance(root, SendMessageSuccessResponse)
    if not isinstance(root.result, Message):
        raise ValueError("Expected text message from white agent")
    parts = get_text_parts(root.result.parts)
    if not parts:
        raise ValueError("White agent response missing text")
    tags = parse_tags(parts[0])
    if "submission" not in tags:
        raise ValueError("White agent response missing <submission> payload")
    return json.loads(tags["submission"])


async def evaluate_experiment(
    spec_id: str,
    submission_entry: Dict[str, object],
    attempt: int = 1,
) -> ExperimentEvaluation:
    spec = get_experiment_spec(spec_id)
    manager = WorkspaceManager(spec)
    log_status("experiment", f"{spec.id}: workspace ready at {manager.workspace_path}", ConsolePalette.DIM)
    variant = submission_entry.get("variant", "unspecified")
    files = submission_entry.get("files", [])
    if not isinstance(files, list):
        raise ValueError("files must be a list")
    if files:
        log_status("files", f"{spec.id}: received {len(files)} file(s) from white agent", ConsolePalette.INFO)
        for file_entry in files:
            log_code_preview(file_entry.get("path", "<unknown>"), file_entry.get("content", ""))
    else:
        log_status("files", f"{spec.id}: no files provided by white agent", ConsolePalette.WARNING)
    file_paths = manager.apply_submission(files)
    if file_paths:
        log_status(
            "workspace",
            f"{spec.id}: materialized {len(file_paths)} file(s): {', '.join(file_paths)}",
            ConsolePalette.DIM,
        )
    commands = submission_entry.get("commands", [])
    if not isinstance(commands, list):
        raise ValueError("commands must be a list")
    if commands:
        log_status("commands", f"{spec.id}: {len(commands)} command(s) queued", ConsolePalette.INFO)
    else:
        log_status("commands", f"{spec.id}: no commands provided", ConsolePalette.WARNING)
    normalized_commands = []
    for command in commands:
        if isinstance(command, str):
            normalized_commands.append(command.split())
        else:
            normalized_commands.append(command)
    if normalized_commands:
        log_status("commands", f"{spec.id}: executing commands", ConsolePalette.INFO)
    command_records = await manager.run_commands(normalized_commands, spec.commands)
    for record in command_records:
        cmd_text = " ".join(record.command)
        color = ConsolePalette.SUCCESS if record.returncode == 0 else ConsolePalette.ERROR
        log_status(
            "cmd",
            f"{spec.id}: `{cmd_text}` -> rc={record.returncode} ({record.duration:.2f}s)",
            color,
        )
        if record.stdout and record.stdout.strip():
            log_text_block("stdout", record.stdout, ConsolePalette.DIM)
        if record.stderr and record.stderr.strip():
            log_text_block("stderr", record.stderr, ConsolePalette.WARNING)
    artifact_checks = manager.evaluate_artifacts()
    for artifact in artifact_checks:
        color = ConsolePalette.SUCCESS if artifact.success else ConsolePalette.ERROR
        log_status(
            "artifact",
            f"{spec.id}: {artifact.path} -> {artifact.details}",
            color,
        )
    command_payload = [_serialize_command_result(record) for record in command_records]
    artifact_payload_full = [
        _serialize_artifact_result(artifact, include_content=True)
        for artifact in artifact_checks
    ]
    artifact_results = [
        _serialize_artifact_result(artifact, include_content=False)
        for artifact in artifact_checks
    ]
    log_status("review", f"{spec.id}: running static review", ConsolePalette.INFO)
    reviews = [
        {
            "path": str(review.path),
            "heuristics": review.heuristics,
            "summary": review.heuristic_summary,
            "llm_feedback": review.llm_feedback,
        }
        for review in review_code_quality(manager.workspace_path, list(spec.review_targets))
    ]
    log_status("review", f"{spec.id}: {len(reviews)} review target(s) analyzed", ConsolePalette.DIM)
    log_status("llm", f"{spec.id}: scoring artifacts via LLM", ConsolePalette.INFO)
    score = score_with_llm(spec, command_payload, artifact_payload_full, reviews)
    verdict = score.get("verdict", "n/a") if score else "n/a"
    log_status("llm", f"{spec.id}: LLM verdict -> {verdict}", ConsolePalette.DIM)
    overall_status, notes = summarize_status(command_records, artifact_results)
    log_payload = {
        "experiment_id": spec.id,
        "variant": variant,
        "attempt": attempt,
        "workspace": str(manager.workspace_path),
        "files_written": file_paths,
        "commands": command_payload,
        "artifacts": artifact_payload_full,
        "score": score,
        "reviews": reviews,
        "status": overall_status,
        "notes": notes,
    }
    log_path = log_experiment_result(spec.id, log_payload)
    return ExperimentEvaluation(
        id=spec.id,
        status=overall_status,
        workspace=str(manager.workspace_path),
        files_written=file_paths,
        command_results=command_payload,
        artifact_results=artifact_results,
        reviews=reviews,
        score=score,
        log_path=str(log_path),
        notes=notes,
        variant=variant,
        attempt=attempt,
    )


def _serialize_command_result(result, stdout_limit: int = 1600, stderr_limit: int = 600):
    stdout = (result.stdout or "")[-stdout_limit:]
    stderr = (result.stderr or "")[-stderr_limit:]
    return {
        "command": " ".join(result.command),
        "returncode": result.returncode,
        "duration": round(result.duration, 2),
        "stdout": stdout,
        "stderr": stderr,
        "checks": result.checks,
    }


def _serialize_artifact_result(result, include_content: bool):
    data: Dict[str, object] = {
        "path": result.path,
        "success": result.success,
        "details": result.details,
    }
    if include_content and result.actual_path.exists():
        try:
            if result.actual_path.suffix == ".json":
                data["content"] = json.loads(result.actual_path.read_text())
            else:
                data["content_preview"] = result.actual_path.read_text()[:1200]
        except Exception as exc:  # pragma: no cover - disk io
            data["content_error"] = str(exc)
    return data


def summarize_status(command_results, artifact_results):
    command_success = all(
        result.returncode == 0
        and all(check["passed"] for check in result.checks)
        for result in command_results
    )
    artifact_success = all(result["success"] for result in artifact_results)
    if command_success and artifact_success:
        return "pass", "Commands and artifacts matched expectations"
    details = []
    if not command_success:
        details.append("One or more commands failed or logs were incomplete")
    if not artifact_success:
        failing = [res["path"] for res in artifact_results if not res["success"]]
        details.append(f"Artifacts did not match: {', '.join(failing)}")
    return "fail", "; ".join(details)


def _format_experiment_report(result: ExperimentEvaluation) -> str:
    lines = [
        f"Experiment: {result.id}",
        f"Status   : {result.status.upper()} ({result.notes})",
        f"Variant  : {result.variant}",
        f"Attempt  : {result.attempt}",
        f"Workspace: {result.workspace}",
    ]
    if result.files_written:
        lines.append("Files    :")
        for path in result.files_written:
            lines.append(f"  • {path}")
    else:
        lines.append("Files    : <none provided>")
    if result.command_results:
        lines.append("Commands :")
        for cmd in result.command_results:
            lines.append(
                f"  • `{cmd['command']}` -> rc={cmd['returncode']} ({cmd['duration']}s)"
            )
            stdout_preview = textwrap.shorten(cmd["stdout"].strip(), width=140)
            if stdout_preview:
                lines.append(f"      stdout: {stdout_preview}")
            if cmd["stderr"].strip():
                stderr_preview = textwrap.shorten(cmd["stderr"].strip(), width=120)
                lines.append(f"      stderr: {stderr_preview}")
    if result.artifact_results:
        lines.append("Artifacts:")
        for artifact in result.artifact_results:
            marker = "ok" if artifact["success"] else "mismatch"
            lines.append(f"  • {artifact['path']}: {marker} ({artifact['details']})")
    if result.score:
        metric_name = result.score.get("metric_name", "metric")
        metric_value = result.score.get("metric_value", "n/a")
        verdict = result.score.get("verdict", "n/a")
        confidence = result.score.get("confidence")
        conf_text = (
            f", conf={confidence:.2f}"
            if isinstance(confidence, (int, float))
            else ""
        )
        lines.append(
            f"LLM score: {metric_name}={metric_value} ({verdict}{conf_text})"
        )
        analysis = result.score.get("analysis")
        if analysis:
            lines.append(f"  analysis: {textwrap.shorten(str(analysis), width=240)}")
        metrics_list = result.score.get("metrics_list")
        if metrics_list:
            lines.append("  checklist:")
            for item in metrics_list:
                lines.append(f"    • {item}")
    if result.reviews:
        lines.append("Reviews  :")
        for review in result.reviews:
            lines.append(f"  • {review['path']}: {review['summary']}")
            if review["llm_feedback"]:
                feedback = textwrap.shorten(review["llm_feedback"], width=220)
                lines.append(f"      LLM: {feedback}")
    lines.append(f"Log file : {result.log_path}")
    return "\n".join(lines)


def _log_experiment_report(result: ExperimentEvaluation) -> None:
    title = f"{result.id}: {result.status.upper()} ({result.notes})"
    log_status("result", title, ConsolePalette.RESULT)
    body = textwrap.indent(_format_experiment_report(result), "    ")
    print(f"{ConsolePalette.RESULT}{body}{ConsolePalette.RESET}")


def _build_correction_prompt(result: ExperimentEvaluation) -> str:
    lines = [
        f"Experiment `{result.id}` requires a corrected submission.",
        "Key issues detected:",
    ]
    for cmd in result.command_results:
        if cmd["returncode"] != 0:
            lines.append(f"- Command `{cmd['command']}` exited with {cmd['returncode']}.")
        for check in cmd.get("checks", []):
            if not check.get("passed"):
                snippet = check.get("snippet", "")
                lines.append(f"- Expected stdout snippet missing: `{snippet}`.")
    for artifact in result.artifact_results:
        if not artifact["success"]:
            lines.append(f"- Artifact {artifact['path']} mismatch: {artifact['details']}.")
    if result.score and result.score.get("verdict") == "fail":
        lines.append(f"- Metric verdict: {result.score.get('analysis', 'LLM flagged failure')}.")
    if result.reviews:
        lines.append("Code review notes:")
        for review in result.reviews:
            lines.append(f"  • {review['path']}: {review['summary']}")
    lines.append("Please address these issues and resubmit a corrected implementation.")
    return "\n".join(lines)


def format_final_message(results: Sequence[ExperimentEvaluation], metrics: Dict[str, object]) -> str:
    lines = [
        "=== Reproduction Audit Complete ===",
        f"Elapsed: {metrics['time_used']:.2f}s",
        "",
        "Experiment Outcomes:",
    ]
    for result in results:
        status_label = "PASS" if result.status == "pass" else "FAIL"
        lines.append(f"- {result.id}: {status_label} ({result.notes})")
        if result.score and result.score.get("metrics_list"):
            lines.append("    metrics:")
            for item in result.score["metrics_list"]:
                lines.append(f"      - {item}")
    lines.append("")
    lines.append("Detailed logs are available at:")
    for result in results:
        lines.append(f"  • {result.id}: {result.log_path}")
    return "\n".join(lines)


class TauGreenAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        print("Green agent: task received, starting reproduction assessment.")
        user_input = context.get_user_input()
        tags = parse_tags(user_input)
        white_agent_url = tags.get("white_agent_url")
        plan_str = tags.get("evaluation_plan")
        if not white_agent_url or not plan_str:
            raise ValueError("Task must include <white_agent_url> and <evaluation_plan>")
        plan = json.loads(plan_str)
        experiment_ids = plan.get("experiments")
        if not experiment_ids:
            raise ValueError("evaluation_plan.experiments cannot be empty")
        plan_variant = plan.get("solution_variant")
        log_status("plan", f"{len(experiment_ids)} experiment(s): {', '.join(experiment_ids)}", ConsolePalette.INFO)
        log_status("white-agent", "Requesting submission package", ConsolePalette.INFO)

        timestamp_started = time.time()
        submission_payload = await request_white_agent_submission(
            white_agent_url,
            experiment_ids,
            solution_variant=plan_variant,
        )
        log_status("white-agent", "Submission received", ConsolePalette.SUCCESS)
        submission_entries = {
            exp["id"]: exp for exp in submission_payload.get("experiments", [])
        }

        results: List[ExperimentEvaluation] = []
        for experiment_id in experiment_ids:
            log_status("experiment", f"{experiment_id}: evaluation starting", ConsolePalette.INFO)
            entry = submission_entries.get(experiment_id)
            if entry is None:
                log_status("experiment", f"{experiment_id}: submission missing", ConsolePalette.ERROR)
                results.append(
                    ExperimentEvaluation(
                        id=experiment_id,
                        status="fail",
                        workspace="n/a",
                        files_written=[],
                        command_results=[],
                        artifact_results=[],
                        reviews=[],
                        score={},
                        log_path="n/a",
                        notes="Submission missing for this experiment",
                        variant="unspecified",
                        attempt=1,
                    )
                )
                continue
            evaluation = await evaluate_experiment(experiment_id, entry, attempt=1)
            results.append(evaluation)
            color = (
                ConsolePalette.SUCCESS
                if evaluation.status == "pass"
                else ConsolePalette.ERROR
            )
            log_status(
                "result",
                f"{evaluation.id}: {evaluation.status.upper()} ({evaluation.notes})",
                color,
            )
            _log_experiment_report(evaluation)

        final_results: List[ExperimentEvaluation] = []
        for evaluation in results:
            if evaluation.status == "pass":
                final_results.append(evaluation)
                continue
            log_status("feedback", f"{evaluation.id}: preparing correction brief", ConsolePalette.WARNING)
            correction_prompt = _build_correction_prompt(evaluation)
            log_text_block("feedback", correction_prompt, ConsolePalette.WARNING)
            log_status("white-agent", f"{evaluation.id}: requesting corrected submission", ConsolePalette.INFO)
            correction_payload = await request_white_agent_submission(
                white_agent_url,
                [evaluation.id],
                solution_variant="good",
                experiment_variants={evaluation.id: "good"},
                experiment_feedback={evaluation.id: correction_prompt},
            )
            entries = {
                exp["id"]: exp for exp in correction_payload.get("experiments", [])
            }
            corrected_entry = entries.get(evaluation.id)
            if corrected_entry is None:
                log_status("feedback", f"{evaluation.id}: correction request failed", ConsolePalette.ERROR)
                final_results.append(evaluation)
                continue
            corrected_eval = await evaluate_experiment(
                evaluation.id, corrected_entry, attempt=evaluation.attempt + 1
            )
            corrected_eval.notes = f"{corrected_eval.notes} (after correction)"
            log_status(
                "result",
                f"{corrected_eval.id}: {corrected_eval.status.upper()} ({corrected_eval.notes})",
                ConsolePalette.RESULT,
            )
            _log_experiment_report(corrected_eval)
            final_results.append(corrected_eval)

        metrics = {"time_used": time.time() - timestamp_started}
        success = all(result.status == "pass" for result in final_results)
        metrics["success"] = success

        final_message = format_final_message(final_results, metrics)
        log_status("summary", "Dispatching final report to coordinator", ConsolePalette.INFO)
        await event_queue.enqueue_event(new_agent_text_message(final_message))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError


def start_green_agent(agent_name="tau_green_agent", host="localhost", port=9001):
    print("Starting green agent...")
    agent_card_dict = load_agent_card_toml(agent_name)
    agent_url = os.getenv("AGENT_URL")
    if not agent_url:
        agent_url = f"http://{host}:{port}"
    agent_card_dict["url"] = agent_url

    request_handler = DefaultRequestHandler(
        agent_executor=TauGreenAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    app = A2AStarletteApplication(
        agent_card=AgentCard(**agent_card_dict),
        http_handler=request_handler,
    )

    import uvicorn

    uvicorn.run(app.build(), host=host, port=port)
