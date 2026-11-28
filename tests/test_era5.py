"""Pruebas de la descarga y la comprobación de ERA5 en un punto, sin red.

Los datos se fabrican en cada prueba: `*.csv` está en `.gitignore`, y una muestra versionada
no llegaría al clon de nadie. La serie fabricada tiene una solución analítica: temperatura
media de 297 K con un ciclo diario de amplitud 4 K y máximo a las 19 UTC, y 1,8 m de lluvia
repartidos por igual entre las 8760 horas de 2025.

Cada control se prueba también con una serie hecha para fallar: si el control no falla con
ella, no está comprobando nada.
"""

import json
import zipfile

import numpy as np
import pandas as pd
import pytest

import src.era5 as era5
from src.era5_checks import G0, expected_hours, run_checks, summarize

START, END = "2025-01-01", "2025-12-31"
POINT = (13.75, -89.0)


def make_series(peak_hour: int = 19, annual_rain_m: float = 1.8) -> pd.DataFrame:
    time = expected_hours(START, END)
    hours = time.hour.to_numpy(dtype="float64")
    t2m = 297.0 + 4.0 * np.cos(2.0 * np.pi * (hours - peak_hour) / 24.0)
    return pd.DataFrame({
        "time": time,
        "t2m": t2m,
        "d2m": t2m - 5.0,
        "tp": np.full(len(time), annual_rain_m / len(time), dtype="float64"),
    })


def failed(series: pd.DataFrame, geo_point=POINT) -> list:
    return [c.name for c in run_checks(series, START, END, POINT, geo_point) if not c.ok]


def test_summary_matches_the_analytic_series():
    summary = summarize(make_series())
    assert summary["rows"] == 8760
    assert summary["peak_hour_utc"] == 19
    assert summary["mean_t2m_k"] == pytest.approx(297.0, abs=1e-9)
    assert summary["annual_rain_m"] == pytest.approx(1.8, rel=1e-12)


def test_full_period_has_the_hours_of_the_order():
    # De 1940 a 2025 son 753888 horas, y el 1 de enero de 2026 añade 24.
    assert (era5.DEFAULT_START, era5.DEFAULT_END) == ("1940-01-01", "2026-01-01")
    assert len(expected_hours(era5.DEFAULT_START, era5.DEFAULT_END)) == 753912


def test_partial_year_does_not_enter_the_annual_rain():
    # 2025 entero con 1,8 m, y el 1 de enero de 2026 con la misma lluvia por hora. Si el
    # año parcial entrara en la media, daría (1,8 + 1,8 · 24 / 8760) / 2, unos 0,90 m.
    time = expected_hours(START, "2026-01-01")
    hours = time.hour.to_numpy(dtype="float64")
    t2m = 297.0 + 4.0 * np.cos(2.0 * np.pi * (hours - 19) / 24.0)
    series = pd.DataFrame({
        "time": time,
        "t2m": t2m,
        "d2m": t2m - 5.0,
        "tp": np.full(len(time), 1.8 / 8760, dtype="float64"),
    })
    assert len(series) == 8760 + 24
    assert summarize(series)["annual_rain_m"] == pytest.approx(1.8, rel=1e-12)
    checks = run_checks(series, START, "2026-01-01", POINT, POINT)
    assert [c.name for c in checks if not c.ok] == []


def test_good_series_passes_every_check():
    assert failed(make_series()) == []


def test_series_in_local_time_fails_the_daily_cycle():
    # Seis horas de desfase: el máximo de las 13 h locales etiquetado como UTC.
    assert failed(make_series(peak_hour=13)) == ["ciclo diario"]


def test_rain_in_millimetres_fails_the_rain_check():
    series = make_series()
    series["tp"] = series["tp"] * 1000.0
    assert failed(series) == ["lluvia"]


def test_celsius_taken_for_kelvin_fails_the_temperature_check():
    series = make_series()
    series["t2m"] = series["t2m"] - 273.15
    series["d2m"] = series["d2m"] - 273.15
    assert failed(series) == ["temperatura"]


def test_swapped_columns_fail_the_dew_point_check():
    series = make_series()
    series[["t2m", "d2m"]] = series[["d2m", "t2m"]].to_numpy()
    assert failed(series) == ["punto de rocío"]


