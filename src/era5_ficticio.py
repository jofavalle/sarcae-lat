"""Serie de ERA5 ficticia de 1940 a 2026, para trabajar mientras falta la descarga real.

Decisión del equipo del 2026-11-28 (comentario en la #61): la serie completa de la 88118 no
llega a tiempo del CDS, y las órdenes que esperan a `clima.json` trabajan con una provisional.
Todo lo que sale de aquí va marcado como ficticio y no se versiona en `recortes/`.

Cada año de 1940 a 2025 copia, hora a hora, uno de los años reales de ERA5 que se le dan
(`--fuente`), elegido con una semilla fija. A cada año le suma una anomalía de temperatura,
N(0; 0,3 K), y multiplica su lluvia por exp(N(0; 0,2)). No se añade ninguna tendencia. El 29
de febrero de un año bisiesto copia el 28 si el año fuente no lo tiene. El 1 de enero de 2026
copia el de la fuente que lo traiga, o el de 2025 desplazado. El geopotencial es una altura
fija en las nueve celdas, como el de `data/processed/era5-ficticio/santa-ana-el-palmar/`.

Con `--serie-real`, la serie no se fabrica: se copia tal cual una descarga real de `src.era5`
que todavía espera su geopotencial, y solo `z_celda` es ficticia. El punto de rejilla sale de
la propia serie.

Uso, desde la raíz del repositorio:

    python -m src.era5_ficticio --escuela sv-88118 --lat 14.0 --lon -89.25 --z-celda 500 \\
        --fuente data/raw/era5/<carpeta>/serie.zip --fuente <otra>/serie.zip
    python -m src.era5_ficticio --escuela sv-88118 --z-celda 313.8 \\
        --serie-real data/raw/era5/.parcial-<carpeta>/serie.zip --peticion <ID>
"""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.era5 import (LEVELS_DATASET, SERIES_DATASET, _commit, _relative, _sha256, grid_point,
                      read_series)
from src.era5_checks import G0, expected_hours

ROOT = Path(__file__).resolve().parents[1]
DESTINO = ROOT / "data" / "processed" / "era5-ficticio"
SEMILLA = 20261128
SIGMA_T_K = 0.3
SIGMA_LOG_LLUVIA = 0.2


def anios_completos(serie: pd.DataFrame) -> dict:
    """Los años de la serie con todas sus horas UTC, como tablas indexadas por la hora."""
    t = serie["time"]
    salida = {}
    for anio, grupo in serie.groupby(t.dt.year):
        horas = 8784 if pd.Timestamp(f"{anio}-01-01").is_leap_year else 8760
        if len(grupo) == horas:
            salida[int(anio)] = grupo.set_index("time")[["t2m", "d2m", "tp"]]
    return salida


def copiar_anio(fuente: pd.DataFrame, anio: int) -> pd.DataFrame:
    """Las horas UTC de `anio` con los valores de la fuente del mismo mes, día y hora."""
    destino = expected_hours(f"{anio}-01-01", f"{anio}-12-31")
    origen = fuente.index
    clave = pd.MultiIndex.from_arrays([origen.month, origen.day, origen.hour])
    valores = fuente.set_axis(clave)
    dia = np.where((destino.month == 2) & (destino.day == 29)
                   & ((2, 29, 0) not in valores.index), 28, destino.day)
    buscada = pd.MultiIndex.from_arrays([destino.month, dia, destino.hour])
    tabla = valores.reindex(buscada)
    tabla.index = destino
    return tabla


