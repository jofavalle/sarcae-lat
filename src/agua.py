"""Escorrentía y puntos bajos sobre el relieve de NASADEM de cada escuela (orden #63).

Lee solo `recortes/<slug>/nasadem/elevacion.csv` y escribe `web/datos/<slug>/agua.geojson`:
por dónde tiende a correr el agua según el relieve (líneas de escorrentía) y dónde tiende a
juntarse (puntos bajos). No simula caudal ni profundidad.

El método, en cuatro pasos:

1. relleno de depresiones con Priority-Flood+ε (Barnes, Lehman y Mulla, 2014, *Computers &
   Geosciences* 62: 117–127), con ε = 0,001 m, para que toda celda desagüe al borde;
2. direcciones D8 por la mayor pendiente, con la distancia diagonal √2;
3. acumulación de flujo en celdas, contando la propia;
4. líneas desde las celdas con 50 o más celdas de acumulación (unas 4,5 ha), encadenadas
   aguas abajo hasta la confluencia o el borde.

Los puntos bajos son las depresiones con un relleno de 0,5 m o más, medido sobre el relieve
original con un relleno sin ε, para que la rampa de ε no cuente como agua. Cada una se marca
en su celda más baja.

Uso, desde la raíz del repositorio:

    python -m src.agua --todas
    python -m src.agua --escuela sv-88118
    python -m src.agua --todas --comprobar
    python -m src.agua --distancia 13.97567 -89.34056 --escuela sv-88118
"""

import argparse
import heapq
import itertools
import json
import math
import sys
from collections import deque
from pathlib import Path

import numpy as np

from . import recortes
from .capas import fuente
from .relieve import EARTH_RADIUS_KM, grid_from_csv

RAIZ_DATOS = recortes.RAIZ / "web" / "datos"
RAIZ_RECORTES = recortes.RECORTES
ARCHIVO = "agua.geojson"
CONTRATO = 1

EPSILON_M = 0.001
UMBRAL_CELDAS = 50
UMBRAL_RELLENO_M = 0.5
RADIO_M = EARTH_RADIUS_KM * 1000.0

LIMITE = ("El relieve tiene cuadros de 30 m: no ve el patio, las canaletas ni los muros. "
          "La capa muestra por dónde tiende a correr el agua según el relieve, y no simula "
          "caudal ni profundidad.")
METODO = {
    "relleno": ("Priority-Flood+ε (Barnes, Lehman y Mulla, 2014, Computers & Geosciences "
                "62: 117–127), para que toda celda desagüe al borde del recorte"),
    "epsilon_m": EPSILON_M,
    "direcciones": "D8 por la mayor pendiente, con la distancia diagonal √2",
    "acumulacion": "en celdas, contando la propia y todas las que desaguan a ella",
    "lineas": ("desde las celdas que alcanzan el umbral, encadenadas aguas abajo hasta la "
               "confluencia o el borde"),
    "puntos_bajos": ("depresiones del relieve original, rellenadas sin ε; cada una se marca "
                     "en su celda más baja"),
}

# Los ocho vecinos (fila, columna, distancia en celdas): N, NE, E, SE, S, SO, O, NO. Con
# pendientes iguales gana el primero de esta lista.
VECINOS = tuple((di, dj, math.sqrt(2.0) if di and dj else 1.0)
                for di, dj in ((-1, 0), (-1, 1), (0, 1), (1, 1),
                               (1, 0), (1, -1), (0, -1), (-1, -1)))


# El método

