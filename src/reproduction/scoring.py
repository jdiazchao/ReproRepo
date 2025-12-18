from __future__ import annotations

import json
import os
from typing import Any, Dict, Sequence

from litellm import completion

from .experiments import ExperimentSpec


def score_with_llm(
    spec: ExperimentSpec,
    command_payload: Sequence[Dict[str, Any]],
    artifact_payload: Sequence[Dict[str, Any]],
    code_reviews: Sequence[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    provider = os.getenv("GREEN_SCORE_PROVIDER", "openai")
    model = os.getenv("GREEN_SCORE_MODEL", "openai/gpt-4o-mini")

    missing_key_message = _missing_key_message(provider)
    if missing_key_message:
        return {
            "metric_name": "unavailable",
            "metric_value": None,
            "verdict": "error",
            "analysis": missing_key_message,
            "confidence": 0.0,
            "raw_response": "",
        }

    context = {
        "experiment": {
            "id": spec.id,
            "title": spec.title,
            "summary": spec.summary,
            "notes": spec.request_notes,
            "score_guidance": getattr(spec, "score_guidance", ""),
        },
        "command_outputs": command_payload,
        "artifact_snapshots": artifact_payload,
        "code_reviews": list(code_reviews or []),
    }
    user_prompt = (
        "You are auditing a research reproduction experiment. "
        "Based on the outputs, determine which quantitative metric best reflects "
        "task success (accuracy, RMSE, correlation, etc.). "
        "If multiple metrics exist, pick the one most aligned with the experiment "
        "goal. Report the numeric value exactly as shown. "
        "Additionally, provide a `metrics_list` array that clearly lists the "
        "personalized evaluation checkpoints (experimental metrics, comparisons "
        "to expectations, and notable code-quality findings from the reviews). "
        "Respond with JSON only using the keys: "
        "metric_name (string), metric_value (string or number), verdict ('pass' or 'fail'), "
        "analysis (short text), confidence (0-1 float), metrics_list (array of strings)."
        "\nContext:\n"
        f"{json.dumps(context, indent=2)}"
    )

    try:
        response = completion(
            model=model,
            custom_llm_provider=provider,
            temperature=0.1,
            max_tokens=400,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an exacting reproducibility auditor. "
                        "Always output valid JSON. Make the metrics_list entries concise and informative."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message["content"]  # type: ignore[index]
        parsed = _extract_json_block(raw)
        parsed["raw_response"] = raw
        return parsed
    except Exception as exc:  # pragma: no cover - dependent on network
        return {
            "metric_name": "unavailable",
            "metric_value": None,
            "verdict": "error",
            "analysis": f"LLM scoring failed: {exc}",
            "confidence": 0.0,
            "raw_response": "",
        }


def _missing_key_message(provider: str) -> str | None:
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        return "OPENAI_API_KEY is required for scoring but is not configured."
    if provider == "litellm_proxy" and not os.getenv("LITELLM_PROXY_API_KEY"):
        return "LITELLM proxy API key is required for scoring but is not configured."
    return None


def _extract_json_block(text: str) -> Dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model response did not contain JSON.")
    snippet = text[start : end + 1]
    return json.loads(snippet)
