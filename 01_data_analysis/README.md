🇬🇧 English | [🇷🇺 Русский](./README_ru.md)

# 01_data_analysis — EDA and data assembly

Exploratory analysis of listening history: what is listened to, when,
how, and what the collection is made of. Input parquet assembly lives
here as well.

## Role in the project

**Input:** ready parquet files from `data/00_output/`. Assembled in
`00_prep/` from raw Spotify exports.
**Output:** understanding of the data — before methodology and dashboard.
The notebooks write nothing to disk, they only print.
**Consumers:** `02_methodology` (takes the primitive PELT from
`03_eda_behavioral` as a starting point), `03_dashboard` (uses the same
parquet files).

## Structure

```
01_data_analysis/
├── README.md
├── CHANGELOG.md
├── 00_prep/               ← parquet assembly
│   ├── README.md
│   ├── 00_0_orphans_detect.ipynb
│   ├── 00_1_build_full_history.ipynb
│   ├── 00_2_account_data.ipynb
│   └── 00_3_quality_check.ipynb
├── 01_eda_basic.ipynb
├── 02_eda_temporal.ipynb
├── 03_eda_behavioral.ipynb
└── 04_eda_playlists.ipynb
```

## What's inside

**Assembly — `00_prep/`.** Four notebooks that turn raw exports into 15
parquet files in `data/00_output/`. Details — in `00_prep/README.md`.

| # | Notebook | Task |
|---|---|---|
| 00_0 | `00_0_orphans_detect.ipynb` | Finds orphans (played but neither in a playlist nor in likes), prepares CSVs for upload to Spotify |
| 00_1 | `00_1_build_full_history.ipynb` | Assembles history + audio features → 8 parquet files |
| 00_2 | `00_2_account_data.ipynb` | Parses Account Data → 7 parquet files + enriches `playlist_links` |
| 00_3 | `00_3_quality_check.ipynb` | Verifies integrity of all parquet files |

**EDA — four notebooks.** Each answers its own question.

| # | Notebook | Question |
|---|---|---|
| 01 | `01_eda_basic.ipynb` | What is listened to — from scale to distribution shape |
| 02 | `02_eda_temporal.ipynb` | When it is listened to — rhythm, trends, anomalies |
| 03 | `03_eda_behavioral.ipynb` | How the interaction is structured — sessions, saves, skips, obsessions |
| 04 | `04_eda_playlists.ipynb` | What the collection is made of — structure, contents, taste core. The only EDA notebook that invokes masking (`src.mask`) |

## How it works

**Order.** `00_prep/` first, then the four EDA notebooks.

**`01_eda_basic`.** Data passport, `valid_play`, five masks
(`All events`, `No skips`, `Core ≥3`, `Core ≥5`, `Deep dive`). Scale,
access technologies, top artists (breadth / depth / lifespan), genre
profile, joint distributions, correlations, extremes.
**Conclusion:** the sound profile is stable across filters; the only
substantive difference is a rise in `instrumentalness` under deliberate
listening.

**`02_eda_temporal`.** Four levels: long-term trend, calendar anomalies,
rhythms, regularity. Plus three slices: platforms, top tracks, genre
dynamics.
**Conclusion:** the rhythm is stable in shape and variable in intensity.
2024 is the only year that stands out simultaneously in audio, time of
day, and regularity.

**`03_eda_behavioral`.** Four levels: sessions, saving, skips and
navigation, obsessions. Plus evolution (Discovery, Retention, Burnout).
**Conclusion:** profile of a pronounced explorer with high variability.
Discovery Rate 65.3%, Retention 35.5%, Burnout 32.3%, Variability
1.18 changepoints per year. The naive PELT is kept here as a historical
reference point for `02_methodology`.

**`04_eda_playlists`.** Four levels: structure, content, filling, taste
core. Masking in block 0, before analysis.
**Conclusion:** curated is the only fill type with a notable share in
the `active_listened` group: 44% of its playlists. For mass_import and
batch, this share is near zero. Listening breadth differs by an order of
magnitude: median 85.7% for curated vs 10.4% for mass_import and 9.5%
for batch. The taste core — 1188 tracks, KMeans k=2, Silhouette 0.215
(6 features with tempo; the final version in `src/clustering/kmeans.py`
— 0.264 on 5 features without tempo, see block 9 of the notebook).

## Running

1. `00_prep/` has run — 15 parquet files in `data/00_output/`.
2. Open the EDA notebooks in order: `01` → `02` → `03` → `04`.
3. Each reads `eda_ready.parquet` from `data/00_output/`. Cell 0 walks
   up the tree to find `src/` itself.
4. The notebooks write nothing — they only print.

## Limitations

- **N=1.** Everything found here is about one profile. None of the
  numbers transfer to other accounts without verification.
- **Genre analysis is limited by the `unknown` share.** Thresholds: 30%
  — warning, 50% — do not draw conclusions. The check is
  `show_unknown_share` in each notebook.
- **`03_eda_behavioral` contains the naive PELT** (`pen=10`, 7 mixed
  features). Kept deliberately — as a reference point. Not used in
  production.
- **EDA is not a source of truth for methodology.** The numbers here are
  descriptive, not protected by bootstrap/permutation. For protected
  conclusions — `02_methodology`.
- **Masking is only in `04_eda_playlists`.** Block 0, before analysis.
  There is no call in `01_eda_basic`, `02_eda_temporal`,
  `03_eda_behavioral`.
- **`dashboard_data_prep.ipynb` also has masking** — but that is not the
  EDA layer.

## See also

- [Root README](../README.md) — project overview, install, deploy
- [00_prep](./00_prep/README.md) — input parquet assembly
- [02_methodology](../02_methodology/README.md) — Time Detector study
- [03_dashboard](../03_dashboard/README.md) — prep and dashboard
- [src](../src/README.md) — pipeline architecture