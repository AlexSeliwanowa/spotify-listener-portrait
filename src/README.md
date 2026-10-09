# src/ — архитектура проекта

Модули для обработки событий Spotify, построения поведенческих метрик
и сборки паркетов дашборда.

Используется в prep-ноутбуке (`03_dashboard/dashboard_data_prep.ipynb`).
Каждая ячейка вызывает функции отсюда, сама ничего не считает.


## Принципы

**1. Слои знают только о слое ниже.**
Нижний слой не ссылается на верхний. `enrich` не знает про `indices`,
`bases` не знает про `detectors`. Меняешь верхний слой — нижний не трогается.

**2. Правило двух.**
Если функция используется в 2+ ноутбуках или 2+ местах — она в `src/`.
Если в одном — inline в ноутбуке.

**3. Модуль — по природе сущности, не по потребителю.**
Определение базы не знает, кто её использует. `bases.py` не упоминает PELT.
Потребитель явно указывает: «беру valid» или «беру trimmed».

**4. Один источник правды.**
`valid_play` определяется один раз в `enrich.add_valid_play`. Все —
`bases.valid`, `indices.skip_risk_index`, `portrait` — читают колонку.
Меняется определение — правится в одном месте.

**5. Папка — если файлов 3+.**
Иначе — плоско. `bases.py`, `temporal.py`, `indices.py` — рядом.
`detectors/`, `aggregators/`, `clustering/` — папки.


## Дерево

```
src/
├── README.md                     ← этот файл
├── __init__.py
│
├── paths.py                      инфраструктура: пути, папки
├── loaders.py                    инфраструктура: загрузка parquet
├── mask.py                       инфраструктура: маскирование личных данных
│
├── helpers.py                    чистые утилиты без домена
├── temporal.py                   окна и обрезка холодного старта
├── bases.py                      срезы df (all / valid / trimmed / …)
├── enrich.py                     добавление колонок в df
├── diagnostics.py                SNR, permutation (для исследований)
├── indices.py                    ~35 индексов + оркестратор kpi_summary
├── portrait.py                   компас: Discovery, Retention, Burnout
├── variability_export.py         экспорт Variability в parquet
│
├── aggregators/                  свёртка событий в периоды
│   ├── music.py                  медианы звука по месяцам
│   ├── behavior.py               поведенческие агрегаты + obsessions
│   └── temporal.py               временные ряды M/W/D для дашборда
│
├── clustering/                   разбиение звука на группы
│   ├── kmeans.py                 подбор k, KMeans, PCA
│   └── sound_core.py             ядро вкуса по окнам
│
└── detectors/                    поиск паттернов в агрегатах
    ├── pelt_common.py            BIC-штраф + bootstrap
    ├── pelt_sound.py             PELT-A (звук)
    ├── pelt_behavior.py          PELT-B (поведение)
    ├── cosine_identity.py        смена идентичности (артисты)
    ├── storm.py                  штормовые эпизоды
    ├── cut_scan.py               регионы перехода
    ├── variability.py            Variability через toolkit
    ├── variability_toolkit.py    универсальный toolkit
    └── changepoints.py           оркестратор: собирает 4 слоя точек
```


## Слои

Каждый слой работает с результатом предыдущего. Обратных ссылок нет.

```
5. Detectors           поиск паттернов (PELT, Cosine, Storm)
   ▲
4. Aggregators         события → периоды (медианы, доли)
   ▲
3. Indices             числа-метрики из срезов
   ▲
2. Bases               срезы df (valid, trimmed, …)
   ▲
1. Enrich              добавление колонок (valid_play, my_music, …)
   ▲
0. Infrastructure      пути, загрузка, маскирование (без работы с данными)
```

**Маскирование — вне слоёв.** `mask.py` вызывается в самом конце
prep-ноутбука, перед записью паркетов в публичную папку `datasets/`.
Это не часть пайплайна расчётов — это отдельный проход по финальным
агрегатам. Читает `scripts/mask_config.json` (локальный, не в git),
заменяет реальные идентификаторы на маски.


## Модули

### Infrastructure

**`paths.py`** — пути и папки.
- `get_project_root()` — корень репозитория
- `get_base_path()` — корень данных `data/00_output/`
- `get_dashboard_path()` — приватные паркеты `data/00_output/dashboard/`
- `get_datasets_path()` — публичные паркеты `03_dashboard/dashboard/datasets/`
- `get_public_dashboard_path()` — корень `03_dashboard/dashboard/`
- `get_config_path()` — конфиги дашборда
- `ensure_dashboard_subdirs()` — создаёт `sound/`, `time/`, `behavior/`, `collection/` в приватной папке
- `ensure_datasets_subdirs()` — то же в публичной папке
- `get_references_path()`, `get_genre_mapping_path()` — справочники

**`loaders.py`** — загрузка.
- `load_all(base_path)` — возвращает dict с `df`, `tracks_exportify`, `playlist_links`, `library_tracks`, `owner_ids`, `playlists_metadata`.

