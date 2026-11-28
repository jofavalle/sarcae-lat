"""Contrato de datos del sitio: comprueba los archivos de `web/datos/` contra
`docs/contrato-datos.md`.

Valida una carpeta de escuela, o el ejemplo, con lo que exista de `escuelas.json` y de
`comun/` a su lado; con `--todas`, todas las carpetas de `web/datos/`, `escuelas.json`,
`comun/` y, si existe, `web/material/material.json`. Un archivo que falta no es un error: la
interfaz dice que todavía no lo hay. Uno que está tiene que estar completo.

Comprueba los campos obligatorios, sus tipos, sus unidades y sus decimales, las reglas
comunes (`contrato`, `generado` y `fuentes`), los rangos de los indicadores, la coherencia
de `clima.json`, el lenguaje de los textos y preguntas y los dos presupuestos de la ADR-001:
20 KB con gzip -9 para los datos de la primera pantalla y 2000 KB para los del mapa, medidos
con `src.presupuesto.medir`.

Imprime una fila por archivo, con su estado y sus KB, los dos totales y los errores, cada uno
con su archivo y su campo. Sale con 1 si algo falla.

Uso, desde la raíz del repositorio:

    python -m src.contrato web/datos/ejemplo
    python -m src.contrato --todas

Solo usa la biblioteca estándar.
"""

import argparse
import gzip
import json
import math
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

from src.presupuesto import kb, medir

CONTRATO = 1

# Las palabras que no van en los campos `texto` y `pregunta` de recorrido.json y
# validacion.json. La herramienta no pronostica ni evalúa (CLAUDE.md, "Del proyecto"), y las
# preguntas son abiertas. Se buscan sin distinguir mayúsculas ni tildes, con sus plurales y
# su femenino. Las importa la orden del recorrido.
PALABRAS_PROHIBIDAS = (
    "alerta", "predicción", "predice", "pronóstico", "pronostica", "riesgo", "peligro",
    "deben", "tienen que", "obligatorio",
)
# Y las del interior de una escuela concreta, por la seguridad de quienes la ocupan
# (docs/PLAN.md, sección 7).
PALABRAS_INTERIOR = ("interior", "puerta", "acceso")

REGISTROS = ("estudiante", "docente", "direccion")
LICENCIAS = ("CC0-1.0", "CC-BY-4.0", "dominio-publico", "cita")

LIMITE_PRIMERA_PANTALLA = 20_000   # bytes con gzip -9 (ADR-001)
LIMITE_MAPA = 2_000_000

ANIO_MIN, ANIO_MAX = 1940, 2025
HORAS_ANIO_MAX = 2620              # 262 días laborables como mucho, por 10 horas
HORAS_MES_MAX = 230                # 23 días laborables como mucho, por 10 horas
DIAS_ANIO_MAX = 366
GAMMA_K_KM = 6.5
UMBRAL_CALOR_C = 27
DIAS_BASE_P99 = 10957              # los días de 1961 a 1990
REFERENCIA = (1961, 1990)
RECIENTE = (1996, 2025)

# Zonas de diseño del Manual Mi Nueva Escuela, A8 p. 16, en m: [desde, hasta).
ZONAS = {"costera": (0, 300), "tropical caliente": (300, 700), "montañosa": (700, None)}

CAPAS_MAQUETA = ("calor", "sombra", "agua")
CAPAS_MAPA = ("relieve", "calor", "cobertura", "agua")
VISTAS = ("2d", "3d")
VARIABLES_VALIDACION = ("horaria", "media", "maxima", "minima")

# Los archivos de una carpeta de escuela, en el orden de la tabla, con su grupo del
# presupuesto: "primera" (la primera pantalla), "mapa" o "peticion" (no cuenta).
ARCHIVOS_ESCUELA = (
    ("escuela.json", "primera"),
    ("clima.json", "primera"),
    ("validacion.json", "primera"),
    ("recorrido.json", "primera"),
    ("relieve/", "mapa"),
    ("edificios.geojson", "mapa"),
    ("calor.geojson", "mapa"),
    ("cobertura.png", "mapa"),
    ("capas.json", "mapa"),
    ("agua.geojson", "mapa"),
    ("maqueta.stl", "peticion"),
    ("maqueta-stl.json", "peticion"),
)
ARCHIVOS_COMUNES = (
    ("comun/limites.json", "primera"),
    ("comun/glosario.json", "primera"),
    ("comun/maqueta-generica.json", "primera"),
    ("comun/reserva.json", "peticion"),
)

PNG = b"\x89PNG\r\n\x1a\n"
EPS = 1e-9


# Lenguaje

def _plano(texto: str) -> str:
    """En minúsculas y sin tildes, para buscar sin distinguirlas."""
    sin = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin if unicodedata.category(c) != "Mn")


def _patron(palabra: str) -> re.Pattern:
    base = _plano(palabra)
    if " " in base:
        return re.compile(r"\b" + r"\s+".join(map(re.escape, base.split())) + r"\b")
    if base.endswith("o"):
        base = re.escape(base[:-1]) + "[oa]"
    else:
        base = re.escape(base)
    # Hasta tres letras más: plurales (riesgos, puertas), verbos (predicen) y derivados.
    return re.compile(r"\b" + base + r"\w{0,3}\b")


_PATRONES = [(p, _patron(p)) for p in PALABRAS_PROHIBIDAS + PALABRAS_INTERIOR]


def vetadas(texto: str) -> list:
    """Las palabras de PALABRAS_PROHIBIDAS y PALABRAS_INTERIOR que aparecen en el texto."""
    plano = _plano(texto)
    return [palabra for palabra, patron in _PATRONES if patron.search(plano)]


# Comprobaciones elementales: cada una apunta el error con su campo y devuelve el valor
# si vale, o None.

class Errores:
    def __init__(self):
        self.lista = []

    def __call__(self, campo: str, mensaje: str):
        self.lista.append((campo, mensaje))


def _es_numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _decimales_ok(v, n: int) -> bool:
    return abs(v * 10 ** n - round(v * 10 ** n)) < 1e-6


def campo(e, d, clave, ruta, nulo=False):
    """El valor de `clave` en el objeto `d`, o None con un error si falta."""
    if not isinstance(d, dict):
        return None
    if clave not in d:
        e(_unir(ruta, clave), "falta")
        return None
    if d[clave] is None and not nulo:
        e(_unir(ruta, clave), "es null")
    return d[clave]


def _unir(ruta, clave):
    if isinstance(clave, int):
        return f"{ruta}[{clave}]"
    return f"{ruta}.{clave}" if ruta else clave


def objeto(e, d, clave, ruta, nulo=False):
    v = campo(e, d, clave, ruta, nulo)
    if v is None:
        return None
    if not isinstance(v, dict):
        e(_unir(ruta, clave), "no es un objeto")
        return None
    return v


