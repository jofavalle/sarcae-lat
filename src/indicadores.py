"""Indicadores de calor y de lluvia de una escuela, desde su recorte de ERA5 (#22).

Lee `recortes/<escuela>/era5/` (`serie.parquet` y `celda.json`), `web/datos/escuelas.json`
(huso y punto) y `web/datos/<escuela>/relieve/relieve.json` (`altitud_escuela_m`), y escribe
`web/datos/<escuela>/escuela.json` y `clima.json` con el contrato de datos
(`docs/contrato-datos.md`).

Uso, desde la raíz del repositorio:

    python -m src.indicadores --escuela sv-88118
    python -m src.indicadores --escuela sv-88118 --comprobar

`--comprobar` recalcula y compara con lo versionado, sin el bloque `generado`. El mismo código
sirve para las tres sedes: lo de cada país (el huso, y en El Salvador la zona de diseño) sale de
`escuelas.json` y de la tabla `ZONAS_DISENO`.

Las funciones de la primera parte son puras: reciben tablas y números y devuelven números. La
serie tiene `time` (hora UTC, con zona), `t2m` (K) y `tp` (m, acumulada en la hora que termina
en `time`), como llega de ERA5.
"""

import argparse
import json
import shlex
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATOS = ROOT / "web" / "datos"
RECORTES = ROOT / "recortes"

CONTRATO = 1
K0 = 273.15
GAMMA_K_KM = 6.5
UMBRAL_C = 27.0
HORA_INICIO, HORA_FIN = 7, 17      # locales; la de fin, fuera: diez horas por día
REFERENCIA = (1961, 1990)
RECIENTE = (1996, 2025)
SERIE = (1940, 2025)
DIAS_BASE_P99 = 10957
N_EPISODIOS = 3
HORARIO = "de lunes a viernes, de 07:00 a 17:00 hora local, con las 17:00 fuera"
FORMULA = "T_local = T_ERA5 − Γ·(z_escuela − z_celda)"
LIMITES = ["no-es-un-pronostico-ni-una-evaluacion-oficial-de-riesgo",
           "era5-describe-la-zona-no-la-escuela"]

MANUAL = {"nombre": "Manual de Diseño Mi Nueva Escuela, MINEDUCYT", "version": "2022",
          "licencia": "cita", "url": "https://www.mined.gob.sv/"}
# Zonas de diseño por país: (zona, desde, hasta), con `desde` dentro y `hasta` fuera. Solo El
# Salvador tiene criterios propios (#16); fuera, la ficha es una referencia de comparación.
ZONAS_DISENO = {
    "SV": {
        "zonas": [("costera", 0, 300), ("tropical caliente", 300, 700), ("montañosa", 700, None)],
        "referencia": "Manual de Diseño Mi Nueva Escuela, anexo 8, p. 16",
        "fuente": MANUAL,
    },
}
NASADEM = {"nombre": "NASADEM_HGT, NASA JPL, distribuido por LP DAAC", "version": "001",
           "licencia": "CC0-1.0",
           "url": "https://www.earthdata.nasa.gov/data/catalog/lpcloud-nasadem-hgt-001"}
ERA5 = {"nombre": "ERA5, serie horaria por punto (ECMWF, para el C3S)",
        "licencia": "CC-BY-4.0",
        "url": "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-timeseries"}
ERA5_Z = {"nombre": "ERA5, niveles de superficie: geopotencial de la celda (ECMWF, para el C3S)",
          "licencia": "CC-BY-4.0",
          "url": "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels"}


# Funciones puras

def correccion_k(z_escuela: float, z_celda: float, gamma: float = GAMMA_K_KM) -> float:
    """−Γ·(z_escuela − z_celda), en K. Positiva si la escuela está más baja que la celda."""
    return -gamma * (z_escuela - z_celda) / 1000.0


def hora_local(time: pd.Series, huso: int) -> pd.Series:
    """La hora UTC pasada a la hora local de un huso fijo, sin zona."""
    return (time + pd.Timedelta(hours=huso)).dt.tz_localize(None)


