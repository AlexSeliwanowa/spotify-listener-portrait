🇬🇧 English | [🇷🇺 Русский](./README_ru.md)

# 00_prep — data assembly

The first layer of the project. Turns raw Spotify exports (JSON + CSV) into 15 parquets in `data/00_output/`. Everything that follows — EDA, methodology, dashboard — reads **only these parquets** and never touches the raw files again.

Four notebooks, each creating its own part:

| Notebook | What it assembles |
|---|---|
| `00_0_orphans_detect` | Finds orphan tracks, prepares CSV for upload to Spotify |
| `00_1_build_full_history` | History + audio features → 8 parquets |
| `00_2_account_data` | Account data: library, playlists, owners → 7 parquets |
| `00_3_quality_check` | Checks the integrity of all 15 parquets |

The only manual step is uploading orphans to Spotify and exporting them via Exportify. `00_0` makes this as painless as possible (see below).

**Code.** The notebooks use `src/paths.py` (`get_data_path()`, `get_project_root()`). `src/` is already in the repository — no setup needed, but the notebooks must be inside the cloned project.

If the `data/` folders don't exist yet — cell 0 of the `00_0` notebook will create the entire structure itself (`Spotify/`, `Exportify/`, `00_output/` and subfolders). You can run it first, place the files in the ready tree, and then run the remaining cells.

## How to get a Spotify export

