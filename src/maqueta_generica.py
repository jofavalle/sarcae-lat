"""Escribe web/datos/comun/maqueta-generica.json desde el esquema del prototipo (orden #65).

Toma de web/direcciones/escuela-esquema.json los volúmenes, superficies, cubiertas, árboles y
agua, en metros, y deja fuera su latitud, su longitud y su huso: la maqueta genérica no lleva
puntos geográficos, y el sol sale de la escuela elegida. Tampoco lleva el calor de Landsat del
prototipo, que era una cifra de ejemplo.

Añade lo que el esquema no tiene: la zona baja, el rectángulo de la esquina suroeste donde el
agua del esquema tiende a juntarse, alrededor de su punto bajo, y dos rutas de evacuación
hipotéticas, la A y la B, que salen del mismo punto junto al pabellón de aulas A. Ninguna es la
recomendada: la interfaz las compara con su largo, sus metros al sol y sus metros por la zona
baja, y con una pregunta para conversar. Sin puertas ni accesos: el punto de salida está fuera
del pabellón, junto a su alero.

Uso: python -m src.maqueta_generica
"""

import argparse
import copy
import hashlib
import json

from src.recortes import RAIZ, generado, guardar_json

ESQUEMA = "web/direcciones/escuela-esquema.json"
DESTINO = "web/datos/comun/maqueta-generica.json"
REPO = "https://github.com/jofavalle/sarcae-lat/blob/main/"
CLAVES = ("terreno", "superficies", "volumenes", "cubiertas", "arboles", "agua")

# x0, y0, x1, y1 en metros, como las superficies.
ZONA_BAJA = {"x0": -42, "y0": -27, "x1": -32, "y1": -18}

# Los segmentos van en ejes, para que el largo se pueda sumar a mano: la A mide 22 + 10 + 12 =
# 44 m, y la B, 24 + 34 = 58 m, 6 de ellos por la zona baja. Salen del frente del pabellón A,
# que se ve en la maqueta: el frente del B queda detrás de él, visto desde el suroeste.
RUTAS = [
    {"id": "a", "nombre": "Ruta A", "hasta": "la cancha",
     "puntos": [[-10, 10], [12, 10], [12, 0], [24, 0]]},
    {"id": "b", "nombre": "Ruta B", "hasta": "el terreno abierto del suroeste",
     "puntos": [[-10, 10], [-34, 10], [-34, -24]]},
]

AVISO = (
    "Maqueta genérica: no es la escuela. Son los volúmenes de una escuela tipo, dibujados por el "
    "equipo con medidas habituales de aulas, sin distribución interior, puertas ni accesos. "
    "El sol y las sombras son los de la escuela elegida; los edificios, no. Las rutas son "
    "hipotéticas, sobre una escuela genérica."
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
        }, {
            "nombre": "Zona baja y rutas hipotéticas, dibujo del equipo Itzpapálotl",
            "version": _sha256(json.dumps({"zona_baja": ZONA_BAJA, "rutas": RUTAS}, sort_keys=True)),
            "licencia": "CC-BY-4.0",
            "url": REPO + "src/maqueta_generica.py",
        }],
        "aviso": AVISO,
        "unidades": esquema["unidades"],
    }
    for clave in CLAVES:
        datos[clave] = esquema[clave]
    datos["agua"] = {**esquema["agua"], "zona_baja": copy.deepcopy(ZONA_BAJA)}
    datos["rutas"] = copy.deepcopy(RUTAS)
    return datos


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    datos = documento(RAIZ, generado("python -m src.maqueta_generica"))
    guardar_json(RAIZ / DESTINO, datos)
    print(f"{len(datos['volumenes'])} volúmenes, {len(datos['cubiertas'])} cubiertas, "
          f"{len(datos['arboles'])} árboles y {len(datos['rutas'])} rutas, escritos en {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