def horas_calor(serie: pd.DataFrame, huso: int, correccion: float) -> pd.Series:
    """Hora local de cada fila del horario escolar con T_local > 27 °C (verdadero o falso).

    El horario es de lunes a viernes, con el día de la semana en hora local, y de las 07:00
    a las 16:00 locales incluidas.
    """
    local = hora_local(serie["time"], huso)
    t_local = serie["t2m"].to_numpy() - K0 + correccion
    escolar = ((local.dt.day_of_week < 5) & (local.dt.hour >= HORA_INICIO)
               & (local.dt.hour < HORA_FIN)).to_numpy()
    sobre = escolar & (t_local > UMBRAL_C)
    return pd.Series(sobre[escolar], index=pd.DatetimeIndex(local[escolar]), name="sobre")


def horas_por_anio(sobre: pd.Series, anios: tuple) -> pd.Series:
    """Horas sobre el umbral de cada año, de `anios[0]` a `anios[1]`, con ceros."""
    cuenta = sobre.groupby(sobre.index.year).sum()
    return cuenta.reindex(range(anios[0], anios[1] + 1), fill_value=0).astype(int)


def horas_por_mes(sobre: pd.Series, periodo: tuple) -> pd.Series:
    """Media anual de las horas sobre el umbral de cada mes en el periodo, de 1 a 12."""
    dentro = sobre[(sobre.index.year >= periodo[0]) & (sobre.index.year <= periodo[1])]
    total = dentro.groupby(dentro.index.month).sum().reindex(range(1, 13), fill_value=0)
    return total / (periodo[1] - periodo[0] + 1)


def lluvia_diaria(serie: pd.DataFrame, huso: int) -> pd.Series:
    """Lluvia de cada día local, en mm. Solo días con sus 24 horas.

    La fila T es la lluvia de la hora que termina en T, y el día local D suma las horas que
    terminan en (D 00:00, D+1 00:00] locales: la hora que termina a medianoche cuenta en el
    día que acaba.
    """
    fin_local = hora_local(serie["time"], huso)
    dia = (fin_local - pd.Timedelta(hours=1)).dt.normalize()
    mm = serie["tp"].to_numpy() * 1000.0
    grupos = pd.Series(mm, index=pd.DatetimeIndex(dia)).groupby(level=0)
    suma, horas = grupos.sum(), grupos.size()
    return suma[horas == 24].rename("mm")


def en_periodo(diaria: pd.Series, periodo: tuple) -> pd.Series:
    anios = diaria.index.year
    return diaria[(anios >= periodo[0]) & (anios <= periodo[1])]


def p99(diaria: pd.Series, periodo: tuple = REFERENCIA, dias_base=DIAS_BASE_P99) -> float:
    """Percentil 99 lineal de la lluvia diaria del periodo, con los días secos.

    Si `dias_base` no es None, el periodo tiene que tener exactamente esos días: un hueco o
    un día de más daría otro umbral sin avisar.
    """
    base = en_periodo(diaria, periodo)
    if dias_base is not None and len(base) != dias_base:
        raise ValueError(f"{len(base)} días en {periodo[0]}–{periodo[1]}, y se esperan "
                         f"{dias_base}")
    return float(np.percentile(base.to_numpy(), 99, method="linear"))


def dias_sobre(diaria: pd.Series, umbral: float, anios: tuple) -> pd.Series:
    """Días de cada año con lluvia > umbral (estricto), de `anios[0]` a `anios[1]`."""
    sobre = diaria[diaria > umbral]
    cuenta = sobre.groupby(sobre.index.year).size()
    return cuenta.reindex(range(anios[0], anios[1] + 1), fill_value=0).astype(int)


def episodios(serie: pd.DataFrame, huso: int, correccion: float, diaria: pd.Series,
              umbral: float, periodo: tuple = RECIENTE, n: int = N_EPISODIOS) -> list:
    """Los `n` días locales del periodo con más lluvia entre los que superan el umbral.

    Cada uno con su fecha, su total (mm) y sus 24 horas: la posición i es la hora local que
    termina a las i+1, con la lluvia de esa hora en mm y la temperatura corregida de ese
    instante en °C. A igual lluvia, va primero el día más antiguo.
    """
    candidatos = en_periodo(diaria, periodo)
    candidatos = candidatos[candidatos > umbral]
    orden = sorted(candidatos.items(), key=lambda par: (-par[1], par[0]))[:n]
    local = pd.DatetimeIndex(hora_local(serie["time"], huso))
    por_hora = pd.DataFrame({"mm": serie["tp"].to_numpy() * 1000.0,
                             "c": serie["t2m"].to_numpy() - K0 + correccion}, index=local)
    lista = []
    for dia, total in orden:
        horas = pd.date_range(dia + pd.Timedelta(hours=1), periods=24, freq="h")
        tramo = por_hora.reindex(horas)
        lista.append({"fecha": dia, "total": float(total),
                      "lluvia": tramo["mm"].tolist(), "temperatura": tramo["c"].tolist()})
    return lista


