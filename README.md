# Earthquakes → DBSCAN (haversine) + интерактивная карта

Инструмент для кластеризации геоточек (например, землетрясений) методом **DBSCAN** в метрике **haversine** и визуализации результатов на **интерактивной карте** Folium. Работает и из Jupyter Notebook, и из обычной консоли.

---

## Возможности

- Загрузка CSV с широтой/долготой (и опционально магнитудой).
- DBSCAN (`metric=haversine`, `ball_tree`) с:
  - автоподбором `eps` по 95-му перцентилю k-расстояний,
  - ручной установкой `eps_km` и `min_samples`.
- Интерактивная карта Folium:
  - фоновая подложка CartoDB,
  - тепловая карта,
  - слои цветных кластеров и их центроидов,
  - подсветка пользовательской точки (в CLI).
- Сохранение карты в HTML и авто-открытие в браузере.

---

## Требования

```bash
pip install numpy pandas scikit-learn folium tqdm matplotlib
```

---

## Формат входного CSV

Обязательно:
- `latitude` — широта (−90..90)
- `longitude` — долгота (−180..180)

Опционально:
- `magnitudo` — магнитуда (фильтрация по порогу)

---

## Быстрый запуск (CLI: `quake_map.py`)

Автоматический подбор `eps`:
```bash
python quake_map.py --csv ./data/Eartquakes-1990-2023.csv   --lat latitude --lon longitude   --auto-eps
```

Фильтр по магнитуде:
```bash
python quake_map.py --csv ./data/Eartquakes-1990-2023.csv   --lat latitude --lon longitude   --magcol magnitudo --minmag 6   --auto-eps
```

Ручные параметры:
```bash
python quake_map.py --csv ./data/Eartquakes-1990-2023.csv   --lat latitude --lon longitude   --eps-km 200 --min-samples 30
```

Добавить точку на карту:
```bash
python quake_map.py --csv ./data/Eartquakes-1990-2023.csv   --lat latitude --lon longitude   --auto-eps   --add-lat 60.17 --add-lon 24.94   --add-label "Моя точка"
```

Сохранить под другим именем и не открывать:
```bash
python quake_map.py ... --output my_map.html --no-open
```

python quake_map.py --csv ./Eartquakes-1990-2023_short.csv  --lat latitude --lon longitude --eps-km 260 --min-sample 49


---

## Параметры CLI

| Аргумент | Описание |
|---|---|
| `--csv` | Путь к CSV |
| `--lat`, `--lon` | Имена колонок широты/долготы |
| `--magcol` | Имя колонки магнитуды |
| `--minmag` | Порог магнитуды |
| `--min-samples` | `min_samples` для DBSCAN |
| `--eps-km` | Радиус соседства `eps` (км) |
| `--auto-eps` | Авто-подбор `eps` |
| `--auto-eps-k` | `k` для авто-eps (по умолчанию 30) |
| `--auto-eps-percentile` | Перцентиль для авто-eps (по умолчанию 95) |
| `--add-lat`, `--add-lon` | Координаты добавленной точки |
| `--add-label` | Подпись добавленной точки |
| `--output` | Имя HTML-карты |
| `--no-open` | Не открывать браузер |

---

## Вариант для ноутбука (грид-поиск DBSCAN, без HDBSCAN)

Лучший результат выбирается по формуле:

- `coverage = 1 − noise`, где `noise` — доля точек с меткой `-1`
- `score = w * coverage + (1 − w) * log1p(n_clusters)/log1p(N)`
- варианты с `noise > max_noise` исключаются
- при равном `score` — предпочтение **большему `eps`**

Пример:

```python
df_db, best_db = grid_dbscan(
    coords_rad,
    eps_km_list=(150, 180, 200, 220, 240, 260),
    k_list=(30,),
    max_noise=0.30,
    coverage_weight=0.80,
    prefer_larger_eps=True
)
```

---

## Визуализация

- `k_distance_plot(...)` — подбор `eps`
- `plot_clusters(...)` — статическая карта
- интерактивная Folium-карта → `earthquakes_map.html`

---

## Структура проекта

```
.
├─ Eartquakes-1990-2023.csv
├─ quake_map.py
├─ notebook_script.py / .ipynb
└─ earthquakes_map.html
```

---

## Частые ошибки

- `FileNotFoundError` → проверь путь к `--csv`
- `нет колонок latitude/longitude` → неправильные имена
- пусто после `--minmag` → слишком высокий порог
- карта не открылась автоматически → открой HTML вручную

---

## Лицензия

MIT
