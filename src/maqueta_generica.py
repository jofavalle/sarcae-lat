"""Escribe web/datos/comun/maqueta-generica.json desde el esquema del prototipo (orden #65).

Toma de web/direcciones/escuela-esquema.json los volúmenes, superficies, cubiertas, árboles y
agua, en metros, y deja fuera su latitud, su longitud y su huso: la maqueta genérica no lleva
puntos geográficos, y el sol sale de la escuela elegida. Tampoco lleva el calor de Landsat del
prototipo, que era una cifra de ejemplo.

Uso: python -m src.maqueta_generica
"""

import argparse
import hashlib
import json

from src.recortes import RAIZ, generado, guardar_json

ESQUEMA = "web/direcciones/escuela-esquema.json"
DESTINO = "web/datos/comun/maqueta-generica.json"
REPO = "https://github.com/jofavalle/sarcae-lat/blob/main/"
CLAVES = ("terreno", "superficies", "volumenes", "cubiertas", "arboles", "agua")

AVISO = (
    "Maqueta genérica: no es la escuela. Son los volúmenes de una escuela tipo, dibujados por el "
    "equipo con medidas habituales de aulas, sin distribución interior, puertas ni accesos. "
    "El sol y las sombras son los de la escuela elegida; los edificios, no."
)


def _sha256(texto):
    return "sha256:" + hashlib.sha256(texto.encode("utf-8")).hexdigest()


def documento(raiz, procedencia):
    texto = (raiz / ESQUEMA).read_text(encoding="utf-8")
    esquema = json.loads(texto)
    datos = {
        "contrato": 1,
        "generado": procedencia,
        "fuentes": [{
            "nombre": "Esquema de una escuela tipo, dibujo del equipo Itzpapálotl",
            "version": _sha256(texto),
            "licencia": "CC-BY-4.0",
            "url": REPO + ESQUEMA,
        }],
        "aviso": AVISO,
        "unidades": esquema["unidades"],
    }
    for clave in CLAVES:
        datos[clave] = esquema[clave]
    return datos


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    datos = documento(RAIZ, generado("python -m src.maqueta_generica"))
    guardar_json(RAIZ / DESTINO, datos)
    print(f"{len(datos['volumenes'])} volúmenes, {len(datos['cubiertas'])} cubiertas y "
          f"{len(datos['arboles'])} árboles, escritos en {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