**`mask.py`** — маскирование личных данных.
- `mask_all(**dfs)` — принимает датафреймы по именам, возвращает маскированные.
- Работает в памяти: получает и возвращает датафреймы, ничего не пишет.
- Читает `scripts/mask_config.json` (в `.gitignore`). Без конфига — предупреждение и возврат как есть.
- Маскирует: `account`, `owner_id`, `display_name`, `email`, `Added By`, `collaborators`, `playlist_name`, `name_norm`, `added_by_id`.


### Primitives

**`helpers.py`** — чистые утилиты. Никаких импортов из `src/`.
- `normalized_entropy(counts)` — энтропия Шеннона в [0, 1]
- `platform_type(platform)` — `mobile / desktop / web / other`
- `is_desktop(platform)`, `is_mobile(platform)`
- `desktop_share(df)`, `mobile_share(df)`
- `night_share(df, hours=(0, 5))`

**`temporal.py`** — время.
- `compute_windows(df, playlist_links)` — три окна: `global`, `recent_6q` (18 мес), `last_90d` (90 дней). Возвращает `max_data_date`, `recent_start`, `last90_start`, `windows`.
- `trim_cold_start(df, gap_months=1)` — отрезает неполный последний месяц и холодный старт (gap > 1 мес в первый год).

**`bases.py`** — срезы df. Только читают колонки, ничего не создают.
- `all_events(df)` — весь df
- `valid(df)` — `valid_play == True`
- `trimmed(df)` — после `trim_cold_start`
- `trimmed_valid(df)` — trimmed ∩ valid

**`enrich.py`** — добавляет колонки. Строк не убирает.
- `add_timestamps(df)` — `ts_naive`, `period`
- `add_valid_play(df)` — `valid_play`
- `add_first_valid_seen(df)` — `first_valid_seen`
- `add_my_music(df, library_tracks, playlist_links, owner_ids)` — `my_music`
- `add_track_source(df, library_tracks, playlist_links, owner_ids)` — `source` (my_music / foreign / orphan)
- `add_sessions(df, gap_min=30)` — `session_id`, `gap_min`, `new_session`
- `session_stats(df)` — агрегат по сессиям

**`diagnostics.py`** — проверки сигнала для исследований.
- `compute_snr(series, window=3)` — signal-to-noise ratio
- `snr_gain_permutation(series, n_perm=200, …)` — permutation-тест

**`indices.py`** — индексы метрик.
- ~35 публичных функций: `hipster_index`, `genre_diversity_index`, `music_day_share`, `skip_risk_index`, `session_depth_index`, …
- Оркестратор `build_kpi_summary(df, windows, tracks_exportify, playlist_links)` — собирает всё в DataFrame (106 строк: ~35 индексов × 3 окна)
- `INDEX_SPECS` — метаданные индексов (unit / category / audience)

**`portrait.py`** — компас. Три публичные функции + два оркестратора.
- `discovery_global(df_valid)` — Discovery (медиана квартального)
- `retention_90(df_valid)` — Retention (90-дневный)
- `burnout(df_valid)` — Burnout
- `build_axes(df, windows)` — три оси без Variability
- `build(df, windows, output_path, variability_score)` — собирает `portrait.parquet` (Variability приходит снаружи)

**`variability_export.py`** — экспорт Variability.
- `export_variability(R, out_dir)` — пишет 4 файла: `variability`, `meta`, `feature_contributions`, `epochs_sound`


### Aggregators

**`aggregators/music.py`** — звук по месяцам.
- `SOUND_FEATURES` — 6 признаков (valence, energy, danceability, instrumentalness, acousticness, tempo)
- `build_monthly_sound(df)` — медианы по месяцам

**`aggregators/behavior.py`** — поведение по месяцам + obsessions.
- `BEHAVIOR_FEATURES_PELT` — 6 признаков для PELT-B
- `build_monthly_behavior(df)` — hours, tracks, skip_rate, played_frac, obsession_share, discovery_rate + сглаженные
- `is_obsession_event(df)` — флаг obsession на событие
- `build_strong_obsessions(df)` — серии ≥5 подряд
- `build_obsession_base(df, freq)` — доля obsession-событий по периодам

**`aggregators/temporal.py`** — временные ряды для дашборда.
- `AGG_WINDOWS` — частоты (global→M, recent_6q→W, last_90d→D)
- `build_time_series(df, label, start, end, freq, first_post_gap_month)` — с NaN-строками для пропущенных периодов
- `build_time_series_meta(df, first_post_gap_month)` — метаданные (первое событие, дырки и т.д.)


### Clustering

**`clustering/kmeans.py`** — общий KMeans/PCA.
- `find_optimal_k(X_scaled)` — перебор k по silhouette
- `fit_clustering(X_scaled, k)`, `fit_pca(X_scaled)`
- `mark_characteristic(df, top_n=5)` — флаг характерных треков

