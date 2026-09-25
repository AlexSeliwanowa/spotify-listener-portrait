"""PELT common: BIC-штраф и bootstrap устойчивость.

Общая логика для PELT-A (звук) и PELT-B (поведение).
Не работает ни с df, ни с периодичностью — принимает матрицу X и индекс.
"""
import numpy as np
import pandas as pd
import ruptures as rpt


def compute_bic_pen(X: np.ndarray):
    """
    BIC-подобный штраф (Lavielle): pen = σ² · dim · log(n).
    σ² оценивается робастно через MAD первых разностей.

    Возвращает (pen, sigma2, n_obs, n_dims, X_norm).
    """
    mean, std = X.mean(axis=0), X.std(axis=0)
    std[std == 0] = 1
    X_norm = (X - mean) / std

    diffs = np.diff(X_norm, axis=0)
    mad = np.median(np.abs(diffs - np.median(diffs, axis=0)), axis=0)
    sigma2 = np.mean((mad / 0.6745) ** 2)

    n_obs, n_dims = X_norm.shape
    pen = sigma2 * n_dims * np.log(n_obs)
    return pen, sigma2, n_obs, n_dims, X_norm


def pelt_points(
    X_norm: np.ndarray,
    sigma2: float,
    n_dims: int,
    index: pd.Index,
    n_boot: int = 200,
    drop_frac: float = 0.15,
    seed: int = 42,
):
    """
    PELT с BIC-штрафом + bootstrap устойчивость точек.

    - X_norm: нормализованная матрица (n_obs × n_dims)
    - sigma2, n_dims: из compute_bic_pen
    - index: pd.Index с месяцами (Period) — для датировки точек

    Возвращает:
        points: список 'YYYY-MM'
        stability: dict {'YYYY-MM': доля}
        pen_bic: использованный штраф
    """
    n_obs = X_norm.shape[0]
    pen_bic = sigma2 * n_dims * np.log(n_obs)

    bkps = rpt.Pelt(model="l2").fit(X_norm).predict(pen=pen_bic)
    points = [index[i].strftime('%Y-%m') for i in bkps[:-1]]

    rng = np.random.default_rng(seed)
    n_keep = int(round(n_obs * (1 - drop_frac)))
    counts = {}

    for _ in range(n_boot):
        keep_idx = np.sort(rng.choice(n_obs, size=n_keep, replace=False))
        X_sub = X_norm[keep_idx]
        pen_sub = sigma2 * n_dims * np.log(n_keep)
        bkps_sub = rpt.Pelt(model="l2").fit(X_sub).predict(pen=pen_sub)
        for i in bkps_sub[:-1]:
            d = index[keep_idx[i]].strftime('%Y-%m')
            counts[d] = counts.get(d, 0) + 1

    stability = {k: v / n_boot for k, v in counts.items()}
    return points, stability, pen_bic