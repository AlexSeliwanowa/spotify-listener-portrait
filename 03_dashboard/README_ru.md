[🇬🇧 English](./README.md) | 🇷🇺 Русский

# 03_dashboard

**Живая версия:** https://spotify-listener-portrait-a3resx9aolc4svjcpegwhq.streamlit.app/

Финальный слой проекта: превращает паркеты из `00_prep` в 31 агрегат, готовый для отображения в Streamlit-дашборде.

## Структура

```
03_dashboard/
├── dashboard_data_prep.ipynb   считает 30 агрегатов, маскирует, копирует в datasets/
├── dashboard/                  сам дашборд (Streamlit)
│   ├── app.py                  точка входа
│   ├── config/                 JSON-конфиги: темы, пороги, тексты, архетипы
│   ├── data/                   Python-модули загрузки паркетов
│   ├── logic/                  логика отрисовки и форматирования
│   ├── ui/                     пять вкладок (sound, time, behavior, collection, overview)
│   ├── tests/                  smoke-тесты
│   └── datasets/               31 паркет — в git; в четырёх личные идентификаторы замаскированы, в остальных их нет
└── README.md
```

## Как это работает целиком

Три слоя:

**1. `01_data_analysis/00_prep/`** — собирает из сырых выгрузок Spotify 15 паркетов в `data/00_output/`. История, фичи, плейлисты, библиотека, владельцы.

**2. `dashboard_data_prep.ipynb`** — читает 6 из этих паркетов, считает 30 агрегатов. Пишет приватно в `data/00_output/dashboard/`, потом маскирует и копирует в `dashboard/datasets/` (31 паркет).

**3. В `datasets/` замаскированы только личные идентификаторы (email, id аккаунтов, названия личных плейлистов), в четырёх паркетах. Остальные паркеты идентификаторов не содержат. Перед записью в `datasets/` эти четыре прогоняются через `src/mask.py`:

```
data/00_output/*.parquet   (15 файлов)
        │
        ↓
dashboard_data_prep.ipynb
   ├─ читает 6 паркетов
   ├─ считает 30 агрегатов → data/00_output/dashboard/
   ├─ маскирует 4 паркета через src/mask.py
   └─ копирует в dashboard/datasets/  (31 паркет)
        │
        ↓
dashboard/app.py  →  streamlit run
```

## Преп-ноутбук `dashboard_data_prep.ipynb`

**Что делает по ячейкам:**

- **Ячейка 0–1.** Импорты из `src/` (агрегаторы, детекторы, кластеризация, портрет, индексы, mask). Читает 6 паркетов: `eda_ready`, `tracks_exportify`, `playlist_links`, `library_tracks`, `owner_ids`, `playlists_metadata`. Прогоняет `enrich` (`valid_play`, `my_music`, `session_id`, `source`). Считает три окна: `global`, `recent_6q`, `last_90d`.
- **Sound.** Отбор ядра вкуса (`valid ∩ my_music`), KMeans на 5 аудио-фичах, PCA. Обучение на global, применение к остальным окнам без переобучения.
- **Time.** Временные ряды по трём окнам. 4 слоя точек разладки: PELT-A (звук), PELT-B (поведение), Cosine (артисты), Storm. Variability через permutation noise floor.
- **Behavior.** Компас (4 оси × 2 стадии). Обсессии, воронки, скипы, когорты. 8 поведенческих индексов.
- **Collection.** Автопортреты плейлистов, участники коллабораций, типы наполнения, активность.
- **KPI.** `build_kpi_summary` из `src/indices.py` — ~35 индексов, но не все считаются для всех окон: 39 (Lifetime) / 34 (Last 18 months) / 33 (Last 90 days) = 106 строк.
- **`eda_enriched.parquet`.** Slim-копия обогащённого `df` — 32 колонки. Отдельный файл, чтобы `app.py` не пересчитывал enrich при каждом запуске.
- **Проверка.** Сверяет все 30 паркетов: файл есть, колонки на месте, ключи уникальны.
- **Маскирование и копирование.** 30 паркетов в `dashboard/datasets/` + `playlist_links.parquet` в корне. Маскирует 4 через `src/mask.py`.

**Когда запускать:** после `00_prep`, перед запуском дашборда. Один раз или заново, если данные в `00_output/` изменились.

## Что попадает в `dashboard/datasets/`

31 паркет: 30 агрегатов считает преп-ноут, 31 паркет уходит в datasets/ — разница в playlist_links.parquet.

| Где | Сколько | Что |
|---|---|---|
| `sound/` | 4 | `sound_core_global / recent_6q / last_90d` + `sound_clustering_meta` |
| `time/` | 10 | `time_series_*` ×3 + meta + changepoints + storms + variability + meta + contributions + epochs |
| `behavior/` | 10 | portrait + obsessions ×4 + funnels ×2 + skip ×2 + cohorts |
| `collection/` | 4 | portraits + collaborators + fill_summary + activity_scatter |
| корень | 3 | `kpi_summary`, `eda_enriched`, `playlist_links` |
| **Итого** | **31** | |

Полное описание полей каждого паркета — в markdown-ячейках в конце `dashboard_data_prep.ipynb`.

## Маскирование

Четыре паркета содержат реальные значения. Перед записью в `datasets/` прогоняются через `src/mask.py`:

| Паркет | Что маскируется |
|---|---|
| `collection/playlist_portraits` | `playlist_name` |
| `collection/playlist_collaborators` | `playlist_name`, `added_by_id`, `display_name` |
| `collection/collection_activity_scatter` | `name_norm` |
| `playlist_links.parquet` | `account`, `Added By`, `playlist_name`, `name_norm` |

