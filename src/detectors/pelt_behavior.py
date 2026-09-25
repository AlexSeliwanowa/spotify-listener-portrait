"""PELT-B: поведенческие разладки.

Финальный набор: 4 сглаженных признака + 2 сырых.
desktop_share исключён (структурный скачок, не разладка).
"""
import pandas as pd

from pelt_common import compute_bic_pen, pelt_points
from aggregators.behavior import BEHAVIOR_FEATURES_PELT


def detect(monthly_behavior: pd.DataFrame,
           features=BEHAVIOR_FEATURES_PELT) -> dict:
    """Прогоняет PELT-B на финальном наборе, возвращает точки и метаданные."""
    df = monthly_behavior[features].fillna(monthly_behavior[features].median())

    pen, sigma2, n_obs, n_dims, X_norm = compute_bic_pen(df.values)
    points, stability, pen_bic = pelt_points(
        X_norm, sigma2, n_dims, monthly_behavior.index
    )

    return {
        'points': points,
        'stability': stability,
        'pen_bic': pen_bic,
        'sigma2': sigma2,
        'n_obs': n_obs,
        'n_dims': n_dims,
    }