15.09.2026
 src/ — карта модулей

Библиотека функций для расчёта паркетов дашборда. Ноутбуки вызывают
функции отсюда, чтобы не дублировать логику между преп-нотом и экспериментами.

Правило: если функция используется в двух и более местах, или содержит
параметры, которые тюнятся — она живёт здесь. Всё остальное — в ноутбуке.

---

## common.py — общие хелперы

Используются почти везде.

| Функция | Что делает |
|---|---|
| `add_valid_play(df)` | Добавляет колонку `valid_play` (≥30 сек, не skip, не технический конец, played_frac ≥ 0.5) |
| `add_sessions(df, gap_min=30)` | Разбивает события на сессии: разрыв > 30 мин = новая сессия |
| `session_stats(df)` | Агрегат по сессиям: длительность, число событий, месяц старта |
| `compute_bic_pen(X)` | BIC-подобный штраф (Lavielle) для PELT: `pen = σ² · dim · log(n)`, σ² через MAD первых разностей |
| `pelt_points(X_norm, sigma2, n_dims, index, ...)` | PELT с BIC-штрафом + bootstrap устойчивость точек |
| `compute_snr(series, window=3)` | Signal-to-Noise Ratio для временного ряда |
| `snr_gain_permutation(series, ...)` | Permutation-тест: отличается ли прирост SNR от случайного |
| `level_from_value(val, thresholds)` | Low / Medium / High / N/A по порогам из JSON |

**Константы:** `EXCLUDE_REASONS` (технические причины окончания).

---

## monthly.py — monthly-ряды для детекторов

| Функция | Что делает |
|---|---|
| `trim_cold_start(df, gap_months=1)` | Отрезает неполный последний месяц + холодный старт (правило: gap > 1 мес в первый год → история начинается после него) |
| `build_monthly_sound(df)` | Медианы звуковых признаков по месяцам: valence, energy, danceability, instrumentalness, acousticness, tempo |
| `build_monthly_behavior(df)` | Поведенческие признаки по месяцам: hours, tracks, skip_rate, played_frac, obsession_share (event-level), discovery_rate + сглаженные версии (`*_smooth`) для PELT-B |

**Константы:**
- `SOUND_FEATURES` — 6 звуковых признаков
- `BEHAVIOR_FEATURES_RAW` — все поведенческие
- `BEHAVIOR_FEATURES_PELT` — финальный набор для PELT-B (4 сглаженных + 2 сырых)

---

## detectors/ — четыре независимых слоя детекции

Каждый детектор — отдельный модуль. Все вызываются из `changepoints.py`,
но могут быть вызваны вручную для отладки или экспериментов.

### pelt_sound.py — PELT-A (звук)

```python
from detectors.pelt_sound import detect
result = detect(monthly_sound)
# result['points'] → ['2023-09', '2024-02', '2024-07']
# result['stability'] → {'2024-02': 0.245, ...}
```

Median-агрегация, BIC-штраф, bootstrap 200 итераций.
Признаки: `SOUND_FEATURES`.

### pelt_behavior.py — PELT-B (поведение)

```python
from detectors.pelt_behavior import detect
result = detect(monthly_behavior)
# result['points'] → ['2021-08', '2024-12', '2025-10', '2026-03']
```

Финальный набор: `BEHAVIOR_FEATURES_PELT` (6 признаков).
`desktop_share` исключён — структурный скачок, не разладка.

### cosine_identity.py — Cosine (смена артистов)

```python
from detectors.cosine_identity import detect
result = detect(df, id_col='artist_name')
# result['points'] → ['2021-02', '2022-05', '2022-09', '2024-02']
```

Косинусное расстояние по составу артистов между соседними месяцами.
Пики через `медиана + 2·MAD`. Bootstrap: пики с устойчивостью ≥ 0.5.

Не по жанрам — жанры слишком инертны.

### cut_scan.py — Cut-scan (регионы переходов)

