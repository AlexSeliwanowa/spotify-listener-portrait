"""Cosine: смена идентичности по составу артистов.

Не по жанрам — жанры слишком инертны. Пики через медиана + 2·MAD.
"""
import numpy as np
import pandas as pd


def _monthly_share_matrix(df_input: pd.DataFrame,
                          id_col: str,
                          explode_by_comma: bool = False,
                          min_events: int = 10) -> pd.DataFrame:
    """Матрица месяц × категория (доля событий месяца)."""
    d = df_input[['period', id_col]].dropna().copy()
    if explode_by_comma:
        d[id_col] = d[id_col].astype(str).str.split(',')
        d = d.explode(id_col)
        d[id_col] = d[id_col].str.strip()
    d = d[d[id_col] != 'unknown']

    month_sizes = d.groupby('period').size()
    valid_months = month_sizes[month_sizes >= min_events].index
    d = d[d['period'].isin(valid_months)]

    counts = d.groupby(['period', id_col]).size().unstack(fill_value=0)
    shares = counts.div(counts.sum(axis=1), axis=0)
    return shares.sort_index()


def _cosine_distance_series(shares: pd.DataFrame) -> pd.Series:
    """Косинусное расстояние между соседними месяцами."""
    vals = shares.values
    idx = shares.index
    out = []
    for i in range(1, len(vals)):
        a, b = vals[i-1], vals[i]
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        out.append(1 - np.dot(a, b) / denom if denom > 0 else np.nan)
    return pd.Series(
        out, index=[idx[i].strftime('%Y-%m') for i in range(1, len(idx))]
    )


def _find_peaks(dist_series: pd.Series, k_mad: float = 2.0):
    """Пики выше медианы + k·MAD."""
    med = dist_series.median()
    mad = np.median(np.abs(dist_series - med))
    threshold = med + k_mad * mad
    peaks = dist_series[dist_series > threshold].sort_values(ascending=False)
    return peaks, threshold

def _group_peaks(peaks_dict: dict, gap_months: int = 3) -> dict:
    """Соседние пики (≤ gap_months) → один. Оставляем пик с макс. distance."""
    if not peaks_dict:
        return {}
    periods = sorted(pd.Period(p, 'M') for p in peaks_dict.keys())
    clusters, current = [], [periods[0]]
    for p in periods[1:]:
        if (p - current[-1]).n <= gap_months:
            current.append(p)
        else:
            clusters.append(current)
            current = [p]
    clusters.append(current)

    out = {}
    for cl in clusters:
        best = max(cl, key=lambda p: peaks_dict.get(str(p), 0))
        out[str(best)] = peaks_dict[str(best)]
    return out



def detect(df: pd.DataFrame, id_col: str = 'artist_name',
           min_confidence: float = 0.5) -> dict:
    """
    Детектор смены идентичности.

    Возвращает:
        points: список 'YYYY-MM' (пики с bootstrap ≥ min_confidence)
        stability: dict {дата: доля}
        peaks_all: все пики выше порога (для отладки)
    """
    artist_dist = _cosine_distance_series(
        _monthly_share_matrix(df, id_col, explode_by_comma=False)
    )
    peaks, threshold = _find_peaks(artist_dist)
    grouped = _group_peaks(peaks.to_dict(), gap_months=3)

    # Bootstrap устойчивости пиков
    rng = np.random.default_rng(42)
    counts = {}
    n_months = len(artist_dist)
    n_keep = int(round(n_months * 0.85))

    for _ in range(200):
        keep_idx = np.sort(rng.choice(n_months, size=n_keep, replace=False))
        subset = artist_dist.iloc[keep_idx]
        med_s = subset.median()
        mad_s = np.median(np.abs(subset - med_s))
        thr_s = med_s + 2 * mad_s
        for d in subset[subset > thr_s].index:
            counts[d] = counts.get(d, 0) + 1

    stability = {k: v / 200 for k, v in counts.items()}
    points = [p for p in grouped.keys() if stability.get(p, 0) >= min_confidence] 
    return {
        'points': points,
        'stability': stability,
        'peaks_all': peaks.to_dict(),
        'threshold': threshold,
    }