Two separate exports, requested on the [Account Privacy](https://www.spotify.com/account/privacy/) page:

| What to request | What arrives | Where to put it |
|---|---|---|
| **Account data** | JSON: `Playlist*.json`, `YourLibrary.json`, `UserAttributes.json`, `Inferences.json`, `SearchQueries.json`, `Follow.json`, etc. | `data/Spotify/Spotify_Account_ Data/` |
| **Extended streaming history** | JSON `Streaming_History_Audio_*.json` — one per year | `data/Spotify/Spotify_ Extended_Streaming_History/` |

Exports arrive by email **one after another, in separate emails**, over several days (sometimes up to 30). The archive contains a `Spotify Account Data/` or `Spotify Extended Streaming History/` folder with the files inside.

## How to get CSV from Exportify

The Spotify API does not provide audio features (`valence`, `energy`, `danceability`, and others) — only Exportify does.

1. Open https://exportify.net/ and log in via Spotify.
2. Wait for Exportify to load the playlist list.
3. Click **Export** on each playlist — including `Liked Songs`.
4. Place the downloaded CSVs into `data/Exportify/spotify_playlists (<account>)/`.

`<account>` is an arbitrary name (nickname, `main`). The notebooks read by the mask `spotify_playlists (*)/*.csv`. One account — you can put them in one folder.

**Where NOT to put them:** `data/Exportify/exportify_orphan_export/` — a separate folder, filled by `00_0` (see "About orphans").

## Input

```
data/
├── Spotify/
│   ├── Spotify_ Extended_Streaming_History/
│   │   └── Streaming_History_Audio_*.json
│   └── Spotify_Account_ Data/
│       ├── Playlist*.json
│       ├── YourLibrary.json
│       ├── UserAttributes.json
│       └── ...
└── Exportify/
    ├── spotify_playlists (<account>)/        ← playlists + Liked_Songs.csv
    └── exportify_orphan_export/              ← result of 00_0
        └── *.csv
```

One account — files can be placed in the root of the folder. Multiple — a subfolder for each. The notebooks search both ways.

## Notebooks

| #    | Notebook                        | Task                                                                                                                                              | What it creates                                                  |
| ---- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| 00_0 | `00_0_orphans_detect.ipynb`     | Finds tracks that were played but did not make it into playlists or likes. Prepares CSV with URIs for upload to Spotify — bypassing the Exportify limitation | `data/Exportify/orphans_to_add/*.csv` + `created_playlists.json` |
| 00_1 | `00_1_build_full_history.ipynb` | Assembles history + audio features                                                                                                                | 8 parquets (see table below)                                     |
| 00_2 | `00_2_account_data.ipynb`       | Parses Account Data: library, playlists, owners                                                                                                   | 7 parquets + enriches `playlist_links`                           |
| 00_3 | `00_3_quality_check.ipynb`      | Checks the integrity of all parquets                                                                                                              | Report ✅ / ⚠️ / ❌                                                |

## Run order

```
00_0  →  find orphans
        ↓
      [manual step: upload orphans to Spotify,
       export via Exportify,
       place CSVs into data/Exportify/exportify_orphan_export/]
        ↓
00_1  →  assemble history + features
00_2  →  assemble reference tables
00_3  →  check everything
```

**The order is mandatory.** `00_2` (cell 8) reads `playlist_links.parquet`, created in `00_1` (cell 3.1). Running `00_2` before `00_1` is impossible — it will crash with `FileNotFoundError`.

**No orphans?** If all tracks are already in playlists or likes — skip `00_0` and start with `00_1`.

## About orphans — why this exists

Exportify provides audio features (`valence`, `energy`, `danceability` and others) only for tracks that sit in playlists or likes. Tracks that were played but did not make it into a playlist or likes — **orphans** — remain without features. This is not a rare case: **a large part of the history ends up without features**, and without them you cannot build a sound portrait, Sound clusters, sound changepoints, or most dashboard indices.

Exportify cannot "give features for a list of URIs" — it can only export playlists. So orphans must **first be placed into a playlist** for Exportify to see them. This is the only manual step in the entire pipeline. `00_0` makes it as painless as possible: it finds orphans, creates playlists (if using the API), and verifies the result.

**Logic in three steps:**

1. Reads all JSON with listening history, collects unique `spotify_track_uri`.
2. Reads all CSVs from Exportify (playlists + likes), collects unique URIs. Deduplication is global, not per-account.
3. Subtracts: `orphans = history − (playlists ∪ likes)`.

An orphan is determined by the intersection of all accounts: a track that was played in at least one account but was not saved to any playlist or liked in any account is an orphan. Splitting by accounts at this step would lose meaning, so `00_0` writes a single combined CSV.

**What is saved:**
- `orphans_uris.csv` — all orphans, a single column `spotify_track_uri`;
- `orphans_batch_NN.csv` — batches of 10,000 URIs;
- `created_playlists.json` — playlist metadata (with `METHOD='api'`).

The CSV has no limit. The **Spotify playlist** has a limit — 10,000 tracks. Hence `BATCH_SIZE = 10_000`: one batch = one private playlist `__ORPHANS_NN`.

**The `METHOD` fork (cell 5):**

**API (automated).** `METHOD = 'api'` (cell 6a). Requires `spotify_credentials.json` next to the notebook (in `.gitignore`), a Premium account, and a one-time OAuth flow. The notebook creates private playlists `__ORPHANS_01`, `__ORPHANS_02`, … and adds tracks in batches of 100 (Spotify API limit). Duplicate protection: if `__ORPHANS_NN` already exists and the track count matches — skip; if the count differs — leave it alone and flag a conflict.

`spotify_credentials.json` is created once: in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), create an app, copy the `client_id` and `client_secret`, add a `redirect_uri` (e.g., `http://127.0.0.1:8080/callback` — the same as specified in the app). File:

```json
{
  "client_id": "...",
  "client_secret": "...",
  "redirect_uri": "http://127.0.0.1:8080/callback"
}
```

The `redirect_uri` must match the one registered in the Dashboard — otherwise OAuth will fail. The file is in `.gitignore`; keys do not enter the repository.

**Manual.** `METHOD = 'manual'` (cell 6b). The notebook prints step-by-step instructions:
1. create private playlists `__ORPHANS_NN` in the **desktop** Spotify (the web version does not support bulk paste);
2. copy the `spotify_track_uri` column from the CSV → paste into the playlist via Ctrl+V — the desktop app accepts the whole batch in one paste;
3. export each playlist via Exportify;
4. place the CSVs into `data/Exportify/exportify_orphan_export/`;
5. run `00_1_build_full_history.ipynb`.

After this, `00_1` picks up the CSVs from `exportify_orphan_export/`.

**The final cell (7)** shows three numbers:
- how many orphans were found;
- how many are already exported (coverage percentage);
- how many exported tracks have audio features (a check that Exportify did not return empty columns).

## Output

`data/00_output/` — 15 parquets:

