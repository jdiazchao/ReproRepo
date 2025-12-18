# Regional Climate Summary

This toy repository mimics a scientific workflow that aggregates climate
observations for a handful of weather stations. The repo is intentionally
missing the summarization script. The evaluator expects the white agent to
write code that:

1. Loads `data/records.json`, which contains per-station measurements.
2. Computes the weighted average temperature and humidity using the sample
   counts as weights.
3. Prints the summary statistics and stores them in `artifacts/summary.json`.
4. Keeps the solution modular so future experiments can reuse the functions.

The helper package `repro_utils` exposes `weighted_mean_std` that you can reuse
instead of rewriting the math from scratch.