**`clustering/sound_core.py`** — специфика Sound.
- `CLUSTER_FEATURES` — 5 признаков (без tempo)
- `prepare_core(df, start, end, my_music_uris)` — valid ∩ my_music
- `apply_to_window(core, scaler, kmeans, pca)` — обученные на global модели к окну


### Detectors

**`detectors/pelt_common.py`** — общая логика PELT.
- `compute_bic_pen(X)` — BIC-штраф (Lavielle)
- `pelt_points(X_norm, sigma2, n_dims, index)` — точки + bootstrap

**`detectors/pelt_sound.py`** — PELT-A (звук). Использует `SOUND_FEATURES` и `pelt_common`.
- `detect(monthly_sound)` → dict с точками и устойчивостью

**`detectors/pelt_behavior.py`** — PELT-B (поведение). Использует `BEHAVIOR_FEATURES_PELT` и `pelt_common`.
- `detect(monthly_behavior)` → dict

**`detectors/cosine_identity.py`** — смена идентичности.
- `detect(df, id_col='artist_name')` → точки (пики cosine distance)

**`detectors/storm.py`** — штормовые эпизоды.
- `detect(monthly_sound)` → df с `std_all`, `is_storm`, `episode_id`

**`detectors/cut_scan.py`** — регионы перехода.
- `detect(monthly_sound)` → регионы (не идёт в дашборд)

**`detectors/variability.py`** — Variability через toolkit.
- `run_variability_pipeline(df, monthly_sound, window, seed)` → dict
- Константа `MIN_TRANSITIONS_FOR_VARIABILITY = 24`

**`detectors/variability_toolkit.py`** — универсальный toolkit.
- `VariabilityAnalyzer` — класс с методами `fit`, `variability_score`, `check_stability`, `feature_contributions`.
- Обобщённый инструмент, не привязанный к Spotify. Кандидат на вынос
  в отдельный репозиторий `variability-toolkit` — решение пока не принято.

**`detectors/changepoints.py`** — оркестратор.
- `build(df, output_path)` — вызывает 4 детектора, собирает `time_changepoints.parquet` + `time_storms.parquet`


## Базы

Какой слой на какой базе считается. **Единое решение на проект.**

| Слой | База | Почему |
|---|---|---|
| **Discovery / Retention / Burnout** | valid | осознанное слушание |
| **Variability** | trimmed_valid | вкус без холодного старта |
| **PELT-A (звук)** | trimmed_valid | звуковой профиль слушания |
| **PELT-B (поведение)** | trimmed | skip_rate и played_frac мертвы на valid |
| **Cosine (артисты)** | trimmed | состав артистов по всем событиям |
| **Storm** | trimmed | скорость изменений по всем |
| **Obsessions** | df (all) | session-level и event-level на всех |
| **Time series** | df (all) | дашборд показывает полную историю с дыркой |
| **Collection** | df (all) | справочники, плейлисты |
| **kpi_summary** | по индексу | одни valid, другие all — каждый сам решает |


## Принципы расчёта

**1. dropna по своим колонкам.**
Каждый индекс/детектор делает `dropna` только по тем колонкам, которые использует. Не по общему набору.
Пример: `acoustic_energy_balance` использует `energy` и `acousticness`, dropna по ним. `loudness` (с NaN) не влияет.

**2. Сглаживание для шумных признаков.**
`tracks`, `skip_rate`, `played_frac`, `discovery_rate` сглаживаются rolling(3) перед PELT-B.

**3. Bootstrap — для устойчивости точек.**
PELT-точки фильтруются по bootstrap ≥ 0.10 (drop 15% месяцев, 200 итераций).

**4. Окна — относительные от max_data_date.**
`recent_6q` = max_data_date − 18 мес. `last_90d` = max_data_date − 90 дней.
Не календарные — иначе при неполных кварталах окно искажается.


## Что НЕ в src/

Всё, что используется только один раз, остаётся **inline в ноутбуке**:
- Behavior-специфика: воронка, скипы, когорты
- Collection-специфика: портреты, collab, fill
- Разовые исследования в отдельных ноутбуках (backbtn, immediate saves, dynamic save status)

**Правило:** второй потребитель → переезд в `src/`. До этого — inline.


## Кто что использует

- **Prep-ноутбук** (`03_dashboard/dashboard_data_prep.ipynb`) — оркестратор.
  Импортирует всё, что нужно, вызывает в нужном порядке, сохраняет паркеты.
  На выходе — `mask_all` для четырёх паркетов с личными данными.
- **Отдельные ноутбуки исследований** (`01_eda_basic`, `02_eda_temporal`,
  `03_eda_behavioral`, `04_eda_playlists`) — берут `get_base_path` из `paths`.
  Только `04_eda_playlists` дополнительно вызывает `mask_all` в блоке 0.
  Логику анализа не дублируют — она inline в ноутбуках.
- **Dashboard** (`03_dashboard/dashboard/app.py`) — читает только `datasets/`,
  не работает с `src/` напрямую.
- **`scripts/mask_config.json`** — читается из `src/mask.py`, в git не попадает.


