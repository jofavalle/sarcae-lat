"""Presupuesto de carga: lo que pesa una carpeta del sitio, comprimida con gzip -9.

Mide cada archivo de la carpeta, también los de sus subcarpetas, sin comprimir y comprimido
con `gzip.compress(datos, compresslevel=9)`, en KB de 1000 bytes y con una décima, en las
mismas unidades que ADR-001; las cifras dependen del zlib de Python y pueden diferir de GNU
gzip en unas décimas. Imprime una fila por archivo y el total, y sale con código 1 si el total
comprimido pasa del límite. El límite se compara con los bytes exactos, no con el total
redondeado.

Uso, desde la raíz del repositorio:

    python -m src.presupuesto web/vendor/maplibre-gl-6.20.0 --limite-kb 480

Solo usa la biblioteca estándar.
"""

import argparse
import gzip
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path


def medir(carpeta: Path) -> list:
    """(ruta relativa con /, bytes sin comprimir, bytes con gzip -9) de cada archivo, en orden."""
    filas = []
    for archivo in carpeta.rglob("*"):
        if not archivo.is_file():
            continue
        datos = archivo.read_bytes()
        comprimido = gzip.compress(datos, compresslevel=9)
        filas.append((archivo.relative_to(carpeta).as_posix(), len(datos), len(comprimido)))
    # Por la ruta como texto: Path ordena sin distinguir mayúsculas en Windows y
    # distinguiéndolas en Linux, y la tabla saldría distinta en cada sistema.
    return sorted(filas)


def kb(n_bytes: int) -> str:
    """Bytes en KB de 1000 bytes, con una décima y coma decimal, redondeando la mitad hacia arriba.

    Se calcula con enteros, para que 1050 bytes sean siempre 1,1 y no dependan de cómo
    represente el ordenador 1,05.
    """
    decimas = (n_bytes + 50) // 100
    return f"{decimas // 10},{decimas % 10}"


def limite(texto: str) -> Decimal:
    try:
        valor = Decimal(texto.replace(",", "."))
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"'{texto}' no es un número")
    if not valor.is_finite() or valor < 0:
        raise argparse.ArgumentTypeError(f"'{texto}' no es un límite válido")
    return valor


def tabla(filas: list) -> list:
    """Las líneas de la tabla: cabecera, una fila por archivo y el total."""
    total = ("Total", sum(f[1] for f in filas), sum(f[2] for f in filas))
    ancho = max([len("Archivo")] + [len(f[0]) for f in filas] + [len(total[0])])
    lineas = [f"{'Archivo':<{ancho}}  {'Sin comprimir':>13}  {'gzip -9':>9}"]
    for nombre, crudo, comprimido in filas + [total]:
        lineas.append(f"{nombre:<{ancho}}  {kb(crudo) + ' KB':>13}  {kb(comprimido) + ' KB':>9}")
    return lineas


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("carpeta", type=Path, help="la carpeta del sitio que se mide")
    parser.add_argument("--limite-kb", type=limite, required=True,
                        help="el límite del total con gzip -9, en KB de 1000 bytes")
    args = parser.parse_args(argv)

    if not args.carpeta.is_dir():
        parser.error(f"{args.carpeta} no es una carpeta")
    filas = medir(args.carpeta)
    if not filas:
        parser.error(f"{args.carpeta} no tiene archivos")

    for linea in tabla(filas):
        print(linea)
    total = sum(f[2] for f in filas)
    limite_texto = f"{args.limite_kb.normalize():f}".replace(".", ",")
    if total > args.limite_kb * 1000:
        print(f"\npasa del límite: {kb(total)} KB con gzip -9, y el límite es {limite_texto} KB")
        return 1
    print(f"\ndentro del límite: {kb(total)} KB con gzip -9, de {limite_texto} KB")
    return 0


if __name__ == "__main__":
    # En Windows la consola no siempre escribe en UTF-8, y "límite" saldría mal.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
