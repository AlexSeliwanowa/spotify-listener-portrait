"""Загрузка parquet-файлов проекта.

Одна точка входа: load_all(base_path) → dict со всеми DataFrame.

Использование:
    from loaders import load_all

    data = load_all(BASE_PATH)
    df = data['df']
    tracks = data['tracks_exportify']
"""
from pathlib import Path
import pandas as pd


# Соответствие: ключ в dict → имя файла в base_path
SOURCE_FILES = {
    'df':                   'eda_ready.parquet',
    'tracks_exportify':     'tracks_exportify.parquet',
    'playlist_links':       'playlist_links.parquet',
    'library_tracks':       'library_tracks.parquet',
    'owner_ids':            'owner_ids.parquet',
    'playlists_metadata':   'playlists_metadata.parquet',
}


def load_all(base_path) -> dict:
    """
    Читает все parquet-файлы из base_path.

    Parameters
    ----------
    base_path : Path
        Обычно результат get_base_path().

    Returns
    -------
    dict — с ключами из SOURCE_FILES.
    """
    base_path = Path(base_path)
    data = {}
    for key, fname in SOURCE_FILES.items():
        path = base_path / fname
        if not path.exists():
            raise FileNotFoundError(f'Не найден: {path}')
        data[key] = pd.read_parquet(path)
    return data