Правила: email → `1@mail.com` / `2@mail.com` / `3@mail.com`, owner_id → `account_N`, display_name → `Account N`, внешние Added By → `user_NN`, личные плейлисты → `personal_<тема>_<номер>`.

Маппинг — в `scripts/mask_config.json`, локально, в `.gitignore`. Без него маскирование пропускается, prep-ноут предупреждает.

## Дашборд

**5 вкладок × 2 режима × 3 периода.**

| Вкладка | Что показывает |
|---|---|
| **Sound** | Кластеры звука, scatter в PCA, signature tracks, топ-артисты, жанровые доньки |
| **Time** | Временные ряды, changepoints, штормы, серая зона холодного старта, Variability |
| **Behavior** | Компас (4 оси), обсессии, воронки, скипы, когорты |
| **Collection** | Плейлисты, автопортреты, участники, типы наполнения |
| **Overview** | Архетип, takeaways, snapshot индексов, biggest shift, полный справочник |

## Personal / Professional

Одни данные, две линзы.

**Personal** отвечает «кто я». Тёмная тема. Обращение на «ты». Архетип крупно, компас геометрией, обсессии — «треки, которые ты не мог перестать слушать». Без формул, без баз, без методологии. Карточки с именами (Niche, Genres, Skipper, Night Owl), не с индексами. Экспорт — PDF за Lifetime.

**Professional** отвечает «что в данных». Светлая тема. Безлично. Caption с базой в каждой вкладке. ⓘ и формулы на карточках индексов. Плюс то, чего нет в Personal: воронки, когорты, skip/full play разрез, таблица changepoints, cluster summary, feature contributions. Экспорт — CSV всех индексов × 3 окна.

Это не «упрощённый / полный». Это два разных языка про одно и то же.

**Периоды:** `Lifetime` (global), `Last 18 months` (recent_6q), `Last 90 days` (last_90d).

## Конфигурация

Пороги отображения, тексты, уровни — в `config/*.json`. Локальные константы логики — в `ui/*.py`.

**JSON:**
- `indices_display.json` — пороги, полярность, `max_value`, тексты, формулы.
- `profile_labels.json` — 9 архетипов с кодами.
- `dashboard_config.json` — темы, цвета, `cluster_colors`, `profile_colors`, `typography`.
- `product_takeaway.json` — рекомендации по осям.
- `time_definitions.json` — определения для аннотаций Time.

**Захардкожено в UI** (осознанно): списки индексов вкладок (`TIME_INDICES`, `BEHAVIOR_INDICES`), порядок осей компаса (`axes_order`), числовые уровни (`level_num`), палитра жанров. Используются в одном месте, меняются редко.

## Контракт данных

`data/schemas.py` — список обязательных колонок для каждого паркета. При загрузке `load_parquet` вызывает `validate()`. Если колонка пропала — красная плашка с указанием, что именно. Дашборд не падает молча.

## Тесты

Из папки `dashboard/`:

```
python -m pytest tests/ -v
```

Smoke-тесты проверяют контракт данных, не логику: паркеты на месте, схемы совпадают, модули `ui/*` импортируются, `app.py` парсится.

## Запуск

**Дашборд готов к запуску сразу после клонирования репозитория.** 31 паркет уже лежит в `dashboard/datasets/`, папка `data/` не нужна.

```
git clone <repo-url>
cd spotify-listener-portrait
pip install -r requirements.txt
streamlit run 03_dashboard/dashboard/app.py
```

Откроется на `http://localhost:8501`.

**Онлайн:** https://spotify-listener-portrait-a3resx9aolc4svjcpegwhq.streamlit.app/

### Если данные изменились

Полный путь:

**1.** Прогнать `00_prep` — собрать 15 паркетов в `data/00_output/`.

**2.** Прогнать преп-ноут:
```
jupyter notebook 03_dashboard/dashboard_data_prep.ipynb
```
На выходе: 30 агрегатов в `data/00_output/dashboard/`, 31 паркет в `dashboard/datasets/`.

**3.** Перезапустить дашборд:
```
streamlit run 03_dashboard/dashboard/app.py
```

**На Streamlit Cloud** — деплой из GitHub, тот же `app.py`. Все паркеты уже в `datasets/`. После `git push` — **Reboot** приложения в панели управления.

## Ограничения

- **Версия Streamlit зафиксирована** в `requirements.txt` (`1.60.0`). Обновлять — вместе с проверкой кастомного CSS.
- **Дашборд не пересчитывает данные.** Устарел паркет — покажет устаревшее.
- **Фронтовый баг Streamlit** — при частом переключении режимов React может упасть с `NotFoundError: removeChild`. Лечится F5.
- **Маскирование зависит от `scripts/mask_config.json`**. Без него данные идут в `datasets/` без маски.
- **PDF-отчёт** — компас рисуется через matplotlib, визуально проще, чем в Streamlit (plotly). Ограничение известно, в приоритетах не стоит.
- **Метка Variability (Low / Medium / High) относительна к профилю** и между пользователями не сопоставима. В дашборде она используется как индикатор внутри истории пользователя, не абсолютная шкала.
- **Перезапуск на своих данных не проверялся.** Преп-ноутбук можно прогнать на своём экспорте Spotify после `00_prep`, но пороги (KMeans silhouette, stability 0.10, практический p75) откалиброваны на текущих данных и могут потребовать пересмотра. Схема выхода (`data/schemas.py`) переносится; числа — нет.

## См. также

- [Корневой README](../README_ru.md) — обзор проекта
- [01_data_analysis](../01_data_analysis/README_ru.md) — EDA и сборка данных
- [00_prep](../01_data_analysis/00_prep/README_ru.md) — сборка паркетов
- [02_methodology](../02_methodology/README_ru.md) — исследование Time Detector
- [src](../src/README_ru.md) — архитектура пайплайна