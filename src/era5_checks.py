"""Núcleo puro de la comprobación de una serie horaria de ERA5 en un punto.

Ninguna función de este módulo lee, escribe ni imprime: reciben una tabla y unos números y
devuelven números, de modo que las pruebas las ejercitan con datos fabricados.

La tabla tiene las columnas `time` (hora UTC, con zona), `t2m` y `d2m` (temperatura y punto
de rocío a 2 m, en K) y `tp` (lluvia acumulada en la hora, en m), que son las unidades en que
ERA5 llega del Climate Data Store.

Los rangos de los controles valen para un punto de El Salvador (UTC-6). Son anchos a
propósito: no miden la calidad de ERA5, sino que detectan los errores de manejo que dan un
número plausible, como unas horas en hora local, una lluvia en milímetros o grados Celsius
tomados por kelvin.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Gravedad estándar con la que ECMWF define el geopotencial: altura = z / G0.
G0 = 9.80665  # m/s2

# El máximo del ciclo diario de la temperatura cae entre el mediodía y la primera tarde
# local, de 11 a 15 en El Salvador, que son de 17 a 21 UTC. Una serie guardada en hora
# local lo pondría entre las 11 y las 15.
PEAK_HOUR_UTC = (17, 21)
# El Salvador recibe del orden de 1,5 a 2 m de lluvia al año. Un factor 1000 (milímetros
# por metros) lo saca del rango por tres órdenes de magnitud.
ANNUAL_RAIN_M = (1.0, 3.5)
# Una media anual de 17 a 32 °C. En grados Celsius la media sería de unos 25.
MEAN_T2M_K = (290.0, 305.0)
# El geopotencial y la serie tienen que ser el mismo punto de la rejilla de 0,25°.
GRID_TOL_DEG = 1e-6


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def expected_hours(start: str, end: str) -> pd.DatetimeIndex:
    """Horas UTC de `start` a las 00:00 a `end` a las 23:00, las dos incluidas."""
    first = pd.Timestamp(start, tz="UTC")
    last = pd.Timestamp(end, tz="UTC") + pd.Timedelta(hours=23)
    return pd.date_range(first, last, freq="h")


def summarize(series: pd.DataFrame) -> dict:
    """Resumen de la serie: filas, extremos, medias y hora del máximo del ciclo diario.

    La lluvia anual es la media, sobre los años del periodo, de la suma de cada año. El
    ciclo diario es la media de `t2m` por hora UTC del día.
    """
    time = series["time"]
    t2m = series["t2m"].astype("float64")
    tp = series["tp"].astype("float64")
    daily_cycle = t2m.groupby(time.dt.hour).mean()
    annual_rain = tp.groupby(time.dt.year).sum()
    return {
        "rows": int(len(series)),
        "first": time.min(),
        "last": time.max(),
        "mean_t2m_k": float(t2m.mean()),
        "mean_d2m_k": float(series["d2m"].astype("float64").mean()),
        "annual_rain_m": float(annual_rain.mean()),
        "peak_hour_utc": int(daily_cycle.idxmax()),
    }


def _inside(value: float, bounds: tuple) -> bool:
    low, high = bounds
    return bool(low <= value <= high)


def run_checks(series: pd.DataFrame, start: str, end: str,
               series_point: tuple, geo_point: tuple) -> list:
    """Controles de la serie de `start` a `end`. Devuelve una lista de `Check`.

    `series_point` es el punto de rejilla (lat, lon) que devolvió la serie, y `geo_point`,
    el del geopotencial con el que se calcula la altura de la celda.
    """
    expected = expected_hours(start, end)
    times = pd.DatetimeIndex(series["time"])
    repeated = int(times.duplicated().sum())
    missing = int(len(expected.difference(times)))
    outside = int(len(times.difference(expected)))
    summary = summarize(series)

    hours_ok = (len(times) == len(expected) and repeated == 0
                and missing == 0 and outside == 0)
    peak = summary["peak_hour_utc"]
    rain = summary["annual_rain_m"]
    t2m = summary["mean_t2m_k"]
    d2m = summary["mean_d2m_k"]
    dlat = abs(float(series_point[0]) - float(geo_point[0]))
    dlon = abs(float(series_point[1]) - float(geo_point[1]))

    return [
        Check("horas", hours_ok,
              f"{len(times)} filas de {len(expected)} esperadas; {repeated} repetidas, "
              f"{missing} huecos y {outside} fuera del periodo"),
        Check("ciclo diario", _inside(peak, PEAK_HOUR_UTC),
              f"máximo medio a las {peak} UTC; se espera entre las "
              f"{PEAK_HOUR_UTC[0]} y las {PEAK_HOUR_UTC[1]}"),
        Check("lluvia", _inside(rain, ANNUAL_RAIN_M),
              f"{rain:.3f} m al año; se espera entre {ANNUAL_RAIN_M[0]} y {ANNUAL_RAIN_M[1]} m"),
        Check("temperatura", _inside(t2m, MEAN_T2M_K),
              f"media de {t2m:.2f} K; se espera entre {MEAN_T2M_K[0]:.0f} y "
              f"{MEAN_T2M_K[1]:.0f} K"),
        Check("punto de rocío", bool(d2m < t2m),
              f"media de {d2m:.2f} K, por debajo de la temperatura ({t2m:.2f} K)"
              if d2m < t2m else
              f"media de {d2m:.2f} K, por encima de la temperatura ({t2m:.2f} K): "
              "¿columnas cambiadas?"),
        Check("rejilla", bool(max(dlat, dlon) < GRID_TOL_DEG),
              f"serie en {series_point[0]:.4f}, {series_point[1]:.4f}; geopotencial en "
              f"{geo_point[0]:.4f}, {geo_point[1]:.4f}"),
    ]


def nearest_index(values: np.ndarray, target: float) -> int:
    """Índice del valor más cercano a `target`."""
    return int(np.argmin(np.abs(np.asarray(values, dtype="float64") - target)))


def wrap_longitude(lon: np.ndarray) -> np.ndarray:
    """Longitudes en [-180, 180), venga la rejilla en [0, 360) o no."""
    lon = np.asarray(lon, dtype="float64")
    return (lon + 180.0) % 360.0 - 180.0