```python
from detectors.cut_scan import detect
result = detect(monthly_sound)
# result['regions'] → [{'date': '2022-09', 'region_start': '2021-12', ...}]
```

Не точки, а регионы. Сканирование точки разреза по всему ряду,
поиск резких изменений градиента Δ между медианами «до» и «после».
Кластеризация близких кандидатов (±3 мес) в один регион.

### storm.py — Шторм-анализ (скорость изменений)

```python
from detectors.storm import detect
result = detect(monthly_sound)
# result['df'] → DataFrame с std_all, is_storm, episode_id
# result['episodes'] → [[Period('2021-01'), ...], [Period('2023-10'), ...]]
# result['threshold'] → 0.0863
```

Rolling std по 4 признакам → агрегат `std_all` → порог `медиана + 1.0·MAD`.
Эпизоды: 3+ штормовых месяца в окне ≤5.

---

## changepoints.py — сборка слоёв

```python
from changepoints import build as build_changepoints
cp, storms = build_changepoints(df, output_path)
```

Вызывает все 4 детектора, объединяет результат, сохраняет:
- `time_changepoints.parquet` — `date | method | layer | confidence`
- `time_storms.parquet` — `date | std_all | is_storm | episode_id`

Единственная точка входа для Time-блока в преп-ноте.

---

## portrait.py — 4 оси профиля слушателя

```python
from portrait import build as build_portrait
portrait = build_portrait(df, changepoints, windows, output_path)
```

Считает: Discovery, Retention, Burnout, Variability.
Сохраняет `portrait.parquet` с колонками `axis | value | short_history | stage`.

**Без `level` и `thresholds`** — они в `indices_display.json`,
дашборд читает оттуда.

Variability — общая (из `time_changepoints`, схлопнутые ±2 мес эпизоды).

---

## obsessions.py — обсессии

```python
from obsessions import build as build_obsessions
strong, share = build_obsessions(df, output_path)
```

- `build_strong(df)` — серии ≥5 повторов подряд в одной сессии
  → `obsessions_strong.parquet`
- `build_share(df)` — доля событий в obsession-парах (event-level)
  → `obsession_share.parquet`

**Старая track-level логика (`obsessions_base_*`) удалена.** Она
завышала числа: трек, попавший в obsession хотя бы в одной сессии,
помечался флагом на все события.

---

## Что НЕ выносим в src/

Логика, которая используется **только в одном месте**:

- **Sound** (KMeans + PCA + characteristic tracks) — только Sound.
- **Funnel** — только воронка.
- **Skip map** — только карта скипов.
- **Cohorts** — только когортное удержание.
- **Collection** — портреты плейлистов, fill types.

Эти блоки живут целиком в `dashboard_data_prep.ipynb`.

Правило простое: **дублируется или тюнится** → в `src/`.
**Один раз и стабильно** → в ноутбуке.

---

## Как использовать в ноутбуке

Первая ячейка `dashboard_data_prep.ipynb`:

```python
import sys
from pathlib import Path

def find_src(start=None):
    start = Path(start or Path.cwd()).resolve()
    for p in [start] + list(start.parents):
        if (p / 'src').is_dir() and (p / 'notebooks').is_dir():
            return p / 'src'
    raise FileNotFoundError('src/ не найден выше текущей директории')

SRC_PATH = find_src()
if str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))

from common import add_valid_play, compute_bic_pen, pelt_points
from monthly import build_monthly_sound, build_monthly_behavior
from detectors import pelt_sound, pelt_behavior, cosine_identity, cut_scan, storm
from changepoints import build as build_changepoints
from portrait import build as build_portrait
from obsessions import build as build_obsessions

print("✅ src/ подключён")
```

---

## Обновление этого файла

При добавлении модуля — дописать раздел. При изменении сигнатуры
функции — обновить таблицу. Если что-то переехало из ноутбука
в `src/` или наоборот — обновить оба места.

Цель файла — **найти нужное за 10 секунд**, не читая код.
