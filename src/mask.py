"""
Маскирование личных данных в датафреймах.

Работает в памяти: получает датафрейм, возвращает маскированный.
Никаких файлов не читает и не пишет — только данные из аргументов.

Реальные значения (email, Spotify ID, личные названия плейлистов)
хранятся в scripts/mask_config.json, который в .gitignore.

Использование в ноутбуке:
    from src.mask import mask_all

    masked = mask_all(
        playlist_links=playlist_links,
        playlists_metadata=playlists_metadata,
        owner_ids=owner_ids_df,
    )
    playlist_links = masked['playlist_links']
"""

import json
import re
from pathlib import Path

import pandas as pd


# --- Путь к локальному конфигу с реальными значениями ---
def _find_config() -> Path:
    """Ищет scripts/mask_config.json от корня репо."""
    start = Path(__file__).resolve().parent.parent
    for p in [start] + list(start.parents):
        cfg = p / 'scripts' / 'mask_config.json'
        if cfg.exists():
            return cfg
    return None





def _load_config():
    """Читает mask_config.json: account_aliases, playlist_mask, collaborator_names."""
    cfg_path = _find_config()
    if cfg_path is None:
        return {}, {}, {}
    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    return (
        cfg.get('account_aliases', {}),
        cfg.get('playlist_mask', {}),
        cfg.get('collaborator_names', {}),
    )


def _clean_account(a):
    """Убирает 'spotify_playlists (...)' обёртку вокруг email."""
    m = re.search(r'\((.+?)\)', str(a))
    return m.group(1).strip() if m else str(a).strip()


def _normalize_name(name):
    return name.lower().strip().replace(' ', '_').replace('*', '').replace('"', '').strip('_')


def _build_mappings(dfs: dict, account_aliases: dict):
    """
    Строит маппинги из самих датафреймов.

    dfs — словарь {'playlist_links': df, 'playlists_metadata': df, 'owner_ids': df, ...}
    account_aliases — из конфига: {'1@mail.com': 'real@mail.com', ...}
    """
    # --- 1. Все форматы account → account_N ---
    def canonical_email(value):
        s = _clean_account(value)
        return account_aliases.get(s, s)

    all_accounts = set()
    for name, df in dfs.items():
        if df is not None and 'account' in df.columns:
            all_accounts.update(df['account'].dropna().unique())

    all_canonical = sorted(set(canonical_email(a) for a in all_accounts))
    email_to_account = {e: f'account_{i+1}' for i, e in enumerate(all_canonical)}
    account_map = {orig: email_to_account[canonical_email(orig)] for orig in all_accounts}

    # --- 2. owner_id → account_N ---
    owner_id_map = {}
    pl_meta = dfs.get('playlists_metadata')
    if pl_meta is not None and {'account', 'owner_id'}.issubset(pl_meta.columns):
        email_to_owner = (
            pl_meta.dropna(subset=['account', 'owner_id'])
            .groupby('account')['owner_id']
            .first()
            .to_dict()
        )
        for email, oid in email_to_owner.items():
            clean_email = _clean_account(email)
            if clean_email in email_to_account:
                owner_id_map[oid] = email_to_account[clean_email]

    # --- 3. display_name → Account N ---
    name_map = {}
    owner_df = dfs.get('owner_ids')
    if owner_df is not None and {'owner_id', 'display_name'}.issubset(owner_df.columns):
        for _, row in owner_df.iterrows():
            oid = row['owner_id']
            if oid in owner_id_map:
                n = owner_id_map[oid].replace('account_', '')
                name_map[row['display_name']] = f'Account {n}'
    # email как display_name
    for email, acc in email_to_account.items():
        name_map.setdefault(email, f'Account {acc.replace("account_", "")}')

    # --- 4. внешние Added By → user_NN ---
    user_map = {}
    all_owner_ids = set(owner_id_map.keys())
    external_ids = set()

    # Из Added By
    pl_links = dfs.get('playlist_links')
    if pl_links is not None and 'Added By' in pl_links.columns:
        external_ids.update(pl_links['Added By'].dropna().unique())

    # Из collaborators (JSON-список)
    pl_meta = dfs.get('playlists_metadata')
    if pl_meta is not None and 'collaborators' in pl_meta.columns:
        for val in pl_meta['collaborators'].dropna().unique():
            if val == '[]':
                continue
            try:
                external_ids.update(json.loads(val))
            except Exception:
                pass

    external_ids = sorted(external_ids - all_owner_ids - {'unknown'})
    user_map = {uid: f'user_{i+1:02d}' for i, uid in enumerate(external_ids)}
    return account_map, owner_id_map, name_map, user_map


