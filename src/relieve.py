"""Teselas de relieve en terrarium a partir de un granulo de NASADEM.

Recorta un granulo `NASADEM_HGT` de un grado alrededor de un punto y escribe las teselas
XYZ en PNG que pide ADR-001 para el terreno 3D y el sombreado de MapLibre: Web Mercator
(EPSG:3857), 256 px y codificación terrarium, `h = R·256 + G + B/256 - 32768`. Al terminar,
cuenta cuántas teselas salen y cuánto pesan.

Uso, desde la raíz del repositorio:

    python -m src.relieve --descargar
    python -m src.relieve --zip data/raw/nasadem/NASADEM_HGT_n13w090.zip \\
        --lat 13.70 --lon -89.12 --lado-km 4 --zoom 10-14 \\
        --salida data/processed/relieve/prueba-ilopango
    python -m src.relieve --comprobar data/processed/relieve/prueba-ilopango

La descarga pide una cuenta gratuita de NASA Earthdata, con las credenciales en `~/.netrc`
y nunca en el repositorio. `data/raw/` es inmutable: si el zip ya existe, no se toca.
"""

import argparse
import hashlib
import json
import math
import re
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

GRANULE = "NASADEM_HGT_n13w090"
GRANULE_URL = ("https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/"
               f"NASADEM_HGT.001/{GRANULE}/{GRANULE}.zip")
LICENSE = "CC0-1.0"

# El .hgt: 3601 × 3601 enteros de 16 bits big-endian, un segundo de arco de paso, filas de
# norte a sur. El primer píxel está en la esquina noroeste de la celda.
HGT_SIDE = 3601
HGT_BYTES = HGT_SIDE * HGT_SIDE * 2  # 25 934 402
HGT_STEP = 1.0 / 3600.0
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


def crop_window(grid: Grid, bounds: dict) -> tuple:
    """Filas y columnas de los píxeles de la malla cuyo centro cae dentro del recorte."""
    row_top, col_left = grid.fractional_index(bounds["norte"], bounds["oeste"])
    row_bottom, col_right = grid.fractional_index(bounds["sur"], bounds["este"])
    rows = slice(int(math.ceil(row_top)), int(math.floor(row_bottom)) + 1)
    cols = slice(int(math.ceil(col_left)), int(math.floor(col_right)) + 1)
    return rows, cols


def inside(grid: Grid, bounds: dict) -> bool:
    return (grid.bottom <= bounds["sur"] and bounds["norte"] <= grid.top
            and grid.left <= bounds["oeste"] and bounds["este"] <= grid.right)


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

def download() -> Path:
    """Descarga el granulo con curl y escribe su `registro.json` al lado.

    Se descarga a una carpeta temporal y se mueve al final: si algo falla a mitad, el
    destino no llega a existir.
    """
    final = RAW / f"{GRANULE}.zip"
    record_path = RAW / "registro.json"
    for path in (final, record_path):
        if path.exists():
            sys.exit(f"{_relative(path)} ya existe, y data/raw es inmutable: no se toca.")
    RAW.mkdir(parents=True, exist_ok=True)
    started_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with tempfile.TemporaryDirectory(prefix="nasadem-") as work:
        work = Path(work)
        landing = work / final.name
        cookies = work / "cookies"
        result = subprocess.run(["curl", "-n", "-L", "-f", "-c", str(cookies), "-b", str(cookies),
                                 "-o", str(landing), GRANULE_URL])
        if result.returncode != 0 or not zipfile.is_zipfile(landing):
            sys.exit("la descarga no trajo un zip: revisa la cuenta de Earthdata en ~/.netrc "
                     "y que la aplicación LP DAAC esté autorizada en ella.")
        with zipfile.ZipFile(landing) as archive:
            member = hgt_member(archive)
        record = {
            "url": GRANULE_URL,
            "granulo": GRANULE,
            "descargado_utc": started_utc,
            "commit": _commit(),
            "licencia": LICENSE,
            "licencia_url": "https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance",
            "archivo": _relative(final),
            "bytes": landing.stat().st_size,
            "sha256": _sha256(landing),
            "hgt": {"nombre": member.filename, "bytes": member.file_size},
        }
        shutil.move(str(landing), final)
    with open(record_path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"guardado en {_relative(final)} ({_kb(record['bytes'])}), "
          f"con {_relative(record_path)}")
    return final


