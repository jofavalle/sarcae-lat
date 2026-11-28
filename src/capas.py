"""Genera las capas del mapa a partir de los recortes versionados de la orden #62."""

import argparse
import csv
import json
import math
from datetime import date, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from . import recortes
from .relieve import read_png, write_png

RAIZ_DATOS = recortes.RAIZ / "web" / "datos"
RAIZ_RECORTES = recortes.RECORTES
DESDE = date(2024, 1, 1)
HASTA_EXCLUSIVO = date(2026, 1, 1)
NUM_CUADROS = 21 ** 2
LADO_COBERTURA = 210

# Umbral de CLOUD_COVER por escena; el mismo que declara `nubes` en gee/recortes.js.
NUBES_ESCENA = {
    "sv-88118": 20,
    "co-nicolas-esguerra": 60,
    "ve-rafael-maria-baralt": 20,
}

PALETA = {
    0: ("Sin dato", "#414653"),
    10: ("Arbolado", "#406857"),
    20: ("Matorral", "#686846"),
    30: ("Pastos", "#536e50"),
    40: ("Cultivos", "#78784a"),
    50: ("Zona construida", "#738094"),
    60: ("Suelo desnudo o con poca vegetación", "#73736a"),
    70: ("Nieve y hielo", "#bbc8d4"),
    80: ("Agua permanente", "#6cc8e0"),
    90: ("Humedal herbáceo", "#496762"),
    95: ("Manglar", "#35676b"),
    100: ("Musgos y líquenes", "#7f8258"),
}

LIMITE_CALOR = (
    "Landsat estima la temperatura de techos y suelos cuando pasa el satélite. "
    "La temperatura del aire se mide por separado."
)
LIMITE_EDIFICIOS = (
    "Los volúmenes representan contornos exteriores y sus alturas son estimaciones. "
    "El error absoluto medio fue de 1,5 m en la evaluación del modelo en Norteamérica, "
    "Europa y Japón."
)


def leer_json(ruta):
    return json.loads(ruta.read_text(encoding="utf-8"))


def fuente(carpeta):
    recortes.comprobar(carpeta)
    manifiesto = leer_json(carpeta / recortes.MANIFIESTO)
    return {
        **manifiesto["fuente"],
        "licencia": manifiesto["licencia"]["spdx"],
        "atribucion": manifiesto["atribucion"],
    }


def cabecera(fuentes):
    return {"contrato": 1, "fuentes": fuentes}


def estadisticas_escenas(ruta, huso_horas, nubosidad_max):
    ids = set()
    segundos_utc = 0
    with ruta.open(encoding="utf-8-sig", newline="") as entrada:
        for fila in csv.DictReader(entrada):
            identidad = fila["id"]
            fecha = date.fromisoformat(fila["fecha"])
            hora = time.fromisoformat(fila["hora_utc"])
            nubosidad = float(fila["nubosidad"])
            if not identidad or identidad in ids:
                raise ValueError(f"{ruta.name}: escena vacía o repetida ({identidad!r})")
            if not DESDE <= fecha < HASTA_EXCLUSIVO or not 0 <= nubosidad < nubosidad_max:
                raise ValueError(f"{ruta.name}: fecha o nubosidad fuera del filtro en {identidad}")
            if hora.tzinfo is not None:
                raise ValueError(f"{ruta.name}: hora_utc debe venir en UTC sin sufijo en {identidad}")
            ids.add(identidad)
            segundos_utc += hora.hour * 3600 + hora.minute * 60 + hora.second
    if not ids:
        raise ValueError(f"{ruta.name}: no hay escenas térmicas para calcular la hora de paso")
    minutos_utc = round(segundos_utc / (60 * len(ids)))
    minutos_locales = (minutos_utc + huso_horas * 60) % (24 * 60)
    hora, minuto = divmod(minutos_locales, 60)
    return {
        "periodo": {"desde": DESDE.isoformat(), "hasta": (HASTA_EXCLUSIVO - timedelta(days=1)).isoformat()},
        "escenas": len(ids),
        "hora_local": f"{hora:02d}:{minuto:02d}",
    }


def posicion(xy):
    lon, lat = xy
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError(f"posición WGS84 fuera de rango: {xy!r}")
    return [round(lon, 6), round(lat, 6)]


