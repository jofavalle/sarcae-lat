"""Pruebas de la escorrentía y los puntos bajos, sin red y con relieves fabricados (#63)."""

import math

import numpy as np

import src.agua as agua
import src.contrato as contrato
from src.relieve import Grid


def salidas(resultado, forma):
    """Las celdas que desaguan fuera del recorte, como (fila, columna)."""
    return [divmod(int(k), forma[1]) for k in np.flatnonzero(resultado["receptor"] < 0)]


def test_plano_inclinado_desagua_por_un_solo_borde():
    filas, cols = 20, 15
    z = 200.0 - 3.0 * np.arange(filas)[:, None] + np.zeros((1, cols))
    r = agua.calcular(z)
    assert {i for i, _ in salidas(r, z.shape)} == {filas - 1}
    assert {agua.bordes(i * cols + j, z.shape)[0] for i, j in salidas(r, z.shape)} == {"sur"}
    # Cada columna baja recta: la acumulación del borde sur es el número de filas.
    assert r["acumulacion"].reshape(z.shape)[-1].tolist() == [filas] * cols
    assert r["puntos_bajos"] == []
    assert agua.subidas(z, r["lineas"], r["puntos_bajos"]) == []


def test_cuenco_con_punto_bajo_de_relleno_conocido():
    # z = (i-5)² + (j-5)²: el borde más bajo está a 25 m, en el centro de cada lado, y el
    # fondo a 0 m. Se rellena hasta 25 m todo lo que está por debajo: 69 celdas.
    i, j = np.mgrid[0:11, 0:11]
    z = ((i - 5) ** 2 + (j - 5) ** 2).astype(float)
    r = agua.calcular(z)
    assert len(r["puntos_bajos"]) == 1
    punto = r["puntos_bajos"][0]
    assert divmod(punto["celda"], 11) == (5, 5)
    assert punto["relleno_m"] == 25.0
    assert punto["celdas"] == 69
    # Con ε, el fondo también desagua al borde, y por una sola salida.
    assert all(agua.bordes(f * 11 + c, z.shape) for f, c in salidas(r, z.shape))
    assert r["acumulacion"].max() >= 69
    assert agua.bordes(int(np.argmax(r["acumulacion"])), z.shape)


def test_cuenco_poco_profundo_no_es_punto_bajo():
    z = np.full((7, 7), 10.0)
    z[3, 3] = 9.6  # 0,4 m de relleno: por debajo del umbral
    assert agua.calcular(z)["puntos_bajos"] == []
    z[3, 3] = 9.5
    assert [p["relleno_m"] for p in agua.calcular(z)["puntos_bajos"]] == [0.5]


def test_valle_en_v_tiene_una_sola_linea_por_el_fondo():
    filas, cols, fondo = 60, 11, 5
    i, j = np.mgrid[0:filas, 0:cols]
    z = (100.0 - 2.0 * i + 3.0 * np.abs(j - fondo)).astype(float)
    r = agua.calcular(z)
    assert len(r["lineas"]) == 1
    linea = [divmod(k, cols) for k in r["lineas"][0]]
    assert {c for _, c in linea} == {fondo}
    assert [f for f, _ in linea] == list(range(linea[0][0], filas))
    assert r["acumulacion"][r["lineas"][0][0]] >= agua.UMBRAL_CELDAS
    assert linea[-1] == (filas - 1, fondo)
    assert r["acumulacion"][r["lineas"][0][-1]] == filas * cols
    assert r["puntos_bajos"] == []
    assert agua.subidas(z, r["lineas"], r["puntos_bajos"]) == []


def test_confluencia_corta_las_lineas():
    # Dos valles que se juntan: dos líneas que acaban en la confluencia y una que sale de ella.
    filas, cols = 80, 21
    i, j = np.mgrid[0:filas, 0:cols]
    brazo = np.where(i < 40, np.minimum(np.abs(j - 5), np.abs(j - 15)), np.abs(j - 10))
    z = (300.0 - 2.0 * i + 3.0 * brazo).astype(float)
    r = agua.calcular(z)
    finales = [linea[-1] for linea in r["lineas"]]
    inicios = [linea[0] for linea in r["lineas"]]
    compartidos = set(finales) & set(inicios)
    assert compartidos, "ninguna línea acaba donde empieza otra"
    for k in compartidos:
        assert finales.count(k) >= 2
    assert agua.subidas(z, r["lineas"], r["puntos_bajos"]) == []


def test_epsilon_deja_toda_celda_interior_con_salida():
    z = np.full((9, 9), 5.0)  # todo plano
    r = agua.calcular(z)
    assert all(agua.bordes(f * 9 + c, z.shape) for f, c in salidas(r, z.shape))
    assert (r["lleno"] - z).max() < 0.01


def test_distancia_cero_en_un_vertice_y_plana_a_una_linea():
    documento = {"features": [
        {"type": "Feature", "geometry": {"type": "LineString",
                                         "coordinates": [[-89.0, 14.0], [-89.0, 14.01]]},
         "properties": {"tipo": "escorrentia", "acumulacion_celdas": 60}},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-89.01, 14.0]},
         "properties": {"tipo": "punto_bajo", "relleno_m": 1.0, "area_m2": 900}},
    ]}
    d = agua.distancias(documento, 14.0, -89.0)
    assert d["escorrentia"][0] < 1e-6
    esperado = math.radians(0.01) * agua.RADIO_M * math.cos(math.radians(14.0))
    assert abs(d["punto_bajo"][0] - esperado) < 1e-6
    # A 0,005° al este de la línea, a media altura: la perpendicular.
    d = agua.distancias(documento, 14.005, -88.995)
    assert abs(d["escorrentia"][0] - esperado / 2) < 0.5


def test_la_capa_cumple_el_contrato():
    filas, cols, fondo = 60, 11, 5
    i, j = np.mgrid[0:filas, 0:cols]
    z = (100.0 - 2.0 * i + 3.0 * np.abs(j - fondo)).astype("int16")
    z[20, 2] -= 10  # una depresión al lado del valle: 59 m, con la vecina más baja a 64 m
    grid = Grid(z, top=14.0, left=-89.0, step=1.0 / 3600.0)
    fuente = {"nombre": "NASADEM_HGT", "version": "001", "licencia": "CC0-1.0",
              "url": "https://www.earthdata.nasa.gov/data/catalog/lpcloud-nasadem-hgt-001"}
    documento, resultado = agua.construir(grid, [fuente])
    documento["metadatos"]["generado"] = {"utc": "2026-11-28T18:00:00+00:00",
                                          "commit": "abcdef1", "comando": "python -m src.agua"}
    errores = []
    contrato.validar_agua(lambda ruta, mensaje: errores.append((ruta, mensaje)),
                          documento, "prueba", False, {})
    assert errores == []
    tipos = [f["properties"]["tipo"] for f in documento["features"]]
    assert tipos.count("escorrentia") == 1 and tipos.count("punto_bajo") == 1
    assert documento["metadatos"]["limite"] == agua.LIMITE
    assert contrato.vetadas(agua.LIMITE) == []
