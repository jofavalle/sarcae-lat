"""Descarga y lectura de la temperatura horaria de una estación de GHCNh.

Descarga de NOAA NCEI los archivos anuales PSV de una estación de GHCNh v1 y los guarda tal
como llegan en `data/raw/ghcnh/<estación>/`, junto con un `registro.json`. `data/raw/` es
inmutable: si el destino ya existe, no se toca. GHCNh se baja sin cuenta.

Las series de El Dorado (`COI0000SKBO`) y La Chinita (`VEI0000SVMC`) no se versionan (#46): el
inventario sub-diario v3.0.0 de C3S y NCEI las marca como `non_commercial`. En el repositorio
entran este script y la métrica.

Por defecto se bajan 2024, 2025 y 2026. El de 2026 hace falta por las primeras horas UTC del
1 de enero, que completan el 31 de diciembre local. El archivo del año en curso sigue
creciendo, así que su SHA-256 cambia de un día a otro, y el registro lo dice.

Uso, desde la raíz del repositorio:

    python -m src.ghcnh --estacion COI0000SKBO --estacion VEI0000SVMC
    python -m src.ghcnh --comprobar data/raw/ghcnh/COI0000SKBO
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "ghcnh"

URL = ("https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access/"
       "by-year/{year}/psv/GHCNh_{station}_{year}.psv")
STATIONS = ("COI0000SKBO", "VEI0000SVMC")
YEARS = (2024, 2025, 2026)
USER_AGENT = "sarcae-lat/ghcnh"
LICENSE = ("CC0 según la ficha del conjunto; el inventario sub-diario v3.0.0 de C3S y NCEI "
           "marca la estación como non_commercial: la serie no se versiona (#46)")
CITATION_AUTHORS = ("Menne, Matthew J.; Noone, Simon; Casey, Nancy W.; Dunn, Robert H.; "
                    "McNeill, Shelley; Kantor, Diana; Thorne, Peter W.; Orcutt, Karen; "
                    "Cunningham, Sam; Risavi, Nicholas. 2023. Global Historical Climatology "
                    "Network-Hourly (GHCNh).")
CITATION_PUBLISHER = ("NOAA National Centers for Environmental Information. "
                      "https://doi.org/10.25921/jp3d-3v19")
CITATION = f"{CITATION_AUTHORS} {CITATION_PUBLISHER}"
GROWING_NOTE = ("el archivo del año en curso sigue creciendo: su SHA-256 cambia de un día a "
                "otro")

# Columnas que se leen del PSV, y su nombre interno.
COLUMNS = {
    "DATE": "time",
    "temperature": "temperature",
    "temperature_Quality_Code": "quality",
    "temperature_Source_Code": "source",
}
GOOD = "1"  # «Good» para la fuente 223 (documentación de GHCNh, sección VI, tabla 3)


# Utilidades de registro

def _relative(path: Path) -> str:
    """Ruta relativa a la raíz: una absoluta publicaría el directorio personal."""
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


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


def ensure_new(final: Path) -> None:
    """Sale con un mensaje si el destino ya existe: data/raw es inmutable."""
    if final.exists():
        sys.exit(f"{_relative(final)} ya existe, y data/raw es inmutable: no se toca.")


def citation(subset: str, accessed: str) -> str:
    """La cita de NCEI (README, "Atribución") con el subconjunto y la fecha de acceso."""
    return f"{CITATION_AUTHORS} {subset}. {CITATION_PUBLISHER}. Consultado el {accessed}."


def file_name(station: str, year: int) -> str:
    return f"GHCNh_{station}_{year}.psv"


# Descarga

def fetch(url: str, target: Path) -> None:
    """Baja una URL a un archivo. Se aísla para que las pruebas no usen la red."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response, \
            open(target, "wb") as handle:
        while block := response.read(1 << 20):
            handle.write(block)


