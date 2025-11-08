import argparse
import os
import sys
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import DBSCAN

import folium
from folium.plugins import HeatMap

EARTH_RADIUS_KM = 6371.0088

# Простая палитра из 20 цветов (без зависимости от matplotlib)
PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    "#393b79", "#637939", "#8c6d31", "#843c39", "#7b4173",
    "#3182bd", "#e6550d", "#31a354", "#756bb1", "#636363",
]


def load_data(csv_path: str, lat_col: str, lon_col: str,
              magcol: str | None = None, minmag: float | None = None) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Файл не найден: {csv_path}")
    df = pd.read_csv(csv_path, low_memory=False)
    if lat_col not in df.columns or lon_col not in df.columns:
        raise ValueError(f"Нет нужных колонок '{lat_col}'/'{lon_col}'. Найдены: {list(df.columns)[:10]} ...")

    cols = [lat_col, lon_col] + ([magcol] if (magcol and magcol in df.columns) else [])
    df = df[cols].dropna()
    # Валидные координаты
    df = df[(df[lat_col].between(-90, 90)) & (df[lon_col].between(-180, 180))]

    if magcol and magcol in df.columns and minmag is not None:
        df = df[df[magcol].astype(float) >= float(minmag)]

    return df.reset_index(drop=True)


def auto_eps_km(coords_rad: np.ndarray, k: int = 30, percentile: float = 95.0) -> float:
    """Автоматический подбор eps (км) по перцентилю k-расстояний."""
    if len(coords_rad) < max(2, k):
        # для очень малого числа точек — небольшой радиус
        return 50.0
    nn = NearestNeighbors(n_neighbors=k, metric="haversine", algorithm="ball_tree").fit(coords_rad)
    dists, _ = nn.kneighbors(coords_rad)
    kth = dists[:, -1] * EARTH_RADIUS_KM  # в км
    return float(np.percentile(kth, percentile))


def run_dbscan(coords_rad: np.ndarray, eps_km: float, min_samples: int) -> np.ndarray:
    eps_rad = eps_km / EARTH_RADIUS_KM
    labels = DBSCAN(eps=eps_rad, min_samples=min_samples, metric="haversine", algorithm="ball_tree").fit_predict(coords_rad)
    return labels


