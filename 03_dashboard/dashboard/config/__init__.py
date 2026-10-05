"""Конфиг дашборда: загрузка JSON + пути из src.paths."""
import json
from pathlib import Path

from src.paths import get_base_path, get_datasets_path

CONFIG_DIR = Path(__file__).resolve().parent

# BASE_PATH — приватные паркеты (источник для prep, не для app в продакшене)
BASE_PATH = get_base_path()

# DASHBOARD_PATH — публичные маскированные паркеты, их читает app
DASHBOARD_PATH = get_datasets_path()


def _load(name):
    with open(CONFIG_DIR / name, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_config() -> dict:
    return {
        'dashboard':       _load('dashboard_config.json'),
        'indices_display': _load('indices_display.json'),
        'profiles':        _load('profile_labels.json'),
        'takeaway':        _load('product_takeaway.json'),
        'time_defs':       _load('time_definitions.json'),
    }