def test_repeated_hour_fails_the_hours_check():
    series = make_series()
    series = pd.concat([series, series.iloc[[100]]], ignore_index=True)
    assert failed(series) == ["horas"]


def test_missing_hour_fails_the_hours_check():
    assert failed(make_series().drop(index=100)) == ["horas"]


def test_other_grid_point_fails_the_grid_check():
    assert failed(make_series(), geo_point=(13.5, -89.0)) == ["rejilla"]


def test_reader_joins_a_zip_with_one_csv_per_variable(tmp_path):
    series = make_series()
    csv = series.assign(time=series["time"].dt.strftime("%Y-%m-%d %H:%M:%S"))
    csv = csv.rename(columns={"time": "valid_time"})
    path = tmp_path / "serie.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for column in ("t2m", "d2m", "tp"):
            archive.writestr(f"{column}.csv", csv[["valid_time", column]].to_csv(index=False))
    read = era5.read_series(path)
    assert list(read.columns) == ["time", "t2m", "d2m", "tp"]
    pd.testing.assert_frame_equal(read, series, check_freq=False)


def test_existing_destination_is_not_touched(tmp_path, monkeypatch):
    monkeypatch.setattr(era5, "ROOT", tmp_path)
    (tmp_path / "ya").mkdir()
    with pytest.raises(SystemExit, match="inmutable"):
        era5.ensure_new(tmp_path / "ya")


class FakeClient:
    """Cliente del CDS que escribe datos fabricados en lugar de descargarlos.

    La serie imita lo que entregó el CDS el 27 de noviembre de 2026: un zip con un solo CSV,
    con las columnas `valid_time,d2m,t2m,tp,latitude,longitude` en ese orden y la hora
    como `2025-01-01 00:00:00`.
    """

    def retrieve(self, dataset, request, target):
        if dataset == era5.SERIES_DATASET:
            series = make_series()
            series["time"] = series["time"].dt.strftime("%Y-%m-%d %H:%M:%S")
            series = series.rename(columns={"time": "valid_time"})
            series["latitude"], series["longitude"] = POINT
            columns = ["valid_time", "d2m", "t2m", "tp", "latitude", "longitude"]
            with zipfile.ZipFile(target, "w") as archive:
                archive.writestr("reanalysis-era5-single-levels-timeseries-prueba.csv",
                                 series[columns].to_csv(index=False))
        else:
            from netCDF4 import Dataset

            lats = np.array([14.0, 13.75, 13.5])
            lons = np.array([-89.25, -89.0, -88.75])
            with Dataset(target, "w") as ds:
                ds.createDimension("valid_time", 1)
                ds.createDimension("latitude", 3)
                ds.createDimension("longitude", 3)
                ds.createVariable("latitude", "f8", ("latitude",))[:] = lats
                ds.createVariable("longitude", "f8", ("longitude",))[:] = lons
                z = ds.createVariable("z", "f8", ("valid_time", "latitude", "longitude"))
                z[:] = np.full((1, 3, 3), 700.0 * G0)
        return target


def test_download_and_check_end_to_end(tmp_path, monkeypatch, capsys):
    import cdsapi

    monkeypatch.setattr(era5, "ROOT", tmp_path)
    monkeypatch.setattr(era5, "RAW", tmp_path / "data" / "raw" / "era5")
    monkeypatch.setattr(cdsapi, "Client", FakeClient)

    final = era5.download("prueba", 13.70, -89.12, START, END)
    record = json.loads((final / "registro.json").read_text(encoding="utf-8"))
    paths = [f["ruta"] for f in record["archivos"]]
    assert paths == ["data/raw/era5/prueba/serie.zip", "data/raw/era5/prueba/geopotencial.nc"]
    assert record["punto_rejilla"] == {"lat": POINT[0], "lon": POINT[1]}
    assert str(tmp_path) not in json.dumps(record)

    assert era5.check(final) == 0
    out = capsys.readouterr().out
    assert "altura de la celda: 700.0 m" in out
    assert "comprobación en orden" in out

    with pytest.raises(SystemExit, match="inmutable"):
        era5.download("prueba", 13.70, -89.12, START, END)