def zona_diseno(altitud: float, iso_pais: str):
    """(zona, desde, hasta, referencia) de la altitud en su país, o None si no tiene tabla."""
    tabla = ZONAS_DISENO.get(iso_pais)
    if tabla is None:
        return None
    for zona, desde, hasta in tabla["zonas"]:
        if hasta is None or altitud < hasta:
            return zona, desde, hasta, tabla["referencia"]
    raise ValueError(f"{altitud} m no cae en ninguna zona")


def media(serie_anual: pd.Series, periodo: tuple) -> float:
    return float(serie_anual.loc[periodo[0]:periodo[1]].mean())


def calcular(serie: pd.DataFrame, huso: int, z_escuela: float, z_celda: float) -> dict:
    """Todos los indicadores, sin redondear, con y sin la corrección por altura."""
    k = correccion_k(round(z_escuela, 1), round(z_celda, 1))
    sobre = horas_calor(serie, huso, k)
    horas = horas_por_anio(sobre, SERIE)
    horas_sin = horas_por_anio(horas_calor(serie, huso, 0.0), SERIE)
    diaria = lluvia_diaria(serie, huso)
    umbral = p99(diaria)
    dias = dias_sobre(diaria, umbral, SERIE)
    return {
        "correccion": k,
        "horas": horas,
        "horas_sin_correccion": horas_sin,
        "por_mes": horas_por_mes(sobre, RECIENTE),
        "p99": umbral,
        "dias": dias,
        "dias_base": int(len(en_periodo(diaria, REFERENCIA))),
        "empates_p99": int((en_periodo(diaria, REFERENCIA) == umbral).sum()),
        "episodios": episodios(serie, huso, k, diaria, umbral),
    }


# Documentos del contrato

def _r1(x: float) -> float:
    return round(float(x), 1) + 0.0  # sin −0.0


def documento_clima(slug: str, ind: dict, z_escuela: float, z_celda: float) -> dict:
    horas, dias = ind["horas"], ind["dias"]
    return {
        "escuela": slug,
        "correccion": {
            "formula": FORMULA,
            "z_escuela": {"valor": _r1(z_escuela), "unidad": "m"},
            "z_celda": {"valor": _r1(z_celda), "unidad": "m"},
            "gamma": {"valor": GAMMA_K_KM, "unidad": "K/km"},
            "correccion": {"valor": _r1(ind["correccion"]), "unidad": "K"},
        },
        "calor": {
            "umbral": {"valor": int(UMBRAL_C), "unidad": "°C"},
            "horario": HORARIO,
            "unidad": "horas",
            "horas_1961_1990": _r1(media(horas, REFERENCIA)),
            "horas_1996_2025": _r1(media(horas, RECIENTE)),
            "serie": [{"anio": int(a), "horas": int(h)} for a, h in horas.items()],
            "por_mes": {
                "periodo": list(RECIENTE),
                "unidad": "horas",
                "meses": [{"mes": int(m), "horas": _r1(h)} for m, h in ind["por_mes"].items()],
            },
        },
        "lluvia": {
            "p99": {"valor": _r1(ind["p99"]), "unidad": "mm", "periodo": list(REFERENCIA),
                    "dias_base": DIAS_BASE_P99},
            "unidad": "días",
            "dias_1961_1990": _r1(media(dias, REFERENCIA)),
            "dias_1996_2025": _r1(media(dias, RECIENTE)),
            "serie": [{"anio": int(a), "dias": int(d)} for a, d in dias.items()],
        },
        "episodios": {
            "unidades": {"lluvia": "mm", "temperatura": "°C"},
            "lista": [{"fecha": e["fecha"].strftime("%Y-%m-%d"),
                       "lluvia_total": _r1(e["total"]),
                       "lluvia": [_r1(v) for v in e["lluvia"]],
                       "temperatura": [_r1(v) for v in e["temperatura"]]}
                      for e in ind["episodios"]],
        },
        "limites": list(LIMITES),
    }


