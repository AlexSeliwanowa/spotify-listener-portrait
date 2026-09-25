"""PELT-A: звуковые разладки.

Median-агрегация по месяцу, BIC-штраф, bootstrap устойчивость.
"""
import pandas as pd

from pelt_common import compute_bic_pen, pelt_points
from aggregators.music import SOUND_FEATURES


def detect(monthly_sound: pd.DataFrame,
           features=SOUND_FEATURES) -> dict:
    """Прогоняет PELT-A, возвращает точки, стабильность и метаданные."""
    df = monthly_sound[features].fillna(monthly_sound[features].median())

    pen, sigma2, n_obs, n_dims, X_norm = compute_bic_pen(df.values)
    points, stability, pen_bic = pelt_points(
        X_norm, sigma2, n_dims, monthly_sound.index
    )

    return {
        'points': points,
        'stability': stability,
        'pen_bic': pen_bic,
        'sigma2': sigma2,
        'n_obs': n_obs,
        'n_dims': n_dims,
    }