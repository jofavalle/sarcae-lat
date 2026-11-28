"""Coordenadas de las tres escuelas y su distancia a la estación con la que se valida ERA5.

Lee `web/datos/escuelas.json`: el punto de cada escuela, con su fuente y su fecha de
consulta, y la estación de validación de su sede (`docs/PLAN.md`, secciones 3 a 5). Calcula
la distancia entre los dos puntos con la fórmula del haversine.

Uso, desde la raíz del repositorio:

    python -m src.escuelas               reescribe `distancia_km` y `generado`
    python -m src.escuelas --comprobar   valida el archivo sin escribir

Imprime una fila por escuela y sale con 1 si algo falla. Solo usa la biblioteca estándar.

Los números se leen como `Decimal` y se escriben tal como estaban: un float perdería los
ceros finales (−74,12200 saldría −74.122), y el archivo tiene que conservar sus 5 decimales.
"""

import argparse
import json
import math
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
ARCHIVO = ROOT / "web" / "datos" / "escuelas.json"
COMANDO = "python -m src.escuelas"

EARTH_RADIUS_KM = 6371.0088  # radio medio, el mismo de src/relieve.py
CONTRATO = 1
DECIMALES = 5

SLUGS = ("sv-88118", "co-nicolas-esguerra", "ve-rafael-maria-baralt")
ANCLA = "sv-88118"
ISO_PAISES = {"SV", "CO", "VE"}
METODOS = {"directorio", "direccion-en-mapa"}
HUSO_RANGO = (-12, 14)

CAMPOS_ESCUELA = ("slug", "nombre", "codigo", "municipio", "division", "pais", "iso_pais",
                  "lat", "lon", "huso_horas", "ancla", "estacion", "fuente_coordenadas")
CAMPOS_ESTACION = ("nombre", "lat", "lon", "distancia_km")
CAMPOS_FUENTE = ("nombre", "url", "fecha_consulta", "metodo", "licencia")

# Una ruta absoluta de este equipo: una letra de unidad, una raíz de Unix o una carpeta
# personal con ~. Solo al empezar el texto o después de un espacio, para que el // de una URL
# no cuente, y la raíz de Unix seguida de un nombre, para que un " / " entre palabras tampoco.
RUTA_ABSOLUTA = re.compile(r"(?:^|\s)(?:[A-Za-z]:[\\/]|/[\w.~-]|~[\\/]|\\\\)")


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Distancia del círculo máximo, en km, entre dos puntos en grados decimales."""
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = phi2 - phi1
    dlmb = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2.0 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def distancia(escuela: dict) -> Decimal:
    """La distancia de la escuela a su estación, redondeada a una décima."""
    estacion = escuela["estacion"]
    km = haversine_km(escuela["lat"], escuela["lon"], estacion["lat"], estacion["lon"])
    return Decimal(f"{km:.1f}")


# Lectura y escritura

def leer(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle, parse_float=Decimal)


def _json(value, nivel: int = 0) -> str:
    """Serializa con sangría de 2 y escribe cada Decimal tal como se leyó."""
    sangria, dentro = "  " * nivel, "  " * (nivel + 1)
    if isinstance(value, dict):
        if not value:
            return "{}"
        filas = [f"{dentro}{json.dumps(k, ensure_ascii=False)}: {_json(v, nivel + 1)}"
                 for k, v in value.items()]
        return "{\n" + ",\n".join(filas) + "\n" + sangria + "}"
    if isinstance(value, list):
        if not value:
            return "[]"
        filas = [f"{dentro}{_json(v, nivel + 1)}" for v in value]
        return "[\n" + ",\n".join(filas) + "\n" + sangria + "]"
    if isinstance(value, Decimal):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def escribir(path: Path, doc: dict) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_json(doc) + "\n")


def _commit() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "desconocido"


# Comprobación

def _decimales(value):
    """Cuántos decimales lleva un número leído como Decimal; None si no es decimal."""
    if not isinstance(value, Decimal):
        return None
    return max(0, -value.as_tuple().exponent)


def _es_numero(value) -> bool:
    return isinstance(value, (int, Decimal)) and not isinstance(value, bool)


def _textos(value, camino: str = ""):
    """Recorre el documento y devuelve (camino, texto) de cada cadena."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _textos(v, f"{camino}.{k}" if camino else k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _textos(v, f"{camino}[{i}]")
    elif isinstance(value, str):
        yield camino, value


def _coordenadas(lat, lon, donde: str) -> list:
    errores = []
    if not _es_numero(lat) or not -90 <= lat <= 90:
        errores.append(f"rango: {donde} lat={lat} fuera de [-90, 90]")
    if not _es_numero(lon) or not -180 <= lon <= 180:
        errores.append(f"rango: {donde} lon={lon} fuera de [-180, 180]")
    return errores


def _fecha(texto, donde: str, con_hora: bool) -> list:
    try:
        if con_hora:
            datetime.fromisoformat(texto)
        else:
            date.fromisoformat(texto)
    except (TypeError, ValueError):
        return [f"fecha: {donde}={texto!r} no es una fecha ISO 8601"]
    return []