def lista(e, d, clave, ruta, n=None, minimo=0):
    v = campo(e, d, clave, ruta)
    if v is None:
        return None
    if not isinstance(v, list):
        e(_unir(ruta, clave), "no es una lista")
        return None
    if n is not None and len(v) != n:
        e(_unir(ruta, clave), f"tiene {len(v)} elementos, y son {n}")
    elif len(v) < minimo:
        e(_unir(ruta, clave), f"tiene {len(v)} elementos, y son {minimo} como mínimo")
    return v


def texto(e, d, clave, ruta, nulo=False, maximo=None):
    v = campo(e, d, clave, ruta, nulo)
    if v is None:
        return None
    if not isinstance(v, str) or not v.strip():
        e(_unir(ruta, clave), "no es un texto, o está vacío")
        return None
    if maximo is not None and len(v) > maximo:
        e(_unir(ruta, clave), f"tiene {len(v)} caracteres, y son {maximo} como mucho")
    return v


def booleano(e, d, clave, ruta):
    v = campo(e, d, clave, ruta)
    if v is not None and not isinstance(v, bool):
        e(_unir(ruta, clave), "no es true ni false")
        return None
    return v


def numero(e, d, clave, ruta, minimo=None, maximo=None, decimales=None, entero=False,
           nulo=False):
    v = campo(e, d, clave, ruta, nulo)
    if v is None:
        return None
    return valor_numerico(e, v, _unir(ruta, clave), minimo, maximo, decimales, entero)


def valor_numerico(e, v, ruta, minimo=None, maximo=None, decimales=None, entero=False):
    if not _es_numero(v):
        e(ruta, f"{v!r} no es un número")
        return None
    if entero and not isinstance(v, int):
        e(ruta, f"{v} no es un entero")
        return None
    if minimo is not None and v < minimo or maximo is not None and v > maximo:
        if minimo is not None and maximo is not None:
            e(ruta, f"{v} está fuera del rango de {minimo} a {maximo}")
        elif minimo is not None:
            e(ruta, f"{v} es menor que {minimo}")
        else:
            e(ruta, f"{v} pasa de {maximo}")
        return None
    if decimales is not None and not _decimales_ok(v, decimales):
        e(ruta, f"{v} lleva más de {decimales} decimales")
    return v


def _elementos(e, valores, ruta):
    """(ruta, elemento) de cada objeto de una lista; los que no son objetos, como error."""
    for i, x in enumerate(valores or []):
        if isinstance(x, dict):
            yield f"{ruta}[{i}]", x
        else:
            e(f"{ruta}[{i}]", "no es un objeto")


def igual(e, d, clave, ruta, esperado):
    v = campo(e, d, clave, ruta)
    if v is not None and v != esperado:
        e(_unir(ruta, clave), f"es {v!r}, y tiene que ser {esperado!r}")
    return v


def una_de(e, d, clave, ruta, opciones, nulo=False):
    v = campo(e, d, clave, ruta, nulo)
    if v is not None and v not in opciones:
        e(_unir(ruta, clave), f"{v!r} no es ninguna de {', '.join(map(repr, opciones))}")
        return None
    return v


def medida(e, d, clave, ruta, unidad, **kw):
    """Un objeto {valor, unidad}, con la unidad esperada."""
    o = objeto(e, d, clave, ruta)
    if o is None:
        return None
    r = _unir(ruta, clave)
    igual(e, o, "unidad", r, unidad)
    return numero(e, o, "valor", r, **kw)


def fecha(e, d, clave, ruta, nulo=False):
    v = texto(e, d, clave, ruta, nulo)
    if v is None:
        return None
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError
        return date.fromisoformat(v)
    except ValueError:
        e(_unir(ruta, clave), f"{v!r} no es una fecha AAAA-MM-DD")
        return None


def registros(e, d, clave, ruta, maximo=None, interrogacion=False):
    o = objeto(e, d, clave, ruta)
    if o is None:
        return
    r = _unir(ruta, clave)
    for reg in REGISTROS:
        t = texto(e, o, reg, r, maximo=maximo)
        if t and interrogacion and not (t.strip().startswith("¿") and t.strip().endswith("?")):
            e(_unir(r, reg), "la pregunta no va entre «¿» y «?»")
    for otra in o:
        if otra not in REGISTROS:
            e(_unir(r, otra), f"no es un registro: son {', '.join(REGISTROS)}")


# Las reglas comunes

def cabecera(e, d, ruta, ejemplo: bool, fuentes=True):
    """`contrato`, `generado` y `fuentes`, y `ejemplo` con su `aviso`."""
    if not isinstance(d, dict):
        e(ruta or "(raíz)", "no es un objeto")
        return
    c = campo(e, d, "contrato", ruta)
    if c is not None and (not isinstance(c, int) or isinstance(c, bool) or c != CONTRATO):
        e(_unir(ruta, "contrato"), f"es {c!r}, y la versión del contrato es {CONTRATO}")
    g = objeto(e, d, "generado", ruta)
    if g is not None:
        r = _unir(ruta, "generado")
        utc = texto(e, g, "utc", r)
        if utc:
            try:
                t = datetime.fromisoformat(utc.replace("Z", "+00:00"))
                if t.utcoffset() is None:
                    raise ValueError
            except ValueError:
                e(_unir(r, "utc"), f"{utc!r} no es una fecha ISO 8601 con zona")
        commit = texto(e, g, "commit", r)
        if commit and not re.fullmatch(r"[0-9a-f]{7,40}", commit):
            e(_unir(r, "commit"), f"{commit!r} no es un commit de git")
        texto(e, g, "comando", r)
    if fuentes:
        fs = lista(e, d, "fuentes", ruta, minimo=1)
        for i, f in enumerate(fs or []):
            rf = _unir(_unir(ruta, "fuentes"), i)
            if not isinstance(f, dict):
                e(rf, "no es un objeto")
                continue
            texto(e, f, "nombre", rf)
            texto(e, f, "version", rf)
            una_de(e, f, "licencia", rf, LICENCIAS)
            url = texto(e, f, "url", rf)
            if url and not url.startswith(("https://", "http://")):
                e(_unir(rf, "url"), f"{url!r} no es una URL")
    if ejemplo:
        if d.get("ejemplo") is not True:
            e(_unir(ruta, "ejemplo"), "el ejemplo lleva \"ejemplo\": true")
        aviso = texto(e, d, "aviso", ruta)
        if aviso and "ficticia" not in aviso.lower():
            e(_unir(ruta, "aviso"), "el aviso no dice que las cifras son ficticias")
    elif d.get("ejemplo") is True:
        e(_unir(ruta, "ejemplo"), "solo el ejemplo lleva \"ejemplo\": true")