def rellenar(z, epsilon=EPSILON_M):
    """Priority-Flood (Barnes et al., 2014): con `epsilon` > 0, el algoritmo 3 (+ε), que deja
    toda celda interior por encima de una vecina; con 0, el 2, el relleno plano."""
    filas, cols = z.shape
    lleno = np.asarray(z, dtype="float64").copy()
    cerrado = np.zeros(z.shape, dtype=bool)
    abiertos, pozo, orden = [], deque(), itertools.count()
    for i in range(filas):
        for j in range(cols):
            if i in (0, filas - 1) or j in (0, cols - 1):
                heapq.heappush(abiertos, (lleno[i, j], next(orden), i, j))
                cerrado[i, j] = True
    while abiertos or pozo:
        if pozo:
            i, j = pozo.popleft()
        else:
            _, _, i, j = heapq.heappop(abiertos)
        for di, dj, _ in VECINOS:
            a, b = i + di, j + dj
            if not (0 <= a < filas and 0 <= b < cols) or cerrado[a, b]:
                continue
            cerrado[a, b] = True
            if lleno[a, b] <= lleno[i, j]:
                lleno[a, b] = lleno[i, j] + epsilon
                pozo.append((a, b))
            else:
                heapq.heappush(abiertos, (lleno[a, b], next(orden), a, b))
    return lleno


def direcciones(lleno):
    """D8: el índice plano de la vecina de mayor pendiente, o -1 si no hay ninguna más baja
    (la celda desagua fuera del recorte). Las celdas del borde también siguen a una vecina
    más baja si la tienen: así un plano desagua por un solo borde."""
    filas, cols = lleno.shape
    alto = np.pad(lleno, 1, constant_values=np.inf)
    pendientes = np.stack([(lleno - alto[1 + di:1 + di + filas, 1 + dj:1 + dj + cols]) / d
                           for di, dj, d in VECINOS])
    mejor = pendientes.argmax(axis=0)
    filas_v = np.array([di for di, _, _ in VECINOS])[mejor] + np.arange(filas)[:, None]
    cols_v = np.array([dj for _, dj, _ in VECINOS])[mejor] + np.arange(cols)[None, :]
    receptor = np.where(pendientes.max(axis=0) > 0, filas_v * cols + cols_v, -1)
    return receptor.ravel()


def acumular(lleno, receptor):
    """Celdas que pasan por cada celda, contando la propia. El receptor siempre está más bajo,
    así que basta con recorrer de la más alta a la más baja."""
    acumulacion = np.ones(lleno.size, dtype="int64")
    for k in np.argsort(-lleno.ravel(), kind="stable"):
        if receptor[k] >= 0:
            acumulacion[receptor[k]] += acumulacion[k]
    return acumulacion


def trazar(acumulacion, receptor, umbral=UMBRAL_CELDAS):
    """Las líneas, como listas de índices planos de aguas arriba a aguas abajo. Empiezan en
    una cabecera (sin vecinas en el umbral que desagüen a ella) o en una confluencia, y
    acaban en la confluencia siguiente, incluida, o en la celda que desagua fuera."""
    canal = acumulacion >= umbral
    desde_canal = receptor[canal & (receptor >= 0)]
    donantes = np.bincount(desde_canal, minlength=acumulacion.size)
    inicio = canal & (donantes != 1)
    lineas = []
    for k in np.flatnonzero(inicio):
        camino = [int(k)]
        while receptor[camino[-1]] >= 0:
            camino.append(int(receptor[camino[-1]]))
            if inicio[camino[-1]]:
                break
        if len(camino) >= 2:
            lineas.append(camino)
    return lineas


def depresiones(z, umbral_m=UMBRAL_RELLENO_M):
    """Las depresiones con un relleno de `umbral_m` o más, medido sobre el relieve original:
    cada una, `{celda, relleno_m, celdas, miembros}`. En el relleno plano, las celdas que
    sube y se tocan comparten nivel, así que cada grupo conexo es una depresión."""
    z = np.asarray(z, dtype="float64")
    plano = rellenar(z, 0.0)
    subida = plano - z > 1e-9
    filas, cols = z.shape
    visto = np.zeros(z.shape, dtype=bool)
    halladas = []
    for i0, j0 in zip(*np.nonzero(subida)):
        if visto[i0, j0]:
            continue
        visto[i0, j0] = True
        miembros, cola = [], deque([(i0, j0)])
        while cola:
            i, j = cola.popleft()
            miembros.append(int(i * cols + j))
            for di, dj, _ in VECINOS:
                a, b = i + di, j + dj
                if 0 <= a < filas and 0 <= b < cols and subida[a, b] and not visto[a, b]:
                    visto[a, b] = True
                    cola.append((a, b))
        miembros.sort()
        alturas = z.ravel()[miembros]
        baja = miembros[int(np.argmin(alturas))]
        relleno = float(plano.ravel()[baja] - z.ravel()[baja])
        if relleno >= umbral_m - 1e-9:
            halladas.append({"celda": baja, "relleno_m": relleno, "celdas": len(miembros),
                             "miembros": miembros})
    return halladas


