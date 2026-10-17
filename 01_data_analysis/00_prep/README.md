# 00_prep — data assembly

Raw Spotify exports → 15 parquet files in `data/00_output/`. Every other
layer of the project (EDA, methodology, dashboard) reads only these
parquet files and never touches the raw JSON/CSV again.

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
    └── exportify_orphan_export/              ← produced by 00_0
        └── *.csv
```

Single account — files can go in the root of the folder. Multiple accounts
— one subfolder per account.

## Notebooks

| # | Notebook | Task | Output |
|---|---|---|---|
| 00_0 | `00_0_orphans_detect.ipynb` | Finds tracks that were played but never made it into playlists or likes. Produces a CSV with URIs for upload to Spotify — a workaround for Exportify's limitation | `data/Exportify/orphans_to_add/*.csv` + `created_playlists.json` |
| 00_1 | `00_1_build_full_history.ipynb` | Assembles history + audio features | 8 parquet files (see table below) |
| 00_2 | `00_2_account_data.ipynb` | Parses Account Data: library, playlists, owners | 7 parquet files + enriches `playlist_links` |
| 00_3 | `00_3_quality_check.ipynb` | Verifies integrity of all parquet files | ✅ / ⚠️ / ❌ report |

## Run order

```
00_0  →  find orphans
        ↓
      [manual step: upload orphans to Spotify,
       export via Exportify,
       drop CSVs into data/Exportify/exportify_orphan_export/]
        ↓
00_1  →  build history + features
00_2  →  build reference tables
00_3  →  verify everything
```

**No orphans?** If every track is already in playlists or likes — skip
`00_0` and start from `00_1`.

## On orphans — why this exists

Exportify returns audio features (`valence`, `energy`, `danceability`, and
the rest) only for tracks that sit in playlists or likes. Tracks that
were played but never saved to a playlist or to likes — **orphans** —
stay without features. This is not a rare case: **without features you
lose a large part of the history**, and without them you cannot build a
sound portrait, Sound clusters, sound changepoints, or most dashboard
indices.

Exportify cannot "return features for a list of URIs" — it can only
export playlists. So orphans must first be **placed into a playlist**
for Exportify to see them. This is the only manual step in the whole
pipeline. `00_0` makes it as painless as possible: it finds orphans,
creates playlists (if the API is available), and verifies the result.

**Three-step logic:**

1. Reads all history JSONs, collects unique `spotify_track_uri`.
2. Reads all Exportify CSVs (playlists + likes), collects unique URIs.
   Deduplication is global, not per-account.
3. Subtracts: `orphans = history − (playlists ∪ likes)`.

An orphan is defined by the intersection across all accounts: a track
played in at least one account but not saved to any playlist or liked in
any account is an orphan. Per-account breakdown would lose meaning at
this step, so `00_0` writes a single combined CSV.

**What is saved:**
- `orphans_uris.csv` — all orphans, single column `spotify_track_uri`;
- `orphans_batch_NN.csv` — batches of 10,000 URIs;
- `created_playlists.json` — playlist metadata (with `METHOD='api'`).

The CSV has no limit. The **Spotify playlist** has a limit — 10,000
tracks. Hence `BATCH_SIZE = 10_000`: one batch = one private playlist
`__ORPHANS_NN`.

**The `METHOD` fork (cell 5):**

**API (automated).** `METHOD = 'api'` (cell 6a). Requires
`spotify_credentials.json` next to the notebook (in `.gitignore`), a
Premium account, and a one-time OAuth flow. The notebook creates private
playlists `__ORPHANS_01`, `__ORPHANS_02`, … and adds tracks in batches
of 100 (Spotify API limit). Duplicate protection: if `__ORPHANS_NN`
already exists and its track count matches — skip; if the count differs
— leave it alone and flag a conflict.

**Manual.** `METHOD = 'manual'` (cell 6b). The notebook prints
step-by-step instructions:
1. create private playlists `__ORPHANS_NN` in the **desktop** Spotify
   (the web version does not support bulk paste);
2. copy the `spotify_track_uri` column from the CSV → paste into the
   playlist via Ctrl+V — the desktop client accepts the whole batch in
   one paste;
3. export each playlist via Exportify;
4. drop the CSVs into `data/Exportify/exportify_orphan_export/`;
5. run `00_1_build_full_history.ipynb`.

After that `00_1` picks up the CSVs from `exportify_orphan_export/`.

**The final cell (7)** prints three numbers:
- how many orphans were found;
- how many are already exported (coverage %);
- how many exported tracks have audio features (a check that Exportify
  did not return empty columns).

## Output

`data/00_output/` — 15 parquet files:

| Parquet | Created in | Contents |
|---|---|---|
| `cleaned_history.parquet` | 00_1, cell 2 | cleaned history |
| `tracks_exportify.parquet` | 00_1, cell 3 | unique tracks with audio features |
| `playlist_links.parquet` | 00_1, cell 3.1 | playlist ↔ track links |
| `history_with_exportify.parquet` | 00_1, cell 4 | history + features |
| `orphans_unified.parquet` | 00_1, cell 5 | orphans with features |
| `history_fully_enriched.parquet` | 00_1, cell 6 | history with enrichments |
| `full_history.parquet` | 00_1, cell 7 | history with categorization |
| `eda_ready.parquet` | 00_1, cell 8 | final event table for EDA |
| `library_tracks.parquet` | 00_2 | likes |
| `playlists_metadata.parquet` | 00_2 | playlists |
| `user_attributes.parquet` | 00_2 | account attributes |
| `inferences.parquet` | 00_2 | Spotify-inferred data |
| `search_queries.parquet` | 00_2 | search queries |
| `owner_ids.parquet` | 00_2 | account owners |
| `track_dates.parquet` | 00_2 | track add dates |

Additionally, `00_2` **enriches** `playlist_links.parquet` — adds the
`playlist_type` and `has_external_adders` columns. The file is created
in `00_1` (cell 3.1) and rewritten in `00_2`.

Not all 15 are used downstream. The dashboard and EDA read a subset:
`eda_ready`, `tracks_exportify`, `playlist_links`, `library_tracks`,
`owner_ids`, `playlists_metadata`. The rest are reference or
intermediate.

## `00_3` checks

Nine blocks, from load to summary:

1. **Load** — all parquet files present.
2. **Time consistency** — `ts − ts_utc = 0`, date range matches the
   expected one.
3. **Clean data** — empty URIs, NaN in genres, `played_frac` (NaN, inf),
   `duration_ms == 0`.
4. **Keys & links** — duplicates by rule, URI integrity across files.
5. **Ranges** — audio features in [0, 1], `popularity` in [0, 100],
   `tempo` in [10, 300].
6. **Flags consistency** — short plays flagged as skip, no analytical
   columns in `eda_ready`, `first_listen` only on orphans.
7. **Forbidden columns** — no podcasts or audiobooks.
8. **UNTRANSLATED** — no `UNTRANSLATED:` in genres.
9. **Summary** — ✅ / ⚠️ / ❌ report.

## Folder structure

```
00_prep/
├── README.md                        ← this file
├── 00_0_orphans_detect.ipynb
├── 00_1_build_full_history.ipynb
├── 00_2_account_data.ipynb
├── 00_3_quality_check.ipynb
├── spotify_credentials.json         ← optional, for API mode, in .gitignore
└── references/
    └── genre_mapping.json           ← genre dictionary (ru → en)
```

## What's next

After `00_3` reports all ✅:

- **EDA** — `01_eda_basic`, `02_eda_temporal`, `03_eda_behavioral`,
  `04_eda_playlists`
- **Methodology** — `02_methodology/time_detector_experiments.ipynb`
- **Dashboard** — `03_dashboard/dashboard_data_prep.ipynb`, then
  `streamlit run 03_dashboard/dashboard/app.py`

## See also

- [Root README](../../README.md) — project overview, install, deploy
- [01_data_analysis](../README.md) — analysis layer overview
- [02_methodology](../../02_methodology/README.md) — Time Detector study
- [03_dashboard](../../03_dashboard/README.md) — prep and dashboard
- [src](../../src/README.md) — pipeline architecture