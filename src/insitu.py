"""Descarga y lectura de las observaciones horarias de una estación del Climate Data Store.

Descarga del CDS el conjunto `insitu-observations-surface-land` (observaciones de estaciones
terrestres de C3S y NCEI, versión 3.0.0, sub-diarias), temperatura del aire, de 2024 y 2025 en
un rectángulo alrededor de El Salvador, y lo guarda tal como llega en
`data/raw/c3s-insitu/<nombre>/`, junto con un `registro.json`. `data/raw/` es inmutable: si el
destino ya existe, no se toca.

El archivo trae todas las estaciones del rectángulo. La lectura (`read_station`) se queda
solo con la estación pedida y con los registros que pasan el control de calidad
(`quality_flag == 0`); el original no se edita.

La serie no se versiona (#39, #46): el inventario de estaciones sub-diarias v3.0.0 marca a
Santa Ana/El Palmar como `non_commercial`, y de ella solo se publica la métrica.

Uso, desde la raíz del repositorio:

    python -m src.insitu
    python -m src.insitu --comprobar data/raw/c3s-insitu/santa-ana-el-palmar

Las credenciales van en `~/.cdsapirc`, nunca en el repositorio, y antes hay que aceptar las
licencias del conjunto en su pestaña "Download".
"""

import argparse
import io
import json
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import pandas as pd

from src.era5 import ROOT, _commit, _relative, _series_extension, _sha256, ensure_new

RAW = ROOT / "data" / "raw" / "c3s-insitu"

DATASET = "insitu-observations-surface-land"
DATASET_VERSION = "3_0_0"
LICENSE = "CC-BY-4.0"
DEFAULT_NAME = "santa-ana-el-palmar"
DEFAULT_STATION = "ESI0000MSSA"
DEFAULT_YEARS = ("2024", "2025")
# [norte, oeste, sur, este]: el rectángulo de la petición de la #39.
DEFAULT_AREA = (14.5, -90.2, 13.1, -87.6)
GOOD_QUALITY = 0

# Columnas del CSV (convención cdm-obs del CDS) que usa la lectura.
STATION_COLUMN = "primary_station_id"
TIME_COLUMN = "report_timestamp"
VALUE_COLUMN = "observation_value"
UNITS_COLUMN = "units"
QUALITY_COLUMN = "quality_flag"
META_COLUMNS = {
    "station_name": "nombre",
    "latitude": "lat",
    "longitude": "lon",
    "height_of_station_above_sea_level": "altura_m",
}


# Petición al CDS

def request(years=DEFAULT_YEARS, area=DEFAULT_AREA) -> dict:
    return {
        "version": DATASET_VERSION,
        "time_aggregation": "sub_daily",
        "variable": ["air_temperature"],
        "year": list(years),
        "month": [f"{m:02d}" for m in range(1, 13)],
        "day": [f"{d:02d}" for d in range(1, 32)],
        "area": list(area),
        "data_format": "csv",
    }


# Lectura de lo descargado

def _read_csv(path: Path) -> pd.DataFrame:
    """El CSV tal como llegó, suelto o dentro de un zip. Las líneas `#` son su cabecera."""
    if not zipfile.is_zipfile(path):
        return pd.read_csv(path, comment="#")
    frames = []
    with zipfile.ZipFile(path) as archive:
        for member in sorted(archive.namelist()):
            if member.lower().endswith(".csv"):
                with archive.open(member) as handle:
                    frames.append(pd.read_csv(io.TextIOWrapper(handle, "utf-8"),
                                              comment="#"))
    if not frames:
        raise ValueError(f"{path.name} no contiene ningún CSV")
    return pd.concat(frames, ignore_index=True)


def read_station(path: Path, station: str) -> tuple:
    """Observaciones de calidad de una estación, y sus metadatos.

    Devuelve una tabla con `time` (hora UTC de la observación, con zona), `valor` y
    `unidades`, ordenada por hora, y un diccionario con el conteo de registros y los
    metadatos de la estación (nombre, lat, lon, altura_m). Las unidades se dejan como las
    trae el CSV: la conversión a kelvin la hace quien las usa. El CDS da las horas en UTC
    (convención cdm-obs), sin zona escrita.
    """
    frame = _read_csv(path)
    rows = frame[frame[STATION_COLUMN] == station]
    if rows.empty:
        raise ValueError(f"{station} no aparece en {path.name}")
    good = rows[rows[QUALITY_COLUMN] == GOOD_QUALITY]
    meta = {"registros": int(len(rows)), "registros_de_calidad": int(len(good))}
    for column, key in META_COLUMNS.items():
        values = rows[column].dropna().unique().tolist() if column in rows.columns else []
        meta[key] = values[0] if len(values) == 1 else None
    out = pd.DataFrame({
        "time": pd.to_datetime(good[TIME_COLUMN], utc=True),
        "valor": good[VALUE_COLUMN].astype("float64"),
        "unidades": good[UNITS_COLUMN].astype(str),
    })
    return out.sort_values("time", ignore_index=True), meta


