"""Pruebas del presupuesto de carga, sin red.

Los archivos se fabrican en `tmp_path`. Cada control del límite se prueba en los dos lados:
si el script no falla con una carpeta que pasa del límite, no está comprobando nada.
"""

import gzip
import os
import subprocess
import sys
from pathlib import Path

import pytest

import src.presupuesto as presupuesto

ROOT = Path(__file__).resolve().parents[1]


def gz(datos: bytes) -> int:
    return len(gzip.compress(datos, compresslevel=9))


def carpeta(tmp_path: Path) -> Path:
    """Cuatro archivos, uno en una subcarpeta: texto repetido, que comprime mucho, bytes
    pseudoaleatorios, que apenas comprimen, un archivo vacío y `D.md`, que está para comprobar
    que el orden de la tabla no depende del sistema."""
    raiz = tmp_path / "sitio"
    (raiz / "sub").mkdir(parents=True)
    (raiz / "a.txt").write_bytes(b"hola " * 2000)
    (raiz / "sub" / "b.bin").write_bytes(os.urandom(5000))
    (raiz / "c.css").write_bytes(b"")
    (raiz / "D.md").write_bytes(b"# origen\n")
    return raiz


@pytest.mark.parametrize("n, texto", [
    (0, "0,0"), (49, "0,0"), (50, "0,1"), (999, "1,0"), (1000, "1,0"),
    (1049, "1,0"), (1050, "1,1"), (301_600, "301,6"), (1_120_720, "1120,7"),
])
def test_kb_en_miles_con_una_decima(n, texto):
    assert presupuesto.kb(n) == texto


def test_medir_recorre_subcarpetas_y_comprime_con_gzip_9(tmp_path):
    raiz = carpeta(tmp_path)
    filas = presupuesto.medir(raiz)
    # Mayúsculas antes que minúsculas, en todos los sistemas.
    assert [f[0] for f in filas] == ["D.md", "a.txt", "c.css", "sub/b.bin"]
    for nombre, crudo, comprimido in filas:
        datos = (raiz / nombre).read_bytes()
        assert crudo == len(datos)
        assert comprimido == gz(datos)
    # El texto repetido comprime; los bytes al azar no.
    assert filas[1][2] < filas[1][1] / 10
    assert filas[3][2] > filas[3][1]


def test_imprime_una_fila_por_archivo_y_el_total(tmp_path, capsys):
    raiz = carpeta(tmp_path)
    assert presupuesto.main([str(raiz), "--limite-kb", "100"]) == 0
    salida = capsys.readouterr().out
    lineas = salida.splitlines()
    total_gz = sum(gz(p.read_bytes()) for p in raiz.rglob("*") if p.is_file())
    for nombre in ("D.md", "a.txt", "c.css", "sub/b.bin"):
        assert sum(l.startswith(nombre + " ") for l in lineas) == 1
    fila_total = next(l for l in lineas if l.startswith("Total"))
    assert fila_total.split()[-2] == presupuesto.kb(total_gz)
    assert fila_total.split()[1] == presupuesto.kb(10_000 + 5000 + 9)
    assert "dentro del límite" in salida


def test_falla_si_pasa_del_limite_y_no_en_el_borde(tmp_path, capsys):
    raiz = carpeta(tmp_path)
    total = sum(gz(p.read_bytes()) for p in raiz.rglob("*") if p.is_file())
    # Justo en el límite no pasa; un byte por debajo, sí.
    assert presupuesto.main([str(raiz), "--limite-kb", str(total / 1000)]) == 0
    assert presupuesto.main([str(raiz), "--limite-kb", str((total - 1) / 1000)]) == 1
    assert "pasa del límite" in capsys.readouterr().out


def test_el_limite_admite_coma_decimal(tmp_path):
    raiz = carpeta(tmp_path)
    total = sum(gz(p.read_bytes()) for p in raiz.rglob("*") if p.is_file())
    assert presupuesto.main([str(raiz), "--limite-kb", str((total - 1) / 1000).replace(".", ",")]) == 1


@pytest.mark.parametrize("argumentos", [
    ["--limite-kb", "-1"], ["--limite-kb", "nada"], ["--limite-kb", "nan"], [],
])
def test_rechaza_limites_invalidos(tmp_path, argumentos):
    with pytest.raises(SystemExit) as salida:
        presupuesto.main([str(carpeta(tmp_path))] + argumentos)
    assert salida.value.code == 2


def test_rechaza_una_carpeta_que_no_existe_o_esta_vacia(tmp_path):
    vacia = tmp_path / "vacia"
    vacia.mkdir()
    for ruta in (tmp_path / "no-existe", vacia):
        with pytest.raises(SystemExit) as salida:
            presupuesto.main([str(ruta), "--limite-kb", "1"])
        assert salida.value.code == 2


def test_el_codigo_de_salida_llega_a_la_linea_de_ordenes(tmp_path):
    raiz = carpeta(tmp_path)

    def ejecutar(limite_kb):
        return subprocess.run(
            [sys.executable, "-m", "src.presupuesto", str(raiz), "--limite-kb", limite_kb],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ).returncode

    assert ejecutar("1000") == 0
    assert ejecutar("0") == 1
