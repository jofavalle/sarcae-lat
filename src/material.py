"""Genera los JSON de docs/material/ o comprueba que siguen al día."""

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from src.recortes import RAIZ, generado, guardar_json

MATERIAL = Path("docs/material")
DESTINO = Path("web/datos/comun")
REGISTROS = {"Estudiantes": "estudiante", "Docentes": "docente", "Dirección": "direccion"}
COLECCIONES = {"limites": "limites", "glosario": "terminos"}


def identificador(titulo):
    texto = unicodedata.normalize("NFKD", titulo.casefold())
    letras = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", letras).strip("-")


def leer_limites(texto):
    partes = re.split(r"^## ([^\n]+)$", texto, flags=re.MULTILINE)
    limites = []
    ids = set()
    for titulo, contenido in zip(partes[1::2], partes[2::2]):
        titulo = titulo.strip()
        clave = identificador(titulo)
        if not clave or clave in ids:
            raise ValueError(f"{titulo}: identificador vacío o repetido")
        ids.add(clave)
        limite = {"id": clave, "titulo": titulo}
        for parrafo in re.split(r"\n\s*\n", contenido.strip()):
            marca = re.fullmatch(r"\*\*(\w+)\.\*\*\s+(.+)", parrafo, flags=re.DOTALL)
            if not marca or marca[1] not in REGISTROS:
                raise ValueError(f"{titulo}: párrafo sin un registro reconocido")
            campo = REGISTROS[marca[1]]
            if campo in limite:
                raise ValueError(f"{titulo}: registro {campo} repetido")
            limite[campo] = " ".join(marca[2].split())
        for campo in REGISTROS.values():
            if campo not in limite:
                raise ValueError(f"{titulo}: falta el registro {campo}")
        limites.append(limite)
    if not limites:
        raise ValueError("limites.md: faltan límites")
    return limites


def leer_glosario(texto):
    terminos = []
    vistos = set()
    entradas = re.split(r"^- ", texto, flags=re.MULTILINE)
    for entrada in entradas[1:]:
        marca = re.fullmatch(r"\*\*(.+?)\*\*:\s+(.+)", entrada.strip(), flags=re.DOTALL)
        if not marca:
            raise ValueError(f"glosario.md: entrada sin término o definición: {entrada.strip()}")
        termino, definicion = marca.groups()
        if termino in vistos:
            raise ValueError(f"glosario.md: término repetido: {termino}")
        vistos.add(termino)
        terminos.append({"termino": termino, "definicion": " ".join(definicion.split())})
    if not terminos:
        raise ValueError("glosario.md: faltan términos")
    return terminos


def documento(raiz, nombre, procedencia):
    ruta = MATERIAL / f"{nombre}.md"
    texto = (raiz / ruta).read_text(encoding="utf-8")
    filas = leer_limites(texto) if nombre == "limites" else leer_glosario(texto)
    return {
        "contrato": 1,
        "generado": procedencia,
        "fuentes": [{
            "nombre": ruta.as_posix(),
            "version": "sha256:" + hashlib.sha256(texto.encode("utf-8")).hexdigest(),
            "licencia": "CC-BY-4.0",
            "url": f"https://github.com/jofavalle/sarcae-lat/blob/main/{ruta.as_posix()}",
        }],
        COLECCIONES[nombre]: filas,
    }


def comprobar_documento(ruta, esperado, coleccion):
    actual = json.loads(ruta.read_text(encoding="utf-8"))
    if not isinstance(actual, dict) or not isinstance(actual.get(coleccion), list):
        raise ValueError(f"{ruta.name}: falta la lista {coleccion}")
    # Primero el contenido: una palabra modificada también cambia la versión de la fuente.
    filas = actual[coleccion]
    for i, fila in enumerate(esperado[coleccion]):
        etiqueta = fila.get("titulo") or fila["termino"]
        if i >= len(filas) or not isinstance(filas[i], dict):
            raise ValueError(f"{ruta.name}: falta {etiqueta}")
        for campo, valor in fila.items():
            if filas[i].get(campo) != valor:
                raise ValueError(f"{ruta.name}: {etiqueta}: difiere {campo}")
    if not isinstance(actual.get("generado"), dict):
        raise ValueError(f"{ruta.name}: falta el bloque generado")
    # Se ignora el valor de generado. La serialización distingue también 1 de true.
    contenido = {k: v for k, v in actual.items() if k != "generado"}
    previsto = {k: v for k, v in esperado.items() if k != "generado"}
    if json.dumps(contenido, sort_keys=True) != json.dumps(previsto, sort_keys=True):
        raise ValueError(f"{ruta.name}: difiere de docs/material/")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comprobar", action="store_true")
    args = parser.parse_args(argv)
    procedencia = {} if args.comprobar else generado("python -m src.material")
    try:
        documentos = {n: documento(RAIZ, n, procedencia) for n in COLECCIONES}
        destino = RAIZ / DESTINO
        if not args.comprobar:
            destino.mkdir(parents=True, exist_ok=True)
        for nombre, datos in documentos.items():
            ruta = destino / f"{nombre}.json"
            if args.comprobar:
                comprobar_documento(ruta, datos, COLECCIONES[nombre])
            else:
                guardar_json(ruta, datos)
    except (ValueError, OSError) as error:
        print(error)
        return 1
    limites = len(documentos["limites"]["limites"])
    terminos = len(documentos["glosario"]["terminos"])
    resultado = "iguales a docs/material/" if args.comprobar else "escritos en web/datos/comun/"
    print(f"{limites} límites y {terminos} términos, {resultado}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
