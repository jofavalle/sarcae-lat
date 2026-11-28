"""Pruebas de la validación diaria de las réplicas, con series sintéticas y sin red.

Las series se fabrican en cada prueba: las de las estaciones no se versionan (#46). Cada
regla se prueba también con un caso hecho para romperla: un día de 19 horas, un cuarto vacío,
una observación del día local anterior, una hora de ERA5 sin pareja.
"""

import json

import numpy as np
import pandas as pd
import pytest

import src.validacion_diaria as vd
from src.validacion import pair_hours

BOGOTA = -5


def hours(start: str, count: int) -> pd.DatetimeIndex:
    return pd.date_range(start, periods=count, freq="h", tz="UTC")


def make_pairs(times, station_k, era5_k) -> pd.DataFrame:
    times = pd.DatetimeIndex(times)
    return pd.DataFrame({"hora": times, "observacion": times, "minutos": 0.0,
                         "estacion_k": np.asarray(station_k, dtype="float64"),
                         "era5_k": np.asarray(era5_k, dtype="float64")})


def test_period_starts_and_ends_at_local_midnight():
    first, after = vd.period_bounds("2024-01-01", "2025-12-31", BOGOTA)
    assert first == pd.Timestamp("2024-01-01 05:00", tz="UTC")
    assert after == pd.Timestamp("2026-01-01 05:00", tz="UTC")
    times = pd.Series(pd.to_datetime([
        "2024-01-01 04:29",  # su hora es las 04:00 UTC: 23:00 del 31 de diciembre local
        "2024-01-01 04:30",  # su hora es las 05:00 UTC: medianoche local del 1 de enero
        "2026-01-01 04:29",  # las 04:00 UTC: 23:00 del 31 de diciembre de 2025 local
        "2026-01-01 04:30",  # las 05:00 UTC: ya es 2026 local
    ], utc=True))
    assert vd.in_period(times, "2024-01-01", "2025-12-31", BOGOTA).tolist() == [
        False, True, True, False]


def test_local_day_runs_from_five_to_four_utc_in_bogota():
    times = hours("2024-03-10 05:00", 24)
    days = vd.daily(make_pairs(times, np.full(24, 290.0), np.full(24, 291.0)),
                    2548.4, 2430.6, BOGOTA)
    assert days["fecha_local"].tolist() == ["2024-03-10"]
    assert days["horas"].tolist() == [24]
    assert days["primera_hora_utc"].iloc[0] == pd.Timestamp("2024-03-10 05:00", tz="UTC")
    assert days["ultima_hora_utc"].iloc[0] == pd.Timestamp("2024-03-11 04:00", tz="UTC")
    # El mismo bloque leído con el huso de Maracaibo cae en dos días locales.
    assert vd.daily(make_pairs(times, np.full(24, 290.0), np.full(24, 291.0)),
                    71.6, 30.4, -4)["fecha_local"].tolist() == ["2024-03-10", "2024-03-11"]


def test_twenty_hours_count_and_nineteen_do_not():
    times = hours("2024-03-10 05:00", 24)
    keep_20 = [i for i in range(24) if i not in (1, 7, 13, 19)]
    keep_19 = keep_20[:-1]
    for keep, valid in ((keep_20, True), (keep_19, False)):
        t = times[keep]
        days = vd.daily(make_pairs(t, np.full(len(t), 290.0), np.full(len(t), 291.0)),
                        0.0, 0.0, BOGOTA)
        assert days["valido"].tolist() == [valid]


def test_an_empty_quarter_leaves_the_day_out():
    # Con 20 horas mínimas, un cuarto vacío deja como mucho 18: la regla de los cuartos solo
    # se ve sola con un mínimo más bajo.
    times = hours("2024-03-10 05:00", 24)
    no_night = times[[i for i in range(24) if not 18 <= i <= 23]]  # sin 18 a 23 local
    days = vd.daily(make_pairs(no_night, np.full(18, 290.0), np.full(18, 291.0)),
                    0.0, 0.0, BOGOTA, min_hours=18)
    assert days["cuartos"].tolist() == [3]
    assert days["valido"].tolist() == [False]