def lenguaje(e, d, ruta=""):
    """Las palabras vetadas en los campos `texto` y `pregunta`, a cualquier profundidad."""
    if isinstance(d, dict):
        for k, v in d.items():
            r = _unir(ruta, k)
            if k in ("texto", "pregunta"):
                for sub_r, t in _cadenas(v, r):
                    for palabra in vetadas(t):
                        e(sub_r, f"lleva «{palabra}»")
            else:
                lenguaje(e, v, r)
    elif isinstance(d, list):
        for i, v in enumerate(d):
            lenguaje(e, v, _unir(ruta, i))


def _cadenas(v, ruta):
    if isinstance(v, str):
        yield ruta, v
    elif isinstance(v, dict):
        for k, w in v.items():
            yield from _cadenas(w, _unir(ruta, k))
    elif isinstance(v, list):
        for i, w in enumerate(v):
            yield from _cadenas(w, _unir(ruta, i))


# Los archivos de una escuela

def _media(serie, clave, desde, hasta):
    vals = [s[clave] for s in serie
            if isinstance(s, dict) and isinstance(s.get("anio"), int)
            and desde <= s["anio"] <= hasta and _es_numero(s.get(clave))]
    return sum(vals) / len(vals) if len(vals) == hasta - desde + 1 else None


def _serie(e, d, ruta, clave, maximo):
    serie = lista(e, d, "serie", ruta, n=ANIO_MAX - ANIO_MIN + 1)
    if serie is None:
        return []
    r = _unir(ruta, "serie")
    for i, s in enumerate(serie):
        ri = _unir(r, i)
        if not isinstance(s, dict):
            e(ri, "no es un objeto")
            continue
        anio = numero(e, s, "anio", ri, ANIO_MIN, ANIO_MAX, entero=True)
        if anio is not None and anio != ANIO_MIN + i:
            e(_unir(ri, "anio"), f"es {anio}, y en esa posición va {ANIO_MIN + i}")
        numero(e, s, clave, ri, 0, maximo, entero=True)
    return serie


def _promedios(e, d, ruta, clave_serie, prefijo, maximo):
    serie = _serie(e, d, ruta, clave_serie, maximo)
    for desde, hasta in (REFERENCIA, RECIENTE):
        clave = f"{prefijo}_{desde}_{hasta}"
        v = numero(e, d, clave, ruta, 0, maximo, decimales=1)
        m = _media(serie, clave_serie, desde, hasta)
        if v is not None and m is not None and abs(v - m) > 0.05 + EPS:
            e(_unir(ruta, clave), f"es {v}, y la media de la serie de {desde} a {hasta} "
              f"es {m:.2f}")
    return serie


def validar_escuela(e, d, slug, ejemplo, contexto):
    cabecera(e, d, "", ejemplo)
    if not isinstance(d, dict):
        return
    igual(e, d, "slug", "", slug)
    for k in ("nombre", "municipio", "division", "pais"):
        texto(e, d, k, "")
    texto(e, d, "codigo", "", nulo=True)
    iso = texto(e, d, "iso_pais", "")
    if iso and not re.fullmatch(r"[A-Z]{2}", iso):
        e("iso_pais", f"{iso!r} no es un código ISO 3166-1 de dos letras")
    lat = numero(e, d, "lat", "", -90, 90, decimales=5)
    lon = numero(e, d, "lon", "", -180, 180, decimales=5)
    huso = numero(e, d, "huso_horas", "", -12, 14, entero=True)
    alt = objeto(e, d, "altitud", "")
    altitud = None
    if alt is not None:
        igual(e, alt, "unidad", "altitud", "m")
        igual(e, alt, "fuente", "altitud", "NASADEM")
        altitud = numero(e, alt, "valor", "altitud", -500, 6000, decimales=1)

    if iso == "SV":
        zona = una_de(e, d, "zona_diseno", "", tuple(ZONAS))
        franja = objeto(e, d, "zona_diseno_franja", "")
        if zona and franja is not None:
            desde, hasta = ZONAS[zona]
            igual(e, franja, "desde", "zona_diseno_franja", desde)
            h = campo(e, franja, "hasta", "zona_diseno_franja", nulo=True)
            if "hasta" in franja and h != hasta:
                e("zona_diseno_franja.hasta", f"es {h!r}, y tiene que ser {hasta!r}")
            igual(e, franja, "unidad", "zona_diseno_franja", "m")
            texto(e, franja, "referencia", "zona_diseno_franja")
            if altitud is not None and not (
                    (altitud >= desde or zona == "costera")
                    and (hasta is None or altitud < hasta)):
                e("zona_diseno", f"la altitud de {altitud} m no cae en la zona {zona}")
        igual(e, d, "criterios", "", "propios")
    elif iso:
        if d.get("zona_diseno") is not None:
            e("zona_diseno", "solo se da en El Salvador: fuera va null")
        igual(e, d, "criterios", "", "referencia de comparación")

    celda = objeto(e, d, "celda_era5", "")
    if celda is not None:
        igual(e, celda, "resolucion", "celda_era5", 0.25)
        igual(e, celda, "unidad", "celda_era5", "grados")
        for k, punto in (("lat", lat), ("lon", lon)):
            c = numero(e, celda, k, "celda_era5", -180, 180)
            if c is None:
                continue
            if not _decimales_ok(c / 0.25, 0):
                e(_unir("celda_era5", k), f"{c} no está en la rejilla de 0,25°")
            elif punto is not None and abs(c - punto) > 0.125 + EPS:
                e(_unir("celda_era5", k), f"{c} no es la celda más cercana a {punto}")

    escuelas = contexto.get("escuelas")
    if escuelas and slug in escuelas:
        ref = escuelas[slug]
        for k, v in (("lat", lat), ("lon", lon), ("huso_horas", huso)):
            if v is not None and ref.get(k) != v:
                e(k, f"es {v}, y en escuelas.json es {ref.get(k)}")


