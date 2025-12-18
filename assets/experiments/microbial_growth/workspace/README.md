# Microbial Growth Kinetics

The lab leaked the OD600 readings for three engineered strains but the
analysis scripts vanished. The study fits an exponential model (linear on the
log-scale) to estimate growth rates and doubling times, then reports the mean
coefficient of determination (R²) across strains.

Recreate the automation by:

1. Loading `data/growth.csv`.
2. For each strain, fit `log(OD) = rate * time + intercept` using ordinary
   least squares. Report the growth rate, intercept, doubling time, and R².
3. Emit `artifacts/growth_report.json` with per-strain metrics, the fastest
   strain, and the average doubling time.
4. Print a short textual summary so the PI can eyeball the slopes.