def documento_escuela(ficha: dict, altitud: float, celda: tuple) -> dict:
    zona = zona_diseno(altitud, ficha["iso_pais"])
    doc = {k: ficha[k] for k in ("slug", "nombre", "municipio", "division", "pais",
                                 "iso_pais", "codigo", "lat", "lon", "huso_horas")}
    doc["altitud"] = {"valor": _r1(altitud), "unidad": "m", "fuente": "NASADEM"}
    if zona is None:
        doc["zona_diseno"] = None
    else:
        nombre, desde, hasta, referencia = zona
        doc["zona_diseno"] = nombre
        doc["zona_diseno_franja"] = {"desde": desde, "hasta": hasta, "unidad": "m",
                                     "referencia": referencia}
    doc["celda_era5"] = {"lat": float(celda[0]), "lon": float(celda[1]), "resolucion": 0.25,
                         "unidad": "grados"}
    doc["criterios"] = "propios" if ficha["iso_pais"] in ZONAS_DISENO else \
        "referencia de comparación"
    return doc


def con_cabecera(cuerpo: dict, generado: dict, fuentes: list, ficticio) -> dict:
    doc = {"contrato": CONTRATO}
    if ficticio:
        doc["datos_ficticios"] = ficticio
    doc["generado"] = generado
    doc["fuentes"] = fuentes
    doc.update(cuerpo)
    return doc


# Lectura y escritura

def _leer_json(ruta: Path) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def leer_entradas(slug: str, recorte: Path, altitud_manual=None) -> dict:
    escuelas = _leer_json(DATOS / "escuelas.json")["escuelas"]
    ficha = next((e for e in escuelas if e["slug"] == slug), None)
    if ficha is None:
        raise SystemExit(f"{slug} no está en web/datos/escuelas.json")
    celda = _leer_json(recorte / "celda.json")
    manifiesto = _leer_json(recorte / "manifiesto.json")
    serie = pd.read_parquet(recorte / "serie.parquet")
    notas = [celda["nota_ficticio"]] if celda.get("ficticio") else []
    relieve = DATOS / slug / "relieve" / "relieve.json"
    nasadem = NASADEM
    if altitud_manual is not None:
        altitud = float(altitud_manual)
        notas.append(f"z_escuela ficticia ({altitud:g} m): falta el relieve de la orden #60.")
    elif relieve.exists():
        datos_relieve = _leer_json(relieve)
        altitud = float(datos_relieve["altitud_escuela_m"])
        nasadem = next((f for f in datos_relieve.get("fuentes", [])
                        if "nasadem" in f.get("nombre", "").lower()), NASADEM)
    else:
        raise SystemExit(f"falta {relieve.relative_to(ROOT).as_posix()} (orden #60); "
                         "con --altitud se da una provisional, que queda marcada como ficticia")
    version = manifiesto["fuente"]["version"]
    fuentes_era5 = [dict(ERA5, version=version), dict(ERA5_Z, version=version)]
    return {"ficha": ficha, "serie": serie, "celda": celda, "altitud": altitud,
            "nasadem": nasadem, "fuentes_era5": fuentes_era5,
            "ficticio": " ".join(notas) or None}


def documentos(slug: str, ent: dict, generado: dict) -> tuple:
    ficha, celda = ent["ficha"], ent["celda"]
    z_celda = float(celda["z_celda"]["valor"])
    punto = (celda["punto_rejilla"]["lat"], celda["punto_rejilla"]["lon"])
    ind = calcular(ent["serie"], int(ficha["huso_horas"]), ent["altitud"], z_celda)
    fuentes_escuela = [ent["nasadem"], ent["fuentes_era5"][1]]
    zona = ZONAS_DISENO.get(ficha["iso_pais"])
    if zona is not None:
        fuentes_escuela.append(zona["fuente"])
    escuela = con_cabecera(documento_escuela(ficha, ent["altitud"], punto), generado,
                           fuentes_escuela, ent["ficticio"])
    clima = con_cabecera(documento_clima(slug, ind, ent["altitud"], z_celda), generado,
                         ent["fuentes_era5"] + [ent["nasadem"]], ent["ficticio"])
    return escuela, clima, ind