def validar_clima(e, d, slug, ejemplo, contexto):
    cabecera(e, d, "", ejemplo)
    if not isinstance(d, dict):
        return
    igual(e, d, "escuela", "", slug)

    c = objeto(e, d, "correccion", "")
    if c is not None:
        texto(e, c, "formula", "correccion")
        ze = medida(e, c, "z_escuela", "correccion", "m", minimo=-500, maximo=6000, decimales=1)
        zc = medida(e, c, "z_celda", "correccion", "m", minimo=-500, maximo=6000, decimales=1)
        g = medida(e, c, "gamma", "correccion", "K/km")
        if g is not None and g != GAMMA_K_KM:
            e("correccion.gamma.valor", f"es {g}, y Γ es {GAMMA_K_KM} K/km")
        k = medida(e, c, "correccion", "correccion", "K", decimales=1)
        if None not in (ze, zc, k) and abs(k - (-GAMMA_K_KM * (ze - zc) / 1000)) > 0.05 + 0.001:
            e("correccion.correccion.valor",
              f"es {k}, y −Γ·(z_escuela − z_celda) da {-GAMMA_K_KM * (ze - zc) / 1000:.2f}")
        altitud = (contexto.get("escuela.json") or {}).get("altitud")
        if isinstance(altitud, dict) and ze is not None and altitud.get("valor") != ze:
            e("correccion.z_escuela.valor",
              f"es {ze}, y la altitud de escuela.json es {altitud.get('valor')}")

    calor = objeto(e, d, "calor", "")
    if calor is not None:
        u = objeto(e, calor, "umbral", "calor")
        if u is not None:
            igual(e, u, "valor", "calor.umbral", UMBRAL_CALOR_C)
            igual(e, u, "unidad", "calor.umbral", "°C")
        texto(e, calor, "horario", "calor")
        igual(e, calor, "unidad", "calor", "horas")
        _promedios(e, calor, "calor", "horas", "horas", HORAS_ANIO_MAX)
        pm = objeto(e, calor, "por_mes", "calor")
        if pm is not None:
            igual(e, pm, "periodo", "calor.por_mes", list(RECIENTE))
            igual(e, pm, "unidad", "calor.por_mes", "horas")
            meses = lista(e, pm, "meses", "calor.por_mes", n=12) or []
            suma, completos = 0.0, True
            for i, m in enumerate(meses):
                ri = f"calor.por_mes.meses[{i}]"
                if not isinstance(m, dict):
                    e(ri, "no es un objeto")
                    completos = False
                    continue
                mes = numero(e, m, "mes", ri, 1, 12, entero=True)
                if mes is not None and mes != i + 1:
                    e(ri + ".mes", f"es {mes}, y en esa posición va {i + 1}")
                h = numero(e, m, "horas", ri, 0, HORAS_MES_MAX, decimales=1)
                if h is None:
                    completos = False
                else:
                    suma += h
            anual = calor.get("horas_1996_2025")
            # Doce redondeos a una décima, y el del promedio anual.
            if completos and len(meses) == 12 and _es_numero(anual) \
                    and abs(suma - anual) > 12 * 0.05 + 0.05 + EPS:
                e("calor.por_mes.meses",
                  f"suman {suma:.1f} horas, y el promedio anual de 1996–2025 es {anual}")

    lluvia = objeto(e, d, "lluvia", "")
    serie_lluvia, p99 = [], None
    if lluvia is not None:
        p = objeto(e, lluvia, "p99", "lluvia")
        if p is not None:
            p99 = numero(e, p, "valor", "lluvia.p99", 0, 2000, decimales=1)
            igual(e, p, "unidad", "lluvia.p99", "mm")
            igual(e, p, "periodo", "lluvia.p99", list(REFERENCIA))
            igual(e, p, "dias_base", "lluvia.p99", DIAS_BASE_P99)
        igual(e, lluvia, "unidad", "lluvia", "días")
        serie_lluvia = _promedios(e, lluvia, "lluvia", "dias", "dias", DIAS_ANIO_MAX)

    ep = objeto(e, d, "episodios", "")
    if ep is not None:
        u = objeto(e, ep, "unidades", "episodios")
        if u is not None:
            igual(e, u, "lluvia", "episodios.unidades", "mm")
            igual(e, u, "temperatura", "episodios.unidades", "°C")
        dias_por_anio = {s.get("anio"): s.get("dias") for s in serie_lluvia
                         if isinstance(s, dict)}
        previo, vistas = None, set()
        for i, x in enumerate(lista(e, ep, "lista", "episodios", n=3) or []):
            ri = f"episodios.lista[{i}]"
            if not isinstance(x, dict):
                e(ri, "no es un objeto")
                continue
            f = fecha(e, x, "fecha", ri)
            if f is not None:
                if not RECIENTE[0] <= f.year <= RECIENTE[1]:
                    e(ri + ".fecha", f"{f} no está en {RECIENTE[0]}–{RECIENTE[1]}")
                elif _es_numero(dias_por_anio.get(f.year)) and dias_por_anio[f.year] < 1:
                    e(ri + ".fecha", f"en {f.year} la serie no tiene ningún día sobre el p99")
                if f in vistas:
                    e(ri + ".fecha", f"{f} se repite")
                vistas.add(f)
            total = numero(e, x, "lluvia_total", ri, 0, 2000, decimales=1)
            if total is not None and p99 is not None and total < p99:
                e(ri + ".lluvia_total", f"{total} mm no supera el p99, {p99} mm")
            if total is not None and previo is not None and total > previo:
                e(ri + ".lluvia_total", "los episodios van de más lluvia a menos")
            previo = total if total is not None else previo
            horas = lista(e, x, "lluvia", ri, n=24) or []
            buenas = [valor_numerico(e, v, f"{ri}.lluvia[{j}]", 0, 500, decimales=1)
                      for j, v in enumerate(horas)]
            if total is not None and len(horas) == 24 and None not in buenas \
                    and abs(sum(buenas) - total) > 24 * 0.05 + 0.05 + EPS:
                e(ri + ".lluvia", f"suman {sum(buenas):.1f} mm, y lluvia_total es {total}")
            for j, v in enumerate(lista(e, x, "temperatura", ri, n=24) or []):
                valor_numerico(e, v, f"{ri}.temperatura[{j}]", -30, 50, decimales=1)

    lims = lista(e, d, "limites", "", minimo=1)
    ids = contexto.get("limites")
    for i, lim in enumerate(lims or []):
        if not isinstance(lim, str):
            e(f"limites[{i}]", "no es un texto")
        elif ids is not None and lim not in ids:
            e(f"limites[{i}]", f"{lim!r} no está en comun/limites.json")


