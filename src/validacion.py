"""Validación de ERA5 contra una estación, hora a hora: sesgo y error cuadrático medio.

El núcleo (de `to_kelvin` a `summarize`) no lee, no escribe y no sabe de ninguna estación:
recibe tablas y números y devuelve tablas y números, para que lo reusen la ancla y las
réplicas (#54, #56) y para que las pruebas lo ejerciten con series fabricadas.

- **Emparejado** (`pair_hours`). ERA5 da la temperatura a la hora en punto. Cada observación
  se asigna a la hora en punto más cercana, si está a `tolerancia` minutos o menos de ella. Si
  dos caen en la misma hora, cuenta la más cercana (a igual distancia, la primera). Solo
  cuentan las horas UTC de la ventana. Lo descartado se cuenta por motivo.
- **Corrección por altura** (`correct_height`): `T_corr = T_ERA5 - Γ·(z_est - z_celda)`, con
  Γ en K/m.
- **Métricas** (`summarize`): el sesgo es la media de ERA5 menos la estación, y el error
  cuadrático medio es la raíz de la media de su cuadrado, los dos en K, sin corrección y con
  ella, por año local y para todo el periodo, con las horas y los días emparejados, y las
  horas emparejadas de cada mes.

La línea de órdenes (`main`) aplica el núcleo a la escuela ancla: Santa Ana/El Palmar, del CDS
(`src/insitu.py`), frente a ERA5 en la ubicación de la estación (`src/era5.py`). Escribe en la
carpeta de `--salida` el `config.yaml` y el `metrics.json` del experimento, que no guardan
ningún valor horario de la estación, porque su serie no se versiona (#39, #46). Con `--pares`,
la lista de horas emparejadas va a `data/processed/validacion-ancla/pares.csv`, que no se
versiona.

Uso, desde la raíz del repositorio:

    python -m src.validacion --estacion data/raw/c3s-insitu/santa-ana-el-palmar \\
        --era5 data/raw/era5/santa-ana-el-palmar \\
        --salida experiments/AAAAMMDD-validacion-ancla --pares

El sesgo es una limitación que se declara en la ficha, no una calificación de ERA5.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

LAPSE_K_PER_KM = 6.5
TOLERANCE_MIN = 10
KELVIN_OFFSET = 273.15
KELVIN_UNITS = {"k", "kelvin"}
CELSIUS_UNITS = {"c", "degc", "deg_c", "°c", "celsius", "degree_celsius"}

DISCARD_REASONS = (
    "sin_valor",
    "a_mas_de_la_tolerancia",
    "fuera_de_la_ventana",
    "otra_mas_cercana_en_la_misma_hora",
    "sin_era5_a_esa_hora",
)


# Núcleo

def to_kelvin(values, units: str) -> np.ndarray:
    """Temperaturas en kelvin, a partir de las unidades escritas en el archivo."""
    key = str(units).strip().lower().replace(" ", "")
    values = np.asarray(values, dtype="float64")
    if key in KELVIN_UNITS:
        return values
    if key in CELSIUS_UNITS:
        return values + KELVIN_OFFSET
    raise ValueError(f"unidades de temperatura desconocidas: {units!r}")


def observations_in_kelvin(observations: pd.DataFrame) -> pd.DataFrame:
    """De una tabla `time`, `valor`, `unidades` a otra `time`, `temp_k`."""
    temp = np.empty(len(observations), dtype="float64")
    units = observations["unidades"].to_numpy()
    values = observations["valor"].to_numpy(dtype="float64")
    for unit in pd.unique(units):
        mask = units == unit
        temp[mask] = to_kelvin(values[mask], unit)
    return pd.DataFrame({"time": _utc(observations["time"]).reset_index(drop=True),
                         "temp_k": temp})


def _utc(times: pd.Series) -> pd.Series:
    return pd.to_datetime(times, utc=True).astype("datetime64[ns, UTC]")


def pair_hours(observations: pd.DataFrame, model: pd.DataFrame, hours_utc,
               tolerance_min: float = TOLERANCE_MIN) -> tuple:
    """Empareja observaciones con las horas en punto del modelo.

    `observations` tiene `time` (UTC) y `temp_k`; `model`, `time` (UTC, en punto) y `t2m`
    (K). `hours_utc` son las horas UTC del día que cuentan. Devuelve los pares, una fila por
    hora, con `hora`, `observacion`, `minutos` (de la hora a la observación, con signo),
    `estacion_k` y `era5_k`, y un diccionario con lo descartado por motivo.
    """
    hours_utc = {int(h) for h in hours_utc}
    discards = dict.fromkeys(DISCARD_REASONS, 0)
    obs = pd.DataFrame({"observacion": _utc(observations["time"]).reset_index(drop=True),
                        "estacion_k": observations["temp_k"].to_numpy(dtype="float64")})

    missing = obs["estacion_k"].isna()
    discards["sin_valor"] = int(missing.sum())
    obs = obs[~missing]

    obs["hora"] = (obs["observacion"] + pd.Timedelta(minutes=30)).dt.floor("h")
    obs["minutos"] = (obs["observacion"] - obs["hora"]).dt.total_seconds() / 60.0
    far = obs["minutos"].abs() > tolerance_min
    discards["a_mas_de_la_tolerancia"] = int(far.sum())
    obs = obs[~far]

    outside = ~obs["hora"].dt.hour.isin(hours_utc)
    discards["fuera_de_la_ventana"] = int(outside.sum())
    obs = obs[~outside]

    obs = (obs.assign(_distancia=obs["minutos"].abs())
              .sort_values(["hora", "_distancia", "observacion"], kind="mergesort"))
    repeated = obs.duplicated("hora", keep="first")
    discards["otra_mas_cercana_en_la_misma_hora"] = int(repeated.sum())
    obs = obs[~repeated].drop(columns="_distancia")

    era5 = pd.DataFrame({"hora": _utc(model["time"]),
                         "era5_k": model["t2m"].to_numpy(dtype="float64")})
    if era5["hora"].duplicated().any():
        raise ValueError("el modelo tiene horas repetidas")
    pairs = obs.merge(era5, on="hora", how="left")
    no_model = pairs["era5_k"].isna()
    discards["sin_era5_a_esa_hora"] = int(no_model.sum())
    pairs = pairs[~no_model]

    columns = ["hora", "observacion", "minutos", "estacion_k", "era5_k"]
    return pairs[columns].sort_values("hora", ignore_index=True), discards


def correct_height(t_model, z_station: float, z_cell: float,
                   lapse_k_per_km: float = LAPSE_K_PER_KM):
    """`T_corr = T_ERA5 - Γ·(z_est - z_celda)`, con Γ en K/km y las alturas en metros."""
    return t_model - (lapse_k_per_km / 1000.0) * (z_station - z_cell)


def bias_rmse(differences) -> tuple:
    """Sesgo (media) y error cuadrático medio (raíz de la media del cuadrado), o NaN."""
    d = np.asarray(differences, dtype="float64")
    if d.size == 0:
        return float("nan"), float("nan")
    return float(d.mean()), float(np.sqrt(np.mean(d * d)))


def _block(local: pd.Series, diff: np.ndarray, diff_corr: np.ndarray, mask) -> dict:
    mask = np.asarray(mask, dtype=bool)
    bias, rmse = bias_rmse(diff[mask])
    bias_c, rmse_c = bias_rmse(diff_corr[mask])
    return {
        "horas": int(mask.sum()),
        "dias": int(local[mask].dt.date.nunique()),
        "sin_correccion": {"sesgo_k": bias, "error_cuadratico_medio_k": rmse},
        "con_correccion": {"sesgo_k": bias_c, "error_cuadratico_medio_k": rmse_c},
    }


def summarize(pairs: pd.DataFrame, z_station: float, z_cell: float,
              lapse_k_per_km: float = LAPSE_K_PER_KM, utc_offset_hours: float = 0,
              months=None) -> dict:
    """Sesgo y error cuadrático medio por año y en total, sin corrección y con ella.

    Los años, los días y los meses son locales: la hora UTC más `utc_offset_hours`. `months`
    es la lista de meses (`AAAA-MM`) cuyas horas se cuentan, con cero si no tienen ninguna;
    si falta, se cuentan los meses que aparecen en los pares.
    """
    local = (pairs["hora"] + pd.Timedelta(hours=utc_offset_hours)).reset_index(drop=True)
    station = pairs["estacion_k"].to_numpy(dtype="float64")
    model = pairs["era5_k"].to_numpy(dtype="float64")
    diff = model - station
    diff_corr = correct_height(model, z_station, z_cell, lapse_k_per_km) - station

    years = local.dt.year
    by_year = {str(y): _block(local, diff, diff_corr, years == y)
               for y in sorted(years.unique())}
    month_keys = local.dt.strftime("%Y-%m")
    counts = month_keys.value_counts()
    if months is None:
        months = sorted(counts.index)
    return {
        "por_anio": by_year,
        "total": _block(local, diff, diff_corr, np.ones(len(local), dtype=bool)),
        "horas_por_mes": {m: int(counts.get(m, 0)) for m in months},
    }


def height_shift(z_station: float, z_cell: float,
                 lapse_k_per_km: float = LAPSE_K_PER_KM) -> float:
    """Lo que la corrección suma a ERA5, en K: `-Γ·(z_est - z_celda)`."""
    return float(correct_height(0.0, z_station, z_cell, lapse_k_per_km))


# La escuela ancla: lo propio de Santa Ana/El Palmar va aquí, fuera del núcleo.

ANCLA = {
    "estacion": "ESI0000MSSA",
    "nombre": "Santa Ana/El Palmar",
    # Del inventario de estaciones sub-diarias v3.0.0 (#39).
    "z_estacion_m": 660.0,
    "inventario": ("https://confluence.ecmwf.int/download/attachments/656869601/"
                   "Sub_daily_inventory_v3.0.0.psv?version=1&modificationDate=1776783749830&api=v2"),
    "periodo": ("2024-01-01", "2025-12-31"),
    # De 07:00 a 17:00 hora local, con las 17:00 fuera: de 13 a 22 UTC (UTC-6).
    "ventana_utc": (13, 23),
    "huso_horas": -6,
    "distancia_escuela_km": 20.5,
    "nota_distancia": ("aproximada, medida en la #39 desde el casco urbano de San Pablo "
                       "Tacachico (13,975; -89,340), porque el repositorio no tiene las "
                       "coordenadas de la escuela"),
    "fuente": {
        "source_id": 223,
        "archivo": ("https://confluence.ecmwf.int/download/attachments/656869601/"
                    "sources_v3.0.0.psv?version=1&modificationDate=1776783749760&api=v2"),
        # Literal, columna acknowledge_as de la fila 223.
        "cita": ("International Civil Aviation Organisation USAF : National Climatic Data "
                 "Center/NESDIS/NOAA/U.S. Department of Commerce. 1982.AWS TD13 Global "
                 "Surface Observations, daily 1901-1973. Research Data Archive at the "
                 "National Center for Atmospheric Research, Computational and Information "
                 "Systems Laboratory. https://rda.ucar.edu/datasets/ds467.0/. "
                 "Accesseddd mmm yyyy."),
    },
    "licencia": {
        "conjunto": "CC-BY-4.0",
        "conjunto_url": "https://cds.climate.copernicus.eu/datasets/insitu-observations-surface-land",
        "registros": "data_policy_licence 1, 'WMO essential'",
        "inventario_estacion": "non_commercial",
        "serie": ("no versionada: se lee lo más restrictivo (regla 6) y solo se publica "
                  "la métrica (#39, #46)"),
    },
}

ROOT = Path(__file__).resolve().parents[1]
PAIRS_PATH = ROOT / "data" / "processed" / "validacion-ancla" / "pares.csv"


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _commit() -> str:
    """El commit de la corrida, marcado si el código de `src/` no está entero en él."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True)
    if head.returncode != 0:
        return "desconocido"
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "src"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    return head.stdout.strip() + ("-modificado" if dirty else "")