# Generación de las teselas

def parse_zooms(text: str) -> list:
    low, _, high = text.partition("-")
    low, high = int(low), int(high or low)
    if not 0 <= low <= high <= 22:
        raise argparse.ArgumentTypeError(f"zoom {text}: se espera 'mín-máx', entre 0 y 22")
    return list(range(low, high + 1))


def generate(zip_path: Path, lat: float, lon: float, side_km: float, zooms: list,
             out: Path) -> int:
    # El manifiesto guarda la ruta del zip relativa a la raíz, y --comprobar la lee desde
    # ahí: se comprueba antes de escribir nada, para no dejar teselas sin manifiesto.
    if not zip_path.resolve().is_relative_to(ROOT):
        sys.exit(f"{zip_path} está fuera del repositorio: el manifiesto guarda su ruta "
                 "relativa a la raíz. Muévelo a data/raw/nasadem/.")
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} ya tiene archivos: elige otra --salida o vacíala a mano, para no "
                 "mezclar teselas de dos ejecuciones.")
    grid = read_hgt(zip_path)
    bounds = crop_bounds(lat, lon, side_km)
    if not inside(grid, bounds):
        sys.exit("el recorte se sale del granulo: hace falta el granulo vecino.")

    rows, cols = crop_window(grid, bounds)
    crop = grid.values[rows, cols]
    crop_voids = int(np.count_nonzero(crop == VOID))
    if crop_voids:
        sys.exit(f"el recorte tiene {crop_voids} píxeles vacíos (-32768). Cómo rellenarlos se "
                 "decide en la issue: no se generan teselas.")

    tiles = {zoom: tiles_for(bounds, zoom) for zoom in zooms}
    for zoom, items in tiles.items():
        for x, y in items:
            lon_c, lat_c = pixel_centers(zoom, x, y)
            voids = voids_under(grid, lat_c, lon_c)
            if voids:
                sys.exit(f"la tesela {zoom}/{x}/{y} pasa por {voids} píxeles vacíos fuera del "
                         "recorte. Cómo rellenarlos se decide en la issue.")

    out.mkdir(parents=True, exist_ok=True)
    total_bytes, outside_by_zoom, names = 0, {}, []
    for zoom, items in tiles.items():
        outside_by_zoom[zoom] = 0
        for x, y in items:
            height, outside = render_tile(grid, zoom, x, y)
            outside_by_zoom[zoom] += outside
            total_bytes += write_png(out / str(zoom) / str(x) / f"{y}.png",
                                     terrarium_encode(height))
            names.append(f"{zoom}/{x}/{y}.png")

    point_height = float(bilinear(grid, np.array([lat]), np.array([lon]))[0][0])
    manifest = {
        "generado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": _commit(),
        "fuente": {"zip": _relative(zip_path), "sha256": _sha256(zip_path),
                   "licencia": LICENSE},
        "punto": {"lat": lat, "lon": lon},
        "lado_km": side_km,
        "recorte": bounds,
        "zoom": [min(zooms), max(zooms)],
        "proyeccion": "EPSG:3857",
        "codificacion": "terrarium",
        "tamano_px": TILE,
        "remuestreo": "bilineal desde la malla geográfica, en el centro de cada píxel",
        "pixeles_fuera_del_granulo": outside_by_zoom,
        "elevacion_recorte_m": {"min": int(crop.min()), "max": int(crop.max())},
        "elevacion_punto_m": round(point_height, 2),
        "teselas": names,
    }
    with open(out / MANIFEST, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    for zoom, items in tiles.items():
        extra = (f", {outside_by_zoom[zoom]} píxeles fuera del granulo, con el valor del borde"
                 if outside_by_zoom[zoom] else "")
        print(f"zoom {zoom}: {len(items)} teselas{extra}")
    print(f"total: {len(names)} archivos, {_kb(total_bytes)}")
    print(f"elevación del recorte: {crop.min()} a {crop.max()} m")
    print(f"elevación en el punto: {point_height:.1f} m")
    print(f"guardado en {out}")
    return 0


# Comprobación

def check(directory: Path) -> int:
    """Decodifica las teselas, imprime su resumen y corre los controles. Devuelve 0 o 1."""
    directory = Path(directory)
    with open(directory / MANIFEST, encoding="utf-8") as handle:
        manifest = json.load(handle)
    lat, lon = manifest["punto"]["lat"], manifest["punto"]["lon"]
    bounds = manifest["recorte"]
    zip_path = ROOT / manifest["fuente"]["zip"]
    results = []

    on_disk = sorted(p.relative_to(directory).as_posix() for p in directory.rglob("*.png"))
    expected = sorted(manifest["teselas"])
    results.append(("las teselas en disco son las del manifiesto", on_disk == expected,
                    f"{len(on_disk)} en disco, {len(expected)} en el manifiesto"))

    by_zoom, total_bytes, low, high = {}, 0, math.inf, -math.inf
    for name in on_disk:
        zoom, x, y = (int(part) for part in name[:-4].split("/"))
        by_zoom[zoom] = by_zoom.get(zoom, 0) + 1
        total_bytes += (directory / name).stat().st_size
        height = terrarium_decode(read_png(directory / name))
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

    south, west = cell_corner(Path(zip_path).name)
    row = int(round((south + 1.0 - lat) * 3600.0))
    col = int(round((lon - west) * 3600.0))
    point_hgt = read_hgt_pixel(zip_path, row, col)
    results.append((f"el punto en zoom {top_zoom} coincide con el .hgt",
                    abs(point_tile - point_hgt) < POINT_TOLERANCE_M,
                    f"tesela {point_tile:.1f} m, píxel ({row}, {col}) del .hgt {point_hgt} m, "
                    f"tolerancia {POINT_TOLERANCE_M:.0f} m"))
    results.append(("el punto está a la altura esperada",
                    POINT_RANGE_M[0] <= point_tile <= POINT_RANGE_M[1],
                    f"{point_tile:.1f} m, entre {POINT_RANGE_M[0]:.0f} y {POINT_RANGE_M[1]:.0f} m"))

    print(f"teselas: {directory.as_posix()}")
    for zoom in sorted(by_zoom):
        print(f"zoom {zoom}: {by_zoom[zoom]} teselas")
    print(f"total: {len(on_disk)} archivos, {_kb(total_bytes)}")
    print(f"elevación decodificada dentro del recorte: {low:.1f} a {high:.1f} m")
    print(f"elevación en el punto (zoom {top_zoom}): {point_tile:.1f} m")
    for name, ok, detail in results:
        print(f"[{'OK' if ok else 'FALLA'}] {name}: {detail}")
    failed = [name for name, ok, _ in results if not ok]
    print("comprobación en orden" if not failed else
          f"comprobación con {len(failed)} fallos: {', '.join(failed)}")
    return 0 if not failed else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--descargar", action="store_true",
                        help=f"descarga {GRANULE} a data/raw/nasadem/")
    parser.add_argument("--comprobar", type=Path, metavar="CARPETA",
                        help="comprueba unas teselas ya generadas")
    parser.add_argument("--zip", type=Path, help="el zip del granulo de NASADEM")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lon", type=float)
    parser.add_argument("--lado-km", type=float, default=4.0)
    parser.add_argument("--zoom", type=parse_zooms, default=parse_zooms("10-14"))
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args(argv)

    if args.descargar:
        download()
        return 0
    if args.comprobar is not None:
        return check(args.comprobar)
    if args.zip is None or args.lat is None or args.lon is None or args.salida is None:
        parser.error("para generar hacen falta --zip, --lat, --lon y --salida")
    return generate(args.zip, args.lat, args.lon, args.lado_km, args.zoom, args.salida)


if __name__ == "__main__":
    sys.exit(main())
