"""El recorrido guiado: marcadores, registros, preguntas y lenguaje, sin red, contra el
ejemplo del contrato copiado en una carpeta temporal."""

import copy
import json
import shutil

import pytest

from src import contrato, recorrido

FUENTE = recorrido.RAIZ / "docs/material/recorrido/sv-88118.json"
EJEMPLO = recorrido.RAIZ / "web/datos/ejemplo"


@pytest.fixture
def caso(tmp_path):
    """Una copia del ejemplo y de la fuente, con una función que escribe la fuente cambiada
    y ejecuta el script contra la copia."""
    datos = tmp_path / "ejemplo"
    shutil.copytree(EJEMPLO, datos)
    (datos / "recorrido.json").unlink()
    fuente = json.loads(FUENTE.read_text(encoding="utf-8"))

    def ejecutar(cambio=None, *extra):
        doc = copy.deepcopy(fuente)
        if cambio:
            cambio(doc)
        ruta = tmp_path / "fuente.json"
        ruta.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return recorrido.main(["--fuente", str(ruta), "--datos", str(datos),
                               "--salida", str(datos / "recorrido.json"), *extra])

    return datos, ejecutar


def _leer(ruta):
    return json.loads(ruta.read_text(encoding="utf-8"))


def test_la_fuente_contra_el_ejemplo_cumple_el_contrato(caso, capsys):
    datos, ejecutar = caso
    assert ejecutar() == 0
    doc = _leer(datos / "recorrido.json")
    assert doc["contrato"] == 1 and doc["escuela"] == "ejemplo" and doc["ejemplo"] is True
    assert set(doc["generado"]) == {"utc", "commit", "comando"}
    assert doc["fuentes"][0]["licencia"] == "CC-BY-4.0"
    assert recorrido.PARADAS_MIN <= len(doc["paradas"]) <= recorrido.PARADAS_MAX
    salida = capsys.readouterr().out
    assert "{{clima.calor.horas_1996_2025}} = 349,7" in salida
    assert "{{clima.episodios.lista.0.fecha|fecha}} = 17 de septiembre de 2008" in salida
    texto = json.dumps(doc["paradas"], ensure_ascii=False)
    assert "{{" not in texto and "349,7" in texto and "85,3" in texto
    # La pregunta de los aleros, literal (#23), y la zona de diseño de escuela.json.
    aleros = next(p for p in doc["paradas"] if p["id"] == "aleros")
    assert aleros["pregunta"]["direccion"] == ("¿Qué ventanas reciben sol directo por la tarde y "
                                               "qué sombra les dan los aleros o parteluces?")
    assert "tropical caliente" in aleros["texto"]["direccion"]
    # El validador del contrato lo acepta.
    informe = contrato.Informe()
    contrato.escuela(datos, informe, contrato.comunes(datos.parent, informe))
    assert informe.errores == []


def test_comprobar_compara_sin_el_bloque_generado(caso, capsys):
    datos, ejecutar = caso
    assert ejecutar() == 0
    ruta = datos / "recorrido.json"
    doc = _leer(ruta)
    doc["generado"]["utc"] = "2026-01-01T00:00:00+00:00"
    ruta.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    assert ejecutar(None, "--comprobar") == 0
    doc["paradas"][0]["titulo"] = "Otro título"
    ruta.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    assert ejecutar(None, "--comprobar") == 1
    assert "distinto en paradas" in capsys.readouterr().out


def test_datos_ficticios_se_repiten_y_se_avisan(caso, capsys):
    datos, ejecutar = caso
    clima = _leer(datos / "clima.json")
    clima["datos_ficticios"] = "Serie ficticia de prueba."
    (datos / "clima.json").write_text(json.dumps(clima, ensure_ascii=False), encoding="utf-8")
    assert ejecutar() == 0
    assert _leer(datos / "recorrido.json")["datos_ficticios"] == "Serie ficticia de prueba."
    assert "AVISO, DATOS FICTICIOS: Serie ficticia de prueba." in capsys.readouterr().out


def _texto(i, reg, nuevo):
    def cambio(doc):
        doc["paradas"][i]["texto"][reg] = nuevo
    return cambio


@pytest.mark.parametrize("cambio, error", [
    (_texto(1, "docente", "Son {{clima.calor.horas_2000_2020}} horas al año."),
     "{{clima.calor.horas_2000_2020}}: clima.calor.horas_2000_2020 no está en clima.json"),
    (_texto(1, "docente", "Son {{clima.calor.horas_1996_2025}} horas {{ sin cerrar."),
     "paradas[1].texto.docente: lleva un marcador sin resolver"),
    (_texto(1, "docente", "Del {{clima.episodios.lista.0.fecha|mes}}."),
     "el filtro «mes» no existe"),
    (lambda d: d["paradas"][2]["pregunta"].update(docente="¿Qué ventanas dan al oeste."),
     "paradas[2].pregunta.docente: la pregunta no va entre «¿» y «?»"),
    (_texto(3, "estudiante", "El calor es un riesgo para la escuela."),
     "paradas[3].texto.estudiante: lleva «riesgo»"),
    (_texto(5, "direccion", "Mira por dónde entra el agua por la puerta."),
     "paradas[5].texto.direccion: lleva «puerta»"),
    (lambda d: d["paradas"][4]["texto"].pop("docente"),
     "paradas[4].texto.docente: falta el registro"),
    (lambda d: d["paradas"][4]["pregunta"].pop("estudiante"),
     "paradas[4].pregunta.estudiante: falta el registro"),
    (_texto(1, "estudiante", "Hubo unas 350 horas al año sobre 27 °C."),
     "paradas[1].texto.estudiante: «350» está escrita a mano"),
    (_texto(0, "docente", "x" * 451),
     "paradas[0].texto.docente: tiene 451 caracteres, y son 450 como mucho"),
    (lambda d: d["paradas"].__delitem__(slice(4, None)),
     "paradas: son 4, y van de 5 a 7"),
])
def test_un_error_impide_escribir(caso, capsys, cambio, error):
    datos, ejecutar = caso
    assert ejecutar(cambio) == 1
    salida = capsys.readouterr().out
    assert error in salida
    assert "no se escribe" in salida
    assert not (datos / "recorrido.json").exists()


def test_formato_de_las_cifras():
    assert recorrido.formatear(2019.4) == "2019,4"
    assert recorrido.formatear(-1.2) == "−1,2"
    assert recorrido.formatear(300) == "300"
    assert recorrido.formatear([1961, 1990]) == "1961–1990"
    assert recorrido.formatear("2021-06-16", "fecha") == "16 de junio de 2021"
    for malo in (None, True, {"valor": 1}, [1, 2, 3], ""):
        with pytest.raises(recorrido.SinResolver):
            recorrido.formatear(malo)


def test_la_fuente_solo_escribe_a_mano_las_cifras_del_metodo():
    fuente = json.loads(FUENTE.read_text(encoding="utf-8"))
    assert recorrido.cifras_a_mano(fuente) == []