def _mask_scalar(value, mapping):
    if pd.isna(value):
        return value
    return mapping.get(value, value)


def _mask_collaborators(value, combined_map):
    if pd.isna(value) or value == '[]':
        return value
    try:
        items = json.loads(value)
    except Exception:
        return value
    masked = [combined_map.get(item, item) for item in items]
    return json.dumps(masked)

def _mask_playlist(value, mask_raw, mask_norm, prefer_norm=False):
    """Плейлист может лежать как в сыром виде, так и в нормализованном —
    пробуем оба словаря, порядок зависит от контекста."""
    if pd.isna(value):
        return value
    s = str(value)
    if prefer_norm:
        if s in mask_norm:
            return mask_norm[s]
        if s in mask_raw:
            return mask_raw[s]
    else:
        if s in mask_raw:
            return mask_raw[s]
        if s in mask_norm:
            return mask_norm[s]
    return value

def _apply_to_df(df: pd.DataFrame, fields: list,
                 account_map, owner_id_map, name_map, user_map, playlist_mask):
    """Маскирует перечисленные поля в одном датафрейме. Возвращает копию."""
    df = df.copy()
    combined_users = {**user_map, **owner_id_map}
    norm_mask = {_normalize_name(k): v for k, v in playlist_mask.items()}

    for field in fields:
        if field not in df.columns:
            continue

        if field == 'account':
            df[field] = df[field].apply(lambda v: _mask_scalar(v, account_map))
        elif field == 'owner_id':
            df[field] = df[field].apply(lambda v: _mask_scalar(v, owner_id_map))
        elif field == 'display_name':
            df[field] = df[field].apply(lambda v: _mask_scalar(v, name_map))
        elif field == 'email':
            df[field] = df[field].apply(lambda v: _mask_scalar(v, account_map))
        elif field == 'Added By':
            df[field] = df[field].apply(lambda v: _mask_scalar(v, combined_users))
        elif field == 'collaborators':
            df[field] = df[field].apply(lambda v: _mask_collaborators(v, {**combined_users, **name_map}))
        elif field == 'playlist_name':
            df[field] = df[field].apply(
                lambda v: _mask_playlist(v, playlist_mask, norm_mask, prefer_norm=False)
            )
        elif field == 'name_norm':
            df[field] = df[field].apply(
                lambda v: _mask_playlist(v, playlist_mask, norm_mask, prefer_norm=True)
            )
        elif field == 'added_by_id':
            df[field] = df[field].apply(lambda v: _mask_scalar(v, combined_users))
    return df


# --- Какие поля в каких сущностях маскируем ---
FIELDS = {
    'cleaned_history':        ['account'],
    'history_with_exportify': ['account', 'Added By'],
    'history_fully_enriched': ['account', 'Added By'],
    'full_history':           ['account', 'Added By'],
    'eda_ready':              ['account', 'Added By'],
    'playlist_links':         ['account', 'Added By', 'playlist_name', 'name_norm'],
    'playlists_metadata':     ['account', 'owner_id', 'collaborators', 'playlist_name', 'name_norm'],
    'owner_ids':              ['owner_id', 'display_name'],
    'user_attributes':        ['account', 'email'],
    'inferences':             ['account'],
    'search_queries':         ['account'],
    'library_tracks':         ['account'],
    'tracks_exportify':       ['account'],
    # --- дашборд (prep) ---
    'playlist_portraits':          ['playlist_name'],
    'playlist_collaborators':      ['playlist_name', 'added_by_id', 'display_name'],
    'collection_activity_scatter': ['name_norm'],
}


def mask_all(**dfs) -> dict:
    """
    Принимает датафреймы по именам, возвращает маскированные.

    Пример:
        result = mask_all(
            playlist_links=playlist_links,
            playlists_metadata=playlists_metadata,
            owner_ids=owner_ids_df,
        )
        playlist_links = result['playlist_links']
        ...

    Если конфиг не найден — возвращает датафреймы без изменений.
    """
    account_aliases, playlist_mask, collaborator_names = _load_config()
    if not account_aliases and not playlist_mask and not collaborator_names:
        print('⚠️ mask_config.json не найден или пуст — маскирование ПРОПУЩЕНО.')
        print('   Данные уйдут в datasets/ без маски.')
        return dfs

    # Дополняем name_map из конфига
    account_map, owner_id_map, name_map, user_map = _build_mappings(dfs, account_aliases)
    name_map.update(collaborator_names)

    result = {}
    for name, df in dfs.items():
        if df is None:
            result[name] = None
            continue
        fields = FIELDS.get(name, [])
        result[name] = _apply_to_df(
            df, fields, account_map, owner_id_map, name_map, user_map, playlist_mask
        )
    return result