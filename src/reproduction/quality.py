from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from litellm import completion


@dataclass
class ReviewResult:
    path: Path
    heuristics: Dict[str, object]
    heuristic_summary: str
    llm_feedback: str


def review_code_quality(workspace: Path, targets: List[str]) -> List[ReviewResult]:
    results: List[ReviewResult] = []
    for relative_path in targets:
        path = workspace / relative_path
        if not path.exists():
            results.append(
                ReviewResult(
                    path=path,
                    heuristics={},
                    heuristic_summary="File missing; unable to review",
                    llm_feedback="",
                )
            )
            continue
        code = path.read_text()
        heuristics = _compute_heuristics(code)
        heuristic_summary = _summarize_heuristics(heuristics)
        llm_feedback = _maybe_run_llm_review(relative_path, code)
        results.append(
            ReviewResult(
                path=path,
                heuristics=heuristics,
                heuristic_summary=heuristic_summary,
                llm_feedback=llm_feedback,
            )
        )
    return results


def _compute_heuristics(code: str) -> Dict[str, object]:
    lines = code.splitlines()
    docstring_present = '"""' in code or "'''" in code
    todo_count = code.lower().count("todo")
    uses_pathlib = "pathlib" in code
    function_defs = sum(1 for line in lines if line.strip().startswith("def "))
    avg_line_length = round(sum(len(line) for line in lines) / max(len(lines), 1), 2)
    return {
        "lines": len(lines),
        "function_defs": function_defs,
        "todo_count": todo_count,
        "docstring_present": docstring_present,
        "uses_pathlib": uses_pathlib,
        "avg_line_length": avg_line_length,
    }


def _summarize_heuristics(heuristics: Dict[str, object]) -> str:
    notes = []
    if heuristics.get("lines", 0) < 10:
        notes.append("File is very small; hard to judge structure.")
    if heuristics.get("todo_count", 0):
        notes.append("Leftover TODO comments detected.")
    if heuristics.get("function_defs", 0) == 0:
        notes.append("No functions detected; consider factoring logic.")
    if heuristics.get("docstring_present"):
        notes.append("Docstring detected.")
    else:
        notes.append("No module-level docstring.")
    if heuristics.get("uses_pathlib"):
        notes.append("Uses pathlib to manage files.")
    summary = " ".join(notes)
    return summary or "Heuristics look reasonable."


def _maybe_run_llm_review(relative_path: str, code: str) -> str:
    provider = os.getenv("GREEN_REVIEW_PROVIDER") or "openai"
    model = (
        os.getenv("GREEN_REVIEW_MODEL")
        or os.getenv("OPENAI_REVIEW_MODEL")
        or "openai/gpt-4o-mini"
    )
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        return "LLM review skipped (OPENAI_API_KEY not configured)."
    if provider == "litellm_proxy" and not os.getenv("LITELLM_PROXY_API_KEY"):
        return "LLM review skipped (LITELLM proxy key not configured)."
    try:
        response = completion(
            model=model,
            custom_llm_provider=provider,
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are auditing code quality for a reproduction study. "
                        "Offer concise, actionable feedback."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Review the code for {relative_path} and highlight "
                        "maintainability and correctness concerns.\n\n"
                        f"```python\n{code}\n```"
                    ),
                },
            ],
        )
        return response.choices[0].message["content"]  # type: ignore[index]
    except Exception as exc:  # pragma: no cover - depends on network
        return f"LLM review unavailable: {exc}"
