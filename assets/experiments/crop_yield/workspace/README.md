# High-Altitude Crop Yield Study

The research group compared rain-fed harvests across three pilot regions.
The raw measurements live in `data/yields.csv` and contain the year,
planted area, rainfall, and adjusted yield (tons per hectare). The paper
reports weighted aggregations by planted area and correlates rainfall with
yields to reason about irrigation needs. The orchestration code was lost and
must be rebuilt from scratch.

The reproduction checklist:

1. Parse `data/yields.csv`.
2. Group by region and compute the area-weighted mean yield, weighted
   standard deviation, total planted area, and the correlation between rainfall
   and yield. The helper `repro_utils.metrics.pearson_r` is available on the
   PYTHONPATH.
3. Report a global section that combines every region, mentions the best
   performing region, and includes the overall correlation.
4. Print a short textual table plus emit the machine-readable
   `artifacts/yield_report.json`.
