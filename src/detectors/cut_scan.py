"""Cut-scan: регионы переходов.

Не точки, а зоны нестабильности — данные меняются за несколько месяцев,
а не за один. Возвращает регионы для фоновой заливки.
"""
import numpy as np
import pandas as pd


SCAN_FEATURES = ['valence', 'energy', 'danceability', 'instrumentalness']
PRACTICAL_THRESHOLD = 0.02
MIN_WINDOW_MONTHS = 4
CLUSTER_GAP_MONTHS = 3


def _scan_deltas(monthly_df: pd.DataFrame, features=SCAN_FEATURES):
    """Считает max_delta для каждой точки разреза."""
    months_sorted = monthly_df.index.sort_values()
    candidate_splits = months_sorted[MIN_WINDOW_MONTHS:-MIN_WINDOW_MONTHS]

    ms = monthly_df.copy()
    for f in features:
        ms[f] = ms[f].fillna(ms[f].median())

    rows = []
    for split in candidate_splits:
        before = ms[ms.index < split]
        after = ms[ms.index >= split]
        if len(before) < MIN_WINDOW_MONTHS or len(after) < MIN_WINDOW_MONTHS:
            continue
        max_diff = max(
            abs(before[f].median() - after[f].median()) for f in features
        )
        rows.append({'split': str(split), 'max_delta': max_diff})

    scan = pd.DataFrame(rows).set_index('split')
    scan['gradient'] = scan['max_delta'].diff().abs()

    # Локальный пик
    vals = scan['max_delta'].values
    is_peak = np.zeros(len(vals), dtype=bool)
    for i in range(1, len(vals) - 1):
        if vals[i] > vals[i-1] and vals[i] > vals[i+1]:
            is_peak[i] = True
    scan['is_peak'] = is_peak

    return scan


def detect(monthly_sound: pd.DataFrame, k_mad: float = 1.5) -> dict:
    """Возвращает регионы переходов."""
    scan = _scan_deltas(monthly_sound)

    grad_valid = scan['gradient'].dropna()
    med_grad = grad_valid.median()
    mad_grad = np.median(np.abs(grad_valid - med_grad))
    grad_threshold = med_grad + k_mad * mad_grad

    scan['is_break'] = (
        (scan['max_delta'] >= PRACTICAL_THRESHOLD) &
        ((scan['gradient'] > grad_threshold) | scan['is_peak'])
    )
    candidates = scan[scan['is_break']].copy()

    # Кластеризация
    cand_months = sorted([pd.Period(s, 'M') for s in candidates.index])
    if not cand_months:
        return {'regions': [], 'threshold': grad_threshold, 'candidates': []}

    clusters = []
    current = [cand_months[0]]
    for m in cand_months[1:]:
        if (m - current[-1]).n <= CLUSTER_GAP_MONTHS:
            current.append(m)
        else:
            clusters.append(current)
            current = [m]
    clusters.append(current)

    regions = []
    for cl in clusters:
        cl_str = [str(m) for m in cl]
        sub = candidates.loc[[s for s in cl_str if s in candidates.index]]
        top = sub['max_delta'].idxmax()
        regions.append({
            'date': top,
            'region_start': cl_str[0],
            'region_end': cl_str[-1],
            'max_delta': float(sub.loc[top, 'max_delta']),
            'n_candidates': len(cl_str),
        })

    return {
        'regions': regions,
        'threshold': grad_threshold,
        'candidates': candidates.index.tolist(),
    }