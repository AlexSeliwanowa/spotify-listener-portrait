"""Diagnostics: проверка качества сигнала.

Проверки, которые не влияют на продакшн:
    - SNR (signal-to-noise ratio) — насколько признак «сигнальный»
    - permutation-тест прироста SNR — прирост реален или артефакт сглаживания

Используется в исследованиях (выбор признаков для PELT-B).
В дашборд не идёт.
"""
import numpy as np
import pandas as pd


# ============================================================================
# SNR
# ============================================================================

def compute_snr(series: pd.Series, window: int = 3) -> float:
    """
    Signal-to-Noise Ratio: std rolling medians / median rolling std.

    signal = насколько меняется уровень месяца к месяцу (std сглаженной линии)
    noise  = насколько шумит внутри окна (median rolling std)
    """
    rolling_med = series.rolling(window, center=True, min_periods=2).median()
    rolling_std = series.rolling(window, center=True, min_periods=2).std()
    signal = rolling_med.std()
    noise = rolling_std.median()
    if noise == 0 or pd.isna(noise):
        return np.nan
    return signal / noise


# ============================================================================
# PERMUTATION-ТЕСТ SNR
# ============================================================================

def snr_gain_permutation(series: pd.Series,
                          n_perm: int = 200,
                          window: int = 3,
                          seed: int = 42):
    """
    Проверяет, отличается ли прирост SNR при сглаживании от прироста
    на случайных данных.

    Логика:
        1. Считаем SNR сырого ряда и сглаженного → real_gain.
        2. Перемешиваем значения (порядок ломается, значения те же).
        3. Считаем SNR на перемешанном и сглаженном → распределение шума.
        4. Если real_gain > 95-й перцентиль шума → сигнал реален.

    Возвращает (real_gain, noise_p95, all_gains).
    """
    snr_raw = compute_snr(series, window)
    snr_smooth = compute_snr(
        series.rolling(window, center=True, min_periods=2).mean(), window
    )
    real_gain = snr_smooth - snr_raw

    rng = np.random.default_rng(seed)
    values = series.dropna().values
    gains = []

    for _ in range(n_perm):
        shuffled = pd.Series(rng.permutation(values),
                             index=series.dropna().index)
        snr_r = compute_snr(shuffled, window)
        snr_s = compute_snr(
            shuffled.rolling(window, center=True, min_periods=2).mean(),
            window,
        )
        if not (np.isnan(snr_r) or np.isnan(snr_s)):
            gains.append(snr_s - snr_r)

    return real_gain, np.percentile(gains, 95), gains