def _months(start: str, end: str) -> list:
    return [p.strftime("%Y-%m") for p in pd.period_range(start[:7], end[:7], freq="M")]


def _rounded(value, digits: int = 4):
    if isinstance(value, dict):
        return {k: _rounded(v, digits) for k, v in value.items()}
    if isinstance(value, float):
        return None if np.isnan(value) else round(value, digits)
    return value


def _yaml(data: dict, indent: int = 0) -> str:
    """YAML de diccionarios, listas cortas y escalares, sin dependencias."""
    lines = []
    pad = "  " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            lines.append(_yaml(value, indent + 1))
        elif isinstance(value, (list, tuple)):
            lines.append(f"{pad}{key}: [{', '.join(json.dumps(v, ensure_ascii=False) for v in value)}]")
        else:
            lines.append(f"{pad}{key}: {json.dumps(value, ensure_ascii=False)}")
    return "\n".join(lines)


def read_era5(directory: Path) -> tuple:
    """La serie de ERA5 de una descarga de `src/era5.py`, su punto de rejilla y `z_celda`."""
    from src.era5 import (LEVELS_DATASET, SERIES_DATASET, grid_point, read_geopotential,
                          read_series)

    directory = directory.resolve()
    with open(directory / "registro.json", encoding="utf-8") as handle:
        record = json.load(handle)
    by_dataset = {f["dataset"]: ROOT / f["ruta"] for f in record["archivos"]}
    series = read_series(by_dataset[SERIES_DATASET])
    point = grid_point(series)
    _, _, z_cell = read_geopotential(by_dataset[LEVELS_DATASET], *point)
    return series, point, z_cell, record


