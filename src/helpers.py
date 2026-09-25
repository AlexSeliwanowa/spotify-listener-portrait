"""Helpers: чистые утилиты без привязки к домену.

Никаких импортов из src/. Работает со скалярами и df напрямую.
"""
import numpy as np
import pandas as pd


# ============================================================================
# ЭНТРОПИЯ
# ============================================================================

def normalized_entropy(counts) -> float:
    """
    Энтропия Шеннона, нормализованная в [0, 1].

    0 — все значения в одной категории.
    1 — все категории представлены равномерно.

    counts : pd.Series или array-like — частоты по категориям.
    """
    if counts is None or len(counts) <= 1:
        return 0.0
    counts = counts[counts > 0]
    if len(counts) <= 1:
        return 0.0
    p = counts / counts.sum()
    H = -np.sum(p * np.log2(p + 1e-12))
    return H / np.log2(len(counts))


# ============================================================================
# ПЛАТФОРМА
# ============================================================================

# Ключевые слова для классификации.
# Порядок важен: сначала mobile, потом desktop, потом web.
# web_player может содержать os в строке — поэтому ищем os-слова, не сам web_player.
_MOBILE_KEYWORDS = ('android', 'ios', 'iphone', 'ipad')
_DESKTOP_KEYWORDS = ('windows', 'linux', 'macos', 'mac os', 'macintosh')


def platform_type(platform) -> str:
    """
    Классификация платформы по подстроке.

    Возвращает одно из:
        'mobile'  — Android, iOS (включая web_player на мобильном)
        'desktop' — Windows, Linux, macOS (включая web_player на десктопе)
        'web'     — web_player без явной OS
        'other'   — unknown, NaN, всё непонятное
    """
    if pd.isna(platform):
        return 'other'
    pl = str(platform).lower()
    if any(k in pl for k in _MOBILE_KEYWORDS):
        return 'mobile'
    if any(k in pl for k in _DESKTOP_KEYWORDS):
        return 'desktop'
    if 'web_player' in pl:
        return 'web'
    return 'other'


def is_desktop(platform) -> bool:
    """Windows, Linux, macOS. Включая web_player на десктопе."""
    return platform_type(platform) == 'desktop'


def is_mobile(platform) -> bool:
    """Android, iOS. Включая web_player на мобильном."""
    return platform_type(platform) == 'mobile'


def desktop_share(df: pd.DataFrame) -> float:
    """Доля событий на десктопе (Windows / Linux / macOS)."""
    if df.empty:
        return np.nan
    return df['platform'].apply(is_desktop).mean()


def mobile_share(df: pd.DataFrame) -> float:
    """Доля событий на мобильном (Android / iOS)."""
    if df.empty:
        return np.nan
    return df['platform'].apply(is_mobile).mean()


# ============================================================================
# ВРЕМЯ СУТОК
# ============================================================================

def night_share(df: pd.DataFrame, hours: tuple = (0, 5)) -> float:
    """
    Доля событий в диапазоне часов (по умолчанию 0–5 включительно).

    Извлекает час из ts_naive. Не требует колонки 'hour'.
    """
    if df.empty:
        return np.nan
    h = df['ts_naive'].dt.hour
    return h.between(hours[0], hours[1], inclusive='both').mean()