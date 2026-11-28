"""Controles del manifiesto, con recortes fabricados en un directorio temporal."""

import hashlib
import json

import pytest

from src import recortes

METADATOS = {
    "fuente": "NASADEM", "version": "v001", "licencia": "CC0-1.0",
    "url_licencia": "https://creativecommons.org/publicdomain/zero/1.0/",
    "atribucion": "NASA JPL. https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001",
    "fecha_descarga": "2026-11-28",
}


@pytest.fixture
def carpeta(tmp_path):
    destino = tmp_path / "escuela" / "nasadem"
    destino.mkdir(parents=True)
    for nombre in ("b.csv", "a.csv"):
        (destino / nombre).write_bytes(b"altura\n25\n")
    return destino


def leer(carpeta):
    return json.loads((carpeta / "manifiesto.json").read_text(encoding="utf-8"))


def verificar(carpeta):
    return recortes.main(["--comprobar", str(carpeta)])


def test_cli_y_funcion_comparten_el_formato(carpeta, capsys):
    args = ["--escribir", str(carpeta)]
    for campo, valor in METADATOS.items():
        args.extend(["--" + campo.replace("_", "-"), valor])
    assert recortes.main(args) == 0
    datos = leer(carpeta)
    assert datos["escuela"] == "escuela"
    assert datos["fuente"]["url"].endswith("/lpcloud-nasadem-hgt-001")
    assert datos["licencia"] == {"spdx": "CC0-1.0", "url": METADATOS["url_licencia"]}
    assert str(carpeta) not in datos["generado"]["comando"]
    assert datos["atribucion"] == METADATOS["atribucion"]
    archivos = datos["archivos"]
    assert [item["nombre"] for item in archivos] == ["a.csv", "b.csv"]
    assert archivos[0] == {"nombre": "a.csv", "bytes": 10,
                           "sha256": hashlib.sha256(b"altura\n25\n").hexdigest()}
    assert verificar(carpeta) == 0
    reescrito = recortes.escribir(carpeta, **METADATOS)
    assert reescrito["archivos"] == archivos
    assert len(capsys.readouterr().out.splitlines()) == 2


@pytest.mark.parametrize("cambio,diagnostico", [
    ("contenido", "sha256"), ("tamano", "bytes"), ("extra", "falta en el manifiesto"),
    ("ausente", "faltan en disco"), ("extension", "extensión"),
])
def test_roturas_del_inventario(carpeta, cambio, diagnostico, capsys):
    recortes.escribir(carpeta, **METADATOS)
    archivo = carpeta / "a.csv"
    if cambio == "contenido":
        archivo.write_bytes(b"altura\n26\n")
    elif cambio == "tamano":
        archivo.write_bytes(b"")
    elif cambio == "extra":
        (carpeta / "c.json").write_bytes(b"{}")
    elif cambio == "ausente":
        archivo.unlink()
    else:
        (carpeta / "c.png").touch()
    assert verificar(carpeta) == 1
    assert diagnostico in capsys.readouterr().out


def test_50_mb_decimales_y_un_byte_mas(carpeta, capsys):
    archivo = carpeta / "grande.tiff"
    with archivo.open("wb") as salida:
        salida.truncate(50_000_000)
    recortes.escribir(carpeta, **METADATOS)
    assert verificar(carpeta) == 0
    with archivo.open("ab") as salida:
        salida.truncate(50_000_001)
    assert verificar(carpeta) == 1
    assert "supera 50000000 bytes" in capsys.readouterr().out


@pytest.mark.parametrize("ruta", ["/var/recortes/a.csv", r"C:\datos\a.csv", r"\\servidor\datos"])
def test_ruta_absoluta_dentro_de_texto_anidado(carpeta, ruta, capsys):
    datos = recortes.escribir(carpeta, **METADATOS)
    datos["extra"] = [{"nota": f"origen: {ruta}"}]
    (carpeta / "manifiesto.json").write_text(json.dumps(datos), encoding="utf-8")
    assert verificar(carpeta) == 1
    assert "ruta absoluta" in capsys.readouterr().out


def test_licencias_y_url_explicita(carpeta, capsys):
    opciones = {**METADATOS, "fuente": "otra", "url_fuente": "https://example.org/datos"}
    for licencia in ("CC0-1.0", "CC-BY-4.0", "dominio-publico"):
        datos = recortes.escribir(carpeta, **{**opciones, "licencia": licencia})
        assert datos["fuente"]["url"] == opciones["url_fuente"]
        assert verificar(carpeta) == 0
    with pytest.raises(ValueError, match="ODbL-1.0"):
        recortes.escribir(carpeta, **{**opciones, "licencia": "ODbL-1.0"})
    assert leer(carpeta) == datos
    datos["licencia"]["spdx"] = "ODbL-1.0"
    (carpeta / "manifiesto.json").write_text(json.dumps(datos), encoding="utf-8")
    assert verificar(carpeta) == 1
    assert "ODbL-1.0" in capsys.readouterr().out


def test_todas_incluye_carpetas_sin_manifiesto_y_sigue(carpeta, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(recortes, "RECORTES", tmp_path)
    otra = tmp_path / "ancla" / "fuente"
    otra.mkdir(parents=True)
    subcarpeta = carpeta / "capas"
    subcarpeta.mkdir()
    (subcarpeta / "capa.geojson").write_bytes(b"{}")
    datos = recortes.escribir(carpeta, **METADATOS)
    assert "capas/capa.geojson" in [archivo["nombre"] for archivo in datos["archivos"]]
    assert recortes.main(["--comprobar", "--todas"]) == 1
    lineas = capsys.readouterr().out.splitlines()
    assert len(lineas) == 2
    assert str(otra) in lineas[0] and "manifiesto.json" in lineas[0]
    assert str(carpeta) in lineas[1] and "en orden" in lineas[1]