def validar_validacion(e, d, slug, ejemplo, contexto):
    cabecera(e, d, "", ejemplo)
    if not isinstance(d, dict):
        return
    igual(e, d, "escuela", "", slug)
    estado = una_de(e, d, "estado", "", ("publicada", "retirada"))
    registros(e, d, "texto", "")
    lenguaje(e, d)
    if estado == "retirada":
        texto(e, d, "motivo", "")
        return
    est = objeto(e, d, "estacion", "")
    if est is not None:
        texto(e, est, "nombre", "estacion")
        texto(e, est, "fuente", "estacion")
        medida(e, est, "distancia", "estacion", "km", minimo=0, maximo=500, decimales=1)
        medida(e, est, "altitud", "estacion", "m", minimo=-500, maximo=6000, decimales=1)
    per = objeto(e, d, "periodo", "")
    if per is not None:
        a, b = fecha(e, per, "desde", "periodo"), fecha(e, per, "hasta", "periodo")
        if a and b and a > b:
            e("periodo", f"empieza el {a} y acaba antes, el {b}")
    texto(e, d, "que_se_valida", "")
    igual(e, d, "unidad", "", "K")
    for i, v in enumerate(lista(e, d, "variables", "", minimo=1) or []):
        ri = f"variables[{i}]"
        if not isinstance(v, dict):
            e(ri, "no es un objeto")
            continue
        una_de(e, v, "id", ri, VARIABLES_VALIDACION)
        texto(e, v, "nombre", ri)
        emp = objeto(e, v, "emparejados", ri)
        if emp is not None:
            numero(e, emp, "valor", ri + ".emparejados", 0, entero=True)
            una_de(e, emp, "unidad", ri + ".emparejados", ("horas", "días"))
        for k in ("sin_correccion", "con_correccion"):
            m = objeto(e, v, k, ri)
            if m is not None:
                numero(e, m, "sesgo", f"{ri}.{k}", -50, 50, decimales=1)
                numero(e, m, "error_cuadratico_medio", f"{ri}.{k}", 0, 50, decimales=1)
    texto(e, d, "nota_licencia", "")
    exp = objeto(e, d, "experimento", "", nulo=ejemplo)
    if exp is not None:
        ruta = texto(e, exp, "ruta", "experimento")
        if ruta and not re.fullmatch(r"experiments/\d{8}-[a-z0-9-]+", ruta):
            e("experimento.ruta", f"{ruta!r} no es experiments/<AAAAMMDD>-<slug>")
        commit = texto(e, exp, "commit", "experimento")
        if commit and not re.fullmatch(r"[0-9a-f]{7,40}", commit):
            e("experimento.commit", f"{commit!r} no es un commit de git")


def validar_recorrido(e, d, slug, ejemplo, contexto):
    cabecera(e, d, "", ejemplo)
    if not isinstance(d, dict):
        return
    igual(e, d, "escuela", "", slug)
    regs = objeto(e, d, "registros", "")
    if regs is not None:
        for reg in REGISTROS:
            o = objeto(e, regs, reg, "registros")
            for k in ("nombre", "titulo", "entrada"):
                texto(e, o, k, f"registros.{reg}")
    ids = set()
    for i, p in enumerate(lista(e, d, "paradas", "", minimo=1) or []):
        ri = f"paradas[{i}]"
        if not isinstance(p, dict):
            e(ri, "no es un objeto")
            continue
        pid = texto(e, p, "id", ri)
        if pid in ids:
            e(ri + ".id", f"{pid!r} se repite")
        ids.add(pid)
        texto(e, p, "titulo", ri)
        m = objeto(e, p, "maqueta", ri)
        if m is not None:
            texto(e, m, "volumen", ri + ".maqueta")
            una_de(e, m, "capa", ri + ".maqueta", CAPAS_MAQUETA)
            numero(e, m, "hora", ri + ".maqueta", 0, 23, entero=True)
        m = objeto(e, p, "mapa", ri)
        if m is not None:
            una_de(e, m, "vista", ri + ".mapa", VISTAS)
            una_de(e, m, "capa", ri + ".mapa", CAPAS_MAPA)
        registros(e, p, "texto", ri, maximo=450)
        registros(e, p, "pregunta", ri, interrogacion=True)
    for r, t in _cadenas(d, ""):
        if "{{" in t or "}}" in t:
            e(r, "lleva un marcador sin resolver")
    lenguaje(e, d)


# Las capas del mapa

def _coordenadas(e, c, ruta, decimales=6):
    """Recorre las coordenadas de una geometría: pares [lon, lat] con 6 decimales."""
    if isinstance(c, list) and len(c) >= 2 and all(_es_numero(x) for x in c[:2]) \
            and not any(isinstance(x, list) for x in c):
        lon, lat = c[0], c[1]
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            e(ruta, f"{c} no es [longitud, latitud]")
        elif not (_decimales_ok(lon, decimales) and _decimales_ok(lat, decimales)):
            e(ruta, f"{c} lleva más de {decimales} decimales")
        return 1
    if isinstance(c, list) and c:
        return sum(_coordenadas(e, x, ruta, decimales) for x in c)
    e(ruta, "no son coordenadas")
    return 0


def _geojson(e, d, ejemplo, geometrias, propiedades):
    if not isinstance(d, dict):
        e("(raíz)", "no es un objeto")
        return []
    igual(e, d, "type", "", "FeatureCollection")
    m = objeto(e, d, "metadatos", "")
    if m is not None:
        cabecera(e, m, "metadatos", ejemplo)
    feats = lista(e, d, "features", "", minimo=1) or []
    for i, f in enumerate(feats):
        ri = f"features[{i}]"
        if not isinstance(f, dict):
            e(ri, "no es un objeto")
            continue
        igual(e, f, "type", ri, "Feature")
        g = objeto(e, f, "geometry", ri)
        if g is not None:
            tipo = una_de(e, g, "type", ri + ".geometry", geometrias)
            if tipo:
                _coordenadas(e, campo(e, g, "coordinates", ri + ".geometry"),
                             ri + ".geometry.coordinates")
        p = objeto(e, f, "properties", ri)
        if p is not None:
            propiedades(e, p, ri + ".properties", g.get("type") if g else None)
    return feats


def validar_edificios(e, d, slug, ejemplo, contexto):
    def props(e, p, r, _):
        alt = numero(e, p, "altura", r, 0, 300, decimales=1)
        base = numero(e, p, "base", r, 0, 300, decimales=1)
        booleano(e, p, "altura_supuesta", r)
        if alt is not None and base is not None and base > alt:
            e(r + ".base", f"{base} m está por encima de la altura, {alt} m")
    _geojson(e, d, ejemplo, ("Polygon", "MultiPolygon"), props)


def validar_calor(e, d, slug, ejemplo, contexto):
    def props(e, p, r, _):
        sin = booleano(e, p, "sin_dato", r)
        numero(e, p, "t_superficie_c", r, -30, 90, decimales=1, nulo=bool(sin))
        numero(e, p, "n_escenas", r, 0, entero=True)
    _geojson(e, d, ejemplo, ("Polygon",), props)


def validar_agua(e, d, slug, ejemplo, contexto):
    if isinstance(d, dict) and isinstance(d.get("metadatos"), dict):
        texto(e, d["metadatos"], "limite", "metadatos")

    def props(e, p, r, geometria):
        tipo = una_de(e, p, "tipo", r, ("escorrentia", "punto_bajo"))
        if tipo == "escorrentia":
            if geometria != "LineString":
                e(r + ".tipo", "una línea de escorrentía es un LineString")
            numero(e, p, "acumulacion_celdas", r, 1, entero=True)
        elif tipo == "punto_bajo":
            if geometria != "Point":
                e(r + ".tipo", "un punto bajo es un Point")
            numero(e, p, "relleno_m", r, 0, decimales=2)
            numero(e, p, "area_m2", r, 0)
    _geojson(e, d, ejemplo, ("LineString", "Point"), props)


