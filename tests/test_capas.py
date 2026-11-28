"""Pruebas sin red para convertir recortes de Earth Engine al contrato del mapa."""

import csv
import json

import pytest

from src import capas, contrato, recortes
from src.relieve import read_png

SLUG = "sv-88118"
ANILLO = [
    [-89.3405612, 13.9756712],
    [-89.3404612, 13.9756712],
    [-89.3404612, 13.9757712],
    [-89.3405612, 13.9757712],
    [-89.3405612, 13.9756712],
]
ESQUINAS = [[-89.35, 13.99], [-89.33, 13.99], [-89.33, 13.96], [-89.35, 13.96]]


def coleccion(ruta, atributos):
    recortes.guardar_json(ruta, {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ANILLO]},
             "properties": propiedades}
            for propiedades in atributos
        ],
    })


@pytest.fixture
def escuela(tmp_path, monkeypatch):
    datos = tmp_path / "web" / "datos"
    datos.mkdir(parents=True)
    recortes.guardar_json(datos / "escuelas.json", {"escuelas": [{"slug": SLUG, "huso_horas": -6}]})
    origen = tmp_path / "recortes"
    monkeypatch.setattr(capas, "RAIZ_DATOS", datos)
    monkeypatch.setattr(capas, "RAIZ_RECORTES", origen)
    landsat, worldcover, edificios = [origen / SLUG / nombre
                                     for nombre in ("landsat", "worldcover", "open-buildings")]
    for carpeta in (landsat, worldcover, edificios):
        carpeta.mkdir(parents=True)

    (landsat / "escenas.csv").write_text(
        "id,fecha,hora_utc,nubosidad\n"
        "l8a,2024-01-01,16:19:00,5.5\n"
        "l9a,2025-03-15,16:21:30,19.99\n"
        "l9b,2025-12-31,16:22:00,0\n",
        encoding="utf-8",
    )
    coleccion(landsat / "cuadros.geojson", [
        {"t_superficie_c": 31.26, "n_escenas": 3},
        {"t_superficie_c": 35.7, "n_escenas": 2},
        *({"n_escenas": 0} for _ in range(439)),
    ])
    coleccion(edificios / "edificios.geojson", [
        {"id": "con-altura", "altura_m": 4.26},
        {"id": "sin-altura", "altura_m": None},
    ])
    with (worldcover / "celdas.csv").open("w", newline="", encoding="utf-8") as salida:
        csv_celdas = csv.writer(salida)
        csv_celdas.writerow(("i", "j", "clase"))
        for j in reversed(range(210)):
            for i in reversed(range(210)):
                csv_celdas.writerow((i + 0.5, j + 0.5, 80 if (i, j) == (2, 1) else 50))
    recortes.guardar_json(worldcover / "esquinas.json", ESQUINAS)

    for carpeta in (landsat, worldcover, edificios):
        recortes.escribir(
            carpeta,
            fuente=carpeta.name,
            version="prueba",
            licencia="dominio-publico" if carpeta == landsat else "CC-BY-4.0",
            url_licencia="https://example.org/licencia",
            url_fuente="https://example.org/fuente",
            atribucion="Crédito de prueba",
            fecha_descarga="2026-11-28",
        )
    return datos / SLUG


def test_genera_y_comprueba_capas(escuela, capsys):
    assert capas.main(["--escuela", SLUG]) == 0
    assert capas.main(["--todas", "--comprobar"]) == 0
    informe = capsys.readouterr().out
    assert "3 escenas Landsat, paso medio 10:21 hora local" in informe
    assert "1 cuadros con dato, 440 sin dato. Rango 31.3 a 31.3 °C" in informe
    assert "1 edificios con altura estimada, 1 con altura supuesta" in informe

    calor = capas.leer_json(escuela / "calor.geojson")
    assert len(calor["features"]) == 441
    assert calor["features"][0]["properties"] == {
        "t_superficie_c": 31.3, "n_escenas": 3, "sin_dato": False,
    }
    assert calor["features"][1]["properties"] == {
        "t_superficie_c": None, "n_escenas": 2, "sin_dato": True,
    }
    capa_edificios = capas.leer_json(escuela / "edificios.geojson")
    edificios = capa_edificios["features"]
    assert edificios[0]["properties"] == {"altura": 4.3, "base": 0.0, "altura_supuesta": False}
    assert edificios[1]["properties"] == {"altura": 3.0, "base": 0.0, "altura_supuesta": True}
    assert edificios[1]["id"] == "sin-altura"
    assert edificios[0]["geometry"]["coordinates"][0][0] == [-89.340561, 13.975671]

    metadatos = capas.leer_json(escuela / "capas.json")
    assert metadatos["cobertura"]["esquinas"] == ESQUINAS
    assert metadatos["landsat"]["periodo"] == {"desde": "2024-01-01", "hasta": "2025-12-31"}
    assert metadatos["edificios"] == {"con_altura": 1, "sin_altura": 1}
    assert len(metadatos["fuentes"]) == 3
    assert all(f["atribucion"] == "Crédito de prueba" for f in metadatos["fuentes"])
    colores = {c["clase"]: bytes.fromhex(c["color"][1:]) for c in metadatos["clases"]}
    assert colores[80] == bytes.fromhex("6cc8e0")
    assert all(r <= max(g, b) for r, g, b in colores.values())
    imagen = read_png(escuela / "cobertura.png")
    assert imagen.shape == (210, 210, 3)
    assert bytes(imagen[1, 2]) == colores[80]
    assert bytes(imagen[2, 1]) == colores[50]

    errores = contrato.Errores()
    contrato.validar_calor(errores, calor, SLUG, False, {})
    contrato.validar_edificios(errores, capa_edificios, SLUG, False, {})
    contrato.validar_capas(errores, metadatos, SLUG, False, {})
    assert not errores.lista


def test_comprobar_detecta_una_capa_modificada(escuela, capsys):
    assert capas.main(["--todas"]) == 0
    ruta = escuela / "capas.json"
    datos = capas.leer_json(ruta)
    datos["edificios"]["sin_altura"] = 42
    recortes.guardar_json(ruta, datos)

    assert capas.main(["--escuela", SLUG, "--comprobar"]) == 1
    assert "capas.json: difiere" in capsys.readouterr().out
    assert capas.leer_json(ruta)["edificios"]["sin_altura"] == 42


@pytest.mark.parametrize("fecha,nubosidad", [("2026-01-01", "0"), ("2024-02-01", "20")])
def test_rechaza_escenas_fuera_del_filtro(tmp_path, fecha, nubosidad):
    ruta = tmp_path / "escenas.csv"
    ruta.write_text(f"id,fecha,hora_utc,nubosidad\nuna,{fecha},16:00:00,{nubosidad}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="fecha o nubosidad fuera del filtro"):
        capas.estadisticas_escenas(ruta, -6)
