"""Pruebas del contrato de datos, sin red.

Cada prueba copia el ejemplo de `web/datos/ejemplo/` a `tmp_path`, rompe una cosa y pasa el
validador. Cada control se prueba en los dos lados: si el validador no falla con el ejemplo
roto, no está comprobando nada.
"""

import base64
import gzip
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import src.contrato as contrato

ROOT = Path(__file__).resolve().parents[1]
EJEMPLO = ROOT / "web" / "datos" / "ejemplo"
GENERADO = {"utc": "2026-11-28T18:00:00+00:00", "commit": "b3e2192", "comando": "prueba"}
FUENTE = {"nombre": "prueba", "version": "1", "licencia": "CC-BY-4.0",
          "url": "https://example.org"}


def copia(tmp_path: Path, nombre="ejemplo") -> Path:
    destino = tmp_path / "datos" / nombre
    shutil.copytree(EJEMPLO, destino)
    return destino


def leer(carpeta: Path, archivo: str) -> dict:
    return json.loads((carpeta / archivo).read_text(encoding="utf-8"))


def escribir(ruta: Path, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def editar(carpeta: Path, archivo: str, cambio):
    datos = leer(carpeta, archivo)
    cambio(datos)
    escribir(carpeta / archivo, datos)


def validar(carpeta: Path, capsys) -> tuple:
    codigo = contrato.main([str(carpeta)])
    return codigo, capsys.readouterr().out


def errores(salida: str) -> list:
    return [l for l in salida.splitlines() if l.count(": ") >= 2 and "KB con" not in l]


# El ejemplo

def test_el_ejemplo_cumple_el_contrato(tmp_path, capsys):
    codigo, salida = validar(copia(tmp_path), capsys)
    assert codigo == 0, salida
    filas = [l.split()[0] for l in salida.splitlines() if l.startswith("ejemplo/")]
    assert filas[:4] == ["ejemplo/escuela.json", "ejemplo/clima.json",
                         "ejemplo/validacion.json", "ejemplo/recorrido.json"]
    for archivo in filas[:4]:
        assert f"{archivo}" in salida
        linea = next(l for l in salida.splitlines() if l.startswith(archivo))
        assert "en orden" in linea
    assert "ejemplo, mapa: 0,0 KB" in salida
    assert salida.rstrip().endswith("contrato en orden")


def test_el_ejemplo_del_repositorio_cumple_el_contrato(capsys):
    codigo, salida = validar(EJEMPLO, capsys)
    assert codigo == 0, salida


def test_el_total_es_la_suma_de_gzip_9(tmp_path, capsys):
    carpeta = copia(tmp_path)
    _, salida = validar(carpeta, capsys)
    total = sum(len(gzip.compress((carpeta / n).read_bytes(), compresslevel=9))
                for n in ("escuela.json", "clima.json", "validacion.json", "recorrido.json"))
    assert f"primera pantalla: {contrato.kb(total)} KB" in salida


def test_las_horas_de_los_meses_suman_el_promedio_anual():
    clima = leer(EJEMPLO, "clima.json")
    suma = sum(m["horas"] for m in clima["calor"]["por_mes"]["meses"])
    assert abs(suma - clima["calor"]["horas_1996_2025"]) <= 0.65


def test_el_ejemplo_esta_en_el_punto_del_esquema():
    esquema = json.loads((ROOT / "web/direcciones/escuela-esquema.json")
                         .read_text(encoding="utf-8"))
    escuela = leer(EJEMPLO, "escuela.json")
    assert (escuela["lat"], escuela["lon"], escuela["huso_horas"]) == (
        esquema["latitud"], esquema["longitud"], esquema["huso_horas"])


def test_por_linea_de_ordenes(tmp_path):
    carpeta = copia(tmp_path)
    r = subprocess.run([sys.executable, "-m", "src.contrato", str(carpeta)], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "contrato en orden" in r.stdout


# Las tres roturas del control de la orden

def test_falla_si_falta_un_campo_obligatorio_de_clima(tmp_path, capsys):
    carpeta = copia(tmp_path)
    editar(carpeta, "clima.json", lambda d: d["lluvia"].pop("p99"))
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 1
    assert "ejemplo/clima.json: lluvia.p99: falta" in errores(salida)


def test_falla_con_alerta_en_el_texto_de_una_parada(tmp_path, capsys):
    carpeta = copia(tmp_path)
    editar(carpeta, "recorrido.json",
           lambda d: d["paradas"][1]["texto"].update(docente="Una alerta de calor."))
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 1
    assert "ejemplo/recorrido.json: paradas[1].texto.docente: lleva «alerta»" in errores(salida)


def test_falla_con_horas_negativas_en_un_anio(tmp_path, capsys):
    carpeta = copia(tmp_path)
    editar(carpeta, "clima.json", lambda d: d["calor"]["serie"][5].update(horas=-1))
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 1
    assert any(l.startswith("ejemplo/clima.json: calor.serie[5].horas: -1")
               for l in errores(salida))


# Los rangos y la coherencia

@pytest.mark.parametrize("cambio, archivo, campo", [
    (lambda d: d["calor"]["serie"][0].update(horas=2621), "clima.json", "calor.serie[0].horas"),
    (lambda d: d["lluvia"]["serie"][0].update(dias=367), "clima.json", "lluvia.serie[0].dias"),
    (lambda d: d["calor"]["serie"].pop(), "clima.json", "calor.serie"),
    (lambda d: d["calor"]["serie"][3].update(anio=1944), "clima.json", "calor.serie[3].anio"),
    (lambda d: d["calor"]["por_mes"]["meses"][0].update(mes=13), "clima.json",
     "calor.por_mes.meses[0].mes"),
    (lambda d: d["episodios"]["lista"][0]["lluvia"].pop(), "clima.json",
     "episodios.lista[0].lluvia"),
    (lambda d: d["episodios"]["lista"][0].update(fecha="1990-05-01"), "clima.json",
     "episodios.lista[0].fecha"),
    (lambda d: d["calor"]["por_mes"]["meses"][0].update(horas=99.0), "clima.json",
     "calor.por_mes.meses"),
    (lambda d: d["calor"].update(horas_1996_2025=d["calor"]["horas_1996_2025"] + 1),
     "clima.json", "calor.horas_1996_2025"),
    (lambda d: d["calor"].update(horas_1961_1990=161.23), "clima.json",
     "calor.horas_1961_1990"),
    (lambda d: d["calor"]["umbral"].update(unidad="K"), "clima.json", "calor.umbral.unidad"),
    (lambda d: d["correccion"]["correccion"].update(valor=-0.7), "clima.json",
     "correccion.correccion.valor"),
    (lambda d: d.update(contrato=2), "clima.json", "contrato"),
    (lambda d: d["generado"].pop("commit"), "clima.json", "generado.commit"),
    (lambda d: d["fuentes"][0].update(licencia="ODbL-1.0"), "clima.json",
     "fuentes[0].licencia"),
    (lambda d: d.pop("ejemplo"), "clima.json", "ejemplo"),
    (lambda d: d.update(zona_diseno="costera"), "escuela.json", "zona_diseno"),
    (lambda d: d.update(criterios="referencia de comparación"), "escuela.json", "criterios"),
    (lambda d: d["celda_era5"].update(lat=14.0), "escuela.json", "celda_era5.lat"),
    (lambda d: d.update(slug="otra"), "escuela.json", "slug"),
    (lambda d: d["variables"][0]["con_correccion"].update(sesgo=-0.12), "validacion.json",
     "variables[0].con_correccion.sesgo"),
    (lambda d: d["texto"].update(direccion="Hay riesgo."), "validacion.json",
     "texto.direccion"),
    (lambda d: d["paradas"][0]["pregunta"].update(estudiante="¿Dónde?."), "recorrido.json",
     "paradas[0].pregunta.estudiante"),
    (lambda d: d["paradas"][0]["texto"].update(docente="x" * 451), "recorrido.json",
     "paradas[0].texto.docente"),
    (lambda d: d["paradas"][0]["texto"].update(estudiante="Hay {{clima.x}} horas."),
     "recorrido.json", "paradas[0].texto.estudiante"),
    (lambda d: d["paradas"][0]["mapa"].update(vista="4d"), "recorrido.json",
     "paradas[0].mapa.vista"),
    (lambda d: d["paradas"][0]["pregunta"].update(direccion="¿Dónde está la puerta?"),
     "recorrido.json", "paradas[0].pregunta.direccion"),
])
def test_cada_rotura_falla_y_nombra_el_campo(tmp_path, capsys, cambio, archivo, campo):
    carpeta = copia(tmp_path)
    editar(carpeta, archivo, cambio)
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 1, salida
    assert any(l.startswith(f"ejemplo/{archivo}: {campo}:") for l in errores(salida)), salida


def test_un_archivo_que_falta_no_es_un_error(tmp_path, capsys):
    carpeta = copia(tmp_path)
    (carpeta / "validacion.json").unlink()
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 0, salida
    linea = next(l for l in salida.splitlines() if l.startswith("ejemplo/validacion.json"))
    assert "falta" in linea


def test_un_archivo_fuera_del_contrato_es_un_error(tmp_path, capsys):
    carpeta = copia(tmp_path)
    (carpeta / "notas.txt").write_text("hola", encoding="utf-8")
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 1
    assert "ejemplo/notas.txt: (archivo): no está en el contrato de datos" in salida


def test_un_json_roto_es_un_error(tmp_path, capsys):
    carpeta = copia(tmp_path)
    (carpeta / "clima.json").write_text("{", encoding="utf-8")
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 1
    assert "ejemplo/clima.json: (archivo): no es JSON" in salida


def test_una_escuela_real_no_lleva_ejemplo(tmp_path, capsys):
    carpeta = copia(tmp_path, "sv-88118")
    for archivo in ("escuela.json", "clima.json", "validacion.json", "recorrido.json"):
        editar(carpeta, archivo, lambda d: d.update(escuela="sv-88118")
               if "escuela" in d else d.update(slug="sv-88118"))
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 1
    assert "sv-88118/clima.json: ejemplo: solo el ejemplo lleva \"ejemplo\": true" in salida


def test_la_validacion_retirada_no_lleva_cifras(tmp_path, capsys):
    carpeta = copia(tmp_path)

    def retirar(d):
        for k in ("estacion", "periodo", "que_se_valida", "unidad", "variables"):
            d.pop(k)
        d.update(estado="retirada", motivo="La estación no se puede usar (#39).")
    editar(carpeta, "validacion.json", retirar)
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 0, salida

    editar(carpeta, "validacion.json", lambda d: d.update(motivo=None))
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 1
    assert "ejemplo/validacion.json: motivo: es null" in salida


# Las palabras

@pytest.mark.parametrize("frase, palabra", [
    ("Las ALERTAS de calor", "alerta"),
    ("una predicción", "predicción"),
    ("lo que predicen", "predice"),
    ("Sin pronósticos", "pronóstico"),
    ("ERA5 no pronostica", "pronostica"),
    ("los riesgos", "riesgo"),
    ("una zona peligrosa", "peligro"),
    ("Deben revisar", "deben"),
    ("tienen   que revisar", "tienen que"),
    ("es obligatoria", "obligatorio"),
    ("el interior del aula", "interior"),
    ("las puertas", "puerta"),
    ("los accesos", "acceso"),
])
def test_las_palabras_vetadas_se_encuentran(frase, palabra):
    assert palabra in contrato.vetadas(frase)


@pytest.mark.parametrize("frase", [
    "el año anterior", "un patio accesible", "el alero", "se debe revisar",
    "tiene que ver", "preparación", "las preguntas para conversar",
])
def test_y_no_hay_falsos_positivos(frase):
    assert contrato.vetadas(frase) == []


def test_las_listas_se_pueden_importar():
    from src.contrato import PALABRAS_INTERIOR, PALABRAS_PROHIBIDAS
    assert "alerta" in PALABRAS_PROHIBIDAS and "puerta" in PALABRAS_INTERIOR


# Los presupuestos y los archivos comunes

def cabecera(**extra):
    return {"contrato": 1, "generado": GENERADO, "fuentes": [FUENTE], **extra}


def test_la_primera_pantalla_pasa_de_20_kb(tmp_path, capsys):
    carpeta = copia(tmp_path)
    # Texto que apenas comprime: unos 30 KB con gzip -9.
    ruido = [{"termino": f"t{i}", "definicion": base64.b64encode(os.urandom(300)).decode()}
             for i in range(100)]
    escribir(carpeta.parent / "comun" / "glosario.json", cabecera(terminos=ruido))
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 1
    assert "primera pantalla" in salida and "pasa del límite" in salida
    assert "comun/glosario.json" in salida


def test_el_mapa_pasa_de_2000_kb(tmp_path, capsys):
    carpeta = copia(tmp_path)
    relieve = carpeta / "relieve"
    escribir(relieve / "relieve.json", cabecera(
        ejemplo=True, aviso="Relieve con cifras ficticias.", escuela="ejemplo",
        granulos=["n13w090"], bounds=[-89.22, 13.68, -89.18, 13.72], minzoom=10,
        maxzoom=14, precision_m=0.25, altitud_escuela_m=412.3))
    tesela = relieve / "12" / "1" / "2.png"
    tesela.parent.mkdir(parents=True)
    tesela.write_bytes(contrato.PNG + os.urandom(2_100_000))
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 1
    assert "ejemplo, mapa:" in salida and "pasa del límite" in salida
    assert "en orden, 1 teselas" in salida

    tesela.write_bytes(contrato.PNG + b"\0" * 1000)
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 0, salida


def escuelas_json(**cambios):
    escuela = {
        "slug": "sv-88118", "nombre": "Escuela", "codigo": "88118", "municipio": "M",
        "division": "D", "pais": "El Salvador", "iso_pais": "SV", "lat": 13.97012,
        "lon": -89.33901, "huso_horas": -6, "ancla": True,
        "estacion": {"nombre": "Santa Ana/El Palmar", "lat": 13.97, "lon": -89.53,
                     "distancia_km": 20.5},
        "fuente_coordenadas": {"nombre": "Directorio", "url": "https://example.org",
                               "fecha_consulta": "2026-11-28", "metodo": "directorio"},
    }
    escuela.update(cambios)
    return {"contrato": 1, "generado": GENERADO, "escuelas": [escuela]}


def test_escuelas_json_cuenta_en_la_primera_pantalla(tmp_path, capsys):
    carpeta = copia(tmp_path)
    escribir(carpeta.parent / "escuelas.json", escuelas_json())
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 0, salida
    linea = next(l for l in salida.splitlines() if l.startswith("escuelas.json"))
    assert "en orden" in linea

    escribir(carpeta.parent / "escuelas.json", escuelas_json(ancla=False, slug="ejemplo"))
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 1
    assert "escuelas.json: escuelas[0].slug: el ejemplo no va en escuelas.json" in salida
    assert "escuelas.json: escuelas: hay 0 escuelas" in salida


def test_los_limites_de_clima_estan_en_comun(tmp_path, capsys):
    carpeta = copia(tmp_path)
    ids = leer(carpeta, "clima.json")["limites"]
    limites = [{"id": i, "titulo": "t", "estudiante": "e", "docente": "d", "direccion": "x"}
               for i in ids]
    escribir(carpeta.parent / "comun" / "limites.json", cabecera(limites=limites))
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 0, salida

    escribir(carpeta.parent / "comun" / "limites.json", cabecera(limites=limites[:1]))
    codigo, salida = validar(carpeta, capsys)
    assert codigo == 1
    assert "ejemplo/clima.json: limites[1]:" in salida


def test_todas(tmp_path, capsys):
    carpeta = copia(tmp_path)
    escribir(carpeta.parent / "escuelas.json", escuelas_json())
    codigo = contrato.main(["--todas", "--raiz", str(carpeta.parent)])
    salida = capsys.readouterr().out
    assert codigo == 0, salida
    assert "escuelas.json" in salida and "ejemplo/clima.json" in salida