def validar_capas(e, d, slug, ejemplo, contexto):
    cabecera(e, d, "", ejemplo)
    if not isinstance(d, dict):
        return
    cob = objeto(e, d, "cobertura", "")
    if cob is not None:
        esquinas = lista(e, cob, "esquinas", "cobertura", n=4) or []
        for i, c in enumerate(esquinas):
            _coordenadas(e, c, f"cobertura.esquinas[{i}]")
    for ri, c in _elementos(e, lista(e, d, "clases", "", minimo=1), "clases"):
        numero(e, c, "clase", ri, 0, 255, entero=True)
        texto(e, c, "nombre", ri)
        color = texto(e, c, "color", ri)
        if color and not re.fullmatch(r"#[0-9a-f]{6}", color):
            e(ri + ".color", f"{color!r} no es #rrggbb en minúsculas")
    ls = objeto(e, d, "landsat", "")
    if ls is not None:
        per = objeto(e, ls, "periodo", "landsat")
        if per is not None:
            fecha(e, per, "desde", "landsat.periodo")
            fecha(e, per, "hasta", "landsat.periodo")
        numero(e, ls, "escenas", "landsat", 0, entero=True)
        hora = texto(e, ls, "hora_local", "landsat")
        if hora and not re.fullmatch(r"\d{2}:\d{2}", hora):
            e("landsat.hora_local", f"{hora!r} no es HH:MM")
    ed = objeto(e, d, "edificios", "")
    if ed is not None:
        numero(e, ed, "con_altura", "edificios", 0, entero=True)
        numero(e, ed, "sin_altura", "edificios", 0, entero=True)


def validar_relieve(e, d, slug, ejemplo, contexto):
    cabecera(e, d, "", ejemplo)
    if not isinstance(d, dict):
        return
    igual(e, d, "escuela", "", slug)
    for i, g in enumerate(lista(e, d, "granulos", "", minimo=1) or []):
        if not isinstance(g, str):
            e(f"granulos[{i}]", "no es un texto")
    b = lista(e, d, "bounds", "", n=4)
    if b and len(b) == 4 and all(_es_numero(x) for x in b):
        oeste, sur, este, norte = b
        if not (-180 <= oeste < este <= 180 and -90 <= sur < norte <= 90):
            e("bounds", f"{b} no es [oeste, sur, este, norte]")
    zmin = numero(e, d, "minzoom", "", 0, 22, entero=True)
    zmax = numero(e, d, "maxzoom", "", 0, 22, entero=True)
    if zmin is not None and zmax is not None and zmin > zmax:
        e("minzoom", f"{zmin} pasa de maxzoom, {zmax}")
    numero(e, d, "precision_m", "", 0.01, 100)
    numero(e, d, "altitud_escuela_m", "", -500, 6000, decimales=1)
    contexto["zoom"] = (zmin, zmax)


def validar_maqueta_stl(e, d, slug, ejemplo, contexto):
    cabecera(e, d, "", ejemplo)
    if not isinstance(d, dict):
        return
    escala = texto(e, d, "escala", "")
    if escala and not re.fullmatch(r"1:\d+", escala):
        e("escala", f"{escala!r} no es 1:N")
    numero(e, d, "exageracion", "", 1, 10)
    numero(e, d, "lado_mm", "", 1, 1000)
    tri = numero(e, d, "triangulos", "", 1, entero=True)
    n_bytes = numero(e, d, "bytes", "", 84, entero=True)
    texto(e, d, "limite", "")
    stl = contexto.get("maqueta.stl")
    if stl is not None:
        if n_bytes is not None and n_bytes != len(stl):
            e("bytes", f"es {n_bytes}, y maqueta.stl tiene {len(stl)}")
        if tri is not None and len(stl) >= 84 and int.from_bytes(stl[80:84], "little") != tri:
            e("triangulos", "no coincide con la cabecera de maqueta.stl")


# Los archivos comunes

def validar_escuelas(e, d, ejemplo=False):
    """escuelas.json, tal como lo define la orden #57: la fuente va en cada escuela."""
    cabecera(e, d, "", False, fuentes=False)
    if not isinstance(d, dict):
        return {}
    salida, anclas = {}, 0
    for i, x in enumerate(lista(e, d, "escuelas", "", minimo=1) or []):
        ri = f"escuelas[{i}]"
        if not isinstance(x, dict):
            e(ri, "no es un objeto")
            continue
        slug = texto(e, x, "slug", ri)
        if slug and not re.fullmatch(r"[a-z]{2}-[a-z0-9-]+", slug):
            e(ri + ".slug", f"{slug!r} no es <país>-<nombre>")
        if slug == "ejemplo":
            e(ri + ".slug", "el ejemplo no va en escuelas.json")
        for k in ("nombre", "municipio", "division", "pais"):
            texto(e, x, k, ri)
        texto(e, x, "codigo", ri, nulo=True)
        texto(e, x, "iso_pais", ri)
        numero(e, x, "lat", ri, -90, 90, decimales=5)
        numero(e, x, "lon", ri, -180, 180, decimales=5)
        numero(e, x, "huso_horas", ri, -12, 14, entero=True)
        if booleano(e, x, "ancla", ri):
            anclas += 1
        est = objeto(e, x, "estacion", ri)
        if est is not None:
            texto(e, est, "nombre", ri + ".estacion")
            numero(e, est, "lat", ri + ".estacion", -90, 90)
            numero(e, est, "lon", ri + ".estacion", -180, 180)
            numero(e, est, "distancia_km", ri + ".estacion", 0, 500, decimales=1)
        fc = objeto(e, x, "fuente_coordenadas", ri)
        if fc is not None:
            rf = ri + ".fuente_coordenadas"
            texto(e, fc, "nombre", rf)
            texto(e, fc, "url", rf)
            fecha(e, fc, "fecha_consulta", rf)
            una_de(e, fc, "metodo", rf, ("directorio", "direccion-en-mapa"))
        if slug:
            salida[slug] = x
    if salida and anclas != 1:
        e("escuelas", f"hay {anclas} escuelas con \"ancla\": true, y es una")
    return salida


def validar_limites(e, d, ejemplo=False):
    cabecera(e, d, "", ejemplo)
    ids = set()
    for ri, x in _elementos(e, lista(e, d, "limites", "", minimo=1), "limites"):
        lid = texto(e, x, "id", ri)
        if lid and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", lid):
            e(ri + ".id", f"{lid!r} no va en minúsculas, sin tildes y con guiones")
        if lid in ids:
            e(ri + ".id", f"{lid!r} se repite")
        ids.add(lid)
        texto(e, x, "titulo", ri)
        for reg in REGISTROS:
            texto(e, x, reg, ri)
    return ids


