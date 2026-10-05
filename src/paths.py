"""Пути проекта. Находятся автоматически относительно расположения src/.

Использование:
    from src.paths import (
        get_base_path, get_dashboard_path,
        get_public_dashboard_path, get_datasets_path,
        get_config_path, ensure_dashboard_subdirs, ensure_datasets_subdirs,
    )
"""
from pathlib import Path


def get_project_root(start=None) -> Path:
    """Корень проекта — папка, в которой есть src/ и 01_data_analysis/."""
    start = Path(start or Path.cwd()).resolve()
    for p in [start] + list(start.parents):
        if (p / 'src').is_dir() and (p / '01_data_analysis').is_dir():
            return p
    raise FileNotFoundError(
        'Корень проекта не найден: нет папки с src/ и 01_data_analysis/ выше текущей директории'
    )


def get_src_path(start=None) -> Path:
    return get_project_root(start) / 'src'


def get_data_path(start=None) -> Path:
    """data/ — сырьё."""
    return get_project_root(start) / 'data'


# --- Приватное (в .gitignore) ---

def get_base_path(start=None) -> Path:
    """Приватные паркеты: data/00_output/."""
    return get_project_root(start) / 'data' / '00_output'


def get_dashboard_path(start=None) -> Path:
    """Приватные агрегаты дашборда: data/00_output/dashboard/."""
    return get_base_path(start) / 'dashboard'


def ensure_dashboard_subdirs(start=None) -> dict:
    """Создаёт sound/, time/, behavior/, collection/ в приватной папке."""
    dashboard = get_dashboard_path(start)
    dashboard.mkdir(parents=True, exist_ok=True)
    paths = {'base': dashboard}
    for sub in ['sound', 'time', 'behavior', 'collection']:
        p = dashboard / sub
        p.mkdir(exist_ok=True)
        paths[sub] = p
    return paths


# --- Публичное (в git) ---

def get_public_dashboard_path(start=None) -> Path:
    """Корень дашборда: 03_dashboard/dashboard/."""
    return get_project_root(start) / '03_dashboard' / 'dashboard'


def get_datasets_path(start=None) -> Path:
    """Публичные маскированные паркеты: 03_dashboard/dashboard/datasets/."""
    return get_public_dashboard_path(start) / 'datasets'


def ensure_datasets_subdirs(start=None) -> dict:
    """Создаёт sound/, time/, behavior/, collection/ в публичной папке."""
    datasets = get_datasets_path(start)
    datasets.mkdir(parents=True, exist_ok=True)
    paths = {'base': datasets}
    for sub in ['sound', 'time', 'behavior', 'collection']:
        p = datasets / sub
        p.mkdir(exist_ok=True)
        paths[sub] = p
    return paths


def get_config_path(start=None) -> Path:
    """JSON-конфиги дашборда: 03_dashboard/dashboard/config/."""
    return get_public_dashboard_path(start) / 'config'


# --- Прочее ---

def get_references_path(start=None) -> Path:
    return get_project_root(start) / '01_data_analysis' / '00_prep' / 'references'


def get_genre_mapping_path(start=None) -> Path:
    return get_references_path(start) / 'genre_mapping.json'