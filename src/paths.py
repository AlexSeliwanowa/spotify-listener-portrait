"""Пути проекта. Находятся автоматически относительно расположения src/.

Никаких абсолютных путей типа D:\\... — работает на любой машине,
если сохранена структура проекта.

Использование:
    from paths import get_base_path, get_dashboard_path, ensure_dashboard_subdirs

    BASE_PATH = get_base_path()
    PATHS = ensure_dashboard_subdirs()
"""
from pathlib import Path


def get_project_root(start=None) -> Path:
    """
    Корень проекта — папка, в которой есть и src/, и notebooks/.
    Ищет вверх от start (по умолчанию — текущая директория).
    """
    start = Path(start or Path.cwd()).resolve()
    for p in [start] + list(start.parents):
        if (p / 'src').is_dir() and (p / 'notebooks').is_dir():
            return p
    raise FileNotFoundError(
        'Корень проекта не найден: нет папки с src/ и notebooks/ выше текущей директории'
    )


def get_src_path(start=None) -> Path:
    """Путь к src/."""
    return get_project_root(start) / 'src'


def get_base_path(start=None) -> Path:
    """Корень данных: data/stage4_output/."""
    return get_project_root(start) / 'data' / 'stage4_output'


def get_dashboard_path(start=None) -> Path:
    """Папка dashboard/ со всеми паркетами для дашборда."""
    return get_base_path(start) / 'dashboard'


def get_config_path(start=None) -> Path:
    """Папка dashboard/config/ с JSON-конфигами."""
    return get_project_root(start) / 'dashboard' / 'config'


def ensure_dashboard_subdirs(start=None) -> dict:
    """
    Создаёт нужные папки в dashboard/ и возвращает словарь с путями.

    Возвращает:
        {
            'base':  DASHBOARD_DATA_PATH,
            'sound': DASHBOARD_DATA_PATH / 'sound',
            'time':  DASHBOARD_DATA_PATH / 'time',
            'behavior': DASHBOARD_DATA_PATH / 'behavior',
            'collection': DASHBOARD_DATA_PATH / 'collection',
        }
    """
    dashboard = get_dashboard_path(start)
    dashboard.mkdir(parents=True, exist_ok=True)

    subdirs = ['sound', 'time', 'behavior', 'collection']
    paths = {'base': dashboard}
    for sub in subdirs:
        p = dashboard / sub
        p.mkdir(exist_ok=True)
        paths[sub] = p

    return paths