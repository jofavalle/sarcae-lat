"""Pruebas de `src.escuelas`, sin red.

El archivo se fabrica en cada prueba, con las coordenadas de `web/datos/escuelas.json` pero
sin depender de él, y se le mete un error de cada tipo para ver que `comprobar` lo nombra.
"""

import copy
import json
from decimal import Decimal

import pytest

import src.escuelas as escuelas


def _escuela(slug, iso, lat, lon, huso, ancla, est_lat, est_lon):
    return {
        "slug": slug, "nombre": slug, "codigo": None, "municipio": "m", "division": "d",
        "pais": "p", "iso_pais": iso, "lat": Decimal(lat), "lon": Decimal(lon),
        "huso_horas": huso, "ancla": ancla,
        "estacion": {"nombre": "e", "lat": Decimal(est_lat), "lon": Decimal(est_lon),
                     "distancia_km": Decimal("0.0")},
        "fuente_coordenadas": {"nombre": "f", "url": "https://example.org/a/b",
                               "fecha_consulta": "2026-11-28", "metodo": "directorio",
                               "licencia": None},
    }


def _valido():
    doc = {
        "contrato": 1,
        "generado": {"utc": "2026-11-28T12:00:00+00:00", "commit": "abc",
                     "comando": "python -m src.escuelas"},
        "escuelas": [
            _escuela("sv-88118", "SV", "13.97567", "-89.34056", -6, True, "13.97", "-89.53"),
            _escuela("co-nicolas-esguerra", "CO", "4.63279", "-74.12200", -5, False,
                     "4.7016", "-74.1469"),
            _escuela("ve-rafael-maria-baralt", "VE", "10.67002", "-71.62749", -4, False,
                     "10.5582", "-71.7279"),
        ],
    }
    for escuela in doc["escuelas"]:
        escuela["estacion"]["distancia_km"] = escuelas.distancia(escuela)
    return doc


def test_un_grado_de_latitud():
    assert round(escuelas.haversine_km(0.0, 0.0, 1.0, 0.0), 1) == 111.2
    assert round(escuelas.haversine_km(13.0, -89.0, 14.0, -89.0), 1) == 111.2


def test_un_grado_de_longitud_en_el_ecuador_y_a_60_grados():
    assert round(escuelas.haversine_km(0.0, 0.0, 0.0, 1.0), 1) == 111.2
    # A 60° el paralelo mide la mitad; el círculo máximo corta un poco por dentro.
    assert 55.5 < escuelas.haversine_km(60.0, 0.0, 60.0, 1.0) < 55.6


def test_distancias_de_las_tres_sedes():
    km = {e["slug"]: float(e["estacion"]["distancia_km"]) for e in _valido()["escuelas"]}
    assert 18.0 <= km["sv-88118"] <= 23.0
    assert 7.0 <= km["co-nicolas-esguerra"] <= 9.0
    assert 15.5 <= km["ve-rafael-maria-baralt"] <= 17.5


def test_el_archivo_valido_pasa():
    assert escuelas.comprobar(_valido()) == []


def _cambia(doc, camino, valor):
    destino = doc
    for clave in camino[:-1]:
        destino = destino[clave]
    destino[camino[-1]] = valor


@pytest.mark.parametrize("tipo, camino, valor", [
    ("slug", ("escuelas", 1, "slug"), "co-esguerra"),
    ("rango", ("escuelas", 0, "lat"), Decimal("93.97567")),
    ("rango", ("escuelas", 0, "lon"), Decimal("-189.34056")),
    ("rango", ("escuelas", 2, "estacion", "lat"), Decimal("-91.0")),
    ("huso", ("escuelas", 1, "huso_horas"), -15),
    ("huso", ("escuelas", 1, "huso_horas"), -5.5),
    ("decimales", ("escuelas", 1, "lon"), Decimal("-74.122")),
    ("decimales", ("escuelas", 2, "lat"), Decimal("10.670015")),
    ("fecha", ("escuelas", 0, "fuente_coordenadas", "fecha_consulta"), "28/11/2026"),
    ("fecha", ("generado", "utc"), "ayer"),
    ("ruta", ("generado", "comando"), "python C:\\proyecto\\src\\escuelas.py"),
    ("ruta", ("escuelas", 0, "fuente_coordenadas", "url"), "/datos/sedes.csv"),
    ("distancia", ("escuelas", 2, "estacion", "distancia_km"), Decimal("16.5")),
    ("ancla", ("escuelas", 1, "ancla"), True),
    ("campos", ("contrato",), 2),
    ("campos", ("escuelas", 0, "fuente_coordenadas", "metodo"), "a-ojo"),
])
def test_cada_error_se_nombra(tipo, camino, valor):
    doc = _valido()
    _cambia(doc, camino, valor)
    errores = escuelas.comprobar(doc)
    assert errores, f"no detectó el error de tipo {tipo}"
    assert all(e.startswith(f"{tipo}:") for e in errores), errores


def test_un_campo_que_falta():
    doc = _valido()
    del doc["escuelas"][0]["estacion"]["distancia_km"]
    errores = escuelas.comprobar(doc)
    assert errores == ["campos: sv-88118 no tiene estacion.distancia_km"]


def test_una_escuela_que_no_es_un_objeto():
    doc = _valido()
    doc["escuelas"][2] = "ve-rafael-maria-baralt"
    errores = escuelas.comprobar(doc)
    assert "campos: escuelas[2] no es un objeto" in errores


def test_grados_por_radianes_o_lat_por_lon_dan_otra_cifra():
    sv = _valido()["escuelas"][0]
    bien = float(sv["estacion"]["distancia_km"])
    cambiada = escuelas.haversine_km(sv["lon"], sv["lat"], sv["estacion"]["lon"],
                                     sv["estacion"]["lat"])
    assert abs(cambiada - bien) > 0.5


def test_escribir_conserva_los_decimales(tmp_path):
    path = tmp_path / "escuelas.json"
    doc = _valido()
    escuelas.escribir(path, doc)
    texto = path.read_text(encoding="utf-8")
    assert '"lon": -74.12200' in texto
    assert json.loads(texto)["escuelas"][1]["lat"] == 4.63279
    assert escuelas.leer(path) == doc
    assert escuelas.comprobar(escuelas.leer(path)) == []