def read_download(directory: Path) -> tuple:
    """La estación de una descarga hecha con `download`, a partir de su `registro.json`."""
    directory = directory.resolve()
    with open(directory / "registro.json", encoding="utf-8") as handle:
        record = json.load(handle)
    path = ROOT / record["archivos"][0]["ruta"]
    observations, meta = read_station(path, record["estacion"])
    return observations, meta, record


# Descarga

def download(name: str, station: str, years=DEFAULT_YEARS, area=DEFAULT_AREA) -> Path:
    """Descarga el conjunto a una carpeta temporal y la renombra al final.

    Si algo falla a mitad, el destino no llega a existir: queda una carpeta
    `.parcial-<nombre>-*` junto a él, que se revisa y se borra a mano.
    """
    import cdsapi

    final = RAW / name
    ensure_new(final)
    RAW.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f".parcial-{name}-", dir=RAW))
    # Sin esperar dentro de retrieve: así se conserva el trabajo y su identificador.
    client = cdsapi.Client(wait_until_complete=False)
    started_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    sent = request(years, area)
    landing = work / "observaciones.descarga"
    clock = time.monotonic()
    job = client.retrieve(DATASET, sent)
    request_id = getattr(job, "request_id", None)
    print(f"petición {request_id} enviada; esperando al CDS", flush=True)
    job.download(str(landing))
    seconds = time.monotonic() - clock
    data_file = landing.rename(work / ("observaciones" + _series_extension(landing)))
    print(f"observaciones descargadas en {seconds:.0f} s", flush=True)

    # Antes de dar la descarga por buena, la estación tiene que estar en el archivo.
    _, meta = read_station(data_file, station)

    record = {
        "descargado_utc": started_utc,
        "commit": _commit(),
        "cdsapi": version("cdsapi"),
        "dataset": DATASET,
        "version": DATASET_VERSION,
        "licencia": LICENSE,
        "nota_licencia": ("el inventario de estaciones sub-diarias v3.0.0 marca la estación "
                          "como non_commercial: la serie no se versiona (#39, #46)"),
        "id_peticion_cds": request_id,
        "estacion": station,
        "filtro": {"estacion": station, QUALITY_COLUMN: GOOD_QUALITY},
        "estacion_en_archivo": meta,
        "archivos": [{
            "ruta": _relative(final / data_file.name),
            "dataset": DATASET,
            "peticion": sent,
            "segundos": round(seconds, 1),
            "bytes": data_file.stat().st_size,
            "sha256": _sha256(data_file),
        }],
    }
    with open(work / "registro.json", "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    work.rename(final)
    print(f"guardado en {_relative(final)}")
    return final


# Comprobación

def check(directory: Path) -> int:
    """Imprime un resumen de la estación descargada, sin valores. Devuelve 0."""
    observations, meta, record = read_download(directory)
    days = observations["time"].dt.strftime("%Y-%m-%d").drop_duplicates()
    print(f"archivo: {record['archivos'][0]['ruta']}")
    print(f"petición del CDS: {record['id_peticion_cds']}")
    print(f"estación: {record['estacion']} ({meta['nombre']}), "
          f"{meta['lat']}, {meta['lon']}, {meta['altura_m']} m")
    print(f"registros: {meta['registros']}, de calidad: {meta['registros_de_calidad']}")
    print(f"unidades: {', '.join(sorted(observations['unidades'].unique()))}")
    print(f"primera observación: {observations['time'].min():%Y-%m-%d %H:%M} UTC")
    print(f"última observación: {observations['time'].max():%Y-%m-%d %H:%M} UTC")
    for year, count in days.str[:4].value_counts().sort_index().items():
        print(f"días con datos en {year}: {count}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--comprobar", type=Path, metavar="CARPETA",
                        help="resume una descarga ya hecha")
    parser.add_argument("--nombre", default=DEFAULT_NAME,
                        help=f"carpeta dentro de data/raw/c3s-insitu/ (por defecto {DEFAULT_NAME})")
    parser.add_argument("--estacion", default=DEFAULT_STATION,
                        help=f"primary_station_id (por defecto {DEFAULT_STATION})")
    args = parser.parse_args(argv)

    if args.comprobar is not None:
        return check(args.comprobar)
    download(args.nombre, args.estacion)
    return 0


if __name__ == "__main__":
    sys.exit(main())
