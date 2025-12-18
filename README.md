# ReproRepo – Agentic Reproduction Harness

ReproRepo wraps a deterministic *white* agent (code generator) and a supervising *green* agent (evaluator) so we can rehearse reproducibility flows with miniature research repos. Each experiment ships as a stubbed repo under `assets/experiments/<id>`, plus an expected artifact and one or more canned submissions. The green agent provisions a workspace, applies the white agent’s files, runs the declared commands, inspects the artifacts, scores them with an LLM, and logs the outcome.

## Capabilities

- Launches local green/white agents (A2A protocol) with `uv run python main.py launch`.
- Supports “good”, “bad”, or randomized submissions via `WHITE_AGENT_VARIANT` / `SOLUTION_VARIANT`.
- Streams detailed progress (files, commands, metrics, code-review remarks) to the console and JSON logs under `logs/experiments/`.
- Automatically issues a correction brief and re-runs an experiment if the first submission fails, so you can demo iterative improvements.

Set `OPENAI_API_KEY` for the LLM scoring to run.

## Install

```bash
uv sync
```

## Run

```bash
# all experiments, default variants
uv run python main.py launch

# subset with bad variants
EVALUATION_EXPERIMENTS="linear_regression,climate_summary" \
SOLUTION_VARIANT=bad \
uv run python main.py launch
```

Useful environment variables:

- `WHITE_AGENT_VARIANT` – default variant the white agent uses (`good`, `bad`, `random`).
- `EVALUATION_EXPERIMENTS` – comma-separated experiment IDs to run.
- `SOLUTION_VARIANT` – optional override baked into the evaluation plan.
- `A2A_CLIENT_TIMEOUT` – HTTP timeout (seconds) for A2A RPCs.

## Layout

```
src/
├── green_agent/        green-agent runtime + logging
├── white_agent/        deterministic white agent + canned submissions
├── reproduction/       workspace helpers, scoring, logging
└── launcher.py         spins up both agents and fires the plan
assets/
├── experiments/<id>/   toy repos (workspace, expected artifacts, solutions)
└── shared_libs/        packages injected into PYTHONPATH
logs/                   JSON transcripts (ignored by git)
.tmp/                   ephemeral workspaces (ignored by git)
```

## Experiments

| ID | Goal | Artifact |
| --- | --- | --- |
| `linear_regression` | rebuild missing regression trainer | `artifacts/metrics.json` |
| `climate_summary` | weighted per-station climate stats | `artifacts/summary.json` |
| `crop_yield` | agronomy aggregation + rainfall correlation | `artifacts/yield_report.json` |
| `microbial_growth` | log-linear growth kinetics | `artifacts/growth_report.json` |

Each workspace contains a README describing the research story, the raw data or scaffolding, and a `run_*.py` skeleton the white agent must complete.