def resumen(escuela: dict, clima: dict, ind: dict) -> list:
    c, ca, ll = clima["correccion"], clima["calor"], clima["lluvia"]
    sin = ind["horas_sin_correccion"]
    sobre_ref = int(ind["dias"].loc[REFERENCIA[0]:REFERENCIA[1]].sum())
    lineas = []
    if escuela.get("datos_ficticios"):
        lineas.append(f"AVISO, DATOS FICTICIOS: {escuela['datos_ficticios']}")
    lineas += [
        f"z_escuela: {c['z_escuela']['valor']} m; z_celda: {c['z_celda']['valor']} m; "
        f"corrección: {c['correccion']['valor']:+.1f} K ({ind['correccion']:+.3f} K)",
        f"zona de diseño: {escuela['zona_diseno']}",
        f"p99 de la lluvia diaria de 1961–1990: {ll['p99']['valor']} mm "
        f"({ind['p99']:.3f} mm, sobre {ind['dias_base']} días; {ind['empates_p99']} empates)",
        f"{sobre_ref} días sobre el p99 en 1961–1990",
        f"horas sobre 27 °C al año, corregidas: {ca['horas_1961_1990']} en 1961–1990 y "
        f"{ca['horas_1996_2025']} en 1996–2025",
        f"horas sobre 27 °C al año, sin corregir: {_r1(media(sin, REFERENCIA))} en 1961–1990 "
        f"y {_r1(media(sin, RECIENTE))} en 1996–2025",
        f"días sobre el p99 al año: {ll['dias_1961_1990']} en 1961–1990 y "
        f"{ll['dias_1996_2025']} en 1996–2025",
        "episodios: " + ", ".join(f"{e['fecha']} ({e['lluvia_total']} mm)"
                                  for e in clima["episodios"]["lista"]),
    ]
    return lineas


def _sin_generado(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != "generado"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--escuela", required=True, help="slug de escuelas.json")
    parser.add_argument("--recorte", type=Path,
                        help="carpeta del recorte (por defecto recortes/<escuela>/era5)")
    parser.add_argument("--altitud", type=float, metavar="M",
                        help="altitud provisional de la escuela, marcada como ficticia, "
                             "mientras falte relieve.json")
    parser.add_argument("--comprobar", action="store_true",
                        help="recalcula y compara con lo versionado, sin escribir")
    args = parser.parse_args(argv)

    from src.recortes import generado, guardar_json

    recorte = (args.recorte or RECORTES / args.escuela / "era5").resolve()
    ent = leer_entradas(args.escuela, recorte, args.altitud)
    argumentos = ["python", "-m", "src.indicadores", "--escuela", args.escuela]
    if args.recorte:
        argumentos += ["--recorte", recorte.relative_to(ROOT).as_posix()]
    if args.altitud is not None:
        argumentos += ["--altitud", f"{args.altitud:g}"]
    escuela, clima, ind = documentos(args.escuela, ent, generado(shlex.join(argumentos)))
    for linea in resumen(escuela, clima, ind):
        print(linea)

    destino = DATOS / args.escuela
    if not args.comprobar:
        destino.mkdir(parents=True, exist_ok=True)
        guardar_json(destino / "escuela.json", escuela)
        guardar_json(destino / "clima.json", clima)
        print(f"escritos web/datos/{args.escuela}/escuela.json y clima.json")
        return 0

    fallos = []
    for nombre, nuevo in (("escuela.json", escuela), ("clima.json", clima)):
        ruta = destino / nombre
        if not ruta.exists():
            fallos.append(f"{nombre}: no existe")
            continue
        versionado = _sin_generado(_leer_json(ruta))
        recalculado = json.loads(json.dumps(_sin_generado(nuevo), ensure_ascii=False))
        if versionado != recalculado:
            distintos = sorted(k for k in set(versionado) | set(recalculado)
                               if versionado.get(k) != recalculado.get(k))
            fallos.append(f"{nombre}: distinto en {', '.join(distintos)}")
    for fallo in fallos:
        print(f"[FALLA] {fallo}")
    print("indicadores en orden: lo versionado coincide con el recálculo" if not fallos
          else f"indicadores con {len(fallos)} diferencias")
    return 0 if not fallos else 1


if __name__ == "__main__":
    sys.exit(main())