def comprobar(doc: dict) -> list:
    """Devuelve la lista de errores del documento; vacía si está en orden.

    Cada error empieza por su tipo (`campos`, `slug`, `rango`, `huso`, `decimales`, `fecha`,
    `ruta`, `distancia`, `ancla`), para que se pueda filtrar.
    """
    errores = []
    if doc.get("contrato") != CONTRATO:
        errores.append(f"campos: contrato={doc.get('contrato')!r}, se esperaba {CONTRATO}")

    generado = doc.get("generado")
    if not isinstance(generado, dict) or any(k not in generado for k in ("utc", "commit",
                                                                         "comando")):
        errores.append("campos: falta el bloque generado con utc, commit y comando")
    else:
        errores += _fecha(generado["utc"], "generado.utc", con_hora=True)

    escuelas = doc.get("escuelas")
    if not isinstance(escuelas, list):
        return errores + ["campos: falta la lista escuelas"]

    slugs = [e.get("slug") for e in escuelas if isinstance(e, dict)]
    if sorted(map(str, slugs)) != sorted(SLUGS):
        errores.append(f"slug: {slugs} no son {list(SLUGS)}, una vez cada uno")

    for i, escuela in enumerate(escuelas):
        if not isinstance(escuela, dict):
            errores.append(f"campos: escuelas[{i}] no es un objeto")
            continue
        donde = escuela.get("slug") or f"escuelas[{i}]"
        faltan = [c for c in CAMPOS_ESCUELA if c not in escuela]
        estacion = escuela.get("estacion") or {}
        fuente = escuela.get("fuente_coordenadas") or {}
        faltan += [f"estacion.{c}" for c in CAMPOS_ESTACION if c not in estacion]
        faltan += [f"fuente_coordenadas.{c}" for c in CAMPOS_FUENTE if c not in fuente]
        if faltan:
            errores.append(f"campos: {donde} no tiene {', '.join(faltan)}")
            continue

        if escuela["iso_pais"] not in ISO_PAISES:
            errores.append(f"campos: {donde} iso_pais={escuela['iso_pais']!r}")
        if (escuela["ancla"] is True) != (escuela["slug"] == ANCLA):
            errores.append(f"ancla: {donde} ancla={escuela['ancla']!r}; solo {ANCLA} es ancla")
        if fuente["metodo"] not in METODOS:
            errores.append(f"campos: {donde} metodo={fuente['metodo']!r} no es "
                           f"{' ni '.join(sorted(METODOS))}")

        malas = (_coordenadas(escuela["lat"], escuela["lon"], donde)
                 + _coordenadas(estacion["lat"], estacion["lon"], f"{donde} estación"))
        errores += malas
        for eje in ("lat", "lon"):
            n = _decimales(escuela[eje])
            if n != DECIMALES:
                errores.append(f"decimales: {donde} {eje}={escuela[eje]} lleva {n} decimales, "
                               f"no {DECIMALES}")

        huso = escuela["huso_horas"]
        if not isinstance(huso, int) or isinstance(huso, bool) or not (
                HUSO_RANGO[0] <= huso <= HUSO_RANGO[1]):
            errores.append(f"huso: {donde} huso_horas={huso!r} no es un entero en "
                           f"[{HUSO_RANGO[0]}, {HUSO_RANGO[1]}]")

        errores += _fecha(fuente["fecha_consulta"], f"{donde} fecha_consulta", con_hora=False)

        if not malas:  # con un punto fuera de rango, la distancia no dice nada
            esperada = distancia(escuela)
            guardada = estacion["distancia_km"]
            if not _es_numero(guardada) or Decimal(guardada) != esperada:
                errores.append(f"distancia: {donde} guarda {guardada} km y la calculada es "
                               f"{esperada} km")

    for camino, texto in _textos(doc):
        if RUTA_ABSOLUTA.search(texto):
            errores.append(f"ruta: {camino}={texto!r} lleva una ruta absoluta")
    return errores


def filas(doc: dict) -> list:
    out = []
    for escuela in doc.get("escuelas", []):
        try:
            estacion = escuela["estacion"]
            out.append(f"{escuela['slug']:<24} {escuela['lat']:>10}, {escuela['lon']:>11}  "
                       f"-> {estacion['nombre']} a {estacion['distancia_km']} km")
        except (KeyError, TypeError):
            out.append(f"{escuela.get('slug', '?')}: incompleta")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--comprobar", action="store_true",
                        help="valida el archivo sin escribirlo")
    args = parser.parse_args(argv)

    doc = leer(ARCHIVO)
    if not args.comprobar:
        for escuela in doc.get("escuelas", []):
            try:
                escuela["estacion"]["distancia_km"] = distancia(escuela)
            except (KeyError, TypeError, ValueError):
                pass  # la escuela está incompleta: lo dice la comprobación de abajo
        doc["generado"] = {
            "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "commit": _commit(),
            "comando": COMANDO,
        }
        escribir(ARCHIVO, doc)

    for fila in filas(doc):
        print(fila)
    errores = comprobar(doc)
    for error in errores:
        print(f"FALLA {error}")
    if errores:
        return 1
    print(f"escuelas en orden: {len(doc['escuelas'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