def build_map(coords_deg: np.ndarray,
              labels: np.ndarray,
              added_point: tuple[float, float] | None = None,
              added_label: str | None = None,
              heat_sample: int = 200_000,
              max_points_per_cluster: int = 2500) -> folium.Map:
    """Строит Folium-карту с кластерами и (опц.) добавленной точкой."""
    # Стартовая карта
    m = folium.Map(location=[0, 0], zoom_start=2, tiles="CartoDB positron")

    # Тепловая подложка
    if len(coords_deg) > 0:
        if heat_sample and len(coords_deg) > heat_sample:
            idx = np.random.choice(len(coords_deg), heat_sample, replace=False)
            heat_points = coords_deg[idx].tolist()
        else:
            heat_points = coords_deg.tolist()

        HeatMap(heat_points, radius=4, blur=3, min_opacity=0.15, max_zoom=6).add_to(m)

    # Слои кластеров
    unique_clusters = sorted(set(labels) - {-1})
    # Шум (-1) как отдельный слой серым
    mask_noise = (labels == -1)
    if mask_noise.any():
        noise = coords_deg[mask_noise]
        if len(noise) > max_points_per_cluster:
            noise = noise[np.random.choice(len(noise), max_points_per_cluster, replace=False)]
        noise_layer = folium.FeatureGroup(name="Noise (DBSCAN)", show=False)
        for (lat, lon) in noise:
            folium.CircleMarker(location=[lat, lon], radius=2, color="#999999",
                                weight=1, fill=True, fill_color="#999999", fill_opacity=0.5).add_to(noise_layer)
        noise_layer.add_to(m)

    for i, cl in enumerate(unique_clusters):
        mask = (labels == cl)
        pts = coords_deg[mask]
        if len(pts) == 0:
            continue
        if len(pts) > max_points_per_cluster:
            pts = pts[np.random.choice(len(pts), max_points_per_cluster, replace=False)]
        color = PALETTE[i % len(PALETTE)]
        layer = folium.FeatureGroup(name=f"Cluster {cl} (≈{mask.sum()} pts)", show=(i == 0))
        for (lat, lon) in pts:
            folium.CircleMarker(location=[lat, lon], radius=2, color=color,
                                weight=1, fill=True, fill_color=color, fill_opacity=0.7).add_to(layer)
        layer.add_to(m)

    # Добавленная точка — сверху и заметно
    if added_point is not None:
        alat, alon = map(float, added_point)
        popup = added_label or "Добавленная точка"
        folium.CircleMarker(location=[alat, alon],
                            radius=9,
                            color="#000000",
                            weight=2,
                            fill=True,
                            fill_color="#ff0000",
                            fill_opacity=0.9,
                            popup=popup).add_to(m)
        # Также вставим обычный Marker для удобного клика
        folium.Marker(location=[alat, alon],
                      popup=popup,
                      tooltip="Добавленная точка",
                      icon=folium.Icon(color="red", icon="star")).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DBSCAN (haversine) + интерактивная карта Folium.")
    p.add_argument("--csv", required=True, help="Путь к CSV с данными.")
    p.add_argument("--lat", required=True, help="Имя колонки широты.")
    p.add_argument("--lon", required=True, help="Имя колонки долготы.")
    p.add_argument("--magcol", default=None, help="(Опц.) Имя колонки магнитуды.")
    p.add_argument("--minmag", type=float, default=None, help="(Опц.) Минимальная магнитуда для фильтра.")
    p.add_argument("--min-samples", type=int, default=30, help="DBSCAN: min_samples (по умолчанию 30).")
    p.add_argument("--eps-km", type=float, default=None, help="DBSCAN: eps в километрах. Если не задан, берём auto-eps.")
    p.add_argument("--auto-eps", action="store_true", help="Включить авто-подбор eps по 95-му перцентилю (k=30).")
    p.add_argument("--auto-eps-k", type=int, default=30, help="k для авто-eps (по умолчанию 30).")
    p.add_argument("--auto-eps-percentile", type=float, default=95.0, help="Перцентиль для авто-eps (по умолчанию 95).")
    p.add_argument("--add-lat", type=float, default=None, help="(Опц.) Добавить точку: широта.")
    p.add_argument("--add-lon", type=float, default=None, help="(Опц.) Добавить точку: долгота.")
    p.add_argument("--add-label", type=str, default=None, help="(Опц.) Подпись для добавленной точки.")
    p.add_argument("--output", default="earthquakes_map.html", help="Имя выходного HTML-файла карты.")
    p.add_argument("--no-open", action="store_true", help="Не открывать карту автоматически в браузере.")
    return p.parse_args()


def main():
    args = parse_args()

    # 1) Загрузка
    df = load_data(args.csv, args.lat, args.lon, args.magcol, args.minmag)
    if len(df) == 0:
        print("❗ После фильтрации точек не осталось. Проверь входные параметры.", file=sys.stderr)
        sys.exit(1)

    coords_deg = df[[args.lat, args.lon]].to_numpy(dtype="float64")
    coords_rad = np.radians(coords_deg)

    # 2) eps
    if args.eps_km is not None:
        eps_km = float(args.eps_km)
    elif args.auto_eps or args.eps_km is None:
        eps_km = auto_eps_km(coords_rad, k=args.auto_eps_k, percentile=args.auto_eps_percentile)
        print(f"[auto-eps] k={args.auto_eps_k}, perc={args.auto_eps_percentile} → eps≈{eps_km:.1f} км")
    else:
        # fallback
        eps_km = 200.0

    # 3) DBSCAN
    labels = run_dbscan(coords_rad, eps_km=eps_km, min_samples=args.min_samples)
    n_clusters = len(set(labels) - {-1})
    noise_ratio = float((labels == -1).mean())
    print(f"DBSCAN: clusters={n_clusters}, noise={noise_ratio:.2%}, eps_km={eps_km:.1f}, min_samples={args.min_samples}")
    print(f"Точек всего: {len(coords_deg)}")

    # 4) Карта
    added_point = None
    if args.add_lat is not None and args.add_lon is not None:
        added_point = (args.add_lat, args.add_lon)

    m = build_map(coords_deg, labels, added_point=added_point, added_label=args.add_label)

    out_path = Path(args.output).resolve()
    m.save(str(out_path))
    print(f"Карта сохранена: {out_path}")

    if not args.no_open:
        try:
            import webbrowser
            webbrowser.open(out_path.as_uri())
            print("Открыл карту в браузере.")
        except Exception as e:
            print(f"⚠️ Не смог открыть браузер автоматически: {e}. Открой файл вручную.", file=sys.stderr)


if __name__ == "__main__":
    main()
