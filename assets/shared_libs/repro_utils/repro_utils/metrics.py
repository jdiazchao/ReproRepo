"""Shared metric helpers used across dummy experiments."""

from __future__ import annotations

import math
from typing import Iterable, Sequence, Tuple


def rmse(true: Sequence[float], pred: Sequence[float]) -> float:
    if len(true) != len(pred):
        raise ValueError("Series must be same length")
    if not true:
        raise ValueError("Series cannot be empty")
    error = sum((t - p) ** 2 for t, p in zip(true, pred)) / len(true)
    return math.sqrt(error)


def pearson_r(true: Sequence[float], pred: Sequence[float]) -> float:
    if len(true) != len(pred):
        raise ValueError("Series must be same length")
    n = len(true)
    sum_x = sum(true)
    sum_y = sum(pred)
    sum_xy = sum(x * y for x, y in zip(true, pred))
    sum_x2 = sum(x * x for x in true)
    sum_y2 = sum(y * y for y in pred)
    numerator = (n * sum_xy) - (sum_x * sum_y)
    denominator = math.sqrt((n * sum_x2 - sum_x**2) * (n * sum_y2 - sum_y**2))
    if denominator == 0:
        raise ValueError("Denominator is zero; cannot compute Pearson R")
    return numerator / denominator


def weighted_mean_std(values: Sequence[float], weights: Sequence[int]) -> Tuple[float, float]:
    if len(values) != len(weights):
        raise ValueError("Mismatched inputs")
    total_weight = sum(weights)
    if total_weight == 0:
        raise ValueError("Total weight is zero")
    mean = sum(v * w for v, w in zip(values, weights)) / total_weight
    variance = sum(w * (v - mean) ** 2 for v, w in zip(values, weights)) / total_weight
    return mean, math.sqrt(variance)
