"""Teselas de relieve en terrarium a partir de NASADEM, para cualquier escuela.

Recorta la malla de NASADEM alrededor de un punto y escribe las teselas XYZ en PNG que pide
ADR-001 para el terreno 3D y el sombreado de MapLibre: Web Mercator (EPSG:3857), 256 px y
codificación terrarium, `h = R·256 + G + B/256 - 32768`. Al terminar, cuenta cuántas teselas
salen y cuánto pesan.

Las teselas salen siempre del recorte: la malla de NASADEM que cubre el lado pedido, con dos
celdas de margen para la interpolación. Fuera del recorte, la tesela repite el valor del
borde; el mapa no deja salir de `bounds` (`maxBounds`), así que nadie ve ese relleno. Con
`--escuela`, el recorte se versiona en `recortes/<slug>/nasadem/elevacion.csv`, y
`--desde-recorte` regenera desde él las mismas teselas, byte a byte, sin cuenta de Earthdata.

Uso, desde la raíz del repositorio:

    python -m src.relieve --descargar --escuela sv-88118
    python -m src.relieve --escuela sv-88118 --precision-m 0.25 --altura-esperada 150-600
    python -m src.relieve --escuela sv-88118 --desde-recorte
    python -m src.relieve --comprobar web/datos/sv-88118/relieve

Con `--escuela`, la posición sale de `web/datos/escuelas.json`, la salida va a
`web/datos/<slug>/relieve/`, la precisión es de 0,25 m y el rango de `--altura-esperada` es el
de `ALTURA_ESPERADA_M`, si no se dan. Lo de antes sigue igual:

    python -m src.relieve --descargar
    python -m src.relieve --zip data/raw/nasadem/NASADEM_HGT_n13w090.zip \\
        --lat 13.70 --lon -89.12 --lado-km 4 --zoom 10-14 \\
        --salida data/processed/relieve/prueba-ilopango

La descarga pide una cuenta gratuita de NASA Earthdata, con las credenciales en `~/.netrc`
y nunca en el repositorio. `data/raw/` es inmutable: si el zip ya existe, no se toca.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "nasadem"
WEB_DATOS = ROOT / "web" / "datos"
ESCUELAS = WEB_DATOS / "escuelas.json"
RECORTES = ROOT / "recortes"
CROP_CSV = "elevacion.csv"

PREFIX = "NASADEM_HGT_"
GRANULE = "NASADEM_HGT_n13w090"
GRANULE_URL = ("https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/"
               f"NASADEM_HGT.001/{GRANULE}/{GRANULE}.zip")
LICENSE = "CC0-1.0"
LICENSE_URL = ("https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/"
               "data-use-guidance")
SOURCE = {"nombre": "NASADEM_HGT", "version": "001", "licencia": LICENSE,
          "url": "https://www.earthdata.nasa.gov/data/catalog/lpcloud-nasadem-hgt-001"}
# La de README.md, «Atribución».
ATTRIBUTION = ("NASA JPL. NASADEM Merged DEM Global 1 arc second V001. 2020, distributed by "
               "NASA EOSDIS Land Processes Distributed Active Archive Center, "
               "https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001")
CONTRACT = 1  # la versión de docs/contrato-datos.md

# Con --escuela, si no se dan --precision-m ni --altura-esperada (#60).
DEFAULT_PRECISION_M = 0.25
ALTURA_ESPERADA_M = {
    # Santa Ana/El Palmar está a 660 m, unos 350 m por encima (docs/PLAN.md, sección 5).
    "sv-88118": (150.0, 600.0),
    "co-nicolas-esguerra": (2500.0, 2700.0),
    "ve-rafael-maria-baralt": (0.0, 100.0),
}
MAX_SCHOOL_BYTES = 1_000_000  # con gzip -9, medido con src.presupuesto

# El .hgt: 3601 × 3601 enteros de 16 bits big-endian, un segundo de arco de paso, filas de
# norte a sur. El primer píxel está en la esquina noroeste de la celda.
HGT_SIDE = 3601
HGT_BYTES = HGT_SIDE * HGT_SIDE * 2  # 25 934 402
HGT_STEP = 1.0 / 3600.0
CELLS = 3600       # celdas por grado
MARGIN_CELLS = 2   # el margen del recorte, para la interpolación
VOID = -32768

TILE = 256
EARTH_RADIUS_KM = 6371.0088  # radio medio, para pasar el lado del recorte a grados
MERCATOR_MAX_LAT = 85.0511287798
MANIFEST = "relieve.json"

# Controles de --comprobar.
POINT_TOLERANCE_M = 5.0
POINT_RANGE_M = (550.0, 700.0)


# Lectura del granulo

class Grid:
    """Malla geográfica: `values[i, j]` está en (top - i·step, left + j·step)."""

    def __init__(self, values: np.ndarray, top: float, left: float, step: float):
        self.values = values
        self.top = top
        self.left = left
        self.step = step

    @property
    def bottom(self) -> float:
        return self.top - (self.values.shape[0] - 1) * self.step

    @property
    def right(self) -> float:
        return self.left + (self.values.shape[1] - 1) * self.step

    def fractional_index(self, lat, lon):
        """Fila y columna fraccionarias de un punto (o de matrices de puntos)."""
        return (self.top - np.asarray(lat)) / self.step, (np.asarray(lon) - self.left) / self.step


def cell_corner(name: str) -> tuple:
    """Esquina suroeste de la celda que nombra un granulo: `n13w090` da (13, -90)."""
    match = re.search(r"([ns])(\d{2})([ew])(\d{3})", name.lower())
    if not match:
        raise ValueError(f"{name}: no se reconoce la celda del granulo")
    lat = int(match.group(2)) * (1 if match.group(1) == "n" else -1)
    lon = int(match.group(4)) * (1 if match.group(3) == "e" else -1)
    return lat, lon


def hgt_member(archive: zipfile.ZipFile) -> zipfile.ZipInfo:
    members = [info for info in archive.infolist() if info.filename.lower().endswith(".hgt")]
    if len(members) != 1:
        raise ValueError(f"se esperaba un solo .hgt en el zip, y hay {len(members)}")
    return members[0]


def read_hgt(path: Path) -> Grid:
    """Lee el .hgt del zip. Sale con un error si no mide lo que tiene que medir."""
    with zipfile.ZipFile(path) as archive:
        member = hgt_member(archive)
        data = archive.read(member)
    if len(data) != HGT_BYTES:
        sys.exit(f"{member.filename} mide {len(data)} bytes, y un .hgt de un segundo de arco "
                 f"mide {HGT_BYTES}: no se lee.")
    south, west = cell_corner(member.filename)
    values = np.frombuffer(data, dtype=">i2").reshape(HGT_SIDE, HGT_SIDE)
    return Grid(values, top=south + 1.0, left=float(west), step=HGT_STEP)


def read_hgt_pixel(path: Path, row: int, col: int) -> int:
    """Un píxel del .hgt leído directamente, sin numpy ni proyección: para el control."""
    with zipfile.ZipFile(path) as archive:
        data = archive.read(hgt_member(archive))
    return struct.unpack_from(">h", data, (row * HGT_SIDE + col) * 2)[0]


# El recorte

def crop_bounds(lat: float, lon: float, side_km: float) -> dict:
    """Cuadrado de `side_km` de lado centrado en el punto, en grados (esfera de radio medio)."""
    half_lat = math.degrees(side_km / 2.0 / EARTH_RADIUS_KM)
    half_lon = half_lat / math.cos(math.radians(lat))
    return {"sur": lat - half_lat, "norte": lat + half_lat,
            "oeste": lon - half_lon, "este": lon + half_lon}


def granule_name(lat: float, lon: float) -> str:
    """El granulo de un punto: `NASADEM_HGT_` + n/s y dos cifras de la latitud redondeada
    hacia abajo, más e/w y tres cifras de la longitud redondeada hacia abajo."""
    south, west = math.floor(lat), math.floor(lon)
    return (f"{PREFIX}{'n' if south >= 0 else 's'}{abs(south):02d}"
            f"{'e' if west >= 0 else 'w'}{abs(west):03d}")


def short_name(granule: str) -> str:
    """`NASADEM_HGT_n13w090` da `n13w090`, como lo escribe relieve.json."""
    return granule[len(PREFIX):] if granule.startswith(PREFIX) else granule


def crop_cells(bounds: dict, cells: int = CELLS, margin: int = MARGIN_CELLS) -> dict:
    """El recorte en índices enteros de la malla (lat · cells, lon · cells): los nodos que
    cubren el cuadrado pedido, más `margin` celdas por cada lado."""
    return {"sur": math.floor(bounds["sur"] * cells) - margin,
            "norte": math.ceil(bounds["norte"] * cells) + margin,
            "oeste": math.floor(bounds["oeste"] * cells) - margin,
            "este": math.ceil(bounds["este"] * cells) + margin}


def granules_for(window: dict, cells: int = CELLS) -> list:
    """Los granulos que hacen falta para un recorte; dos o más si cruza un borde. Un nodo en
    el borde está en los dos granulos, así que basta con uno de ellos."""
    lats = range(window["sur"] // cells, -(-window["norte"] // cells))
    lons = range(window["oeste"] // cells, -(-window["este"] // cells))
    return sorted(granule_name(south + 0.5, west + 0.5) for south in lats for west in lons)


def mosaic(grids: list, window: dict, cells: int = CELLS) -> Grid:
    """El recorte, unido desde uno o más granulos. ValueError si alguno falta."""
    rows = window["norte"] - window["sur"] + 1
    cols = window["este"] - window["oeste"] + 1
    values = np.zeros((rows, cols), dtype="int16")
    filled = np.zeros((rows, cols), dtype=bool)
    for grid in grids:
        top, left = round(grid.top * cells), round(grid.left * cells)
        bottom, right = top - (grid.values.shape[0] - 1), left + grid.values.shape[1] - 1
        north, south = min(window["norte"], top), max(window["sur"], bottom)
        west, east = max(window["oeste"], left), min(window["este"], right)
        if north < south or east < west:
            continue
        target = (slice(window["norte"] - north, window["norte"] - south + 1),
                  slice(west - window["oeste"], east - window["oeste"] + 1))
        values[target] = grid.values[top - north:top - south + 1, west - left:east - left + 1]
        filled[target] = True
    if not filled.all():
        raise ValueError(f"faltan {int(np.count_nonzero(~filled))} nodos del recorte: hace "
                         "falta otro granulo")
    return Grid(values, window["norte"] / cells, window["oeste"] / cells, 1.0 / cells)


def grid_window(grid: Grid, cells: int = CELLS) -> dict:
    """Los índices enteros de una malla: lo inverso de `mosaic`."""
    top, left = round(grid.top * cells), round(grid.left * cells)
    return {"sur": top - (grid.values.shape[0] - 1), "norte": top,
            "oeste": left, "este": left + grid.values.shape[1] - 1}


def window_bounds(window: dict, cells: int = CELLS) -> dict:
    return {k: v / cells for k, v in window.items()}


def crop_to_csv(grid: Grid, cells: int = CELLS) -> str:
    """El recorte como CSV: `lat`, `lon` y `altura_m`, en metros enteros como en el .hgt,
    de norte a sur y de oeste a este. Siete decimales bastan para volver al nodo."""
    window = grid_window(grid, cells)
    lons = [f"{(window['oeste'] + c) / cells:.7f}" for c in range(grid.values.shape[1])]
    out = io.StringIO()
    out.write("lat,lon,altura_m\n")
    for r, row in enumerate(grid.values.tolist()):
        lat = f"{(window['norte'] - r) / cells:.7f}"
        out.writelines(f"{lat},{lon},{v}\n" for lon, v in zip(lons, row))
    return out.getvalue()


def grid_from_csv(text: str, cells: int = CELLS) -> Grid:
    """La malla de un CSV de `crop_to_csv`. ValueError si no es una malla completa."""
    reader = csv.reader(io.StringIO(text))
    if next(reader, None) != ["lat", "lon", "altura_m"]:
        raise ValueError("el recorte no empieza por lat,lon,altura_m")
    nodes = {}
    for line, row in enumerate(reader, start=2):
        try:
            key = (round(float(row[0]) * cells), round(float(row[1]) * cells))
            value = int(row[2])
        except (ValueError, IndexError):
            raise ValueError(f"línea {line} del recorte: {row!r} no es lat,lon,altura_m")
        if key in nodes:
            raise ValueError(f"línea {line} del recorte: el nodo se repite")
        if not -32768 <= value <= 32767:
            raise ValueError(f"línea {line} del recorte: {value} no cabe en 16 bits")
        nodes[key] = value
    if not nodes:
        raise ValueError("el recorte no tiene filas")
    lats = sorted({i for i, _ in nodes}, reverse=True)
    lons = sorted({j for _, j in nodes})
    if len(nodes) != len(lats) * len(lons) or lats[0] - lats[-1] + 1 != len(lats) \
            or lons[-1] - lons[0] + 1 != len(lons):
        raise ValueError("el recorte no es una malla rectangular completa")
    values = np.array([[nodes[(i, j)] for j in lons] for i in lats], dtype="int16")
    return Grid(values, lats[0] / cells, lons[0] / cells, 1.0 / cells)


def inward_bounds(bounds: dict) -> list:
    """`[oeste, sur, este, norte]` con 6 decimales, redondeados hacia dentro: `maxBounds`
    no deja ver nada fuera del recorte."""
    return [math.ceil(bounds["oeste"] * 1e6 - 1e-6) / 1e6,
            math.ceil(bounds["sur"] * 1e6 - 1e-6) / 1e6,
            math.floor(bounds["este"] * 1e6 + 1e-6) / 1e6,
            math.floor(bounds["norte"] * 1e6 + 1e-6) / 1e6]


# Web Mercator y teselas XYZ

def lonlat_to_tile(lon, lat, zoom: int):
    """Coordenadas de tesela fraccionarias; la parte entera es la tesela."""
    n = 2.0 ** zoom
    lat = np.clip(np.asarray(lat, dtype="float64"), -MERCATOR_MAX_LAT, MERCATOR_MAX_LAT)
    x = (np.asarray(lon, dtype="float64") + 180.0) / 360.0 * n
    y = (1.0 - np.arcsinh(np.tan(np.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def tile_to_lonlat(x, y, zoom: int):
    """Inversa de `lonlat_to_tile`, para coordenadas de tesela fraccionarias."""
    n = 2.0 ** zoom
    lon = np.asarray(x, dtype="float64") / n * 360.0 - 180.0
    lat = np.degrees(np.arctan(np.sinh(math.pi * (1.0 - 2.0 * np.asarray(y, dtype="float64") / n))))
    return lon, lat


def tile_of(lon: float, lat: float, zoom: int) -> tuple:
    x, y = lonlat_to_tile(lon, lat, zoom)
    return int(math.floor(x)), int(math.floor(y))


def tiles_for(bounds: dict, zoom: int) -> list:
    """Las teselas de un zoom que tocan el recorte, como (x, y)."""
    x0, y0 = lonlat_to_tile(bounds["oeste"], bounds["norte"], zoom)
    x1, y1 = lonlat_to_tile(bounds["este"], bounds["sur"], zoom)
    # Una tesela que solo comparte un borde con el recorte no lo toca.
    xs = range(int(math.floor(x0)), max(int(math.floor(x0)), int(math.ceil(x1)) - 1) + 1)
    ys = range(int(math.floor(y0)), max(int(math.floor(y0)), int(math.ceil(y1)) - 1) + 1)
    return [(x, y) for x in xs for y in ys]


def pixel_centers(zoom: int, x: int, y: int) -> tuple:
    """Longitud y latitud del centro de cada píxel de una tesela, en matrices 256 × 256."""
    offsets = np.arange(TILE, dtype="float64") + 0.5
    gx, gy = np.meshgrid(x + offsets / TILE, y + offsets / TILE)
    return tile_to_lonlat(gx, gy, zoom)


# Remuestreo

def bilinear(grid: Grid, lat, lon) -> tuple:
    """Elevación bilineal en cada punto, y cuántos puntos caen fuera de la malla.

    Un punto fuera de la malla toma el valor del borde más cercano. Los vacíos se descartan
    antes de llegar aquí: `render_tile` se para si los encuentra.
    """
    row, col = grid.fractional_index(lat, lon)
    rows, cols = grid.values.shape
    outside = int(np.count_nonzero((row < 0) | (row > rows - 1) | (col < 0) | (col > cols - 1)))
    row = np.clip(row, 0.0, rows - 1.0)
    col = np.clip(col, 0.0, cols - 1.0)
    r0 = np.minimum(np.floor(row).astype("int64"), rows - 2)
    c0 = np.minimum(np.floor(col).astype("int64"), cols - 2)
    fr = row - r0
    fc = col - c0
    v = grid.values
    top = v[r0, c0] * (1.0 - fc) + v[r0, c0 + 1] * fc
    bottom = v[r0 + 1, c0] * (1.0 - fc) + v[r0 + 1, c0 + 1] * fc
    return top * (1.0 - fr) + bottom * fr, outside


def voids_under(grid: Grid, lat, lon) -> int:
    """Cuántos píxeles vacíos entran en el remuestreo de estos puntos."""
    row, col = grid.fractional_index(lat, lon)
    rows, cols = grid.values.shape
    r0 = int(np.clip(np.floor(row.min()), 0, rows - 1))
    r1 = int(np.clip(np.ceil(row.max()), 0, rows - 1))
    c0 = int(np.clip(np.floor(col.min()), 0, cols - 1))
    c1 = int(np.clip(np.ceil(col.max()), 0, cols - 1))
    return int(np.count_nonzero(grid.values[r0:r1 + 1, c0:c1 + 1] == VOID))


def render_tile(grid: Grid, zoom: int, x: int, y: int) -> tuple:
    """Elevaciones de una tesela (256 × 256, en m) y cuántos píxeles caen fuera de la malla."""
    lon, lat = pixel_centers(zoom, x, y)
    return bilinear(grid, lat, lon)


def quantize(height, precision_m):
    """Las alturas redondeadas a múltiplos de `precision_m` antes de codificarlas (#11: a
    0,25 m, el canal B de terrarium solo toma 0, 64, 128 y 192, y se comprime). Sin
    precisión, se devuelven como están."""
    if precision_m is None:
        return height
    return np.round(np.asarray(height, dtype="float64") / precision_m) * precision_m


# Terrarium

def terrarium_encode(height: np.ndarray) -> np.ndarray:
    """Elevación en m a RGB de 8 bits: `h = R·256 + G + B/256 - 32768`."""
    value = np.clip(np.asarray(height, dtype="float64") + 32768.0, 0.0, 65536.0 - 1.0 / 256.0)
    red = np.floor(value / 256.0)
    green = np.floor(value - red * 256.0)
    blue = np.floor((value - red * 256.0 - green) * 256.0)
    return np.stack([red, green, blue], axis=-1).astype("uint8")


def terrarium_decode(rgb: np.ndarray) -> np.ndarray:
    rgb = np.asarray(rgb, dtype="float64")
    return rgb[..., 0] * 256.0 + rgb[..., 1] + rgb[..., 2] / 256.0 - 32768.0


# PNG con la biblioteca estándar

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib_crc(kind + payload)))


def zlib_crc(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def _filtered_rows(rgb: np.ndarray) -> bytes:
    """Cada fila con el filtro que deja la suma de valores absolutos más pequeña.

    Es la heurística que recomienda la especificación de PNG. Se prueban los filtros None,
    Sub y Up, que bastan para un relieve suave y se deshacen con una resta.
    """
    rows = rgb.reshape(rgb.shape[0], -1).astype("int16")
    none = rows
    sub = rows.copy()
    sub[:, 3:] = rows[:, 3:] - rows[:, :-3]
    up = rows.copy()
    up[1:] = rows[1:] - rows[:-1]
    candidates = np.stack([none, sub, up]) & 0xFF
    signed = np.where(candidates > 127, 256 - candidates, candidates)
    choice = signed.sum(axis=2).argmin(axis=0)
    out = bytearray()
    for index, kind in enumerate(choice):
        out.append(int(kind))
        out += candidates[kind, index].astype("uint8").tobytes()
    return bytes(out)


def write_png(path: Path, rgb: np.ndarray) -> int:
    """Escribe un PNG RGB de 8 bits, sin pérdida. Devuelve los bytes escritos."""
    height, width, channels = rgb.shape
    if channels != 3 or rgb.dtype != np.uint8:
        raise ValueError("se espera una matriz alto × ancho × 3 de uint8")
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    data = (PNG_SIGNATURE + _chunk(b"IHDR", header)
            + _chunk(b"IDAT", zlib.compress(_filtered_rows(rgb), 9)) + _chunk(b"IEND", b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return len(data)


def read_png(path: Path) -> np.ndarray:
    """Lee un PNG RGB de 8 bits como los que escribe `write_png` (filtros 0, 1 y 2)."""
    data = Path(path).read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(f"{path}: no es un PNG")
    offset, idat, header = len(PNG_SIGNATURE), b"", None
    while offset < len(data):
        length, kind = struct.unpack_from(">I4s", data, offset)
        payload = data[offset + 8:offset + 8 + length]
        if struct.unpack_from(">I", data, offset + 8 + length)[0] != zlib_crc(kind + payload):
            raise ValueError(f"{path}: CRC incorrecto en {kind!r}")
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            idat += payload
        offset += 12 + length
    width, height, depth, color = header[:4]
    if (depth, color) != (8, 2):
        raise ValueError(f"{path}: se espera RGB de 8 bits")
    raw = np.frombuffer(zlib.decompress(idat), dtype="uint8").reshape(height, 1 + width * 3)
    out = np.zeros((height, width * 3), dtype="uint8")
    for index in range(height):
        kind, line = raw[index, 0], raw[index, 1:].astype("int16")
        if kind == 1:
            line = (line.reshape(width, 3).cumsum(axis=0) & 0xFF).reshape(-1)
        elif kind == 2 and index > 0:
            line = (line + out[index - 1]) & 0xFF
        elif kind not in (0, 2):
            raise ValueError(f"{path}: filtro {kind} no admitido")
        out[index] = line
    return out.reshape(height, width, 3)


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


def _kb(size: int) -> str:
    return f"{size / 1000:.1f} KB"


# Descarga

def granule_url(granule: str) -> str:
    return ("https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/"
            f"NASADEM_HGT.001/{granule}/{granule}.zip")


def record_path(granule: str, raw: Path = RAW) -> Path:
    """El registro de un granulo. El de n13w090, el primero que se bajó, se llama
    `registro.json`; los demás, `<GRANULO>.registro.json`."""
    return raw / ("registro.json" if granule == GRANULE else f"{granule}.registro.json")


def download(granule: str = GRANULE) -> Path:
    """Descarga el granulo con curl y escribe su registro al lado.

    Se descarga a una carpeta temporal y se mueve al final: si algo falla a mitad, el
    destino no llega a existir.
    """
    final = RAW / f"{granule}.zip"
    record = record_path(granule)
    url = granule_url(granule)
    for path in (final, record):
        if path.exists():
            sys.exit(f"{_relative(path)} ya existe, y data/raw es inmutable: no se toca.")
    RAW.mkdir(parents=True, exist_ok=True)
    started_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with tempfile.TemporaryDirectory(prefix="nasadem-") as work:
        work = Path(work)
        landing = work / final.name
        cookies = work / "cookies"
        result = subprocess.run(["curl", "-n", "-L", "-f", "-c", str(cookies), "-b", str(cookies),
                                 "-o", str(landing), url])
        if result.returncode != 0 or not zipfile.is_zipfile(landing):
            sys.exit("la descarga no trajo un zip: revisa la cuenta de Earthdata en ~/.netrc "
                     "y que la aplicación LP DAAC esté autorizada en ella.")
        with zipfile.ZipFile(landing) as archive:
            member = hgt_member(archive)
        data = {
            "url": url,
            "granulo": granule,
            "descargado_utc": started_utc,
            "commit": _commit(),
            "licencia": LICENSE,
            "licencia_url": LICENSE_URL,
            "archivo": _relative(final),
            "bytes": landing.stat().st_size,
            "sha256": _sha256(landing),
            "hgt": {"nombre": member.filename, "bytes": member.file_size},
        }
        shutil.move(str(landing), final)
    with open(record, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"guardado en {_relative(final)} ({_kb(data['bytes'])}), con {_relative(record)}")
    return final


def download_school(slug: str, side_km: float, escuelas: Path = ESCUELAS) -> int:
    """Baja los granulos que pide el recorte de una escuela y no estén ya en data/raw."""
    lat, lon = school_point(slug, escuelas)
    for granule in granules_for(crop_cells(crop_bounds(lat, lon, side_km))):
        final, record = RAW / f"{granule}.zip", record_path(granule)
        if final.exists() and record.exists():
            print(f"{_relative(final)} ya está, con {_relative(record)}: no se toca")
        elif final.exists() or record.exists():
            sys.exit(f"de {granule} está el zip o su registro, pero no los dos. data/raw es "
                     "inmutable: lo resuelve una persona.")
        else:
            download(granule)
    return 0


# Generación de las teselas

def parse_zooms(text: str) -> list:
    low, _, high = text.partition("-")
    low, high = int(low), int(high or low)
    if not 0 <= low <= high <= 22:
        raise argparse.ArgumentTypeError(f"zoom {text}: se espera 'mín-máx', entre 0 y 22")
    return list(range(low, high + 1))


def parse_range(text: str) -> tuple:
    match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*", text)
    if not match or float(match.group(1)) > float(match.group(2)):
        raise argparse.ArgumentTypeError(f"{text}: se espera 'MIN-MAX' en metros, como 150-600")
    return float(match.group(1)), float(match.group(2))


def parse_precision(text: str) -> float:
    value = float(text)
    if not 0 < value <= 100:
        raise argparse.ArgumentTypeError(f"{text}: la precisión va de 0 a 100 m")
    return value


def school_point(slug: str, escuelas: Path = ESCUELAS) -> tuple:
    """Latitud y longitud de una escuela de escuelas.json."""
    with open(escuelas, encoding="utf-8") as handle:
        data = json.load(handle)
    by_slug = {e.get("slug"): e for e in data.get("escuelas", [])}
    if slug not in by_slug:
        sys.exit(f"{slug} no está en {escuelas.name}: son {', '.join(sorted(by_slug))}")
    return float(by_slug[slug]["lat"]), float(by_slug[slug]["lon"])


def _empty_output(out: Path):
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} ya tiene archivos: elige otra --salida o vacíala a mano, para no "
                 "mezclar teselas de dos ejecuciones.")


def _no_voids(grid: Grid):
    voids = int(np.count_nonzero(grid.values == VOID))
    if voids:
        sys.exit(f"el recorte tiene {voids} píxeles vacíos (-32768). Cómo rellenarlos se "
                 "decide en la issue: no se generan teselas.")


def render(grid: Grid, zooms: list, precision_m, out: Path) -> tuple:
    """Las teselas que cubren el recorte, desde el recorte: (nombres, bytes, píxeles fuera
    del recorte por zoom). Fuera del recorte, el bilineal repite el borde."""
    extent = window_bounds(grid_window(grid))
    names, total_bytes, outside_by_zoom = [], 0, {}
    for zoom in zooms:
        outside_by_zoom[zoom] = 0
        for x, y in tiles_for(extent, zoom):
            height, outside = render_tile(grid, zoom, x, y)
            outside_by_zoom[zoom] += outside
            total_bytes += write_png(out / str(zoom) / str(x) / f"{y}.png",
                                     terrarium_encode(quantize(height, precision_m)))
            names.append(f"{zoom}/{x}/{y}.png")
    return names, total_bytes, outside_by_zoom


def _finish(grid: Grid, *, lat, lon, side_km, zooms, precision_m, expected, out, escuela,
            granules, comando, extra=None) -> int:
    """Escribe las teselas y relieve.json, e imprime el resumen."""
    out.mkdir(parents=True, exist_ok=True)
    names, total_bytes, outside_by_zoom = render(grid, zooms, precision_m, out)
    extent = window_bounds(grid_window(grid))
    point_height = float(bilinear(grid, np.array([lat]), np.array([lon]))[0][0])
    manifest = {
        "contrato": CONTRACT,
        "generado": {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "commit": _commit(), "comando": comando},
        "fuentes": [SOURCE],
        "escuela": escuela,
        "granulos": [short_name(g) for g in granules],
        "bounds": inward_bounds(extent),
        "minzoom": min(zooms),
        "maxzoom": max(zooms),
        "precision_m": precision_m,
        "altitud_escuela_m": round(point_height, 1),
        "altura_esperada_m": list(expected),
        "punto": {"lat": lat, "lon": lon},
        "lado_km": side_km,
        "recorte": extent,
        "margen_celdas": MARGIN_CELLS,
        "proyeccion": "EPSG:3857",
        "codificacion": "terrarium",
        "tamano_px": TILE,
        "remuestreo": ("bilineal desde el recorte, en el centro de cada píxel; fuera del "
                       "recorte, el valor del borde"),
        "pixeles_fuera_del_recorte": outside_by_zoom,
        "elevacion_recorte_m": {"min": int(grid.values.min()), "max": int(grid.values.max())},
        "teselas": names,
    }
    manifest.update(extra or {})
    with open(out / MANIFEST, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    by_zoom = {}
    for name in names:
        by_zoom[int(name.split("/")[0])] = by_zoom.get(int(name.split("/")[0]), 0) + 1
    for zoom in zooms:
        extra_px = (f", {outside_by_zoom[zoom]} píxeles fuera del recorte, con el valor del "
                    "borde" if outside_by_zoom[zoom] else "")
        print(f"zoom {zoom}: {by_zoom.get(zoom, 0)} teselas{extra_px}")
    print(f"total: {len(names)} archivos, {_kb(total_bytes)}")
    print(f"elevación del recorte: {grid.values.min()} a {grid.values.max()} m")
    print(f"elevación en el punto: {point_height:.1f} m")
    print(f"guardado en {out}")
    return 0


def generate(zip_path: Path, lat: float, lon: float, side_km: float, zooms: list,
             out: Path, precision_m=None, expected=POINT_RANGE_M,
             comando="python -m src.relieve") -> int:
    """Las teselas de un punto desde un zip, sin escuela: el uso de antes."""
    # El manifiesto guarda la ruta del zip relativa a la raíz, y --comprobar la lee desde
    # ahí: se comprueba antes de escribir nada, para no dejar teselas sin manifiesto.
    if not zip_path.resolve().is_relative_to(ROOT):
        sys.exit(f"{zip_path} está fuera del repositorio: el manifiesto guarda su ruta "
                 "relativa a la raíz. Muévelo a data/raw/nasadem/.")
    _empty_output(out)
    granule = read_hgt(zip_path)
    try:
        crop = mosaic([granule], crop_cells(crop_bounds(lat, lon, side_km)))
    except ValueError:
        sys.exit("el recorte se sale del granulo: hace falta el granulo vecino.")
    _no_voids(crop)
    # Un solo camino: las teselas salen del recorte leído de su CSV.
    crop = grid_from_csv(crop_to_csv(crop))
    south, west = cell_corner(zip_path.name)
    return _finish(crop, lat=lat, lon=lon, side_km=side_km, zooms=zooms,
                   precision_m=precision_m, expected=expected, out=out, escuela=None,
                   granules=[granule_name(south + 0.5, west + 0.5)], comando=comando,
                   extra={"fuente": {"zip": _relative(zip_path), "sha256": _sha256(zip_path),
                                     "licencia": LICENSE}})


def _download_date(granules: list, raw: Path) -> str:
    """La fecha de descarga del recorte: la más reciente de sus granulos."""
    dates = []
    for granule in granules:
        path = record_path(granule, raw)
        if not path.is_file():
            sys.exit(f"falta {path.name} en {raw.name}/: sin él no se sabe la fecha de descarga.")
        with open(path, encoding="utf-8") as handle:
            dates.append(json.load(handle)["descargado_utc"][:10])
    return max(dates)


def crop_path(slug: str, recortes: Path = RECORTES) -> Path:
    return recortes / slug / "nasadem" / CROP_CSV


def generate_school(slug: str, side_km: float, zooms: list, precision_m, expected,
                    from_crop: bool, out: Path, comando: str, *, escuelas: Path = ESCUELAS,
                    raw: Path = RAW, recortes: Path = RECORTES) -> int:
    """Las teselas de una escuela, desde los zip de data/raw o desde su recorte versionado.

    Desde los zip, escribe antes el recorte en recortes/<slug>/nasadem/, con su manifiesto.
    En los dos casos las teselas salen del texto del CSV, y por eso son las mismas.
    """
    from src import recortes as manifests  # solo aquí: src.recortes no hace falta para lo demás

    lat, lon = school_point(slug, escuelas)
    _empty_output(out)
    window = crop_cells(crop_bounds(lat, lon, side_km))
    granules = granules_for(window)
    csv_file = crop_path(slug, recortes)
    if from_crop:
        if not csv_file.is_file():
            sys.exit(f"falta el recorte de {slug} en recortes/{slug}/nasadem/{CROP_CSV}.")
        text = csv_file.read_bytes().decode("utf-8")
    else:
        zips = [raw / f"{g}.zip" for g in granules]
        missing = [z.name for z in zips if not z.is_file()]
        if missing:
            sys.exit(f"faltan en {raw.name}/: {', '.join(missing)}. Se bajan con "
                     f"python -m src.relieve --descargar --escuela {slug}")
        try:
            crop = mosaic([read_hgt(z) for z in zips], window)
        except ValueError as error:
            sys.exit(f"{error}.")
        _no_voids(crop)
        text = crop_to_csv(crop)
        fecha = _download_date(granules, raw)
        csv_file.parent.mkdir(parents=True, exist_ok=True)
        csv_file.write_bytes(text.encode("utf-8"))
        manifests.escribir(csv_file.parent, fuente=SOURCE["nombre"], version=SOURCE["version"],
                           licencia=LICENSE, url_licencia=LICENSE_URL, atribucion=ATTRIBUTION,
                           fecha_descarga=fecha)
        print(f"recorte: recortes/{slug}/nasadem/{CROP_CSV}, "
              f"{crop.values.shape[0]} × {crop.values.shape[1]} nodos, con su manifiesto")
    try:
        grid = grid_from_csv(text)
    except ValueError as error:
        sys.exit(f"recortes/{slug}/nasadem/{CROP_CSV}: {error}")
    if grid_window(grid) != window:
        sys.exit(f"el recorte de {slug} no es el de un lado de {side_km:g} km: se generó con "
                 "otro --lado-km, o el CSV cambió.")
    return _finish(grid, lat=lat, lon=lon, side_km=side_km, zooms=zooms,
                   precision_m=precision_m, expected=expected, out=out, escuela=slug,
                   granules=granules, comando=comando)


# Comprobación

def _reference(manifest: dict, lat: float, lon: float) -> tuple:
    """La altura del píxel más cercano al punto en el .hgt, o en el recorte si el zip no
    está en data/raw (quien regenera sin cuenta de Earthdata). (valor, descripción)."""
    if "fuente" in manifest:
        zip_path = ROOT / manifest["fuente"]["zip"]
    else:
        zip_path = RAW / f"{granule_name(lat, lon)}.zip"
    if zip_path.is_file():
        south, west = cell_corner(zip_path.name)
        row = int(round((south + 1.0 - lat) * 3600.0))
        col = int(round((lon - west) * 3600.0))
        return read_hgt_pixel(zip_path, row, col), f"píxel ({row}, {col}) del .hgt"
    csv_file = crop_path(manifest.get("escuela") or "")
    if manifest.get("escuela") and csv_file.is_file():
        grid = grid_from_csv(csv_file.read_bytes().decode("utf-8"))
        row = int(round((grid.top - lat) / grid.step))
        col = int(round((lon - grid.left) / grid.step))
        return (int(grid.values[row, col]),
                f"nodo ({row}, {col}) del recorte, sin el .hgt en data/raw")
    sys.exit(f"para comprobar el punto falta {zip_path.name} en data/raw/nasadem/ y el "
             "recorte versionado.")


def _decimal(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def check(directory: Path) -> int:
    """Decodifica las teselas, imprime su resumen y corre los controles. Devuelve 0 o 1."""
    from src.presupuesto import kb, medir

    directory = Path(directory)
    with open(directory / MANIFEST, encoding="utf-8") as handle:
        manifest = json.load(handle)
    lat, lon = manifest["punto"]["lat"], manifest["punto"]["lon"]
    bounds = manifest["recorte"]
    precision = manifest.get("precision_m")
    low_ok, high_ok = manifest.get("altura_esperada_m", POINT_RANGE_M)
    school = manifest.get("escuela")
    results = []

    on_disk = sorted(p.relative_to(directory).as_posix() for p in directory.rglob("*.png"))
    expected = sorted(manifest["teselas"])
    results.append(("las teselas en disco son las del manifiesto", on_disk == expected,
                    f"{len(on_disk)} en disco, {len(expected)} en el manifiesto"))

    by_zoom, total_bytes, low, high = {}, 0, math.inf, -math.inf
    off_grid = 0
    for name in on_disk:
        zoom, x, y = (int(part) for part in name[:-4].split("/"))
        by_zoom[zoom] = by_zoom.get(zoom, 0) + 1
        total_bytes += (directory / name).stat().st_size
        height = terrarium_decode(read_png(directory / name))
        if precision:
            steps = height / precision
            off_grid += int(np.count_nonzero(np.abs(steps - np.round(steps)) > 1e-9))
        lon_c, lat_c = pixel_centers(zoom, x, y)
        mask = ((lat_c >= bounds["sur"]) & (lat_c <= bounds["norte"])
                & (lon_c >= bounds["oeste"]) & (lon_c <= bounds["este"]))
        if mask.any():
            low, high = min(low, height[mask].min()), max(high, height[mask].max())

    top_zoom = max(by_zoom)
    x, y = tile_of(lon, lat, top_zoom)
    px, py = lonlat_to_tile(lon, lat, top_zoom)
    decoded = terrarium_decode(read_png(directory / str(top_zoom) / str(x) / f"{y}.png"))
    point_tile = float(decoded[int((py - y) * TILE), int((px - x) * TILE)])

    reference, where = _reference(manifest, lat, lon)
    results.append((f"el punto en zoom {top_zoom} coincide con el .hgt",
                    abs(point_tile - reference) < POINT_TOLERANCE_M,
                    f"tesela {point_tile:.1f} m, {where} {reference} m, diferencia "
                    f"{abs(point_tile - reference):.1f} m, tolerancia {POINT_TOLERANCE_M:.0f} m"))
    school_height = manifest.get("altitud_escuela_m", point_tile)
    results.append(("el punto está a la altura esperada",
                    low_ok <= school_height <= high_ok,
                    f"{school_height:.1f} m, entre {low_ok:.0f} y {high_ok:.0f} m"))
    if school:
        gzip_bytes = sum(g for _, _, g in medir(directory))
        results.append(("el relieve cabe en su presupuesto", gzip_bytes <= MAX_SCHOOL_BYTES,
                        f"{kb(gzip_bytes)} KB con gzip -9, de {MAX_SCHOOL_BYTES // 1000} KB"))
    if precision:
        results.append((f"precision {_decimal(precision)} m", off_grid == 0,
                        "todas las alturas son múltiplos" if not off_grid
                        else f"{off_grid} píxeles no son múltiplos"))

    print(f"teselas: {directory.as_posix()}")
    if school:
        print(f"escuela: {school}, granulos {', '.join(manifest.get('granulos', []))}")
    for zoom in sorted(by_zoom):
        print(f"zoom {zoom}: {by_zoom[zoom]} teselas")
    print(f"total: {len(on_disk)} archivos, {_kb(total_bytes)}")
    print(f"elevación decodificada dentro del recorte: {low:.1f} a {high:.1f} m")
    print(f"elevación en el punto (zoom {top_zoom}): {point_tile:.1f} m")
    if "altitud_escuela_m" in manifest:
        print(f"altitud de la escuela (bilineal, relieve.json): {school_height:.1f} m")
    for name, ok, detail in results:
        print(f"[{'OK' if ok else 'FALLA'}] {name}: {detail}")
    failed = [name for name, ok, _ in results if not ok]
    print("comprobación en orden" if not failed else
          f"comprobación con {len(failed)} fallos: {', '.join(failed)}")
    return 0 if not failed else 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--descargar", action="store_true",
                        help=f"descarga {GRANULE} a data/raw/nasadem/; con --escuela, los "
                             "granulos de su recorte que falten")
    parser.add_argument("--comprobar", type=Path, metavar="CARPETA",
                        help="comprueba unas teselas ya generadas")
    parser.add_argument("--escuela", metavar="SLUG",
                        help="toma lat y lon de web/datos/escuelas.json y escribe en "
                             "web/datos/<slug>/relieve/")
    parser.add_argument("--desde-recorte", action="store_true",
                        help="con --escuela, genera desde recortes/<slug>/nasadem/elevacion.csv, "
                             "sin el zip")
    parser.add_argument("--precision-m", type=parse_precision,
                        help="redondea las alturas a múltiplos de este valor antes de "
                             f"codificarlas (con --escuela, {DEFAULT_PRECISION_M} por defecto)")
    parser.add_argument("--altura-esperada", type=parse_range, metavar="MIN-MAX",
                        help="el rango de la altura del punto en --comprobar; se guarda en "
                             "relieve.json")
    parser.add_argument("--zip", type=Path, help="el zip del granulo de NASADEM")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lon", type=float)
    parser.add_argument("--lado-km", type=float, default=4.0)
    parser.add_argument("--zoom", type=parse_zooms, default=parse_zooms("10-14"))
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args(argv)
    comando = shlex.join(["python", "-m", "src.relieve", *argv])

    if args.descargar:
        if args.escuela:
            return download_school(args.escuela, args.lado_km)
        download()
        return 0
    if args.comprobar is not None:
        return check(args.comprobar)
    if args.escuela:
        if args.zip or args.lat is not None or args.lon is not None:
            parser.error("con --escuela, la posición sale de escuelas.json: sin --zip, --lat "
                         "ni --lon")
        expected = args.altura_esperada or ALTURA_ESPERADA_M.get(args.escuela)
        if expected is None:
            parser.error(f"{args.escuela} no tiene rango en ALTURA_ESPERADA_M: da "
                         "--altura-esperada MIN-MAX")
        precision = DEFAULT_PRECISION_M if args.precision_m is None else args.precision_m
        out = args.salida or WEB_DATOS / args.escuela / "relieve"
        return generate_school(args.escuela, args.lado_km, args.zoom, precision, expected,
                               args.desde_recorte, out, comando)
    if args.desde_recorte:
        parser.error("--desde-recorte va con --escuela")
    if args.zip is None or args.lat is None or args.lon is None or args.salida is None:
        parser.error("para generar hacen falta --zip, --lat, --lon y --salida, o --escuela")
    return generate(args.zip, args.lat, args.lon, args.lado_km, args.zoom, args.salida,
                    precision_m=args.precision_m,
                    expected=args.altura_esperada or POINT_RANGE_M, comando=comando)


if __name__ == "__main__":
    # En Windows la consola no siempre escribe en UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