def calcular(z, umbral_celdas=UMBRAL_CELDAS, umbral_relleno_m=UMBRAL_RELLENO_M,
             epsilon=EPSILON_M):
    """Los cuatro pasos y los puntos bajos sobre una malla de alturas (filas de norte a sur)."""
    z = np.asarray(z, dtype="float64")
    lleno = rellenar(z, epsilon)
    receptor = direcciones(lleno)
    acumulacion = acumular(lleno, receptor)
    return {
        "lleno": lleno,
        "receptor": receptor,
        "acumulacion": acumulacion,
        "lineas": trazar(acumulacion, receptor, umbral_celdas),
        "puntos_bajos": depresiones(z, umbral_relleno_m),
    }


# Controles

def bordes(k, forma):
    """Los bordes del recorte en los que está la celda: norte, sur, oeste o este."""
    i, j = divmod(int(k), forma[1])
    return [nombre for nombre, en in (("norte", i == 0), ("sur", i == forma[0] - 1),
                                      ("oeste", j == 0), ("este", j == forma[1] - 1)) if en]


def subidas(z, lineas, puntos_bajos):
    """Los pasos de línea en los que la altura original sube fuera de un punto bajo
    rellenado: (línea, vértice). Una dirección invertida aparece aquí."""
    rellenadas = {m for p in puntos_bajos for m in p["miembros"]}
    plano = np.asarray(z, dtype="float64").ravel()
    return [(n, v) for n, linea in enumerate(lineas)
            for v, (a, b) in enumerate(zip(linea, linea[1:]))
            if plano[b] > plano[a] and a not in rellenadas and b not in rellenadas]


# La capa

def area_celda_m2(grid):
    """El área de una celda en el centro del recorte, en la esfera de radio medio."""
    lado = math.radians(grid.step) * RADIO_M
    centro = grid.top - (grid.values.shape[0] - 1) * grid.step / 2.0
    return lado * lado * math.cos(math.radians(centro))


def posicion(grid, k):
    i, j = divmod(int(k), grid.values.shape[1])
    return [round(grid.left + j * grid.step, 6), round(grid.top - i * grid.step, 6)]


def construir(grid, fuentes):
    """El GeoJSON sin `generado`, y lo que se calculó, para el resumen y los controles."""
    resultado = calcular(grid.values)
    area = area_celda_m2(grid)
    acumulacion = resultado["acumulacion"]
    rasgos = [{"type": "Feature",
               "geometry": {"type": "LineString", "coordinates": [posicion(grid, k) for k in linea]},
               "properties": {"tipo": "escorrentia", "acumulacion_celdas": int(acumulacion[linea[-1]])}}
              for linea in resultado["lineas"]]
    rasgos += [{"type": "Feature",
                "geometry": {"type": "Point", "coordinates": posicion(grid, p["celda"])},
                "properties": {"tipo": "punto_bajo", "relleno_m": round(p["relleno_m"], 2),
                               "area_m2": int(round(p["celdas"] * area))}}
               for p in resultado["puntos_bajos"]]
    documento = {
        "type": "FeatureCollection",
        "metadatos": {
            "contrato": CONTRATO,
            "fuentes": fuentes,
            "metodo": METODO,
            "umbral": {"escorrentia_celdas": UMBRAL_CELDAS,
                       "punto_bajo_relleno_m": UMBRAL_RELLENO_M},
            "celda_m2": int(round(area)),
            "limite": LIMITE,
        },
        "features": rasgos,
    }
    return documento, resultado


