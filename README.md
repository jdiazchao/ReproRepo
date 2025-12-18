# Agentify Example: Reproduction Benchmark

This repo hosts a pair of agents wired together through the A2A protocol.
The green agent assembles miniature research repositories, asks the white agent
for fixes, executes the submitted code, validates the outputs, and emits a short
code-quality critique. The white agent is a deterministic stub that returns
prebuilt solutions so we can focus on the evaluation flow.

## Project Structure

```
src/
├── green_agent/    # Assessment manager agent
├── white_agent/    # Deterministic target agent
└── launcher.py     # Evaluation coordinator
assets/
├── experiments/    # Toy repositories, expected artifacts, solutions
└── shared_libs/    # Local dependencies injected into experiments
```

## Installation

```bash
uv sync
```

## Usage

```bash
# Launch complete evaluation
uv run python main.py launch
```

The green agent now always pushes the command outputs and artifacts through an
OpenAI LLM to derive an adaptive metric (accuracy, RMSE, etc.). Set
`OPENAI_API_KEY` in `.env` (optional overrides: `GREEN_SCORE_MODEL`,
`GREEN_SCORE_PROVIDER`) so the scoring call succeeds. Every experiment is also
logged under `logs/experiments/<experiment>_<timestamp>.json`, which captures the
commands, artifacts, LLM verdict, and code-review notes for later inspection.

## Available Toy Experiments

| ID                | Theme                               | Expected Artifact                 |
| ----------------- | ----------------------------------- | --------------------------------- |
| `linear_regression` | Recover the missing regression script | `artifacts/metrics.json`          |
| `climate_summary` | Weighted climate aggregation        | `artifacts/summary.json`          |
| `crop_yield`      | Area-weighted agronomy pipeline     | `artifacts/yield_report.json`     |
| `microbial_growth`| Log-linear growth kinetics          | `artifacts/growth_report.json`    |

Each workspace ships with a README plus skeletal script (`run_*.py`) the white
agent must rebuild.

## White Agent Variants

Every experiment now includes a *good* and *bad* canned submission so the green
agent can exercise both success and failure paths. Choose which variant the
white agent emits by setting `WHITE_AGENT_VARIANT` before launching:

```bash
export WHITE_AGENT_VARIANT=good   # other options: bad, random
uv run python main.py launch
```

You can also set `WHITE_AGENT_VARIANT=random` to let each request sample a
variant randomly. The green agent request payload supports an optional
`solution_variant` field for finer control during integration tests.
