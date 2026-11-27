"""Descarga y comprobación de la serie horaria de ERA5 en un punto.

Descarga del Climate Data Store la serie horaria de ERA5 de un punto
(`reanalysis-era5-single-levels-timeseries`) y el geopotencial de su celda
(`reanalysis-era5-single-levels`), y los guarda tal como llegan en
`data/raw/era5/<nombre>/`, junto con un `registro.json`. `data/raw/` es inmutable: si el
destino ya existe, no se toca.

Uso, desde la raíz del repositorio:

    python -m src.era5 --lat 13.70 --lon -89.12 --nombre prueba-ilopango
    python -m src.era5 --lat 13.70 --lon -89.12 --nombre prueba-ilopango-2025 \\
        --inicio 2025-01-01 --fin 2025-12-31
    python -m src.era5 --comprobar data/raw/era5/prueba-ilopango

Las credenciales van en `~/.cdsapirc`, nunca en el repositorio, y antes hay que aceptar la
licencia de los dos datasets en su pestaña "Download".
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from src.era5_checks import G0, nearest_index, run_checks, summarize, wrap_longitude

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "era5"

SERIES_DATASET = "reanalysis-era5-single-levels-timeseries"
LEVELS_DATASET = "reanalysis-era5-single-levels"
VARIABLES = ["2m_temperature", "2m_dewpoint_temperature", "total_precipitation"]
LICENSE = "CC-BY-4.0"
DEFAULT_START = "1940-01-01"
DEFAULT_END = "2025-12-31"

# Nombres con que pueden llegar las columnas, y el nombre interno de cada una.
TIME_COLUMNS = ("valid_time", "time", "date")
COLUMN_NAMES = {
    "t2m": "t2m", "2m_temperature": "t2m",
    "d2m": "d2m", "2m_dewpoint_temperature": "d2m",
    "tp": "tp", "total_precipitation": "tp",
    "latitude": "latitude", "lat": "latitude",
    "longitude": "longitude", "lon": "longitude",
}


# Peticiones al CDS

def series_request(lat: float, lon: float, start: str, end: str) -> dict:
    return {
        "variable": VARIABLES,
        "location": {"latitude": lat, "longitude": lon},
        "date": [f"{start}/{end}"],
        "data_format": "csv",
    }


def geopotential_request(lat: float, lon: float) -> dict:
    """Geopotencial de una sola hora en las nueve celdas que rodean el punto de rejilla.

    Es un campo invariante: cualquier hora vale. Se piden las vecinas para no depender de
    cómo recorta el CDS un área de un solo punto; luego se elige el punto exacto.
    """
    return {
        "product_type": ["reanalysis"],
        "variable": ["geopotential"],
        "year": ["2025"], "month": ["01"], "day": ["01"], "time": ["00:00"],
        "area": [lat + 0.25, lon - 0.25, lat - 0.25, lon + 0.25],
        "data_format": "netcdf",
        "download_format": "unarchived",
    }


# Lectura de lo descargado

def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    """Columnas con los nombres internos y la hora como fecha UTC."""
    time_column = next((c for c in TIME_COLUMNS if c in frame.columns), None)
    if time_column is None:
        raise ValueError(f"no hay columna de hora entre {list(frame.columns)}")
    renamed = {c: COLUMN_NAMES[c] for c in frame.columns if c in COLUMN_NAMES}
    out = frame.rename(columns=renamed)
    keep = [c for c in ("t2m", "d2m", "tp", "latitude", "longitude") if c in out.columns]
    out = out[[time_column] + keep].rename(columns={time_column: "time"})
    out["time"] = pd.to_datetime(out["time"], utc=True)
    for column in keep:
        out[column] = out[column].astype("float64")
    return out


def read_series(path: Path) -> pd.DataFrame:
    """Serie tal como llegó: un CSV, o un zip con uno o varios CSV (se unen por la hora)."""
    if not zipfile.is_zipfile(path):
        return _normalize(pd.read_csv(path))
    frames = []
    with zipfile.ZipFile(path) as archive:
        for member in sorted(archive.namelist()):
            if member.lower().endswith(".csv"):
                with archive.open(member) as handle:
                    frames.append(_normalize(pd.read_csv(handle)))
    if not frames:
        raise ValueError(f"{path.name} no contiene ningún CSV")
    merged = frames[0]
    for frame in frames[1:]:
        shared = [c for c in frame.columns if c in merged.columns and c != "time"]
        merged = merged.merge(frame.drop(columns=shared), on="time", how="outer")
    order = [c for c in ("time", "t2m", "d2m", "tp", "latitude", "longitude")
             if c in merged.columns]
    return merged[order].sort_values("time", ignore_index=True)


def grid_point(series: pd.DataFrame) -> tuple:
    """Punto de rejilla que devolvió la serie, si lo trae; si no, NaN."""
    if "latitude" in series.columns and "longitude" in series.columns:
        lat = series["latitude"].unique()
        lon = series["longitude"].unique()
        if len(lat) == 1 and len(lon) == 1:
            return float(lat[0]), float(wrap_longitude(lon[0]))
    return float("nan"), float("nan")


def read_geopotential(path: Path, lat: float, lon: float) -> tuple:
    """Punto de rejilla más cercano a (lat, lon) y la altura de su celda en metros."""
    from netCDF4 import Dataset

    with Dataset(path) as ds:
        lats = np.asarray(ds["latitude"][:], dtype="float64")
        lons = wrap_longitude(ds["longitude"][:])
        z = np.asarray(ds["z"][:], dtype="float64").squeeze()
    i, j = nearest_index(lats, lat), nearest_index(lons, lon)
    return float(lats[i]), float(lons[j]), float(z[i, j] / G0)


# Utilidades de registro

def _relative(path: Path) -> str:
    """Ruta relativa a la raíz: una absoluta publicaría el directorio personal."""
    return path.resolve().relative_to(ROOT).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _commit() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "desconocido"


def _series_extension(path: Path) -> str:
    if zipfile.is_zipfile(path):
        return ".zip"
    with open(path, "rb") as handle:
        head = handle.read(4)
    return ".nc" if head in (b"\x89HDF", b"CDF\x01", b"CDF\x02") else ".csv"


def ensure_new(final: Path) -> None:
    """Sale con un mensaje si el destino ya existe: data/raw es inmutable."""
    if final.exists():
        sys.exit(f"{_relative(final)} ya existe, y data/raw es inmutable: no se toca.")


# Descarga

def download(name: str, lat: float, lon: float, start: str, end: str) -> Path:
    """Descarga la serie y el geopotencial a una carpeta temporal y la renombra al final.

    Si algo falla a mitad, el destino no llega a existir: queda una carpeta
    `.parcial-<nombre>-*` junto a él, que se revisa y se borra a mano.
    """
    import cdsapi

    final = RAW / name
    ensure_new(final)
    RAW.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f".parcial-{name}-", dir=RAW))
    client = cdsapi.Client()
    started_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    request = series_request(lat, lon, start, end)
    landing = work / "serie.descarga"
    clock = time.monotonic()
    client.retrieve(SERIES_DATASET, request, str(landing))
    series_seconds = time.monotonic() - clock
    series_file = landing.rename(work / ("serie" + _series_extension(landing)))
    print(f"serie descargada en {series_seconds:.0f} s", flush=True)

    series = read_series(series_file)
    point = grid_point(series)
    target = point if not np.isnan(point[0]) else (lat, lon)
    geo_request = geopotential_request(*target)
    geo_file = work / "geopotencial.nc"
    clock = time.monotonic()
    client.retrieve(LEVELS_DATASET, geo_request, str(geo_file))
    geo_seconds = time.monotonic() - clock
    print(f"geopotencial descargado en {geo_seconds:.0f} s", flush=True)

    files = []
    for path, dataset, sent, seconds in (
            (series_file, SERIES_DATASET, request, series_seconds),
            (geo_file, LEVELS_DATASET, geo_request, geo_seconds)):
        files.append({
            "ruta": _relative(final / path.name),
            "dataset": dataset,
            "peticion": sent,
            "segundos": round(seconds, 1),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        })
    record = {
        "descargado_utc": started_utc,
        "commit": _commit(),
        "cdsapi": version("cdsapi"),
        "licencia": LICENSE,
        "periodo": {"inicio": start, "fin": end},
        "punto_pedido": {"lat": lat, "lon": lon},
        "punto_rejilla": {"lat": point[0], "lon": point[1]},
        "archivos": files,
    }
    with open(work / "registro.json", "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    work.rename(final)
    print(f"guardado en {_relative(final)}")
    return final


# Comprobación

def check(directory: Path) -> int:
    """Imprime el resumen y los controles de una descarga. Devuelve 0 o 1."""
    directory = directory.resolve()
    with open(directory / "registro.json", encoding="utf-8") as handle:
        record = json.load(handle)
    by_dataset = {f["dataset"]: ROOT / f["ruta"] for f in record["archivos"]}
    series = read_series(by_dataset[SERIES_DATASET])
    start, end = record["periodo"]["inicio"], record["periodo"]["fin"]
    asked = record["punto_pedido"]
    point = grid_point(series)
    geo_lat, geo_lon, height = read_geopotential(by_dataset[LEVELS_DATASET], *point)
    summary = summarize(series)
    checks = run_checks(series, start, end, point, (geo_lat, geo_lon))

    print(f"serie: {_relative(by_dataset[SERIES_DATASET])}")
    print(f"filas: {summary['rows']}")
    print(f"primera hora: {summary['first']:%Y-%m-%d %H:%M} UTC")
    print(f"última hora: {summary['last']:%Y-%m-%d %H:%M} UTC")
    print(f"punto de rejilla: {point[0]:.4f}, {point[1]:.4f} "
          f"(pedido {asked['lat']}, {asked['lon']})")
    print(f"altura de la celda: {height:.1f} m")
    print(f"temperatura media a 2 m: {summary['mean_t2m_k']:.2f} K")
    print(f"lluvia anual media: {summary['annual_rain_m']:.3f} m")
    print(f"máximo del ciclo diario medio: {summary['peak_hour_utc']} UTC")
    for item in checks:
        print(f"[{'OK' if item.ok else 'FALLA'}] {item.name}: {item.detail}")
    failed = [item.name for item in checks if not item.ok]
    print("comprobación en orden" if not failed else
          f"comprobación con {len(failed)} fallos: {', '.join(failed)}")
    return 0 if not failed else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--comprobar", type=Path, metavar="CARPETA",
                        help="comprueba una descarga ya hecha")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lon", type=float)
    parser.add_argument("--nombre", help="carpeta de destino dentro de data/raw/era5/")
    parser.add_argument("--inicio", default=DEFAULT_START)
    parser.add_argument("--fin", default=DEFAULT_END)
    args = parser.parse_args(argv)

    if args.comprobar is not None:
        return check(args.comprobar)
    if args.lat is None or args.lon is None or not args.nombre:
        parser.error("para descargar hacen falta --lat, --lon y --nombre")
    download(args.nombre, args.lat, args.lon, args.inicio, args.fin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