def preparar(slug, raiz_recortes=RAIZ_RECORTES):
    carpeta = raiz_recortes / slug / "nasadem"
    grid = grid_from_csv((carpeta / "elevacion.csv").read_bytes().decode("utf-8"))
    documento, resultado = construir(grid, [fuente(carpeta)])
    return grid, documento, resultado


def comprobar(slug, grid, documento, resultado, destino):
    """Los controles de --comprobar: (nombre, ok, detalle)."""
    publicado = json.loads((destino / ARCHIVO).read_text(encoding="utf-8"))
    generado = publicado.get("metadatos", {}).pop("generado", None)
    recortes.objeto_con_textos(generado, "utc", "commit", "comando")
    esperado = json.loads(json.dumps(documento, ensure_ascii=False))
    forma = grid.values.shape
    salidas = [k for k in np.flatnonzero(resultado["receptor"] < 0) if not bordes(k, forma)]
    mayor = int(np.argmax(resultado["acumulacion"]))
    malas = subidas(grid.values, resultado["lineas"], resultado["puntos_bajos"])
    return [
        (f"{ARCHIVO} es el que sale del recorte", publicado == esperado,
         "coincide" if publicado == esperado else "difiere: se regenera con python -m src.agua"),
        ("toda celda desagua al borde", not salidas,
         "ninguna salida interior" if not salidas else f"{len(salidas)} salidas interiores"),
        ("la mayor acumulación está en el borde", bool(bordes(mayor, forma)),
         f"celda {divmod(mayor, forma[1])}"),
        ("las líneas no suben fuera de un punto bajo", not malas,
         "en elevacion.csv" if not malas else f"{len(malas)} pasos suben, el primero {malas[0]}"),
    ]


def informar(slug, grid, resultado):
    forma = grid.values.shape
    acumulacion = resultado["acumulacion"]
    mayor = int(np.argmax(acumulacion))
    i, j = divmod(mayor, forma[1])
    lon, lat = posicion(grid, mayor)
    hectareas = acumulacion[mayor] * area_celda_m2(grid) / 10_000
    print(f"{slug}: malla de {forma[0]} × {forma[1]} celdas")
    print(f"  {len(resultado['lineas'])} líneas de escorrentía, desde {UMBRAL_CELDAS} celdas")
    puntos = resultado["puntos_bajos"]
    print(f"  {len(puntos)} puntos bajos, con {UMBRAL_RELLENO_M} m de relleno o más")
    if puntos:
        hondo = max(puntos, key=lambda p: (p["relleno_m"], p["celdas"]))
        sueltos = sum(1 for p in puntos if p["celdas"] == 1)
        de_un_metro = sum(1 for p in puntos if p["relleno_m"] < 1.5)
        print(f"    {sueltos} de una sola celda, {de_un_metro} con 1 m de relleno; el más hondo, "
              f"{hondo['relleno_m']:.2f} m en la celda {divmod(hondo['celda'], forma[1])}, "
              f"con {hondo['celdas']} celdas")
    print(f"  mayor acumulación: {acumulacion[mayor]} celdas, unas {hectareas:.0f} ha")
    print(f"  sale por la celda ({i}, {j}) del borde {' y '.join(bordes(mayor, forma)) or 'ninguno'}, "
          f"en {lat:.6f}, {lon:.6f}")


# La distancia

def distancia_segmento(p, a, b):
    """Distancia del punto p al segmento ab, en el plano."""
    ax, ay, bx, by, px, py = *a, *b, *p
    dx, dy = bx - ax, by - ay
    largo = dx * dx + dy * dy
    t = 0.0 if largo == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / largo))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def plano_local(lat0, lon0):
    """La aproximación plana alrededor de (lat0, lon0): de [lon, lat] a metros."""
    escala = math.cos(math.radians(lat0))
    return lambda c: (math.radians(c[0] - lon0) * RADIO_M * escala,
                      math.radians(c[1] - lat0) * RADIO_M)