def fabricar(fuentes: list, lat: float, lon: float, semilla: int = SEMILLA,
             inicio: int = 1940, fin: int = 2025) -> tuple:
    """La serie ficticia y la lista (año, año fuente) que la explica."""
    rng = np.random.default_rng(semilla)
    pool = []
    for i, serie in enumerate(fuentes):
        for anio, tabla in anios_completos(serie).items():
            pool.append((i, anio, tabla))
    if not pool:
        raise ValueError("ninguna fuente tiene un año completo")
    partes, elegidos = [], []
    for anio in range(inicio, fin + 1):
        i, anio_fuente, tabla = pool[int(rng.integers(len(pool)))]
        dt = float(rng.normal(0.0, SIGMA_T_K))
        factor = float(np.exp(rng.normal(0.0, SIGMA_LOG_LLUVIA)))
        copia = copiar_anio(tabla, anio)
        copia["t2m"] += dt
        copia["d2m"] += dt
        copia["tp"] *= factor
        partes.append(copia)
        elegidos.append({"anio": anio, "fuente": i, "anio_fuente": anio_fuente,
                         "anomalia_k": round(dt, 3), "factor_lluvia": round(factor, 3)})
    # El 1 de enero siguiente, de la fuente que lo tenga; si ninguna, el del último año.
    siguiente = expected_hours(f"{fin + 1}-01-01", f"{fin + 1}-01-01")
    extra = None
    for serie in fuentes:
        trozo = serie.set_index("time")[["t2m", "d2m", "tp"]].reindex(siguiente)
        if not trozo.isna().any().any():
            extra = trozo
            break
    if extra is None:
        extra = partes[-1].iloc[:24].copy()
        extra.index = siguiente
    partes.append(extra)
    tabla = pd.concat(partes)
    if tabla.isna().any().any():
        raise ValueError("quedaron horas sin valor")
    tabla.index.name = "valid_time"
    tabla = tabla.reset_index()
    tabla["latitude"], tabla["longitude"] = lat, lon
    return tabla, elegidos


def escribir_geopotencial(ruta: Path, lat: float, lon: float, z: float) -> None:
    from netCDF4 import Dataset

    with Dataset(ruta, "w") as ds:
        ds.createDimension("latitude", 3)
        ds.createDimension("longitude", 3)
        ds.createVariable("latitude", "f8", ("latitude",))[:] = [lat + 0.25, lat, lat - 0.25]
        ds.createVariable("longitude", "f8", ("longitude",))[:] = [lon - 0.25, lon, lon + 0.25]
        ds.createVariable("z", "f8", ("latitude", "longitude"))[:] = np.full((3, 3), z * G0)


def _ruta(path: Path) -> str:
    """Ruta relativa a la raíz si está dentro del repositorio; si no (en las pruebas), tal cual."""
    try:
        return _relative(path)
    except ValueError:
        return Path(path).as_posix()