def main(argv=None) -> int:
    from src.insitu import read_download

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--estacion", type=Path, required=True, metavar="CARPETA",
                        help="descarga de src/insitu.py en data/raw/c3s-insitu/")
    parser.add_argument("--era5", type=Path, required=True, metavar="CARPETA",
                        help="descarga de src/era5.py en data/raw/era5/")
    parser.add_argument("--salida", type=Path, required=True, metavar="CARPETA",
                        help="carpeta del experimento: experiments/AAAAMMDD-validacion-ancla")
    parser.add_argument("--pares", action="store_true",
                        help=f"escribe las horas emparejadas en {_relative(PAIRS_PATH)}")
    args = parser.parse_args(argv)
    cfg = ANCLA

    raw_obs, meta, obs_record = read_download(args.estacion)
    if obs_record["estacion"] != cfg["estacion"]:
        sys.exit(f"la descarga es de {obs_record['estacion']}, no de {cfg['estacion']}")
    observations = observations_in_kelvin(raw_obs)
    series, point, z_cell, era5_record = read_era5(args.era5)
    first, last = cfg["ventana_utc"]
    hours = range(first, last)

    pairs, discards = pair_hours(observations, series, hours, TOLERANCE_MIN)
    z_station = cfg["z_estacion_m"]
    result = summarize(pairs, z_station, z_cell, LAPSE_K_PER_KM, cfg["huso_horas"],
                       _months(*cfg["periodo"]))
    shift = height_shift(z_station, z_cell, LAPSE_K_PER_KM)
    hours_in_pairs = sorted(int(h) for h in pairs["hora"].dt.hour.unique())
    # Una carpeta de ERA5 marcada como ficticia (decisión del equipo del 2026-11-28, #54) se
    # declara arriba del todo en las dos salidas; con una descarga real no aparece.
    fake = ({"datos_ficticios": era5_record.get("nota_ficticio", "ERA5 ficticio")}
            if era5_record.get("ficticio") else {})

    config = {
        **fake,
        "experimento": "validación de ERA5 en la escuela ancla contra Santa Ana/El Palmar (#54)",
        "estacion": {"id": cfg["estacion"], "nombre": cfg["nombre"],
                     "z_estacion_m": z_station, "z_estacion_fuente": cfg["inventario"]},
        "datos": {"estacion": f"{obs_record['dataset']} v{obs_record['version']}",
                  "era5": "reanalysis-era5-single-levels-timeseries, en la ubicación de la "
                          "estación, y reanalysis-era5-single-levels para z_celda"},
        "periodo": {"inicio": cfg["periodo"][0], "fin": cfg["periodo"][1]},
        "ventana_utc": {"desde": first, "hasta_excluida": last,
                        "nota": "de 07:00 a 17:00 hora local, con las 17:00 fuera; "
                                "todos los días de la semana"},
        "huso_horas": cfg["huso_horas"],
        "gradiente_k_por_km": LAPSE_K_PER_KM,
        "tolerancia_min": TOLERANCE_MIN,
        "filtro_calidad": obs_record["filtro"],
        "semilla": None,
        "nota_semilla": "no hay semilla: el cálculo no tiene aleatoriedad",
    }
    metrics = {
        **fake,
        "descripcion": ("ERA5 frente a la estación, hora a hora, en el horario escolar. El "
                        "sesgo es una limitación que se declara, no una calificación."),
        "definiciones": {
            "sesgo_k": "media de ERA5 menos la estación, en K",
            "error_cuadratico_medio_k": "raíz de la media de (ERA5 menos la estación) al "
                                        "cuadrado, en K",
            "con_correccion": "ERA5 corregido: T_ERA5 - Γ·(z_est - z_celda)",
            "dias": "días locales con al menos una hora emparejada",
        },
        "estacion": {"id": cfg["estacion"], "nombre": meta["nombre"], "lat": meta["lat"],
                     "lon": meta["lon"], "z_estacion_m": z_station,
                     "altura_en_el_archivo_m": meta["altura_m"]},
        "era5": {"punto_pedido": era5_record["punto_pedido"],
                 "punto_rejilla": {"lat": point[0], "lon": point[1]},
                 "z_celda_m": round(z_cell, 2)},
        "correccion_k": round(shift, 4),
        "distancia_estacion_escuela_km": cfg["distancia_escuela_km"],
        "nota_distancia": cfg["nota_distancia"],
        **_rounded(result),
        "horas_utc_en_pares": hours_in_pairs,
        "descartes": discards,
        "observaciones_de_calidad": len(observations),
        "fuente": cfg["fuente"],
        "licencia": cfg["licencia"],
        "insumos": {
            "id_peticion_cds_estacion": obs_record["id_peticion_cds"],
            "sha256": {f["ruta"]: f["sha256"]
                       for f in obs_record["archivos"] + era5_record["archivos"]},
        },
        "commit": _commit(),
        "corrida_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    args.salida.mkdir(parents=True, exist_ok=True)
    with open(args.salida / "config.yaml", "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_yaml(config) + "\n")
    with open(args.salida / "metrics.json", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    if fake:
        print(f"AVISO, DATOS FICTICIOS: {fake['datos_ficticios']}")
    if meta["altura_m"] != z_station:
        print(f"aviso: el archivo da {meta['altura_m']} m de altura para la estación, "
              f"y el inventario {z_station} m")
    for label, block in list(result["por_anio"].items()) + [("2024 y 2025", result["total"])]:
        raw, corr = block["sin_correccion"], block["con_correccion"]
        print(f"{label}: {block['horas']} horas, {block['dias']} días | sin corrección: "
              f"sesgo {raw['sesgo_k']:+.3f} K, error cuadrático medio "
              f"{raw['error_cuadratico_medio_k']:.3f} K | con corrección: sesgo "
              f"{corr['sesgo_k']:+.3f} K, error cuadrático medio "
              f"{corr['error_cuadratico_medio_k']:.3f} K")
    print(f"z_celda: {z_cell:.1f} m (z_est {z_station:.0f} m; la corrección suma "
          f"{shift:+.4f} K a ERA5)")
    print(f"horas UTC en los pares: {', '.join(str(h) for h in hours_in_pairs)}")
    print("descartadas: " + ", ".join(f"{k} {v}" for k, v in discards.items()))
    print(f"escrito: {_relative(args.salida / 'config.yaml')}, "
          f"{_relative(args.salida / 'metrics.json')}")

    if args.pares:
        out = pairs.assign(
            era5_corregido_k=correct_height(pairs["era5_k"], z_station, z_cell, LAPSE_K_PER_KM))
        out["diferencia_k"] = out["era5_k"] - out["estacion_k"]
        out["diferencia_corregida_k"] = out["era5_corregido_k"] - out["estacion_k"]
        out["hora"] = out["hora"].dt.strftime("%Y-%m-%d %H:%M")
        out["observacion"] = out["observacion"].dt.strftime("%Y-%m-%d %H:%M")
        out = out.rename(columns={"hora": "hora_utc", "observacion": "observacion_utc",
                                  "minutos": "minutos_a_la_hora"})
        PAIRS_PATH.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(PAIRS_PATH, index=False, float_format="%.4f", lineterminator="\n")
        print(f"pares: {_relative(PAIRS_PATH)} ({len(out)} filas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