def poligono(anillos):
    if not anillos:
        raise ValueError("polígono sin anillos")
    resultado = []
    for anillo in anillos:
        puntos = []
        for xy in anillo:
            punto = posicion(xy)
            if not puntos or punto != puntos[-1]:
                puntos.append(punto)
        if len(puntos) < 4 or puntos[0] != puntos[-1]:
            raise ValueError("anillo abierto o degenerado al redondear su contorno")
        lon0, lat0 = puntos[0]
        area_doble = sum((lon1 - lon0) * (lat2 - lat0) - (lon2 - lon0) * (lat1 - lat0)
                         for (lon1, lat1), (lon2, lat2) in zip(puntos, puntos[1:]))
        if area_doble == 0:
            raise ValueError("anillo sin área al redondear su contorno")
        # GeoJSON usa sentido antihorario en el exterior y horario en los huecos.
        if (area_doble > 0) != (not resultado):
            puntos.reverse()
        resultado.append(puntos)
    return resultado


def rasgos(ruta):
    datos = leer_json(ruta)
    if datos["type"] != "FeatureCollection" or not isinstance(datos["features"], list):
        raise ValueError(f"{ruta.name}: se esperaba una colección GeoJSON")
    return datos["features"]


def capa_calor(ruta, origen, numero_escenas):
    cuadros = rasgos(ruta)
    if len(cuadros) != NUM_CUADROS:
        raise ValueError(f"{ruta.name}: se esperaban {NUM_CUADROS} cuadros, hay {len(cuadros)}")
    salida = []
    for cuadro in cuadros:
        props = cuadro["properties"]
        n = props["n_escenas"]
        if isinstance(n, bool) or not 0 <= n <= numero_escenas or int(n) != n:
            raise ValueError(f"{ruta.name}: n_escenas inválido ({n!r})")
        sin_dato = n < 3
        valor = None if sin_dato else props["t_superficie_c"]
        if not sin_dato and (valor is None or not math.isfinite(valor)):
            raise ValueError(f"{ruta.name}: falta la temperatura de un cuadro con {n} escenas")
        geo = cuadro["geometry"]
        if geo["type"] != "Polygon":
            raise ValueError(f"{ruta.name}: un cuadro debe ser un Polygon")
        salida.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": poligono(geo["coordinates"])},
            "properties": {
                "t_superficie_c": None if sin_dato else round(valor, 1),
                "n_escenas": int(n),
                "sin_dato": sin_dato,
            },
        })
    return {
        "type": "FeatureCollection",
        "metadatos": {**cabecera([origen]), "limite": LIMITE_CALOR},
        "features": salida,
    }


def capa_edificios(ruta, origen):
    salida = []
    for edificio in rasgos(ruta):
        props = edificio["properties"]
        altura = props.get("altura_m")
        if altura is not None and not 0 <= altura <= 100:
            raise ValueError(f"{ruta.name}: altura fuera de rango en {props['id']}")
        geo = edificio["geometry"]
        tipo = geo["type"]
        if tipo == "Polygon":
            coordenadas = poligono(geo["coordinates"])
        elif tipo == "MultiPolygon":
            coordenadas = [poligono(anillos) for anillos in geo["coordinates"]]
        else:
            raise ValueError(f"{ruta.name}: contorno {tipo!r} en {props['id']}")
        salida.append({
            "type": "Feature",
            "id": props["id"],
            "geometry": {"type": tipo, "coordinates": coordenadas},
            "properties": {
                "altura": 3.0 if altura is None else round(altura, 1),
                "base": 0.0,
                "altura_supuesta": altura is None,
            },
        })
    return {
        "type": "FeatureCollection",
        "metadatos": {**cabecera([origen]), "limite": LIMITE_EDIFICIOS},
        "features": salida,
    }


def imagen_cobertura(ruta):
    clases = np.full((LADO_COBERTURA, LADO_COBERTURA), -1, dtype=np.int16)
    with ruta.open(encoding="utf-8-sig", newline="") as entrada:
        for fila in csv.DictReader(entrada):
            x, y = float(fila["i"]), float(fila["j"])
            if not all(0 <= valor < LADO_COBERTURA and valor % 1 in (0, 0.5)
                       for valor in (x, y)):
                raise ValueError(f"{ruta.name}: posición de celda inválida ({x}, {y})")
            # Earth Engine entrega la posición del centro de cada píxel.
            i, j, clase = int(x), int(y), int(fila["clase"])
            if clases[j, i] != -1 or clase not in PALETA:
                raise ValueError(f"{ruta.name}: celda ({i}, {j}) repetida o con clase inválida")
            clases[j, i] = clase
    faltan = int(np.count_nonzero(clases == -1))
    if faltan:
        raise ValueError(f"{ruta.name}: faltan {faltan} celdas de {clases.size}")

    colores = np.zeros((max(PALETA) + 1, 3), dtype=np.uint8)
    for clave, (_, color) in PALETA.items():
        colores[clave] = list(bytes.fromhex(color[1:]))
    leyenda = [{"clase": clave, "nombre": nombre, "color": color}
               for clave, (nombre, color) in PALETA.items() if clave or np.any(clases == 0)]
    return colores[clases], leyenda


