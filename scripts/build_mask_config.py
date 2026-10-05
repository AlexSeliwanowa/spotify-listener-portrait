"""
Одноразовая генерация mask_config.json из приватных паркетов.

Читает data/00_output/, извлекает реальные email, Spotify ID,
display_name и названия плейлистов, пишет scripts/mask_config.json.

Запуск: python scripts/build_mask_config.py

После этого файл mask_config.json заполняется всеми маппингами,
которые нужны для маскирования. Далее только src/mask.py его читает.
"""

import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE = PROJECT_ROOT / 'data' / '00_output'
CONFIG_PATH = Path(__file__).resolve().parent / 'mask_config.json'


def clean_account(a):
    """'spotify_playlists (1@mail.com)' → '1@mail.com'."""
    import re
    m = re.search(r'\((.+?)\)', str(a))
    return m.group(1).strip() if m else str(a).strip()


def main():
    print(f'Reading from: {SOURCE}')

    # --- 1. Все форматы account из разных паркетов ---
    all_accounts = set()
    for f in SOURCE.glob('*.parquet'):
        try:
            df = pd.read_parquet(f)
            if 'account' in df.columns:
                all_accounts.update(df['account'].dropna().unique())
        except Exception:
            pass

    # Уникальные аккаунты по чистому email (снимаем обёртку Exportify)
    clean_emails = sorted(set(clean_account(a) for a in all_accounts))

    # --- 2. owner_id и display_name ---
    owner_ids_df = pd.read_parquet(SOURCE / 'owner_ids.parquet')
    real_owner_ids = sorted(owner_ids_df['owner_id'].dropna().tolist())
    real_names = sorted(owner_ids_df['display_name'].dropna().tolist())

    # --- 3. Внешние Added By из playlist_links ---
    pl = pd.read_parquet(SOURCE / 'playlist_links.parquet')
    all_added_by = pl['Added By'].dropna().unique()
    owner_set = set(real_owner_ids)
    external_ids = sorted(
        set(all_added_by) - owner_set - {'unknown'}
    )

    # --- 4. Уникальные названия плейлистов (только personal/collaborative) ---
    pl_personal = pl[pl['playlist_type'].isin(['personal', 'collaborative'])]
    playlist_names = sorted(
        pl_personal['playlist_name'].dropna().unique().tolist()
    )

    # --- 5. Сборка конфига ---
    # account_map: все форматы → account_N (по алфавиту чистого email)
    account_map = {}
    for i, email in enumerate(clean_emails):
        mask = f'account_{i+1}'
        account_map[email] = mask
        account_map[f'spotify_playlists ({email})'] = mask

    # owner_map: реальный Spotify username → account_N
    # Связка через playlists_metadata: email и owner_id в одной строке
    pl_meta = pd.read_parquet(SOURCE / 'playlists_metadata.parquet')
    email_to_owner = (
        pl_meta.dropna(subset=['account', 'owner_id'])
        .groupby('account')['owner_id']
        .first()
        .to_dict()
    )
    owner_map = {}
    for email, oid in email_to_owner.items():
        clean_e = clean_account(email)
        if clean_e in account_map:
            owner_map[oid] = account_map[clean_e]

    # name_map: display_name → Account N
    name_map = {}
    for _, row in owner_ids_df.iterrows():
        oid = row['owner_id']
        if oid in owner_map:
            n = owner_map[oid].replace('account_', '')
            name_map[row['display_name']] = f'Account {n}'

    # external_user_map: внешние ID → user_NN
    external_user_map = {
        uid: f'user_{i+1:02d}'
        for i, uid in enumerate(external_ids)
    }

    # playlist_mask: заготовка — только нейтральные по умолчанию
    # личные названия надо будет разметить вручную
    playlist_mask = {}

    config = {
        'account_map': account_map,
        'owner_map': owner_map,
        'name_map': name_map,
        'external_user_map': external_user_map,
        'playlist_mask': playlist_mask,
    }

    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f'\n✅ Config written: {CONFIG_PATH}')
    print(f'   account_map:        {len(account_map)} entries')
    print(f'   owner_map:          {len(owner_map)} entries')
    print(f'   name_map:           {len(name_map)} entries')
    print(f'   external_user_map:  {len(external_user_map)} entries')
    print(f'   playlist_mask:      {len(playlist_mask)} entries (empty — fill manually)')

    # Показать список плейлистов для ручной разметки
    print('\n📋 Playlists to review for personal masking:')
    for name in playlist_names:
        print(f'   {name}')


if __name__ == '__main__':
    main()