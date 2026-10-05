import pandas as pd


def format_value(value, unit):
    if unit == 'percent':
        return f'{value * 100:.0f}%'
    elif unit == 'index':
        return f'{value:.2f}'
    elif unit == 'hours':
        return f'{value:,.0f}h'
    elif unit == 'days':
        return f'{value:,.0f}d'
    elif unit == 'count':
        return f'{value:,.1f}'
    return f'{value:.2f}'


def format_table_value(v, unit):
    if pd.isna(v):
        return '—'
    if unit == 'percent':
        return f"{v * 100:.0f}%"
    elif unit == 'index':
        return f"{v:.2f}"
    elif unit == 'hours':
        return f"{v:,.0f}"
    elif unit == 'days':
        return f"{v:,.0f}"
    elif unit == 'count':
        return f"{v:.1f}"
    return f"{v:.2f}"


def is_borderline(value, thresholds, margin_ratio=0.06):
    if not thresholds or len(thresholds) != 2:
        return False
    low_t, high_t = thresholds
    span = (high_t - low_t) or max(abs(high_t), 1)
    margin = span * margin_ratio
    return abs(value - low_t) < margin or abs(value - high_t) < margin