def preparar(escuela):
    carpeta = RAIZ_RECORTES / escuela["slug"]
    landsat, worldcover, open_buildings = (carpeta / nombre
                                         for nombre in ("landsat", "worldcover", "open-buildings"))
    fuentes = [fuente(ruta) for ruta in (landsat, worldcover, open_buildings)]
    escenas = estadisticas_escenas(landsat / "escenas.csv", escuela["huso_horas"],
                                   NUBES_ESCENA[escuela["slug"]])
    calor = capa_calor(landsat / "cuadros.geojson", fuentes[0], escenas["escenas"])
    edificios = capa_edificios(open_buildings / "edificios.geojson", fuentes[2])
    rgb, clases = imagen_cobertura(worldcover / "celdas.csv")
    esquinas = [posicion(xy) for xy in leer_json(worldcover / "esquinas.json")]
    if len(esquinas) != 4:
        raise ValueError("esquinas.json: se esperaban cuatro esquinas en orden de MapLibre")
    sin_altura = sum(f["properties"]["altura_supuesta"] for f in edificios["features"])
    capas = {
        **cabecera(fuentes),
        "cobertura": {"esquinas": esquinas},
        "clases": clases,
        "landsat": escenas,
        "edificios": {"con_altura": len(edificios["features"]) - sin_altura, "sin_altura": sin_altura},
    }
    return {"calor.geojson": calor, "edificios.geojson": edificios, "capas.json": capas}, rgb


def escribir(destino, documentos, rgb, comando):
    generado = recortes.generado(comando)
    destino.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destino) as temporal:
        carpeta = Path(temporal)
        for nombre, documento in documentos.items():
            documento.get("metadatos", documento)["generado"] = generado
            recortes.guardar_json(carpeta / nombre, documento)
        write_png(carpeta / "cobertura.png", rgb)
        for nombre in (*documentos, "cobertura.png"):
            (carpeta / nombre).replace(destino / nombre)


def comprobar(destino, documentos, rgb):
    for nombre, esperado in documentos.items():
        datos = leer_json(destino / nombre)
        generado = datos.get("metadatos", datos).pop("generado", None)
        recortes.objeto_con_textos(generado, "utc", "commit", "comando")
        if datos != esperado:
            raise ValueError(f"{nombre}: difiere de las capas calculadas desde los recortes")
    if not np.array_equal(read_png(destino / "cobertura.png"), rgb):
        raise ValueError("cobertura.png: difiere de las clases calculadas desde el recorte")


def informar(slug, documentos):
    escenas = documentos["capas.json"]["landsat"]
    medidas = [f["properties"]["t_superficie_c"] for f in documentos["calor.geojson"]["features"]
              if not f["properties"]["sin_dato"]]
    conteo = documentos["capas.json"]["edificios"]
    rango = f"{min(medidas):.1f} a {max(medidas):.1f} °C" if medidas else "sin datos"
    print(f"{slug}: {escenas['escenas']} escenas Landsat, paso medio {escenas['hora_local']} hora local")
    print(f"  {len(medidas)} cuadros con dato, {NUM_CUADROS - len(medidas)} sin dato. Rango {rango}")
    print(f"  {conteo['con_altura']} edificios con altura estimada, {conteo['sin_altura']} con altura supuesta")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--escuela", metavar="SLUG")
    grupo.add_argument("--todas", action="store_true")
    parser.add_argument("--comprobar", action="store_true", help="coteja las capas sin escribir")
    args = parser.parse_args(argv)
    escuelas = leer_json(RAIZ_DATOS / "escuelas.json")["escuelas"]
    seleccion = [e for e in escuelas if args.todas or e["slug"] == args.escuela]
    if not seleccion:
        parser.error(f"escuela desconocida: {args.escuela}")

    comando = "python -m src.capas " + ("--todas" if args.todas else f"--escuela {args.escuela}")
    estado = 0
    for escuela in seleccion:
        slug = escuela["slug"]
        destino = RAIZ_DATOS / slug
        try:
            documentos, rgb = preparar(escuela)
            if args.comprobar:
                comprobar(destino, documentos, rgb)
            else:
                escribir(destino, documentos, rgb, comando)
            informar(slug, documentos)
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f"{slug}: {error}")
            estado = 1
    return estado


if __name__ == "__main__":
    raise SystemExit(main())