| Parquet                          | Created in       | What's inside                                  |
| -------------------------------- | ---------------- | ---------------------------------------------- |
| `cleaned_history.parquet`        | 00_1, cell 2     | cleaned history                                |
| `tracks_exportify.parquet`       | 00_1, cell 3     | unique tracks with audio features              |
| `playlist_links.parquet`         | 00_1, cell 3.1   | "playlist ↔ track" links                       |
| `history_with_exportify.parquet` | 00_1, cell 4     | history + features                             |
| `orphans_unified.parquet`        | 00_1, cell 5     | orphans with features                          |
| `history_fully_enriched.parquet` | 00_1, cell 6     | history with enrichments                       |
| `full_history.parquet`           | 00_1, cell 7     | history with categorization                    |
| `eda_ready.parquet`              | 00_1, cell 8     | final event table for EDA                      |
| `library_tracks.parquet`         | 00_2             | likes                                          |
| `playlists_metadata.parquet`     | 00_2             | playlists                                      |
| `user_attributes.parquet`        | 00_2             | account attributes                             |
| `inferences.parquet`             | 00_2             | Spotify inferred data                          |
| `search_queries.parquet`         | 00_2             | search queries                                 |
| `owner_ids.parquet`              | 00_2             | account owners                                 |
| `track_dates.parquet`            | 00_2             | dates added to library / to own playlist       |

Additionally, `00_2` **enriches** `playlist_links.parquet` — adds the `playlist_type` and `has_external_adders` columns. The file is created in `00_1` (cell 3.1) and overwritten in `00_2`.

Not all 15 are used downstream. The dashboard and EDA read a subset: `eda_ready`, `tracks_exportify`, `playlist_links`, `library_tracks`, `owner_ids`, `playlists_metadata`. The rest are reference or intermediate.

## `00_3` checks

Nine blocks, from loading to summary:

1. **Load** — all parquets are present.
2. **Time consistency** — `ts − ts_utc = 0`, date range matches the expected one.
3. **Clean data** — empty URIs, NaN in genres, `played_frac` (NaN, inf), `duration_ms == 0`.
4. **Keys & links** — duplicates by rules, URI integrity across files.
5. **Ranges** — audio features in [0, 1], `popularity` in [0, 100], `tempo` in [10, 300].
6. **Flags consistency** — short plays are marked as skip, no analytical columns in `eda_ready`, `first_listen` only on orphans.
7. **Forbidden columns** — no podcasts or audiobooks.
8. **UNTRANSLATED** — no `UNTRANSLATED:` in genres.
9. **Summary** — report ✅ / ⚠️ / ❌.

## Genre mapping

`references/genre_mapping.json` — a fixed dictionary for the current profile. Format: `{"ru_genre": "en_genre"}`. On other data, some genres may not be covered: genres outside the mapping remain as is, Cyrillic goes to `unknown`. If coverage is low (the share of `unknown` is visible in cell 5.1 of the `00_1` notebook) — build your own `genre_mapping.json` from your data and replace the file.

## Directory structure

```
00_prep/
├── README.md                        ← this file
├── README_ru.md
├── 00_0_orphans_detect.ipynb
├── 00_1_build_full_history.ipynb
├── 00_2_account_data.ipynb
├── 00_3_quality_check.ipynb
├── spotify_credentials.json         ← optional, for API mode, in .gitignore
└── references/
    └── genre_mapping.json           ← genre dictionary ru → en (fixed;
                                        genres outside the mapping remain as is,
                                        Cyrillic → unknown; can be replaced with your own)
```

## What's next

After `00_3` with all ✅:

- **EDA** — `01_eda_basic`, `02_eda_temporal`, `03_eda_behavioral`, `04_eda_playlists`
- **Methodology** — `02_methodology/time_detector_experiments.ipynb`
- **Dashboard** — `03_dashboard/dashboard_data_prep.ipynb`, then `streamlit run 03_dashboard/dashboard/app.py`

## See also

- [Root README](../../README.md) — project overview, installation, deployment
- [01_data_analysis](../README.md) — analysis layer overview
- [02_methodology](../../02_methodology/README.md) — Time Detector study
- [03_dashboard](../../03_dashboard/README.md) — prep and dashboard
- [src](../../src/README.md) — pipeline architecture