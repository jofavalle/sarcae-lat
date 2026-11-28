"""Validación de ERA5 contra una estación, día a día: la media, la máxima y la mínima.

Compara ERA5 en la ubicación de cada estación de las réplicas (#56) con la temperatura de
GHCNh: El Dorado (Bogotá) y La Chinita (Maracaibo), en los días locales de 2024 y 2025. El
emparejado por hora, la corrección por altura y el sesgo con el error cuadrático medio vienen
de `src/validacion.py` (#54); aquí van la calidad, el periodo, el día local, el criterio de
cobertura y las cifras diarias.

- **Calidad.** Solo cuentan las filas con temperatura y código `1` (`src/ghcnh.py`), antes de
  emparejar: una fila descartada no le quita la hora a otra buena.
- **Periodo.** Cuentan las observaciones cuya hora en punto más cercana cae en un día local
  de 2024 o 2025. Con husos fijos y sin horario de verano: UTC-5 en Bogotá y UTC-4 en
  Maracaibo (`docs/PLAN.md`, sección 5, punto 1).
- **Cobertura.** Un día cuenta si tiene al menos 20 horas emparejadas y al menos una en cada
  cuarto del día local: madrugada (00 a 05), mañana (06 a 11), tarde (12 a 17) y noche (18 a
  23). Los demás no entran en ninguna métrica.
- **Cifras diarias.** La media, la máxima y la mínima de las mismas horas emparejadas en la
  estación y en ERA5. La corrección por altura se aplica a cada hora de ERA5 antes de agregar.
- **Métricas.** El sesgo (ERA5 menos la estación) y el error cuadrático medio, en K, de cada
  cifra diaria, sin corrección y con ella, por año y para los dos años juntos.

Escribe en `--salida` el `config.yaml` y el `metrics.json` del experimento, que no guardan
ningún valor horario ni diario de las estaciones: sus series no se versionan (#46). Con
`--dias`, las cifras de cada día válido van a
`data/processed/validacion-replicas/<estación>-dias.csv`, que no se versiona.

Uso, desde la raíz del repositorio:

    python -m src.validacion_diaria \\
        --estacion data/raw/ghcnh/COI0000SKBO --era5 data/raw/era5/el-dorado \\
        --estacion data/raw/ghcnh/VEI0000SVMC --era5 data/raw/era5/la-chinita \\
        --salida experiments/AAAAMMDD-validacion-replicas --dias

El sesgo es una limitación que se declara en la ficha, no una calificación de ERA5.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src import ghcnh
from src.validacion import (LAPSE_K_PER_KM, TOLERANCE_MIN, _commit, _months, _rounded,
                            _yaml, bias_rmse, correct_height, height_shift, pair_hours,
                            read_era5, to_kelvin)

ROOT = Path(__file__).resolve().parents[1]
DAYS_DIR = ROOT / "data" / "processed" / "validacion-replicas"

PERIOD = ("2024-01-01", "2025-12-31")
MIN_HOURS = 20
QUARTERS = {"madrugada": (0, 5), "manana": (6, 11), "tarde": (12, 17), "noche": (18, 23)}
STATS = ("media", "maxima", "minima")
STATION_LIST = ("https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/"
                "doc/ghcnh-station-list.txt")
LICENSE = ("CC0 en la ficha del conjunto; non_commercial en el inventario sub-diario v3.0.0 "
           "de C3S y NCEI. La serie no se versiona (#46): solo se publica esta métrica.")

# Coordenadas y altura, de la lista de estaciones de GHCNh; distancia a la escuela, de la #19.
STATIONS = {
    "COI0000SKBO": {"nombre": "Bogotá/El Dorado", "lat": 4.7016, "lon": -74.1469,
                    "z_estacion_m": 2548.4, "huso_horas": -5, "distancia_escuela_km": 8.1},
    "VEI0000SVMC": {"nombre": "Maracaibo/La Chinita", "lat": 10.5582, "lon": -71.7279,
                    "z_estacion_m": 71.6, "huso_horas": -4, "distancia_escuela_km": 16.5},
}


# Núcleo: tablas y números, sin leer ni escribir.

def period_bounds(start: str, end: str, utc_offset_hours: float) -> tuple:
    """Primera hora UTC del primer día local y primera hora UTC después del último."""
    shift = pd.Timedelta(hours=utc_offset_hours)
    first = pd.Timestamp(start, tz="UTC") - shift
    after = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1) - shift
    return first, after


def in_period(times: pd.Series, start: str, end: str, utc_offset_hours: float) -> pd.Series:
    """Observaciones cuya hora en punto más cercana cae en un día local del periodo.

    `pair_hours` lleva cada observación a `floor(t + 30 min)`, así que esa hora está en
    `[primera, después)` si y solo si `t` está en `[primera - 30 min, después - 30 min)`.
    """
    first, after = period_bounds(start, end, utc_offset_hours)
    half = pd.Timedelta(minutes=30)
    times = pd.to_datetime(times, utc=True)
    return (times >= first - half) & (times < after - half)


def daily(pairs: pd.DataFrame, z_station: float, z_cell: float, utc_offset_hours: float,
          lapse_k_per_km: float = LAPSE_K_PER_KM, min_hours: int = MIN_HOURS) -> pd.DataFrame:
    """Una fila por día local con horas emparejadas: cobertura y cifras diarias.

    `pairs` es la salida de `pair_hours`. ERA5 se corrige hora a hora antes de agregar.
    """
    local = pairs["hora"] + pd.Timedelta(hours=utc_offset_hours)
    frame = pd.DataFrame({
        "fecha_local": local.dt.strftime("%Y-%m-%d"),
        "cuarto": local.dt.hour // 6,
        "hora_utc": pairs["hora"],
        "estacion": pairs["estacion_k"].to_numpy(dtype="float64"),
        "era5": pairs["era5_k"].to_numpy(dtype="float64"),
    })
    frame["era5_corregida"] = correct_height(frame["era5"], z_station, z_cell, lapse_k_per_km)
    groups = frame.groupby("fecha_local", sort=True)
    days = pd.DataFrame({
        "horas": groups.size(),
        "cuartos": groups["cuarto"].nunique(),
        "primera_hora_utc": groups["hora_utc"].min(),
        "ultima_hora_utc": groups["hora_utc"].max(),
    })
    aggregations = {"media": "mean", "maxima": "max", "minima": "min"}
    for source in ("estacion", "era5", "era5_corregida"):
        for stat, how in aggregations.items():
            days[f"{source}_{stat}_k"] = groups[source].agg(how)
    days["valido"] = (days["horas"] >= min_hours) & (days["cuartos"] == len(QUARTERS))
    return days.reset_index()


def _stats_block(days: pd.DataFrame) -> dict:
    block = {"dias": int(len(days))}
    for stat in STATS:
        station = days[f"estacion_{stat}_k"].to_numpy(dtype="float64")
        bias, rmse = bias_rmse(days[f"era5_{stat}_k"].to_numpy(dtype="float64") - station)
        bias_c, rmse_c = bias_rmse(
            days[f"era5_corregida_{stat}_k"].to_numpy(dtype="float64") - station)
        block[stat] = {
            "sin_correccion": {"sesgo_k": bias, "error_cuadratico_medio_k": rmse},
            "con_correccion": {"sesgo_k": bias_c, "error_cuadratico_medio_k": rmse_c},
        }
    return block


def daily_metrics(days: pd.DataFrame, months) -> dict:
    """Sesgo y error de las cifras diarias, por año y en total, solo con los días válidos.

    `months` es la lista de meses (`AAAA-MM`) cuyos días válidos se cuentan, con cero si no
    tienen ninguno.
    """
    valid = days[days["valido"]]
    years = valid["fecha_local"].str[:4]
    month_keys = valid["fecha_local"].str[:7]
    counts = month_keys.value_counts()
    per_month = {m: int(counts.get(m, 0)) for m in months}
    all_years = sorted({m[:4] for m in months})
    return {
        "por_anio": {y: _stats_block(valid[years == y]) for y in all_years},
        "total": _stats_block(valid),
        "dias_validos_por_mes": per_month,
        "meses_sin_dias_validos": [m for m, n in per_month.items() if n == 0],
    }


# Una estación: lectura, calidad, emparejado y cifras.

def _station_record(directory: Path) -> dict:
    with open(Path(directory) / "registro.json", encoding="utf-8") as handle:
        return json.load(handle)


def validate_station(station_dir: Path, era5_dir: Path) -> dict:
    """Todo lo de una estación: lo que va al `metrics.json` y la tabla de días."""
    record = _station_record(station_dir)
    station_id = record["estacion"]
    if station_id not in STATIONS:
        sys.exit(f"{station_id} no es una estación de esta validación: {', '.join(STATIONS)}")
    cfg = STATIONS[station_id]
    offset = cfg["huso_horas"]

    raw = ghcnh.read_station(station_dir)
    raw = raw[in_period(raw["time"], *PERIOD, offset)].reset_index(drop=True)
    kept, quality = ghcnh.filter_quality(raw)
    observations = pd.DataFrame({"time": kept["time"],
                                 "temp_k": to_kelvin(kept["temperature"], "°C")})

    series, point, z_cell, era5_record = read_era5(era5_dir)
    pairs, discards = pair_hours(observations, series, range(24), TOLERANCE_MIN)
    days = daily(pairs, cfg["z_estacion_m"], z_cell, offset, LAPSE_K_PER_KM)
    metrics = daily_metrics(days, _months(*PERIOD))

    used = [f for f in record["archivos"] if f["anio"] in (2024, 2025)]
    extra = [f for f in record["archivos"] if f["anio"] not in (2024, 2025)]
    return {
        "id": station_id,
        "cfg": cfg,
        "days": days,
        "pairs": len(pairs),
        "z_cell": z_cell,
        "fake": era5_record.get("nota_ficticio", "ERA5 ficticio")
                if era5_record.get("ficticio") else None,
        "metrics": {
            "nombre": cfg["nombre"],
            "lat": cfg["lat"], "lon": cfg["lon"],
            "z_estacion_m": cfg["z_estacion_m"],
            "huso_horas": offset,
            "distancia_estacion_escuela_km": cfg["distancia_escuela_km"],
            "era5": {"punto_pedido": era5_record["punto_pedido"],
                     "punto_rejilla": {"lat": point[0], "lon": point[1]},
                     "z_celda_m": round(z_cell, 2)},
            "correccion_k": round(height_shift(cfg["z_estacion_m"], z_cell, LAPSE_K_PER_KM), 4),
            **_rounded(metrics),
            "horas_emparejadas": int(len(pairs)),
            "filas_del_periodo": int(len(raw)),
            "descartes": {
                "por_calidad": quality,
                "por_minutos": discards["a_mas_de_la_tolerancia"],
                "repetidas": discards["otra_mas_cercana_en_la_misma_hora"],
                "sin_era5_a_esa_hora": discards["sin_era5_a_esa_hora"],
            },
            "dias_con_horas_no_validos": int((~days["valido"]).sum()),
            "fuente": ghcnh.citation(
                f"Estación {station_id}, archivos anuales PSV de 2024, 2025 y 2026",
                record["descargado_utc"][:10]),
            "licencia": LICENSE,
            "insumos": {
                "sha256": {Path(f["ruta"]).name: f["sha256"] for f in used},
                "otros_archivos": [{"archivo": Path(f["ruta"]).name, "sha256": f["sha256"],
                                    "nota": "solo aportan las primeras horas UTC del 1 de "
                                            "enero de 2026; " + ghcnh.GROWING_NOTE}
                                   for f in extra],
                "era5_sha256": {f["ruta"]: f["sha256"] for f in era5_record["archivos"]},
            },
        },
    }


# Salidas

def _config() -> dict:
    return {
        "experimento": "validación de ERA5 en las réplicas contra El Dorado y La Chinita, "
                       "con las cifras diarias (#56)",
        "estaciones": {sid: {"nombre": c["nombre"], "lat": c["lat"], "lon": c["lon"],
                             "z_estacion_m": c["z_estacion_m"], "huso_horas": c["huso_horas"]}
                       for sid, c in STATIONS.items()},
        "fuente_coordenadas_y_altura": STATION_LIST,
        "datos": {"estacion": "NOAA NCEI GHCNh v1, archivos anuales PSV (src/ghcnh.py)",
                  "era5": "reanalysis-era5-single-levels-timeseries, en la ubicación de la "
                          "estación, y reanalysis-era5-single-levels para z_celda"},
        "periodo": {"inicio": PERIOD[0], "fin": PERIOD[1],
                    "nota": "días locales; el archivo de 2026 aporta las primeras horas UTC "
                            "del 1 de enero, que completan el 31 de diciembre local"},
        "husos": {"nota": "fijos y sin horario de verano: UTC-5 en Bogotá y UTC-4 en "
                          "Maracaibo"},
        "filtro_calidad": {
            "regla": "temperature no vacía y temperature_Quality_Code igual a 1",
            "nota": "elección conservadora: se descartan el código vacío (filas de la fuente "
                    "999, sin control propio), el 2 («Suspect») y el 4 («Calculated»), según "
                    "la documentación de GHCNh, sección VI, tabla 3. El filtro va antes del "
                    "emparejado.",
        },
        "tolerancia_min": TOLERANCE_MIN,
        "regla_emparejado": "cada observación va a la hora en punto más cercana si está a "
                            "10 minutos o menos; si dos caen en la misma hora, cuenta la más "
                            "cercana (src/validacion.py, pair_hours)",
        "cobertura": {"horas_minimas": MIN_HOURS,
                      "cuartos_locales": {k: f"{a:02d} a {b:02d}"
                                          for k, (a, b) in QUARTERS.items()},
                      "nota": "al menos una hora emparejada en cada cuarto; los días que no "
                              "lo cumplen no entran en ninguna métrica"},
        "cifras_diarias": "media, máxima y mínima de las mismas horas emparejadas en la "
                          "estación y en ERA5",
        "gradiente_k_por_km": LAPSE_K_PER_KM,
        "correccion": "T_corr = T_ERA5 - Γ·(z_est - z_celda), en cada hora antes de agregar",
        "semilla": None,
        "nota_semilla": "no hay semilla: el cálculo no tiene aleatoriedad",
    }


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def write_days(result: dict) -> Path:
    """Las cifras de cada día válido, para el control a mano. No se versiona."""
    days = result["days"][result["days"]["valido"]].copy()
    for column in ("primera_hora_utc", "ultima_hora_utc"):
        days[column] = days[column].dt.strftime("%Y-%m-%d %H:%M")
    days["estacion_maxima_c"] = (days["estacion_maxima_k"] - 273.15).round(2)
    days = days.drop(columns=["valido", "cuartos"])
    path = DAYS_DIR / f"{result['id']}-dias.csv"
    DAYS_DIR.mkdir(parents=True, exist_ok=True)
    days.to_csv(path, index=False, float_format="%.4f", lineterminator="\n")
    return path


def _report(result: dict) -> None:
    m, cfg = result["metrics"], result["cfg"]
    years = m["por_anio"]
    print(f"== {result['id']}, {cfg['nombre']} (UTC{cfg['huso_horas']:+d})")
    print("días válidos: " + ", ".join(f"{y} {b['dias']}" for y, b in years.items())
          + f", total {m['total']['dias']}")
    empty = m["meses_sin_dias_validos"]
    print(f"meses sin días válidos: {', '.join(empty) if empty else 'ninguno'}")
    print(f"z_celda: {result['z_cell']:.1f} m (z_est {cfg['z_estacion_m']} m; la corrección "
          f"suma {m['correccion_k']:+.4f} K a ERA5)")
    d, q = m["descartes"], m["descartes"]["por_calidad"]
    print(f"descartadas: por calidad {sum(q.values())} ({q['sin_temperatura']} sin "
          f"temperatura, {q['codigo_vacio']} con código vacío, {q['otro_codigo']} con otro "
          f"código); por minutos {d['por_minutos']}; repetidas {d['repetidas']}; sin ERA5 "
          f"{d['sin_era5_a_esa_hora']}")
    for label, block in list(years.items()) + [("2024 y 2025", m["total"])]:
        for stat in STATS:
            raw, corr = block[stat]["sin_correccion"], block[stat]["con_correccion"]
            if raw["sesgo_k"] is None:
                print(f"{label}, {stat}: sin días válidos")
                continue
            print(f"{label}, {stat}: sin corrección sesgo {raw['sesgo_k']:+.3f} K, error "
                  f"cuadrático medio {raw['error_cuadratico_medio_k']:.3f} K | con "
                  f"corrección sesgo {corr['sesgo_k']:+.3f} K, error cuadrático medio "
                  f"{corr['error_cuadratico_medio_k']:.3f} K")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--estacion", type=Path, action="append", required=True,
                        metavar="CARPETA", help="descarga de src/ghcnh.py; se repite")
    parser.add_argument("--era5", type=Path, action="append", required=True,
                        metavar="CARPETA",
                        help="descarga de src/era5.py en la ubicación de la estación "
                             "anterior; se repite, en el mismo orden")
    parser.add_argument("--salida", type=Path, required=True, metavar="CARPETA",
                        help="carpeta del experimento: experiments/AAAAMMDD-validacion-replicas")
    parser.add_argument("--dias", action="store_true",
                        help=f"escribe las cifras de cada día válido en "
                             f"{_relative(DAYS_DIR)}/<estación>-dias.csv")
    args = parser.parse_args(argv)
    if len(args.estacion) != len(args.era5):
        parser.error("cada --estacion va con su --era5")

    results = [validate_station(s, e) for s, e in zip(args.estacion, args.era5)]
    # Una ERA5 marcada como ficticia (decisión del equipo del 2026-11-28, #54) se declara
    # arriba del todo en las dos salidas; con descargas reales no aparece.
    fakes = {r["id"]: r["fake"] for r in results if r["fake"]}
    fake = {"datos_ficticios": fakes} if fakes else {}

    metrics = {
        **fake,
        "descripcion": ("ERA5 frente a la estación, día a día: la media, la máxima y la mínima "
                        "de las horas emparejadas. El sesgo es una limitación que se declara, "
                        "no una calificación."),
        "definiciones": {
            "sesgo_k": "media de ERA5 menos la estación, en K",
            "error_cuadratico_medio_k": "raíz de la media de (ERA5 menos la estación) al "
                                        "cuadrado, en K",
            "con_correccion": "ERA5 corregido en cada hora: T_ERA5 - Γ·(z_est - z_celda)",
            "dias": "días locales válidos según el criterio de cobertura del config.yaml",
        },
        "estaciones": {r["id"]: r["metrics"] for r in results},
        "commit": _commit(),
        "corrida_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    args.salida.mkdir(parents=True, exist_ok=True)
    with open(args.salida / "config.yaml", "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_yaml({**fake, **_config()}) + "\n")
    with open(args.salida / "metrics.json", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    for sid, note in fakes.items():
        print(f"AVISO, DATOS FICTICIOS en {sid}: {note}")
    for result in results:
        _report(result)
        if args.dias:
            path = write_days(result)
            print(f"días: {_relative(path)} ({int(result['days']['valido'].sum())} filas)")
    print(f"escrito: {_relative(args.salida / 'config.yaml')}, "
          f"{_relative(args.salida / 'metrics.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
