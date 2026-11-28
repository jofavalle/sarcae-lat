"""Recorrido guiado de una escuela: sus paradas y sus preguntas para conversar, en los tres
registros, con las cifras tomadas de sus datos.

Lee la fuente, `docs/material/recorrido/<slug>.json` (material propio, CC BY 4.0), y
resuelve sus marcadores, como `{{clima.calor.horas_1996_2025}}` o
`{{clima.episodios.lista.0.fecha|fecha}}`, contra `escuela.json`, `clima.json` y, si existe,
`validacion.json` de la carpeta de datos. Escribe `recorrido.json` con la cabecera del
contrato (docs/contrato-datos.md).

Antes de escribir comprueba:
- que no queda ningún marcador sin resolver;
- que la fuente no escribe a mano más cifras que las del método (CIFRAS_METODO);
- que hay de 5 a 7 paradas, con `id` distintos, `maqueta` y `mapa`;
- que cada parada tiene los tres registros en `texto` y en `pregunta`, con 450 caracteres
  como mucho por texto y cada pregunta entre «¿» y «?»;
- que ningún texto lleva las palabras de PALABRAS_PROHIBIDAS ni de PALABRAS_INTERIOR,
  importadas de `src.contrato`.

Si `escuela.json` o `clima.json` traen `datos_ficticios` (#61), la nota se repite en la raíz
de `recorrido.json` y se imprime como aviso. Si los datos son del ejemplo, se repiten
`ejemplo` y `aviso`.

Uso, desde la raíz del repositorio:

    python -m src.recorrido --escuela sv-88118
    python -m src.recorrido --escuela sv-88118 --comprobar
    python -m src.recorrido --fuente docs/material/recorrido/sv-88118.json \\
        --datos web/datos/ejemplo --salida data/processed/recorrido-prueba.json

`--comprobar` regenera y compara con lo versionado, sin el bloque `generado` y sin escribir.

Solo usa la biblioteca estándar.
"""

import argparse
import hashlib
import json
import re
import shlex
import sys
from datetime import date
from pathlib import Path

from src.contrato import CAPAS_MAPA, CAPAS_MAQUETA, CONTRATO, REGISTROS, VISTAS, vetadas
from src.recortes import RAIZ, generado, guardar_json

MATERIAL = Path("docs/material/recorrido")
DATOS = Path("web/datos")
REPOSITORIO = "https://github.com/jofavalle/sarcae-lat"

# Los archivos contra los que se resuelven los marcadores; validacion.json puede faltar.
ARCHIVOS = ("escuela", "clima", "validacion")
OPCIONALES = ("validacion",)

PARADAS_MIN, PARADAS_MAX = 5, 7
MAX_TEXTO = 450

MARCADOR = re.compile(r"\{\{\s*([a-z]+)((?:\.[A-Za-z0-9_]+)+)\s*(?:\|\s*([a-z]+)\s*)?\}\}")
# Las únicas cifras que la fuente escribe a mano: las del método de la #22, el umbral, el
# horario y los dos periodos. Las de los datos van siempre con un marcador. Una cifra pegada
# a una letra es parte de un nombre, como ERA5 o la vista 2d, y no cuenta.
CIFRAS_METODO = frozenset({"27", "07:00", "17:00", "1961", "1990", "1996", "2025"})
CIFRA = re.compile(r"(?<!\w)\d+(?:[.,:]\d+)*(?!\w)")

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")


# Los marcadores

class SinResolver(ValueError):
    pass


def buscar(datos: dict, archivo: str, ruta: list):
    """El valor de `archivo` en la ruta dada: claves de objeto o posiciones de lista."""
    if archivo not in datos:
        raise SinResolver(f"no hay {archivo}.json en los datos")
    valor = datos[archivo]
    for i, paso in enumerate(ruta):
        hecho = ".".join([archivo, *ruta[:i + 1]])
        if isinstance(valor, dict) and paso in valor:
            valor = valor[paso]
        elif isinstance(valor, list) and paso.isdigit() and int(paso) < len(valor):
            valor = valor[int(paso)]
        else:
            raise SinResolver(f"{hecho} no está en {archivo}.json")
    return valor


