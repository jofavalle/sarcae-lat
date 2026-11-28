"""La maqueta genérica, generada en una copia temporal y validada con el contrato (#65)."""

import json
import shutil

from src import contrato, maqueta_generica


def test_escribe_una_maqueta_que_cumple_el_contrato_y_sin_puntos_geograficos(tmp_path, monkeypatch):
    origen = maqueta_generica.RAIZ / maqueta_generica.ESQUEMA
    (tmp_path / origen.relative_to(maqueta_generica.RAIZ)).parent.mkdir(parents=True)
    shutil.copy(origen, tmp_path / maqueta_generica.ESQUEMA)
    (tmp_path / "web/datos/comun").mkdir(parents=True)
    monkeypatch.setattr(maqueta_generica, "RAIZ", tmp_path)
    assert maqueta_generica.main([]) == 0

    datos = json.loads((tmp_path / maqueta_generica.DESTINO).read_text(encoding="utf-8"))
    errores = contrato.Errores()
    contrato.validar_maqueta_generica(errores, datos)
    assert errores.lista == []
    assert not {"latitud", "longitud", "huso_horas", "lat", "lon"} & set(datos)
    assert "calor_landsat" not in datos and "entorno_calor" not in datos
    assert datos["aviso"].startswith("Maqueta genérica: no es la escuela.")
    assert datos["fuentes"][0]["licencia"] == "CC-BY-4.0"
    assert datos["generado"]["comando"] == "python -m src.maqueta_generica"


def test_la_maqueta_versionada_esta_al_dia_con_el_esquema():
    versionada = json.loads((maqueta_generica.RAIZ / maqueta_generica.DESTINO).read_text(encoding="utf-8"))
    prevista = maqueta_generica.documento(maqueta_generica.RAIZ, versionada["generado"])
    assert versionada == prevista