def test_daily_figures_use_only_the_paired_hours():
    # ERA5 tiene un pico a una hora sin observación: no puede entrar en su máxima.
    times = hours("2024-03-10 05:00", 24)
    station = 290.0 + np.arange(24) * 0.1
    era5 = station + 1.0
    pairs = make_pairs(times, station, era5)
    observations = pairs.rename(columns={"hora": "time", "estacion_k": "temp_k"})[
        ["time", "temp_k"]].drop(index=12)
    model = pd.DataFrame({"time": times, "t2m": np.where(np.arange(24) == 12, 400.0, era5)})
    paired, _ = pair_hours(observations, model, range(24))
    day = vd.daily(paired, 0.0, 0.0, BOGOTA).iloc[0]
    assert day["horas"] == 23
    assert day["era5_maxima_k"] == pytest.approx(day["estacion_maxima_k"] + 1.0)
    assert day["era5_media_k"] - day["estacion_media_k"] == pytest.approx(1.0)


def test_correction_shifts_every_daily_bias_by_the_same_amount():
    rng = np.random.default_rng(56)
    times = hours("2024-01-01 05:00", 24 * 40)
    station = 285.0 + 5.0 * np.sin(np.arange(len(times)) * 2 * np.pi / 24)
    era5 = station + rng.normal(1.0, 0.8, len(times))
    z_station, z_cell = 2548.4, 2430.6
    days = vd.daily(make_pairs(times, station, era5), z_station, z_cell, BOGOTA)
    result = vd.daily_metrics(days, ["2024-01", "2024-02"])
    expected = -0.0065 * (z_station - z_cell)
    for stat in vd.STATS:
        block = result["total"][stat]
        shift = block["con_correccion"]["sesgo_k"] - block["sin_correccion"]["sesgo_k"]
        assert shift == pytest.approx(expected, abs=1e-9)


def test_metrics_count_valid_days_per_year_and_month_with_zeros():
    times = hours("2024-12-30 05:00", 24 * 3)  # 30 y 31 de diciembre de 2024, 1 de enero
    days = vd.daily(make_pairs(times, np.full(72, 290.0), np.full(72, 292.0)),
                    0.0, 0.0, BOGOTA)
    one_out = days.copy()
    result = vd.daily_metrics(days, ["2024-11", "2024-12", "2025-01"])
    assert result["por_anio"]["2024"]["dias"] == 2
    assert result["por_anio"]["2025"]["dias"] == 1
    assert result["total"]["dias"] == 3
    assert result["dias_validos_por_mes"] == {"2024-11": 0, "2024-12": 2, "2025-01": 1}
    assert result["meses_sin_dias_validos"] == ["2024-11"]
    raw = result["total"]["media"]["sin_correccion"]
    assert raw == {"sesgo_k": pytest.approx(2.0), "error_cuadratico_medio_k": pytest.approx(2.0)}
    # Un día no válido no entra en ninguna métrica.
    one_out.loc[0, "valido"] = False
    assert vd.daily_metrics(one_out, ["2024-12", "2025-01"])["total"]["dias"] == 2


# De punta a punta, con una descarga de GHCNh fabricada y ERA5 sustituido.

HEADER = "STATION|DATE|temperature|temperature_Quality_Code|temperature_Source_Code"


def write_station(directory, rows_by_year):
    directory.mkdir(parents=True)
    files = []
    for year, rows in rows_by_year.items():
        name = f"GHCNh_COI0000SKBO_{year}.psv"
        lines = [HEADER] + [f"COI0000SKBO|{t:%Y-%m-%dT%H:%M:%S}|{v}|{q}|223"
                            for t, v, q in rows]
        (directory / name).write_text("\n".join(lines) + "\n", encoding="ascii")
        files.append({"ruta": f"data/raw/ghcnh/COI0000SKBO/{name}", "anio": year,
                      "sha256": "0" * 64})
    record = {"descargado_utc": "2026-11-28T13:32:08+00:00", "estacion": "COI0000SKBO",
              "archivos": files}
    (directory / "registro.json").write_text(json.dumps(record), encoding="utf-8")