def formatear(valor, filtro=None) -> str:
    """El valor como se lee en pantalla: coma decimal, signo menos y fechas en palabras."""
    if filtro == "fecha":
        if not isinstance(valor, str):
            raise SinResolver(f"{valor!r} no es una fecha AAAA-MM-DD")
        try:
            d = date.fromisoformat(valor)
        except ValueError:
            raise SinResolver(f"{valor!r} no es una fecha AAAA-MM-DD") from None
        return f"{d.day} de {MESES[d.month - 1]} de {d.year}"
    if filtro is not None:
        raise SinResolver(f"el filtro «{filtro}» no existe: solo hay «fecha»")
    if isinstance(valor, bool) or valor is None:
        raise SinResolver(f"es {json.dumps(valor)}, y no es una cifra ni un texto")
    if isinstance(valor, int):
        return str(valor).replace("-", "−")
    if isinstance(valor, float):
        texto = str(valor)
        if "e" in texto or "n" in texto:
            raise SinResolver(f"{valor!r} no se puede escribir como cifra")
        return texto.replace("-", "−").replace(".", ",")
    if isinstance(valor, str) and valor.strip():
        return valor
    if (isinstance(valor, list) and len(valor) == 2
            and all(isinstance(x, int) and not isinstance(x, bool) for x in valor)):
        return f"{valor[0]}–{valor[1]}"
    raise SinResolver(f"{json.dumps(valor, ensure_ascii=False)[:60]} no es una cifra ni un texto")


def resolver(texto: str, datos: dict, resueltos: dict, usados: set, errores: list, ruta: str):
    """El texto con sus marcadores sustituidos; los que fallan quedan como estaban."""
    def sustituir(m):
        archivo, pasos, filtro = m.group(1), m.group(2)[1:].split("."), m.group(3)
        try:
            valor = formatear(buscar(datos, archivo, pasos), filtro)
        except SinResolver as fallo:
            errores.append(f"{ruta}: {m.group(0)}: {fallo}")
            return m.group(0)
        resueltos[m.group(0)] = valor
        usados.add(archivo)
        return valor
    return MARCADOR.sub(sustituir, texto)


def resolver_todo(valor, datos, resueltos, usados, errores, ruta=""):
    if isinstance(valor, str):
        return resolver(valor, datos, resueltos, usados, errores, ruta)
    if isinstance(valor, dict):
        return {k: resolver_todo(v, datos, resueltos, usados, errores, _unir(ruta, k))
                for k, v in valor.items()}
    if isinstance(valor, list):
        return [resolver_todo(v, datos, resueltos, usados, errores, _unir(ruta, i))
                for i, v in enumerate(valor)]
    return valor


def _unir(ruta, clave):
    if isinstance(clave, int):
        return f"{ruta}[{clave}]"
    return f"{ruta}.{clave}" if ruta else clave


def _cadenas(valor, ruta=""):
    if isinstance(valor, str):
        yield ruta, valor
    elif isinstance(valor, dict):
        for k, v in valor.items():
            yield from _cadenas(v, _unir(ruta, k))
    elif isinstance(valor, list):
        for i, v in enumerate(valor):
            yield from _cadenas(v, _unir(ruta, i))


# Las comprobaciones

def cifras_a_mano(fuente: dict) -> list:
    """Las cifras que la fuente escribe fuera de un marcador y que no son del método."""
    errores = []
    for ruta, texto in _cadenas({"registros": fuente.get("registros"),
                                 "paradas": fuente.get("paradas")}):
        for cifra in CIFRA.findall(MARCADOR.sub("", texto)):
            if cifra not in CIFRAS_METODO:
                errores.append(f"{ruta}: «{cifra}» está escrita a mano; las cifras de los "
                               "datos van con un marcador {{archivo.ruta}}")
    return errores


