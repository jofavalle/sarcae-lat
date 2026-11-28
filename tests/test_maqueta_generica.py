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


def test_las_rutas_se_suman_a_mano_y_el_validador_las_comprueba():
    datos = maqueta_generica.documento(maqueta_generica.RAIZ, {})
    largos = {r["id"]: sum(abs(b[0] - a[0]) + abs(b[1] - a[1])  # segmentos en ejes
                           for a, b in zip(r["puntos"], r["puntos"][1:])) for r in datos["rutas"]}
    assert largos == {"a": 44, "b": 58}
    assert datos["agua"]["zona_baja"] == {"x0": -42, "y0": -27, "x1": -32, "y1": -18}

    datos["rutas"][1]["hasta"] = "la puerta del fondo"
    datos["rutas"][0]["puntos"] = [[0, 0]]
    datos["agua"]["zona_baja"]["x1"] = -50
    errores = contrato.Errores()
    contrato.validar_maqueta_generica(errores, datos)
    campos = [c for c, _ in errores.lista]
    assert "rutas[1].hasta" in campos
    assert "rutas[0].puntos" in campos
    assert "agua.zona_baja" in campos


def test_la_maqueta_versionada_esta_al_dia_con_el_esquema():
    versionada = json.loads((maqueta_generica.RAIZ / maqueta_generica.DESTINO).read_text(encoding="utf-8"))
    prevista = maqueta_generica.documento(maqueta_generica.RAIZ, versionada["generado"])
    assert versionada == prevista