def download(station: str, years=YEARS) -> Path:
    """Baja los años de una estación a una carpeta temporal y la renombra al final.

    Si algo falla a mitad, el destino no llega a existir: queda una carpeta
    `.parcial-<estación>-*` junto a él, que se revisa y se borra a mano.
    """
    final = RAW / station
    ensure_new(final)
    RAW.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f".parcial-{station}-", dir=RAW))
    started = datetime.now(timezone.utc)

    files = []
    for year in years:
        url = URL.format(station=station, year=year)
        path = work / file_name(station, year)
        clock = time.monotonic()
        fetch(url, path)
        seconds = time.monotonic() - clock
        entry = {
            "ruta": _relative(final / path.name),
            "url": url,
            "anio": year,
            "segundos": round(seconds, 1),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        if year >= started.year:
            entry["nota"] = GROWING_NOTE
        files.append(entry)
        print(f"{path.name}: {entry['bytes']} bytes en {seconds:.0f} s", flush=True)

    record = {
        "descargado_utc": started.isoformat(timespec="seconds"),
        "commit": _commit(),
        "estacion": station,
        "fuente": "NOAA NCEI, GHCNh v1, archivos anuales PSV",
        "cita": CITATION,
        "licencia": LICENSE,
        "archivos": files,
    }
    with open(work / "registro.json", "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    work.rename(final)
    print(f"guardado en {_relative(final)}")
    return final


# Lectura

def read_psv(path: Path) -> pd.DataFrame:
    """Temperatura de un PSV anual: hora UTC, °C, código de calidad y fuente.

    Los códigos se leen como texto, y el vacío queda como cadena vacía: un código vacío no es
    un `1`, y no se confunde con él al convertir.
    """
    frame = pd.read_csv(path, sep="|", usecols=list(COLUMNS), dtype=str,
                        keep_default_na=False)
    frame = frame.rename(columns=COLUMNS)[list(COLUMNS.values())]
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame["temperature"] = pd.to_numeric(frame["temperature"].str.strip(), errors="coerce")
    frame["quality"] = frame["quality"].str.strip()
    frame["source"] = frame["source"].str.strip()
    return frame


def read_station(directory: Path) -> pd.DataFrame:
    """Todos los años de una descarga, en el orden del registro, por hora."""
    with open(Path(directory) / "registro.json", encoding="utf-8") as handle:
        record = json.load(handle)
    frames = [read_psv(Path(directory) / Path(f["ruta"]).name) for f in record["archivos"]]
    return pd.concat(frames, ignore_index=True).sort_values("time", ignore_index=True)


def filter_quality(frame: pd.DataFrame) -> tuple:
    """Filas con temperatura y código `1`, y cuántas se descartaron y por qué.

    Elección conservadora: el código vacío también se descarta (en El Dorado son filas de la
    fuente 999, sin control propio), igual que `2` («Suspect») y `4` («Calculated»).
    """
    no_value = frame["temperature"].isna()
    empty_code = ~no_value & (frame["quality"] == "")
    other_code = ~no_value & ~empty_code & (frame["quality"] != GOOD)
    kept = frame[~(no_value | empty_code | other_code)].reset_index(drop=True)
    discarded = {
        "sin_temperatura": int(no_value.sum()),
        "codigo_vacio": int(empty_code.sum()),
        "otro_codigo": int(other_code.sum()),
    }
    return kept, discarded


# Comprobación

def check(directory: Path) -> int:
    """Compara los SHA-256 con el registro y resume la calidad por año. Devuelve 0 o 1."""
    directory = Path(directory)
    with open(directory / "registro.json", encoding="utf-8") as handle:
        record = json.load(handle)
    print(f"estación: {record['estacion']}, descargada {record['descargado_utc']}")
    failed = []
    for entry in record["archivos"]:
        path = directory / Path(entry["ruta"]).name
        same = path.exists() and _sha256(path) == entry["sha256"]
        if not same:
            failed.append(path.name)
        frame = read_psv(path) if path.exists() else None
        if frame is None:
            print(f"[FALLA] {path.name}: no existe")
            continue
        kept, discarded = filter_quality(frame)
        print(f"[{'OK' if same else 'FALLA'}] {path.name}: sha256 {entry['sha256'][:12]}…, "
              f"{len(frame)} filas, {len(kept)} con código 1; descartadas: "
              f"{discarded['sin_temperatura']} sin temperatura, "
              f"{discarded['codigo_vacio']} con código vacío, "
              f"{discarded['otro_codigo']} con otro código")
    print("comprobación en orden" if not failed else
          f"comprobación con {len(failed)} fallos: {', '.join(failed)}")
    return 0 if not failed else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--comprobar", type=Path, metavar="CARPETA",
                        help="comprueba una descarga ya hecha")
    parser.add_argument("--estacion", action="append", metavar="ID",
                        help=f"identificador de GHCNh; se repite (por defecto "
                             f"{' y '.join(STATIONS)})")
    parser.add_argument("--anios", type=int, nargs="+", default=list(YEARS), metavar="AAAA",
                        help=f"años que se bajan (por defecto {' '.join(map(str, YEARS))})")
    args = parser.parse_args(argv)

    if args.comprobar is not None:
        return check(args.comprobar)
    for station in args.estacion or STATIONS:
        download(station, args.anios)
    return 0


if __name__ == "__main__":
    sys.exit(main())
