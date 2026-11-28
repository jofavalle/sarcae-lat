"""Crea y comprueba manifiestos de recortes. Uso: python -m src.recortes --help."""

import argparse
import hashlib
import json
import re
import shlex
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

RAIZ = Path(__file__).resolve().parents[1]
RECORTES = RAIZ / "recortes"
MANIFIESTO = "manifiesto.json"
MAX_BYTES = 50_000_000
EXTENSIONES = {".csv", ".parquet", ".tif", ".tiff", ".json", ".geojson"}
LICENCIAS = {"CC0-1.0", "CC-BY-4.0", "dominio-publico"}

# Enlaces de la columna «Enlace» del README. Para otra fuente se pasa --url-fuente.
CDS = "https://cds.climate.copernicus.eu/datasets/"
URL_FUENTE = {
    "era5": CDS + "reanalysis-era5-single-levels-timeseries",
    "reanalysis-era5-single-levels-timeseries": CDS + "reanalysis-era5-single-levels-timeseries",
    "reanalysis-era5-single-levels": CDS + "reanalysis-era5-single-levels",
    "era5-land": CDS + "reanalysis-era5-land",
    "nasadem": "https://www.earthdata.nasa.gov/data/catalog/lpcloud-nasadem-hgt-001",
    "landsat": "https://www.usgs.gov/landsat-missions/landsat-collection-2-level-2-science-products",
    "worldcover": "https://esa-worldcover.org/en/data-access",
    "google open buildings v3": "https://sites.research.google/gr/open-buildings/",
    "google open buildings 2.5d temporal": "https://sites.research.google/gr/open-buildings/temporal/",
    "chirps": "https://www.chc.ucsb.edu/data/chirps3",
}
URL_FUENTE["nasadem_hgt"] = URL_FUENTE["nasadem"]
URL_FUENTE["nasadem_hgt v001"] = URL_FUENTE["nasadem"]
URL_FUENTE["reanalysis-era5-land"] = URL_FUENTE["era5-land"]
URL_FUENTE["landsat 8 y 9"] = URL_FUENTE["landsat"]
URL_FUENTE["esa worldcover"] = URL_FUENTE["worldcover"]
URL_FUENTE["chirps v3.0"] = URL_FUENTE["chirps"]

# Una URL web puede contener barras absolutas y una atribución puede citarla en prosa.
URL_WEB = re.compile(r"https?://[^\s<>\"']+", re.I)
RUTA_ABSOLUTA = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|file:/|(?<![\w./-])/(?:[^\s]|$))", re.I)


def generado(comando):
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ, capture_output=True, text=True)
    return {
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": commit.stdout.strip() if commit.returncode == 0 else "desconocido",
        "comando": comando,
    }