def comprobar(doc: dict) -> list:
    """Los errores del recorrido ya resuelto."""
    errores = []
    for ruta, texto in _cadenas(doc):
        if "{{" in texto or "}}" in texto:
            errores.append(f"{ruta}: lleva un marcador sin resolver")

    regs = doc.get("registros")
    if not isinstance(regs, dict):
        errores.append("registros: falta")
        regs = {}
    for reg in REGISTROS:
        o = regs.get(reg)
        if not isinstance(o, dict):
            errores.append(f"registros.{reg}: falta el registro")
            continue
        for k in ("nombre", "titulo", "entrada"):
            if not isinstance(o.get(k), str) or not o[k].strip():
                errores.append(f"registros.{reg}.{k}: falta")

    paradas = doc.get("paradas")
    if not isinstance(paradas, list):
        return errores + ["paradas: falta la lista"]
    if not PARADAS_MIN <= len(paradas) <= PARADAS_MAX:
        errores.append(f"paradas: son {len(paradas)}, y van de {PARADAS_MIN} a {PARADAS_MAX}")
    ids = set()
    for i, p in enumerate(paradas):
        ri = f"paradas[{i}]"
        if not isinstance(p, dict):
            errores.append(f"{ri}: no es un objeto")
            continue
        pid = p.get("id")
        if not isinstance(pid, str) or not pid.strip():
            errores.append(f"{ri}.id: falta")
        elif pid in ids:
            errores.append(f"{ri}.id: «{pid}» se repite")
        ids.add(pid)
        if not isinstance(p.get("titulo"), str) or not p["titulo"].strip():
            errores.append(f"{ri}.titulo: falta")
        errores += _maqueta_y_mapa(p, ri)
        for clave in ("texto", "pregunta"):
            o = p.get(clave)
            if not isinstance(o, dict):
                errores.append(f"{ri}.{clave}: falta")
                continue
            for reg in REGISTROS:
                t = o.get(reg)
                r = f"{ri}.{clave}.{reg}"
                if not isinstance(t, str) or not t.strip():
                    errores.append(f"{r}: falta el registro")
                elif clave == "texto" and len(t) > MAX_TEXTO:
                    errores.append(f"{r}: tiene {len(t)} caracteres, y son {MAX_TEXTO} como mucho")
                elif clave == "pregunta" and not (t.strip().startswith("¿")
                                                  and t.strip().endswith("?")):
                    errores.append(f"{r}: la pregunta no va entre «¿» y «?»")
            for otro in o:
                if otro not in REGISTROS:
                    errores.append(f"{ri}.{clave}.{otro}: no es un registro: son "
                                   f"{', '.join(REGISTROS)}")

    for ruta, texto in _cadenas({"registros": regs, "paradas": paradas}):
        for palabra in vetadas(texto):
            errores.append(f"{ruta}: lleva «{palabra}»")
    return errores


def _maqueta_y_mapa(p, ri):
    errores = []
    m = p.get("maqueta")
    if not isinstance(m, dict):
        errores.append(f"{ri}.maqueta: falta")
    else:
        if not isinstance(m.get("volumen"), str) or not m["volumen"].strip():
            errores.append(f"{ri}.maqueta.volumen: falta")
        if m.get("capa") not in CAPAS_MAQUETA:
            errores.append(f"{ri}.maqueta.capa: es {m.get('capa')!r}, y es una de "
                           f"{', '.join(CAPAS_MAQUETA)}")
        h = m.get("hora")
        if not (isinstance(h, int) and not isinstance(h, bool) and 0 <= h <= 23):
            errores.append(f"{ri}.maqueta.hora: {h!r} no es una hora entera de 0 a 23")
    m = p.get("mapa")
    if not isinstance(m, dict):
        errores.append(f"{ri}.mapa: falta")
    else:
        if m.get("vista") not in VISTAS:
            errores.append(f"{ri}.mapa.vista: es {m.get('vista')!r}, y es una de "
                           f"{', '.join(VISTAS)}")
        if m.get("capa") not in CAPAS_MAPA:
            errores.append(f"{ri}.mapa.capa: es {m.get('capa')!r}, y es una de "
                           f"{', '.join(CAPAS_MAPA)}")
    return errores


# El documento

def _relativa(ruta: Path) -> str:
    try:
        return ruta.resolve().relative_to(RAIZ).as_posix()
    except ValueError:
        return ruta.name


def leer_datos(carpeta: Path) -> dict:
    datos = {}
    for nombre in ARCHIVOS:
        ruta = carpeta / f"{nombre}.json"
        if ruta.exists():
            datos[nombre] = json.loads(ruta.read_text(encoding="utf-8"))
        elif nombre not in OPCIONALES:
            raise FileNotFoundError(f"falta {_relativa(ruta)}")
    return datos


def fuente_material(ruta: Path, texto: str, licencia) -> dict:
    nombre = _relativa(ruta)
    return {
        "nombre": nombre,
        "version": "sha256:" + hashlib.sha256(texto.encode("utf-8")).hexdigest(),
        "licencia": licencia,
        "url": f"{REPOSITORIO}/blob/main/{nombre}",
    }


