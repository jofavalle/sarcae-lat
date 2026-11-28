"""Generación y comparación del material en una copia temporal."""

import json
import shutil

import pytest

from src import material


@pytest.fixture
def copia(tmp_path, monkeypatch):
    shutil.copytree(material.RAIZ / "docs/material", tmp_path / "docs/material")
    monkeypatch.setattr(material, "RAIZ", tmp_path)
    assert material.main([]) == 0
    return tmp_path


def test_documentos_completos_y_verificacion_de_solo_lectura(copia, capsys):
    destino = copia / "web/datos/comun"
    for nombre in ("limites", "glosario"):
        ruta = destino / f"{nombre}.json"
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        assert datos["contrato"] == 1
        assert set(datos["generado"]) == {"utc", "commit", "comando"}
        assert datos["fuentes"][0]["licencia"] == "CC-BY-4.0"
        assert datos["fuentes"][0]["nombre"] == f"docs/material/{nombre}.md"
        if nombre == "limites":
            assert len(datos["limites"]) == 6
            for limite in datos["limites"]:
                assert set(limite) == {"id", "titulo", "estudiante", "docente", "direccion"}
                assert limite["id"].isascii() and limite["id"].islower()
            assert datos["limites"][-1]["id"] == "la-maqueta-muestra-volumenes-no-el-interior"
            assert "patio y por dónde" in datos["limites"][-1]["estudiante"]
        else:
            assert len(datos["terminos"]) == 25
            assert datos["terminos"][0]["termino"] == "celda"
            assert all(set(fila) == {"termino", "definicion"} for fila in datos["terminos"])
        datos["generado"]["utc"] = "2026-01-01T00:00:00Z"
        ruta.write_text(json.dumps(datos), encoding="utf-8")
    antes = {ruta: ruta.read_bytes() for ruta in destino.iterdir()}
    assert material.main(["--comprobar"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "6 límites y 25 términos, iguales a docs/material/"
    assert antes == {ruta: ruta.read_bytes() for ruta in destino.iterdir()}


def test_ubica_una_palabra_en_su_limite_y_registro(copia, capsys):
    ruta = copia / "docs/material/limites.md"
    texto = ruta.read_text(encoding="utf-8")
    ruta.write_text(texto.replace("combina un programa", "combina un modelo", 1), encoding="utf-8")
    assert material.main(["--comprobar"]) == 1
    assert "ERA5 describe la zona, no la escuela: difiere docente" in capsys.readouterr().out


def test_detecta_termino_y_metadatos_modificados(copia, capsys):
    ruta = copia / "web/datos/comun/glosario.json"
    original = ruta.read_text(encoding="utf-8")
    datos = json.loads(original)
    datos["terminos"][0]["definicion"] = "otro texto"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    assert material.main(["--comprobar"]) == 1
    assert "celda: difiere definicion" in capsys.readouterr().out
    datos = json.loads(original)
    datos["fuentes"][0]["licencia"] = "CC0-1.0"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    assert material.main(["--comprobar"]) == 1
    assert "glosario.json" in capsys.readouterr().out


def test_diagnostica_registro_ausente(copia, capsys):
    ruta = copia / "docs/material/limites.md"
    texto = ruta.read_text(encoding="utf-8")
    inicio = texto.index("**Docentes.**")
    final = texto.index("**Dirección.**", inicio)
    ruta.write_text(texto[:inicio] + texto[final:], encoding="utf-8")
    assert material.main(["--comprobar"]) == 1
    assert "falta el registro docente" in capsys.readouterr().out