def validar_glosario(e, d, ejemplo=False):
    cabecera(e, d, "", ejemplo)
    for ri, x in _elementos(e, lista(e, d, "terminos", "", minimo=1), "terminos"):
        texto(e, x, "termino", ri)
        texto(e, x, "definicion", ri)


def validar_maqueta_generica(e, d, ejemplo=False):
    cabecera(e, d, "", ejemplo)
    if not isinstance(d, dict):
        return
    texto(e, d, "aviso", "")
    for k in ("volumenes", "superficies", "cubiertas", "arboles"):
        lista(e, d, k, "")
    objeto(e, d, "agua", "")
    for k in ("lat", "lon", "latitud", "longitud"):
        if k in d:
            e(k, "la maqueta genérica no lleva puntos geográficos")


def validar_reserva(e, d, ejemplo=False):
    cabecera(e, d, "", ejemplo)
    regs = objeto(e, d, "registros", "")
    if regs is None:
        return
    for reg in REGISTROS:
        for ri, x in _elementos(e, lista(e, regs, reg, "registros", minimo=1),
                                f"registros.{reg}"):
            texto(e, x, "pregunta", ri)
            texto(e, x, "respuesta", ri)
            numero(e, x, "fila_bateria", ri, 1, entero=True)


def validar_material(e, d, carpeta: Path):
    cabecera(e, d, "", False)
    for ri, x in _elementos(e, lista(e, d, "pdfs", "", minimo=1), "pdfs"):
        texto(e, x, "escuela", ri)
        una_de(e, x, "registro", ri, REGISTROS)
        nombre = texto(e, x, "archivo", ri)
        numero(e, x, "paginas", ri, 1, 4, entero=True)
        numero(e, x, "kb", ri, 0, 500, decimales=1)
        if nombre and not (carpeta / nombre).is_file():
            e(ri + ".archivo", f"{nombre} no está en {carpeta.name}/")


VALIDADORES = {
    "escuela.json": validar_escuela,
    "clima.json": validar_clima,
    "validacion.json": validar_validacion,
    "recorrido.json": validar_recorrido,
    "edificios.geojson": validar_edificios,
    "calor.geojson": validar_calor,
    "capas.json": validar_capas,
    "agua.geojson": validar_agua,
    "maqueta-stl.json": validar_maqueta_stl,
}
VALIDADORES_COMUNES = {
    "comun/limites.json": validar_limites,
    "comun/glosario.json": validar_glosario,
    "comun/maqueta-generica.json": validar_maqueta_generica,
    "comun/reserva.json": validar_reserva,
}


# La carpeta

def _gzip(datos: bytes) -> int:
    return len(gzip.compress(datos, compresslevel=9))


def _leer_json(e, ruta: Path):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        e("(archivo)", "no está en UTF-8")
    except json.JSONDecodeError as exc:
        e("(archivo)", f"no es JSON: línea {exc.lineno}, columna {exc.colno}")
    return None


def _errores(n: int) -> str:
    return "1 error" if n == 1 else f"{n} errores"


class Informe:
    """Las filas de la tabla y los errores, cada uno con su archivo."""

    def __init__(self):
        self.filas = []     # (nombre, estado, bytes con gzip o None, grupo)
        self.errores = []   # (archivo, campo, mensaje)

    def fila(self, nombre, estado, n, grupo):
        self.filas.append((nombre, estado, n, grupo))

    def anotar(self, nombre, e: Errores):
        for c, m in e.lista:
            self.errores.append((nombre, c, m))
        return "en orden" if not e.lista else _errores(len(e.lista))


def comunes(raiz: Path, informe: Informe) -> dict:
    """Valida escuelas.json y comun/, y devuelve el contexto y los bytes de cada uno."""
    contexto, pesos = {}, {}
    ruta = raiz / "escuelas.json"
    if ruta.is_file():
        e = Errores()
        d = _leer_json(e, ruta)
        if d is not None:
            contexto["escuelas"] = validar_escuelas(e, d)
        pesos["escuelas.json"] = _gzip(ruta.read_bytes())
        informe.fila("escuelas.json", informe.anotar("escuelas.json", e),
                     pesos["escuelas.json"], "primera")
    else:
        informe.fila("escuelas.json", "falta", None, "primera")

    comun = raiz / "comun"
    medidos = {f"comun/{n}": g for n, _, g in medir(comun)} if comun.is_dir() else {}
    for nombre, grupo in ARCHIVOS_COMUNES:
        if nombre not in medidos:
            informe.fila(nombre, "falta", None, grupo)
            continue
        e = Errores()
        d = _leer_json(e, raiz / nombre)
        if d is not None:
            r = VALIDADORES_COMUNES[nombre](e, d)
            if nombre == "comun/limites.json":
                contexto["limites"] = r
        pesos[nombre] = medidos[nombre]
        informe.fila(nombre, informe.anotar(nombre, e), medidos[nombre], grupo)
    conocidos = {n for n, _ in ARCHIVOS_COMUNES}
    for nombre in sorted(set(medidos) - conocidos):
        informe.errores.append((nombre, "(archivo)", "no está en el contrato de datos"))
        informe.fila(nombre, "fuera del contrato", medidos[nombre], "peticion")
    return {"contexto": contexto, "pesos": pesos}


