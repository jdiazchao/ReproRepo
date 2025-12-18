# Linear Response Benchmark

This toy project mimics a small research codebase where the goal is to fit a
simple linear model to a provided CSV dataset. The repository intentionally
omits the finished training script so the evaluator can ask a white agent to
reconstruct the missing logic.

Key details:
- Data lives in `data.csv` and represents a noisy linear relationship.
- The desired script must compute the slope/intercept, generate predictions,
  print metrics, and store them under `artifacts/metrics.json`.
- Dependencies include a tiny internal module called `repro_utils` with helper
  functions for regression metrics.
- The evaluator expects to run `python run_experiment.py` from the repo root.