def copiar_real(fuente: Path, destino: Path, z_celda: float, peticion: str) -> dict:
    """Copia una serie real de ERA5 con un geopotencial ficticio, y devuelve su registro.

    La serie se copia byte a byte: lo único ficticio es `z_celda`. El registro tiene la forma
    que lee `src.era5_recorte`, con `ficticio: true` y su nota.
    """
    fuente, destino = Path(fuente), Path(destino)
    lat, lon = grid_point(read_series(fuente))
    if np.isnan(lat):
        raise ValueError("la serie no trae su punto de rejilla")
    destino.mkdir(parents=True, exist_ok=True)
    serie = destino / ("serie" + "".join(fuente.suffixes))
    shutil.copyfile(fuente, serie)
    geo = destino / "geopotencial.nc"
    escribir_geopotencial(geo, lat, lon, z_celda)
    nota = (f"Serie real de ERA5; z_celda ficticia ({z_celda:g} m) hasta que llegue el "
            f"geopotencial de la celda ({peticion}). Decisión del equipo del 2026-11-28 (#61): "
            "se sustituye por la descarga completa.")
    return {
        "ficticio": True,
        "nota_ficticio": nota,
        "creado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": _commit(),
        "licencia": "CC-BY-4.0",
        "periodo": {"inicio": "1940-01-01", "fin": "2026-01-01"},
        "punto_rejilla": {"lat": lat, "lon": lon},
        "fuentes": [{"ruta": _ruta(fuente), "sha256": _sha256(fuente)}],
        "archivos": [
            {"ruta": _ruta(serie), "dataset": SERIES_DATASET, "sha256": _sha256(serie),
             "origen": "copia de la descarga real"},
            {"ruta": _ruta(geo), "dataset": LEVELS_DATASET, "sha256": _sha256(geo),
             "origen": f"ficticio: z = {z_celda:g} m · G0 en las 9 celdas"},
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--escuela", required=True)
    parser.add_argument("--lat", type=float, help="punto de rejilla (con --fuente)")
    parser.add_argument("--lon", type=float, help="punto de rejilla (con --fuente)")
    parser.add_argument("--z-celda", type=float, required=True, help="altura ficticia, en m")
    origen = parser.add_mutually_exclusive_group(required=True)
    origen.add_argument("--fuente", type=Path, action="append",
                        help="serie real de ERA5 (CSV o zip de src.era5); se repite")
    origen.add_argument("--serie-real", type=Path, metavar="RUTA",
                        help="descarga real de src.era5 que se copia tal cual")
    parser.add_argument("--peticion", default="petición en la cola del CDS",
                        help="con --serie-real: qué petición traerá el geopotencial")
    parser.add_argument("--punto-pedido", type=float, nargs=2, metavar=("LAT", "LON"),
                        help="con --serie-real: el punto que se pidió al CDS")
    parser.add_argument("--semilla", type=int, default=SEMILLA)
    args = parser.parse_args(argv)

    if args.serie_real:
        destino = DESTINO / args.escuela
        registro = copiar_real(args.serie_real, destino, args.z_celda, args.peticion)
        if args.punto_pedido:
            registro["punto_pedido"] = {"lat": args.punto_pedido[0],
                                        "lon": args.punto_pedido[1]}
        else:
            registro["punto_pedido"] = dict(registro["punto_rejilla"])
        with open(destino / "registro.json", "w", encoding="utf-8") as f:
            json.dump(registro, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"AVISO, DATOS FICTICIOS: {registro['nota_ficticio']}")
        print(f"serie copiada en {registro['archivos'][0]['ruta']}")
        return 0
    if args.lat is None or args.lon is None:
        parser.error("--fuente necesita --lat y --lon")

    # data/processed es derivado: con la misma semilla y las mismas fuentes sale lo mismo.
    destino = DESTINO / args.escuela
    fuentes = [read_series(p) for p in args.fuente]
    tabla, elegidos = fabricar(fuentes, args.lat, args.lon, args.semilla)
    destino.mkdir(parents=True, exist_ok=True)
    serie = destino / "serie.zip"
    tabla.to_csv(serie, index=False, date_format="%Y-%m-%d %H:%M:%S",
                 compression={"method": "zip", "archive_name": "serie.csv"})
    geo = destino / "geopotencial.nc"
    escribir_geopotencial(geo, args.lat, args.lon, args.z_celda)

    n_anios = len({(e["fuente"], e["anio_fuente"]) for e in elegidos})
    nota = (f"Serie de ERA5 ficticia: cada año de 1940 a 2025 copia uno de {n_anios} años "
            f"reales de ERA5, elegido con la semilla {args.semilla}, con una anomalía "
            f"aleatoria y sin tendencia; z_celda ficticia ({args.z_celda:g} m). "
            "Decisión del equipo del 2026-11-28 (#61): se sustituye por la descarga real.")
    registro = {
        "ficticio": True,
        "nota_ficticio": nota,
        "creado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": _commit(),
        "licencia": "CC-BY-4.0",
        "semilla": args.semilla,
        "periodo": {"inicio": "1940-01-01", "fin": "2026-01-01"},
        "punto_pedido": {"lat": args.lat, "lon": args.lon},
        "punto_rejilla": {"lat": args.lat, "lon": args.lon},
        "fuentes": [{"ruta": _relative(p), "sha256": _sha256(p)} for p in args.fuente],
        "anios": elegidos,
        "archivos": [
            {"ruta": _relative(serie), "dataset": SERIES_DATASET, "sha256": _sha256(serie),
             "origen": "ficticio: años reales de ERA5 recombinados"},
            {"ruta": _relative(geo), "dataset": LEVELS_DATASET, "sha256": _sha256(geo),
             "origen": f"ficticio: z = {args.z_celda:g} m · G0 en las 9 celdas"},
        ],
    }
    with open(destino / "registro.json", "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"AVISO, DATOS FICTICIOS: {nota}")
    print(f"{len(tabla)} filas en {_relative(serie)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
