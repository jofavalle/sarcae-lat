"""Recorte versionado de la serie de ERA5 de una escuela.

Lee una descarga de `src.era5` (`data/raw/era5/<escuela>/`, con su `registro.json`) y escribe
en `recortes/<escuela>/era5/`:

- `serie.parquet`: `time` en UTC, `t2m` en K y `tp` en m, comprimido con zstd;
- `celda.json`: el punto de rejilla y `z_celda`, la altura de la celda en m;
- `manifiesto.json`, con `src.recortes`.

Después, los indicadores corren desde el recorte, sin cuenta del Climate Data Store.

Uso, desde la raíz del repositorio:

    python -m src.era5_recorte --escuela sv-88118

`--origen` y `--destino` cambian las dos carpetas. Si el `registro.json` de origen dice
`"ficticio": true`, `celda.json` lo repite con su nota, y el recorte no va a `recortes/`.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.era5 import LEVELS_DATASET, SERIES_DATASET, read_geopotential, read_series, grid_point
from src.recortes import escribir, guardar_json

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "era5"
RECORTES = ROOT / "recortes"

URL_CC_BY = "https://creativecommons.org/licenses/by/4.0/"
TOL_GRADOS = 1e-6


def atribucion(anio: str) -> str:
    """La de ERA5 en el README, para datos adaptados."""
    return (f"Contains modified Copernicus Climate Change Service information {anio}. "
            "Neither the European Commission nor ECMWF is responsible for any use that may be "
            "made of the Copernicus information or data it contains. ERA5, serie por punto: "
            "https://doi.org/10.24381/1cf1ad76 · ERA5, niveles de superficie: "
            "https://doi.org/10.24381/cds.adbb2d47")


def tabla_recorte(serie: pd.DataFrame) -> pd.DataFrame:
    """Solo `time` (UTC), `t2m` y `tp`, en orden y sin horas repetidas."""
    tabla = serie[["time", "t2m", "tp"]].sort_values("time", ignore_index=True)
    if tabla["time"].duplicated().any():
        raise ValueError("la serie tiene horas repetidas")
    if str(tabla["time"].dt.tz) != "UTC":
        raise ValueError("la hora de la serie no está en UTC")
    return tabla


def recortar(escuela: str, origen: Path, destino: Path) -> dict:
    origen, destino = Path(origen).resolve(), Path(destino).resolve()
    with open(origen / "registro.json", encoding="utf-8") as f:
        registro = json.load(f)
    # Los archivos están en la carpeta de origen: la ruta del registro sirve para el nombre.
    por_dataset = {a["dataset"]: origen / Path(a["ruta"]).name for a in registro["archivos"]}
    serie = read_series(por_dataset[SERIES_DATASET])
    lat, lon = grid_point(serie)
    if np.isnan(lat):
        raise ValueError("la serie no trae su punto de rejilla")
    geo_lat, geo_lon, z_celda = read_geopotential(por_dataset[LEVELS_DATASET], lat, lon)
    if max(abs(geo_lat - lat), abs(geo_lon - lon)) > TOL_GRADOS:
        raise ValueError(f"serie en {lat}, {lon} y geopotencial en {geo_lat}, {geo_lon}")
    tabla = tabla_recorte(serie)

    destino.mkdir(parents=True, exist_ok=True)
    tabla.to_parquet(destino / "serie.parquet", engine="pyarrow", compression="zstd",
                     index=False)
    fecha = (registro.get("descargado_utc") or registro.get("creado_utc"))[:10]
    celda = {
        "escuela": escuela,
        "punto_pedido": registro["punto_pedido"],
        "punto_rejilla": {"lat": lat, "lon": lon},
        "z_celda": {"valor": round(z_celda, 2), "unidad": "m",
                    "dataset": LEVELS_DATASET},
        "periodo": registro["periodo"],
        "filas": int(len(tabla)),
        "primera_hora_utc": tabla["time"].iloc[0].isoformat(),
        "ultima_hora_utc": tabla["time"].iloc[-1].isoformat(),
    }
    if registro.get("ficticio"):
        celda["ficticio"] = True
        celda["nota_ficticio"] = registro.get("nota_ficticio", "ERA5 ficticio")
    guardar_json(destino / "celda.json", celda)
    escribir(destino, fuente="ERA5",
             version=f"{SERIES_DATASET} y {LEVELS_DATASET} (geopotencial)",
             url_fuente=f"https://cds.climate.copernicus.eu/datasets/{SERIES_DATASET}",
             licencia="CC-BY-4.0", url_licencia=URL_CC_BY,
             atribucion=atribucion(fecha[:4]), fecha_descarga=fecha)
    return celda


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--escuela", required=True)
    parser.add_argument("--origen", type=Path, help="por defecto data/raw/era5/<escuela>")
    parser.add_argument("--destino", type=Path, help="por defecto recortes/<escuela>/era5")
    args = parser.parse_args(argv)
    origen = args.origen or RAW / args.escuela
    destino = args.destino or RECORTES / args.escuela / "era5"
    celda = recortar(args.escuela, origen, destino)
    if celda.get("ficticio"):
        print(f"AVISO, DATOS FICTICIOS: {celda['nota_ficticio']}")
    print(f"recorte: {celda['filas']} filas, de {celda['primera_hora_utc']} a "
          f"{celda['ultima_hora_utc']}")
    print(f"punto de rejilla: {celda['punto_rejilla']['lat']}, {celda['punto_rejilla']['lon']}; "
          f"z_celda: {celda['z_celda']['valor']} m")
    print(f"escrito en {Path(destino).resolve().relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