def test_end_to_end_writes_only_the_metric(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(vd, "ROOT", tmp_path)
    monkeypatch.setattr(vd, "DAYS_DIR", tmp_path / "data" / "processed" / "validacion-replicas")
    monkeypatch.setattr(vd, "_commit", lambda: "abc123")

    # Un día local entero (el 2 de marzo de 2024) y, en cada hora, una fila de código 2 a la
    # hora en punto, la buena a los 3 minutos y otra buena a los 30, que cae fuera.
    day = hours("2024-03-02 05:00", 24)
    rows = []
    for i, t in enumerate(day):
        rows += [(t, "99.0", "2"), (t + pd.Timedelta(minutes=3), f"{14 + i * 0.25:.2f}", "1"),
                 (t + pd.Timedelta(minutes=30), "50.0", "1")]
    rows.append((pd.Timestamp("2024-03-02 04:00", tz="UTC"), "12.0", "1"))  # día anterior
    station_dir = tmp_path / "data" / "raw" / "ghcnh" / "COI0000SKBO"
    write_station(station_dir, {2024: rows, 2026: []})

    era5_hours = hours("2024-01-01 00:00", 24 * 100)
    series = pd.DataFrame({"time": era5_hours, "t2m": np.full(len(era5_hours), 290.0)})
    era5_record = {"punto_pedido": {"lat": 4.7016, "lon": -74.1469},
                   "archivos": [{"ruta": "data/raw/era5/el-dorado/serie.zip", "sha256": "1" * 64}]}
    monkeypatch.setattr(vd, "read_era5",
                        lambda d: (series, (4.75, -74.25), 2430.6, era5_record))

    out = tmp_path / "experiments" / "20261128-validacion-replicas"
    assert vd.main(["--estacion", str(station_dir), "--era5", "x", "--salida", str(out),
                    "--dias"]) == 0
    printed = capsys.readouterr().out
    assert "días válidos: 2024 1, 2025 0, total 1" in printed
    assert "por calidad 24 (0 sin temperatura, 0 con código vacío, 24 con otro código)" in printed
    assert "por minutos 24; repetidas 0" in printed
    assert "AVISO" not in printed

    metrics_text = (out / "metrics.json").read_text(encoding="utf-8")
    metrics = json.loads(metrics_text)
    assert "datos_ficticios" not in metrics
    assert str(tmp_path) not in metrics_text and str(tmp_path) not in (
        out / "config.yaml").read_text(encoding="utf-8")
    station = metrics["estaciones"]["COI0000SKBO"]
    assert station["era5"]["z_celda_m"] == 2430.6
    assert station["meses_sin_dias_validos"][:2] == ["2024-01", "2024-02"]
    assert list(station["insumos"]["sha256"]) == ["GHCNh_COI0000SKBO_2024.psv"]
    assert "Consultado el 2026-11-28" in station["fuente"]
    # Ningún valor de la estación: ni las temperaturas del PSV ni sus fechas.
    assert "14.25" not in metrics_text and "2024-03-02" not in metrics_text

    days = pd.read_csv(tmp_path / "data" / "processed" / "validacion-replicas" /
                       "COI0000SKBO-dias.csv")
    assert days["fecha_local"].tolist() == ["2024-03-02"]
    assert days["estacion_maxima_c"].iloc[0] == pytest.approx(14 + 23 * 0.25)
    assert days["primera_hora_utc"].iloc[0] == "2024-03-02 05:00"


def test_fake_era5_is_declared_at_the_top(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(vd, "ROOT", tmp_path)
    monkeypatch.setattr(vd, "DAYS_DIR", tmp_path / "data" / "processed" / "validacion-replicas")
    monkeypatch.setattr(vd, "_commit", lambda: "abc123")
    station_dir = tmp_path / "data" / "raw" / "ghcnh" / "COI0000SKBO"
    write_station(station_dir, {2024: []})
    series = pd.DataFrame({"time": hours("2024-01-01", 24), "t2m": np.full(24, 290.0)})
    record = {"punto_pedido": {}, "archivos": [], "ficticio": True, "nota_ficticio": "z falsa"}
    monkeypatch.setattr(vd, "read_era5", lambda d: (series, (4.75, -74.25), 2400.0, record))
    out = tmp_path / "salida"
    vd.main(["--estacion", str(station_dir), "--era5", "x", "--salida", str(out)])
    metrics = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert next(iter(metrics)) == "datos_ficticios"
    assert metrics["datos_ficticios"] == {"COI0000SKBO": "z falsa"}
    assert (out / "config.yaml").read_text(encoding="utf-8").startswith("datos_ficticios:")
    assert "AVISO, DATOS FICTICIOS en COI0000SKBO: z falsa" in capsys.readouterr().out