def distancias(documento, lat, lon):
    """La distancia desde (lat, lon) a la línea y al punto bajo más cercanos, con su rasgo:
    {'escorrentia': (m, rasgo) o None, 'punto_bajo': (m, rasgo) o None}."""
    metros = plano_local(lat, lon)
    mejor = {"escorrentia": None, "punto_bajo": None}
    for rasgo in documento["features"]:
        tipo, coords = rasgo["properties"]["tipo"], rasgo["geometry"]["coordinates"]
        if tipo == "escorrentia":
            puntos = [metros(c) for c in coords]
            d = min(distancia_segmento((0.0, 0.0), a, b) for a, b in zip(puntos, puntos[1:]))
        else:
            d = math.hypot(*metros(coords))
        if mejor[tipo] is None or d < mejor[tipo][0]:
            mejor[tipo] = (d, rasgo)
    return mejor


def imprimir_distancia(slug, lat, lon):
    documento = json.loads((RAIZ_DATOS / slug / ARCHIVO).read_text(encoding="utf-8"))
    mejor = distancias(documento, lat, lon)
    print(f"{slug}, desde {lat:.6f}, {lon:.6f}:")
    if mejor["escorrentia"]:
        d, rasgo = mejor["escorrentia"]
        print(f"  línea de escorrentía más cercana: {d:.1f} m "
              f"({rasgo['properties']['acumulacion_celdas']} celdas en su extremo aguas abajo)")
    else:
        print("  no hay líneas de escorrentía")
    if mejor["punto_bajo"]:
        d, rasgo = mejor["punto_bajo"]
        print(f"  punto bajo más cercano: {d:.1f} m (relleno {rasgo['properties']['relleno_m']:.2f} m, "
              f"{rasgo['properties']['area_m2']} m²)")
    else:
        print("  no hay puntos bajos")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--escuela", metavar="SLUG")
    grupo.add_argument("--todas", action="store_true")
    parser.add_argument("--comprobar", action="store_true",
                        help="coteja agua.geojson con el cálculo desde el recorte, sin escribir")
    parser.add_argument("--distancia", nargs=2, type=float, metavar=("LAT", "LON"),
                        help="con --escuela, la distancia desde el punto a la línea y al punto "
                             "bajo más cercanos de agua.geojson")
    args = parser.parse_args(argv)
    escuelas = json.loads((RAIZ_DATOS / "escuelas.json").read_text(encoding="utf-8"))["escuelas"]
    slugs = [e["slug"] for e in escuelas if args.todas or e["slug"] == args.escuela]
    if not slugs:
        parser.error(f"escuela desconocida: {args.escuela}")
    if args.distancia:
        if args.todas or args.comprobar:
            parser.error("--distancia va con --escuela, sin --comprobar")
        return imprimir_distancia(slugs[0], *args.distancia)

    comando = "python -m src.agua " + ("--todas" if args.todas else f"--escuela {args.escuela}")
    estado = 0
    for slug in slugs:
        destino = RAIZ_DATOS / slug
        try:
            grid, documento, resultado = preparar(slug)
            informar(slug, grid, resultado)
            if args.comprobar:
                for nombre, ok, detalle in comprobar(slug, grid, documento, resultado, destino):
                    print(f"  [{'OK' if ok else 'FALLA'}] {nombre}: {detalle}")
                    estado |= 0 if ok else 1
            else:
                documento["metadatos"]["generado"] = recortes.generado(comando)
                recortes.guardar_json(destino / ARCHIVO, documento)
                print(f"  guardado en web/datos/{slug}/{ARCHIVO}")
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"{slug}: {error}")
            estado = 1
    print("agua en orden" if estado == 0 else "agua con fallos")
    return estado


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