def escuela(carpeta: Path, informe: Informe, compartido: dict) -> tuple:
    """Valida una carpeta de escuela. Devuelve los bytes de la primera pantalla y del mapa,
    con lo que exista de escuelas.json y comun/."""
    slug = carpeta.name
    ejemplo = slug == "ejemplo"
    contexto = dict(compartido["contexto"])
    medidos = {n: g for n, _, g in medir(carpeta)}
    primera = sum(g for n, g in compartido["pesos"].items()
                  if n in ("escuelas.json", "comun/limites.json", "comun/glosario.json",
                           "comun/maqueta-generica.json"))
    mapa = 0

    stl = carpeta / "maqueta.stl"
    if stl.is_file():
        contexto["maqueta.stl"] = stl.read_bytes()
    vistos = set()
    for nombre, grupo in ARCHIVOS_ESCUELA:
        mostrado = f"{slug}/{nombre}"
        if nombre == "relieve/":
            n_bytes, estado = _relieve(carpeta, slug, ejemplo, contexto, medidos, informe,
                                       vistos)
        elif nombre not in medidos:
            n_bytes, estado = None, "falta"
        else:
            vistos.add(nombre)
            n_bytes = medidos[nombre]
            e = Errores()
            ruta = carpeta / nombre
            if nombre == "cobertura.png":
                if not ruta.read_bytes().startswith(PNG):
                    e("(archivo)", "no es un PNG")
                if "capas.json" not in medidos:
                    e("(archivo)", "sus esquinas van en capas.json, que falta")
            elif nombre == "maqueta.stl":
                datos = contexto["maqueta.stl"]
                n_tri = int.from_bytes(datos[80:84], "little") if len(datos) >= 84 else -1
                if len(datos) < 84 or len(datos) != 84 + 50 * n_tri:
                    e("(archivo)", "no es un STL binario completo")
                if "maqueta-stl.json" not in medidos:
                    e("(archivo)", "su descripción va en maqueta-stl.json, que falta")
            else:
                d = _leer_json(e, ruta)
                if d is not None:
                    VALIDADORES[nombre](e, d, slug, ejemplo, contexto)
                    contexto[nombre] = d
            estado = informe.anotar(mostrado, e)
        if n_bytes is not None:
            if grupo == "primera":
                primera += n_bytes
            elif grupo == "mapa":
                mapa += n_bytes
        informe.fila(mostrado, estado if grupo != "peticion" or estado == "falta"
                     else f"{estado}, a petición", n_bytes, grupo)
    for nombre in sorted(set(medidos) - vistos):
        informe.errores.append((f"{slug}/{nombre}", "(archivo)",
                                "no está en el contrato de datos"))
        informe.fila(f"{slug}/{nombre}", "fuera del contrato", medidos[nombre], "peticion")
    return primera, mapa


def _relieve(carpeta, slug, ejemplo, contexto, medidos, informe, vistos):
    nombres = [n for n in medidos if n.startswith("relieve/")]
    if not nombres:
        return None, "falta"
    vistos.update(nombres)
    mostrado = f"{slug}/relieve/"
    e = Errores()
    if "relieve/relieve.json" not in medidos:
        e("relieve.json", "falta, y sin él no se leen las teselas")
    else:
        d = _leer_json(e, carpeta / "relieve" / "relieve.json")
        if d is not None:
            validar_relieve(e, d, slug, ejemplo, contexto)
    zmin, zmax = contexto.get("zoom", (None, None))
    teselas = 0
    for n in sorted(nombres):
        if n == "relieve/relieve.json":
            continue
        m = re.fullmatch(r"relieve/(\d+)/(\d+)/(\d+)\.png", n)
        if not m:
            e(n, "no es una tesela {z}/{x}/{y}.png")
            continue
        teselas += 1
        z = int(m.group(1))
        if zmin is not None and zmax is not None and not zmin <= z <= zmax:
            e(n, f"el zum {z} está fuera de minzoom y maxzoom")
        if not (carpeta / n).read_bytes().startswith(PNG):
            e(n, "no es un PNG")
    if not teselas:
        e("relieve/", "no tiene teselas")
    estado = informe.anotar(mostrado, e)
    if estado == "en orden":
        estado = f"en orden, {teselas} teselas"
    return sum(medidos[n] for n in nombres), estado


def material(raiz_web: Path, informe: Informe):
    ruta = raiz_web / "material" / "material.json"
    nombre = "material/material.json"
    if not ruta.is_file():
        informe.fila(nombre, "falta", None, "peticion")
        return
    e = Errores()
    d = _leer_json(e, ruta)
    if d is not None:
        validar_material(e, d, ruta.parent)
    informe.fila(nombre, informe.anotar(nombre, e), _gzip(ruta.read_bytes()), "peticion")


# La salida

def _tabla(filas) -> list:
    ancho = max([len("Archivo")] + [len(f[0]) for f in filas])
    ancho_e = max([len("Estado")] + [len(f[1]) for f in filas])
    lineas = [f"{'Archivo':<{ancho}}  {'Estado':<{ancho_e}}  {'gzip -9':>9}"]
    for nombre, estado, n, _ in filas:
        peso = f"{kb(n)} KB" if n is not None else "—"
        lineas.append(f"{nombre:<{ancho}}  {estado:<{ancho_e}}  {peso:>9}")
    return lineas


def _totales(slug, primera, mapa) -> tuple:
    lineas, bien = [], True
    for rotulo, total, limite in (("primera pantalla", primera, LIMITE_PRIMERA_PANTALLA),
                                  ("mapa", mapa, LIMITE_MAPA)):
        dentro = total <= limite
        bien &= dentro
        verbo = "dentro del límite" if dentro else "pasa del límite"
        lineas.append(f"{slug}, {rotulo}: {kb(total)} KB con gzip -9, de "
                      f"{limite // 1000} KB ({verbo})")
    return lineas, bien


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("carpeta", nargs="?", type=Path,
                        help="la carpeta de una escuela, o del ejemplo, en web/datos/")
    parser.add_argument("--todas", action="store_true",
                        help="todas las carpetas de web/datos/, escuelas.json y comun/")
    parser.add_argument("--raiz", type=Path, default=Path("web/datos"),
                        help="la carpeta de los datos con --todas (por defecto, web/datos)")
    args = parser.parse_args(argv)
    if args.todas == (args.carpeta is not None):
        parser.error("se da una carpeta o --todas, una de las dos")

    if args.todas:
        raiz = args.raiz
        if not raiz.is_dir():
            parser.error(f"{raiz} no es una carpeta")
        carpetas = sorted(p for p in raiz.iterdir() if p.is_dir() and p.name != "comun")
    else:
        if not args.carpeta.is_dir():
            parser.error(f"{args.carpeta} no es una carpeta")
        raiz = args.carpeta.resolve().parent
        carpetas = [args.carpeta]

    informe = Informe()
    compartido = comunes(raiz, informe)
    totales = []
    for carpeta in carpetas:
        totales.append((carpeta.name, *escuela(carpeta, informe, compartido)))
    if args.todas:
        for p in sorted(raiz.iterdir()):
            if p.is_file() and p.name != "escuelas.json":
                informe.errores.append((p.name, "(archivo)", "no está en el contrato de datos"))
        material(raiz.parent, informe)

    for linea in _tabla(informe.filas):
        print(linea)
    print()
    bien = True
    for slug, primera, mapa in totales:
        lineas, ok = _totales(slug, primera, mapa)
        bien &= ok
        for linea in lineas:
            print(linea)
    if informe.errores:
        print()
        for archivo, c, m in informe.errores:
            print(f"{archivo}: {c}: {m}")
    if informe.errores or not bien:
        print(f"\nel contrato no se cumple: {_errores(len(informe.errores))}"
              + ("" if bien else ", y un presupuesto superado"))
        return 1
    print("\ncontrato en orden")
    return 0


if __name__ == "__main__":
    # En Windows la consola no siempre escribe en UTF-8.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