def construir(ruta_fuente: Path, datos: dict, procedencia: dict):
    """(documento, marcadores resueltos, errores) del recorrido."""
    texto = ruta_fuente.read_text(encoding="utf-8")
    fuente = json.loads(texto)
    errores = []
    if fuente.get("licencia") != "CC-BY-4.0":
        errores.append(f"{ruta_fuente.name}: licencia: es {fuente.get('licencia')!r}, y el "
                       "material propio va con 'CC-BY-4.0'")
    errores += cifras_a_mano(fuente)

    resueltos, usados = {}, set()
    cuerpo = resolver_todo({"registros": fuente.get("registros"),
                            "paradas": fuente.get("paradas")},
                           datos, resueltos, usados, errores)

    fuentes = [fuente_material(ruta_fuente, texto, fuente.get("licencia"))]
    vistas = set()
    for nombre in ARCHIVOS:
        if nombre not in usados:
            continue
        for f in datos[nombre].get("fuentes", []):
            clave = (f.get("nombre"), f.get("version"))
            if clave not in vistas:
                vistas.add(clave)
                fuentes.append(f)

    doc = {"contrato": CONTRATO}
    escuela = datos["escuela"]
    if escuela.get("ejemplo") is True:
        doc["ejemplo"] = True
        doc["aviso"] = escuela.get("aviso")
    notas = []
    for nombre in ARCHIVOS:
        nota = datos.get(nombre, {}).get("datos_ficticios")
        if nota and nota not in notas:
            notas.append(nota)
    if notas:
        doc["datos_ficticios"] = " ".join(notas)
    doc["generado"] = procedencia
    doc["fuentes"] = fuentes
    doc["escuela"] = escuela.get("slug")
    doc.update(cuerpo)
    errores += comprobar(doc)
    return doc, resueltos, errores


def _sin_generado(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != "generado"}


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--escuela", help="slug de escuelas.json: da la fuente, los datos y "
                                          "la salida por defecto")
    parser.add_argument("--fuente", type=Path, help="el recorrido con sus marcadores")
    parser.add_argument("--datos", type=Path, help="la carpeta con escuela.json y clima.json")
    parser.add_argument("--salida", type=Path, help="el recorrido.json que se escribe")
    parser.add_argument("--comprobar", action="store_true",
                        help="regenera y compara con la salida, sin escribir")
    args = parser.parse_args(argv)

    if args.escuela:
        fuente = args.fuente or RAIZ / MATERIAL / f"{args.escuela}.json"
        carpeta = args.datos or RAIZ / DATOS / args.escuela
        salida = args.salida or carpeta / "recorrido.json"
    elif args.fuente and args.datos and args.salida:
        fuente, carpeta, salida = args.fuente, args.datos, args.salida
    else:
        parser.error("se da --escuela, o --fuente, --datos y --salida")

    argumentos = ["python", "-m", "src.recorrido"]
    if args.escuela:
        argumentos += ["--escuela", args.escuela]
    for opcion, valor in (("--fuente", args.fuente), ("--datos", args.datos),
                          ("--salida", args.salida)):
        if valor is not None:
            argumentos += [opcion, _relativa(valor)]

    try:
        datos = leer_datos(carpeta)
    except FileNotFoundError as fallo:
        print(f"[FALLA] {fallo}")
        return 1
    doc, resueltos, errores = construir(fuente, datos, generado(shlex.join(argumentos)))

    if "datos_ficticios" in doc:
        print(f"AVISO, DATOS FICTICIOS: {doc['datos_ficticios']}")
    paradas = doc.get("paradas") or []
    print(f"paradas: {len(paradas)}")
    for i, p in enumerate(paradas, 1):
        if isinstance(p, dict):
            print(f"  {i}. {p.get('id')}: {p.get('titulo')}")
    print(f"marcadores resueltos: {len(resueltos)}")
    for marcador, valor in resueltos.items():
        print(f"  {marcador} = {valor}")

    if errores:
        for fallo in errores:
            print(f"[FALLA] {fallo}")
        print(f"recorrido con {len(errores)} errores: no se escribe {_relativa(salida)}")
        return 1

    if not args.comprobar:
        salida.parent.mkdir(parents=True, exist_ok=True)
        guardar_json(salida, doc)
        print(f"escrito {_relativa(salida)}")
        return 0

    if not salida.exists():
        print(f"[FALLA] {_relativa(salida)}: no existe")
        return 1
    versionado = _sin_generado(json.loads(salida.read_text(encoding="utf-8")))
    regenerado = json.loads(json.dumps(_sin_generado(doc), ensure_ascii=False))
    if versionado != regenerado:
        distintos = sorted(k for k in set(versionado) | set(regenerado)
                           if versionado.get(k) != regenerado.get(k))
        print(f"[FALLA] {_relativa(salida)}: distinto en {', '.join(distintos)}")
        return 1
    print(f"recorrido en orden: {_relativa(salida)} coincide con lo regenerado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
