"""Pruebas de los indicadores de calor y de lluvia, sin red y con series fabricadas."""

import numpy as np
import pandas as pd
import pytest

import src.indicadores as ind
from src.era5_checks import expected_hours

K28 = 28.0 + ind.K0


def serie(inicio: str, fin: str, t2m=K28, tp=0.0) -> pd.DataFrame:
    time = expected_hours(inicio, fin)
    return pd.DataFrame({"time": time,
                         "t2m": np.full(len(time), t2m, dtype="float64"),
                         "tp": np.full(len(time), tp, dtype="float64")})


def test_28_grados_constantes_dan_10_horas_por_dia_laborable():
    # Del lunes 2025-03-03 al domingo 2025-03-09 locales: cinco días laborables.
    s = serie("2025-03-02", "2025-03-10")
    sobre = ind.horas_calor(s, -6, 0.0)
    semana = sobre["2025-03-03":"2025-03-09"]
    assert int(semana.sum()) == 50
    por_dia = semana.groupby(semana.index.normalize()).sum()
    assert list(por_dia) == [10, 10, 10, 10, 10]
    assert sorted(set(semana.index.hour)) == list(range(7, 17))


def test_el_umbral_es_estricto_y_el_dia_de_la_semana_es_local():
    s = serie("2025-03-02", "2025-03-10", t2m=27.0 + ind.K0)
    assert int(ind.horas_calor(s, -6, 0.0).sum()) == 0
    # El viernes 2025-03-07 a las 16:00 locales son las 22:00 UTC, y el sábado a las 07:00
    # locales, las 13:00 UTC: cuenta el viernes y no el sábado.
    s = serie("2025-03-07", "2025-03-09", t2m=20.0 + ind.K0)
    calientes = s["time"].isin([pd.Timestamp("2025-03-07 22:00", tz="UTC"),
                                pd.Timestamp("2025-03-08 13:00", tz="UTC")])
    s.loc[calientes, "t2m"] = K28
    sobre = ind.horas_calor(s, -6, 0.0)
    assert list(sobre[sobre].index) == [pd.Timestamp("2025-03-07 16:00")]


def test_p99_conocido():
    # 10 957 días de 1961–1990 con 0, 1, ..., 10 956 mm: el p99 lineal es 0,99 · 10 956, y
    # lo superan 110 días.
    dias = pd.date_range("1961-01-01", "1990-12-31", freq="D")
    assert len(dias) == ind.DIAS_BASE_P99
    diaria = pd.Series(np.arange(len(dias), dtype="float64"), index=dias)
    umbral = ind.p99(diaria)
    assert umbral == pytest.approx(0.99 * 10956)
    assert int(ind.dias_sobre(diaria, umbral, ind.REFERENCIA).sum()) == 110
    with pytest.raises(ValueError):
        ind.p99(diaria.iloc[1:])


def test_los_dias_secos_cuentan_en_el_p99():
    dias = pd.date_range("1961-01-01", "1990-12-31", freq="D")
    valores = np.zeros(len(dias))
    valores[-200:] = np.arange(1, 201)
    umbral = ind.p99(pd.Series(valores, index=dias))
    assert umbral == pytest.approx(np.percentile(valores, 99))
    assert umbral < np.percentile(valores[valores > 0], 99)


def test_la_lluvia_de_las_06_utc_cuenta_en_el_dia_local_anterior():
    s = serie("2025-12-30", "2026-01-01")
    s.loc[s["time"] == pd.Timestamp("2026-01-01 06:00", tz="UTC"), "tp"] = 0.010
    s.loc[s["time"] == pd.Timestamp("2025-12-31 06:00", tz="UTC"), "tp"] = 0.002
    diaria = ind.lluvia_diaria(s, -6)
    assert diaria[pd.Timestamp("2025-12-31")] == pytest.approx(10.0)
    assert diaria[pd.Timestamp("2025-12-30")] == pytest.approx(2.0)
    # Solo días con sus 24 horas: el 29 local empieza antes de la serie, y el 1 de enero
    # local acaba después.
    assert list(diaria.index) == [pd.Timestamp("2025-12-30"), pd.Timestamp("2025-12-31")]


def test_signo_de_la_correccion():
    assert ind.correccion_k(400.0, 500.0) == pytest.approx(0.65)
    assert ind.correccion_k(600.0, 500.0) == pytest.approx(-0.65)
    # Con la escuela más baja que la celda, 26,5 °C pasan a 27,15 °C y cuentan.
    s = serie("2025-03-02", "2025-03-10", t2m=26.5 + ind.K0)
    assert int(ind.horas_calor(s, -6, ind.correccion_k(400.0, 500.0)).sum()) > 0
    assert int(ind.horas_calor(s, -6, 0.0).sum()) == 0


def test_anios_bisiestos():
    s = serie("2023-12-31", "2025-01-01")
    horas = ind.horas_por_anio(ind.horas_calor(s, -6, 0.0), (2024, 2024))
    assert int(horas[2024]) == 262 * 10      # 2024 tiene 262 días laborables
    diaria = ind.lluvia_diaria(s, -6)
    assert int((diaria.index.year == 2024).sum()) == 366
    assert len(pd.date_range("1961-01-01", "1990-12-31")) == ind.DIAS_BASE_P99


def test_horas_por_mes_suman_el_promedio_anual():
    s = serie("2020-12-31", "2023-01-01", t2m=K28)
    sobre = ind.horas_calor(s, -6, 0.0)
    anual = ind.horas_por_anio(sobre, (2021, 2022))
    meses = ind.horas_por_mes(sobre, (2021, 2022))
    assert float(meses.sum()) == pytest.approx(float(anual.mean()))


def test_episodios_con_sus_24_horas_locales():
    s = serie("2000-06-01", "2000-06-04", t2m=25.0 + ind.K0)
    # 2 mm en cada hora del día local 2000-06-02, de las 01:00 a las 24:00 locales.
    fin = s["time"] + pd.Timedelta(hours=-6)
    dia = (fin.dt.tz_localize(None) - pd.Timedelta(hours=1)).dt.normalize()
    s.loc[dia == pd.Timestamp("2000-06-02"), "tp"] = 0.002
    diaria = ind.lluvia_diaria(s, -6)
    lista = ind.episodios(s, -6, 0.5, diaria, 1.0, periodo=(1996, 2025))
    assert len(lista) == 1
    e = lista[0]
    assert e["fecha"] == pd.Timestamp("2000-06-02")
    assert e["total"] == pytest.approx(48.0)
    assert e["lluvia"] == pytest.approx([2.0] * 24)
    assert e["temperatura"] == pytest.approx([25.5] * 24)


def test_zona_de_diseno():
    assert ind.zona_diseno(120.0, "SV")[0] == "costera"
    assert ind.zona_diseno(300.0, "SV")[0] == "tropical caliente"
    assert ind.zona_diseno(699.9, "SV")[0] == "tropical caliente"
    assert ind.zona_diseno(700.0, "SV")[:3] == ("montañosa", 700, None)
    assert ind.zona_diseno(2600.0, "CO") is None