def guardar_json(ruta, datos, max_bytes=None):
    """Sustituye el archivo completo, incluso si ya existía una versión válida."""
    texto = json.dumps(datos, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    contenido = texto.encode("utf-8")
    if max_bytes is not None and len(contenido) > max_bytes:
        raise ValueError(f"{ruta.name}: supera {max_bytes} bytes")
    temporal = ruta.with_name(f".{ruta.name}.{uuid4().hex}.tmp")
    try:
        with temporal.open("xb") as salida:
            salida.write(contenido)
        temporal.replace(ruta)
    finally:
        temporal.unlink(missing_ok=True)


def comprobar_rutas(valor):
    if isinstance(valor, dict):
        for clave, contenido in valor.items():
            comprobar_rutas(clave)
            comprobar_rutas(contenido)
    elif isinstance(valor, list):
        for elemento in valor:
            comprobar_rutas(elemento)
    elif isinstance(valor, str) and RUTA_ABSOLUTA.search(URL_WEB.sub("URL", valor)):
        raise ValueError("ruta absoluta en el manifiesto")


def objeto_con_textos(objeto, *campos):
    if not isinstance(objeto, dict):
        raise ValueError(f"se esperaba un objeto con {', '.join(campos)}")
    for campo in campos:
        if not isinstance(objeto.get(campo), str) or not objeto[campo].strip():
            raise ValueError(f"falta texto en {campo}")


def validar_metadatos(datos, escuela):
    objeto_con_textos(datos, "escuela", "atribucion", "fecha_descarga")
    if datos["escuela"] != escuela:
        raise ValueError("escuela distinta de la carpeta padre")
    fuente, licencia = datos.get("fuente"), datos.get("licencia")
    objeto_con_textos(fuente, "nombre", "version", "url")
    objeto_con_textos(licencia, "spdx", "url")
    objeto_con_textos(datos.get("generado"), "utc", "commit", "comando")
    if licencia["spdx"] not in LICENCIAS:
        raise ValueError(f"licencia no admitida: {licencia['spdx']}")
    for objeto in (fuente, licencia):
        url = urlsplit(objeto["url"])
        if url.scheme not in ("http", "https") or not url.hostname:
            raise ValueError("la fuente y la licencia requieren enlaces web")
    fecha = datos["fecha_descarga"]
    if date.fromisoformat(fecha).isoformat() != fecha:
        raise ValueError("fecha_descarga debe tener el formato AAAA-MM-DD")
    comprobar_rutas(datos)


def archivos_de(carpeta, manifiesto):
    for ruta in carpeta.iterdir():
        if ruta == manifiesto:
            continue
        if ruta.is_symlink():
            raise ValueError(f"{ruta.name}: enlace simbólico en el recorte")
        if ruta.is_dir():
            yield from archivos_de(ruta, manifiesto)
        elif ruta.is_file() and ruta.suffix.lower() in EXTENSIONES:
            yield ruta
        else:
            raise ValueError(f"{ruta.name}: se requiere un archivo con extensión admitida")


def inventario(carpeta):
    archivos = []
    for ruta in sorted(archivos_de(carpeta, carpeta / MANIFIESTO), key=Path.as_posix):
        tamano = ruta.stat().st_size
        if tamano > MAX_BYTES:
            raise ValueError(f"{ruta.name}: supera {MAX_BYTES} bytes")
        digest = hashlib.sha256()
        with ruta.open("rb") as entrada:
            for bloque in iter(lambda: entrada.read(1 << 20), b""):
                digest.update(bloque)
        archivos.append({"nombre": ruta.relative_to(carpeta).as_posix(), "bytes": tamano,
                         "sha256": digest.hexdigest()})
    return archivos


def escribir(carpeta, *, fuente, version, licencia, url_licencia, atribucion, fecha_descarga,
             url_fuente=None):
    """Escribe y devuelve el manifiesto. La atribución es el crédito de la fuente en el README."""
    carpeta = Path(carpeta).resolve()
    url = url_fuente or URL_FUENTE.get(fuente.casefold())
    if not url:
        raise ValueError(f"{fuente}: indica la URL de la fuente con --url-fuente")
    args = ["python", "-m", "src.recortes", "--escribir",
            f"recortes/{carpeta.parent.name}/{carpeta.name}", "--fuente", fuente,
            "--version", version, "--url-fuente", url, "--licencia", licencia,
            "--url-licencia", url_licencia, "--atribucion", atribucion, "--fecha-descarga", fecha_descarga]
    datos = {
        "escuela": carpeta.parent.name,
        "fuente": {"nombre": fuente, "version": version, "url": url},
        "licencia": {"spdx": licencia, "url": url_licencia},
        "atribucion": atribucion, "fecha_descarga": fecha_descarga,
        "generado": generado(shlex.join(args)),
        "archivos": inventario(carpeta),
    }
    validar_metadatos(datos, carpeta.parent.name)
    guardar_json(carpeta / MANIFIESTO, datos, MAX_BYTES)
    return datos


def comprobar(carpeta):
    carpeta = Path(carpeta).resolve()
    ruta = carpeta / MANIFIESTO
    if ruta.is_symlink() or not ruta.is_file():
        raise ValueError(f"falta un {MANIFIESTO} regular")
    if ruta.stat().st_size > MAX_BYTES:
        raise ValueError(f"{MANIFIESTO}: supera {MAX_BYTES} bytes")
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    validar_metadatos(datos, carpeta.parent.name)
    if not isinstance(datos.get("archivos"), list):
        raise ValueError("archivos debe ser una lista")
    declarados = {}
    for archivo in datos["archivos"]:
        objeto_con_textos(archivo, "nombre", "sha256")
        nombre = archivo["nombre"]
        if nombre in declarados or type(archivo.get("bytes")) is not int:
            raise ValueError(f"{nombre}: nombre repetido o bytes inválidos")
        declarados[nombre] = archivo
    for real in inventario(carpeta):
        nombre = real["nombre"]
        previsto = declarados.pop(nombre, None)
        if previsto is None:
            raise ValueError(f"{nombre}: está en disco y falta en el manifiesto")
        for campo in ("bytes", "sha256"):
            if previsto[campo] != real[campo]:
                raise ValueError(f"{nombre}: {campo} no coincide")
    if declarados:
        raise ValueError("faltan en disco: " + ", ".join(declarados))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--escribir", type=Path, metavar="CARPETA")
    modo.add_argument("--comprobar", action="store_true")
    parser.add_argument("carpeta", nargs="?", type=Path)
    parser.add_argument("--todas", action="store_true")
    opciones = ("fuente", "version", "licencia", "url-licencia", "atribucion", "fecha-descarga")
    for nombre in (*opciones, "url-fuente"):
        parser.add_argument("--" + nombre)
    args = parser.parse_args(argv)
    if args.escribir:
        if args.todas or args.carpeta:
            parser.error("--escribir recibe una sola carpeta")
        valores = {}
        for nombre in opciones:
            clave = nombre.replace("-", "_")
            valores[clave] = getattr(args, clave)
            if not valores[clave]:
                parser.error(f"falta --{nombre}")
        carpetas = [args.escribir]
    else:
        if bool(args.carpeta) == args.todas:
            parser.error("--comprobar requiere una carpeta o --todas")
        carpetas = (sorted(p for p in RECORTES.glob("*/*") if p.is_dir())
                    if args.todas else [args.carpeta])
    estado = 0
    for carpeta in carpetas:
        try:
            if args.escribir:
                escribir(carpeta, url_fuente=args.url_fuente, **valores)
            else:
                comprobar(carpeta)
            print(f"{carpeta}: en orden")
        except (ValueError, OSError) as error:
            print(f"{carpeta}: {error}")
            estado = 1
    return estado


if __name__ == "__main__":
    raise SystemExit(main())
