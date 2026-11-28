"""Pruebas de la validación de ERA5 contra una estación, sin red.

Las series se fabrican en cada prueba (`*.csv` está en `.gitignore`). La estación sintética
mide siempre 1 K menos que ERA5, así que el sesgo sin corrección es +1 K exacto, y con una
celda a 500 m y la estación a 660 m la corrección resta 0,0065 · 160 = 1,04 K: el sesgo
corregido es -0,04 K.
"""

import json
import zipfile

import numpy as np
import pandas as pd
import pytest

import src.era5 as era5
import src.insitu as insitu
import src.validacion as validacion
from src.era5_checks import G0, expected_hours
from src.validacion import (bias_rmse, correct_height, height_shift, pair_hours,
                            summarize, to_kelvin)

WINDOW = range(13, 23)


def utc(*stamps):
    return pd.to_datetime(list(stamps), utc=True)


def model(start="2024-01-01", end="2024-01-03", value=300.0):
    time = expected_hours(start, end)
    return pd.DataFrame({"time": time, "t2m": np.full(len(time), value)})


def obs(stamps, values):
    return pd.DataFrame({"time": utc(*stamps), "temp_k": np.asarray(values, dtype="float64")})


# Unidades

def test_units_are_read_and_converted():
    assert to_kelvin([300.0], "K")[0] == 300.0
    assert to_kelvin([26.85], "degC")[0] == pytest.approx(300.0)
    assert to_kelvin([26.85], "°C")[0] == pytest.approx(300.0)
    with pytest.raises(ValueError, match="desconocidas"):
        to_kelvin([80.0], "degF")


def test_mixed_units_in_one_table():
    table = pd.DataFrame({"time": utc("2024-01-01 13:00", "2024-01-01 14:00"),
                          "valor": [300.0, 26.85], "unidades": ["K", "C"]})
    out = validacion.observations_in_kelvin(table)
    np.testing.assert_allclose(out["temp_k"], [300.0, 300.0])


# Emparejado

def test_fifty_past_goes_to_the_next_hour():
    pairs, discards = pair_hours(obs(["2024-01-01 12:50"], [299.0]), model(), WINDOW)
    assert pairs["hora"].tolist() == list(utc("2024-01-01 13:00"))
    assert pairs["minutos"].tolist() == [-10.0]
    assert sum(discards.values()) == 0


def test_eleven_minutes_is_too_far():
    pairs, discards = pair_hours(obs(["2024-01-01 13:11", "2024-01-01 13:49"], [1, 2]),
                                 model(), WINDOW)
    assert pairs.empty
    assert discards["a_mas_de_la_tolerancia"] == 2


def test_closest_in_the_same_hour_wins():
    # 14:50 y 15:00 caen en las 15 UTC: cuenta la de las 15:00.
    pairs, discards = pair_hours(obs(["2024-01-01 14:50", "2024-01-01 15:00"], [1.0, 2.0]),
                                 model(), WINDOW)
    assert len(pairs) == 1
    assert pairs.loc[0, "estacion_k"] == 2.0
    assert discards["otra_mas_cercana_en_la_misma_hora"] == 1


def test_tie_keeps_the_first():
    pairs, _ = pair_hours(obs(["2024-01-01 15:10", "2024-01-01 14:50"], [2.0, 1.0]),
                          model(), WINDOW)
    assert pairs.loc[0, "estacion_k"] == 1.0


def test_window_is_in_utc():
    # 12:00 y 23:00 UTC quedan fuera; 22:50 va a las 23 UTC y también.
    stamps = ["2024-01-01 12:00", "2024-01-01 13:00", "2024-01-01 22:00",
              "2024-01-01 22:50", "2024-01-01 23:00"]
    pairs, discards = pair_hours(obs(stamps, np.ones(5)), model(), WINDOW)
    assert sorted(pairs["hora"].dt.hour) == [13, 22]
    assert discards["fuera_de_la_ventana"] == 3


def test_missing_values_and_missing_model_are_counted():
    pairs, discards = pair_hours(obs(["2024-01-01 13:00", "2024-01-01 14:00",
                                      "2024-02-01 13:00"], [np.nan, 1.0, 1.0]),
                                 model(), WINDOW)
    assert len(pairs) == 1
    assert discards["sin_valor"] == 1
    assert discards["sin_era5_a_esa_hora"] == 1


def test_pairs_take_the_model_at_the_same_hour():
    series = model()
    series["t2m"] = 280.0 + series["time"].dt.hour
    pairs, _ = pair_hours(obs(["2024-01-02 17:55"], [0.0]), series, WINDOW)
    assert pairs.loc[0, "era5_k"] == 298.0


# Corrección por altura y métricas

def test_correction_sign_and_units():
    # La estación más alta que la celda: ERA5 corregido sale más frío.
    assert correct_height(300.0, 660.0, 500.0) == pytest.approx(300.0 - 1.04)
    assert correct_height(300.0, 400.0, 500.0) == pytest.approx(300.0 + 0.65)
    assert height_shift(660.0, 500.0) == pytest.approx(-1.04)


def test_bias_and_rmse():
    assert bias_rmse([1.0, -1.0]) == (0.0, 1.0)
    assert bias_rmse([3.0, 3.0]) == (3.0, 3.0)
    bias, rmse = bias_rmse([])
    assert np.isnan(bias) and np.isnan(rmse)


def make_pairs():
    hours = utc("2024-01-01 13:00", "2024-01-01 14:00", "2024-03-05 20:00",
                "2025-06-10 22:00")
    return pd.DataFrame({"hora": hours, "observacion": hours, "minutos": 0.0,
                         "estacion_k": [299.0, 297.0, 301.0, 299.0],
                         "era5_k": [300.0, 300.0, 300.0, 300.0]})


def test_summary_by_year_and_total():
    result = summarize(make_pairs(), 660.0, 500.0, utc_offset_hours=-6,
                       months=["2024-01", "2024-02", "2024-03", "2025-06"])
    y2024, y2025, total = result["por_anio"]["2024"], result["por_anio"]["2025"], result["total"]
    assert (y2024["horas"], y2024["dias"]) == (3, 2)
    assert (y2025["horas"], y2025["dias"]) == (1, 1)
    assert (total["horas"], total["dias"]) == (4, 3)
    # Diferencias de 2024: +1, +3, -1.
    assert y2024["sin_correccion"]["sesgo_k"] == pytest.approx(1.0)
    assert y2024["sin_correccion"]["error_cuadratico_medio_k"] == pytest.approx(np.sqrt(11 / 3))
    assert result["horas_por_mes"] == {"2024-01": 2, "2024-02": 0, "2024-03": 1, "2025-06": 1}


def test_corrected_minus_raw_bias_is_the_shift():
    result = summarize(make_pairs(), 660.0, 500.0)
    for block in list(result["por_anio"].values()) + [result["total"]]:
        delta = block["con_correccion"]["sesgo_k"] - block["sin_correccion"]["sesgo_k"]
        assert delta == pytest.approx(-0.0065 * (660.0 - 500.0))


def test_days_and_years_are_local():
    # Las 03:00 UTC del 1 de enero de 2025 son las 21:00 del 31 de diciembre de 2024 en UTC-6.
    hours = utc("2025-01-01 03:00")
    pairs = pd.DataFrame({"hora": hours, "observacion": hours, "minutos": 0.0,
                          "estacion_k": [300.0], "era5_k": [301.0]})
    assert list(summarize(pairs, 0, 0, utc_offset_hours=-6)["por_anio"]) == ["2024"]
    assert list(summarize(pairs, 0, 0)["por_anio"]) == ["2025"]


# Lectura del CSV del CDS

CSV_HEADER = """########################################################################################
# This file contains data retrieved from the CDS
# air_temperature [K]
########################################################################################
index,observation_id,report_id,data_policy_licence,longitude,latitude,observed_variable,observation_value,value_significance,units,quality_flag,source_id,report_type,station_name,primary_station_id,height_of_station_above_sea_level,report_meaning_of_timestamp,report_timestamp,report_duration
"""


def cds_csv(rows) -> str:
    lines = [CSV_HEADER.rstrip("\n")]
    for i, (station, stamp, value, units, flag) in enumerate(rows):
        name, lat, lon, z = (("SANTA ANA/EL PALMAR", 13.97, -89.53, 660.0)
                             if station == "ESI0000MSSA" else ("ILOPANGO INTL", 13.7, -89.12, 616.0))
        lines.append(f"{i},o{i},r{i},1,{lon},{lat},air_temperature,{value},12,{units},{flag},"
                     f"223,4,{name},{station},{z},1,{stamp},0")
    return "\n".join(lines) + "\n"


def test_read_station_filters_station_and_quality(tmp_path):
    path = tmp_path / "observaciones.zip"
    rows = [("ESI0000MSSA", "2024-01-01 13:50:00", 299.0, "K", 0),
            ("ESI0000MSSA", "2024-01-01 12:50:00", 298.0, "K", 0),
            ("ESI0000MSSA", "2024-01-01 14:50:00", 250.0, "K", 1),
            ("ESI0000MSSS", "2024-01-01 13:50:00", 301.0, "K", 0)]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("insitu.csv", cds_csv(rows))
    table, meta = insitu.read_station(path, "ESI0000MSSA")
    assert table["valor"].tolist() == [298.0, 299.0]
    assert str(table["time"].dt.tz) == "UTC"
    assert (meta["registros"], meta["registros_de_calidad"]) == (3, 2)
    assert (meta["lat"], meta["lon"], meta["altura_m"]) == (13.97, -89.53, 660.0)
    with pytest.raises(ValueError, match="no aparece"):
        insitu.read_station(path, "ESI0000XXXX")


def test_request_is_the_one_of_issue_39():
    sent = insitu.request()
    assert sent["version"] == "3_0_0"
    assert sent["time_aggregation"] == "sub_daily"
    assert sent["variable"] == ["air_temperature"]
    assert sent["year"] == ["2024", "2025"]
    assert len(sent["month"]) == 12 and len(sent["day"]) == 31
    assert sent["area"] == [14.5, -90.2, 13.1, -87.6]
    assert sent["data_format"] == "csv"


# De punta a punta: descarga fabricada de las dos fuentes y corrida del experimento

STATION_HOURS = ["2024-01-01 12:50", "2024-01-01 15:00", "2024-01-01 14:50",
                 "2024-07-15 18:00", "2025-03-03 21:50", "2025-03-03 22:50",
                 "2025-03-03 23:00"]


def numbers(value):
    """Todos los números de un JSON leído, a cualquier profundidad."""
    if isinstance(value, dict):
        return [n for v in value.values() for n in numbers(v)]
    if isinstance(value, list):
        return [n for v in value for n in numbers(v)]
    return [value] if isinstance(value, (int, float)) and not isinstance(value, bool) else []


class FakeJob:
    request_id = "00000000-0000-0000-0000-000000000000"

    def __init__(self, text):
        self.text = text

    def download(self, target):
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("insitu-observations-surface-land_prueba.csv", self.text)
        return target


class FakeClient:
    """Cliente del CDS que escribe datos fabricados: ERA5 a 300 K y la estación a 299 K."""

    def __init__(self, *args, **kwargs):
        pass

    def retrieve(self, dataset, request, target=None):
        if dataset == insitu.DATASET:
            rows = [("ESI0000MSSA", f"{s}:00", 299.0, "K", 0) for s in STATION_HOURS]
            rows.append(("ESI0000MSSS", "2024-01-01 15:00:00", 280.0, "K", 0))
            return FakeJob(cds_csv(rows))
        if dataset == era5.SERIES_DATASET:
            series = model("2024-01-01", "2025-12-31")
            series["valid_time"] = series.pop("time").dt.strftime("%Y-%m-%d %H:%M:%S")
            series["latitude"], series["longitude"] = 14.0, -89.5
            with zipfile.ZipFile(target, "w") as archive:
                archive.writestr("serie.csv", series.to_csv(index=False))
        else:
            from netCDF4 import Dataset

            with Dataset(target, "w") as ds:
                ds.createDimension("latitude", 3)
                ds.createDimension("longitude", 3)
                ds.createVariable("latitude", "f8", ("latitude",))[:] = [14.25, 14.0, 13.75]
                ds.createVariable("longitude", "f8", ("longitude",))[:] = [-89.75, -89.5, -89.25]
                ds.createVariable("z", "f8", ("latitude", "longitude"))[:] = \
                    np.full((3, 3), 500.0 * G0)
        return target


def test_end_to_end(tmp_path, monkeypatch, capsys):
    import cdsapi

    for module in (era5, insitu, validacion):
        monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(era5, "RAW", tmp_path / "data" / "raw" / "era5")
    monkeypatch.setattr(insitu, "RAW", tmp_path / "data" / "raw" / "c3s-insitu")
    pairs_path = tmp_path / "data" / "processed" / "validacion-ancla" / "pares.csv"
    monkeypatch.setattr(validacion, "PAIRS_PATH", pairs_path)
    monkeypatch.setattr(cdsapi, "Client", FakeClient)

    station_dir = insitu.download("santa-ana-el-palmar", "ESI0000MSSA")
    era5_dir = era5.download("santa-ana-el-palmar", 13.97, -89.53, "2024-01-01", "2025-12-31")
    record = json.loads((station_dir / "registro.json").read_text(encoding="utf-8"))
    assert record["id_peticion_cds"] == FakeJob.request_id
    assert record["archivos"][0]["ruta"] == \
        "data/raw/c3s-insitu/santa-ana-el-palmar/observaciones.zip"
    with pytest.raises(SystemExit, match="inmutable"):
        insitu.download("santa-ana-el-palmar", "ESI0000MSSA")
    capsys.readouterr()

    out_dir = tmp_path / "experiments" / "20261128-validacion-ancla"
    assert validacion.main(["--estacion", str(station_dir), "--era5", str(era5_dir),
                            "--salida", str(out_dir), "--pares"]) == 0
    printed = capsys.readouterr().out
    assert "horas UTC en los pares: 13, 15, 18, 22" in printed
    assert "z_celda: 500.0 m" in printed

    metrics = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
    # 12:50 -> 13; 14:50 y 15:00 -> 15, gana 15:00; 18:00; 21:50 -> 22; 22:50 y 23:00 fuera.
    assert metrics["total"]["horas"] == 4
    assert metrics["por_anio"]["2024"]["dias"] == 2
    assert metrics["descartes"]["otra_mas_cercana_en_la_misma_hora"] == 1
    assert metrics["descartes"]["fuera_de_la_ventana"] == 2
    assert metrics["total"]["sin_correccion"]["sesgo_k"] == pytest.approx(1.0)
    assert metrics["total"]["con_correccion"]["sesgo_k"] == pytest.approx(-0.04)
    assert metrics["correccion_k"] == pytest.approx(-1.04)
    assert len(metrics["horas_por_mes"]) == 24

    config = (out_dir / "config.yaml").read_text(encoding="utf-8")
    assert "gradiente_k_por_km: 6.5" in config and "tolerancia_min: 10" in config
    # Ni rutas absolutas ni valores de la estación en lo que se versiona.
    for text in (config, json.dumps(metrics)):
        assert str(tmp_path) not in text and tmp_path.as_posix() not in text
    assert 299.0 not in numbers(metrics)
    assert "estacion_k" not in json.dumps(metrics)
    pares = pd.read_csv(pairs_path)
    assert len(pares) == 4
    assert set(pares["diferencia_k"]) == {1.0}

    # Con una descarga real no hay aviso; con una marcada como ficticia, va arriba del todo.
    assert "datos_ficticios" not in metrics and "datos_ficticios" not in config
    assert "FICTICIOS" not in printed
    record_path = era5_dir / "registro.json"
    era5_record = json.loads(record_path.read_text(encoding="utf-8"))
    era5_record.update(ficticio=True, nota_ficticio="z_celda ficticia (500 m)")
    record_path.write_text(json.dumps(era5_record), encoding="utf-8")
    fake_dir = tmp_path / "experiments" / "ficticio"
    assert validacion.main(["--estacion", str(station_dir), "--era5", str(era5_dir),
                            "--salida", str(fake_dir)]) == 0
    assert capsys.readouterr().out.startswith("AVISO, DATOS FICTICIOS: z_celda ficticia")
    fake_metrics = json.loads((fake_dir / "metrics.json").read_text(encoding="utf-8"))
    assert list(fake_metrics)[0] == "datos_ficticios"
    assert (fake_dir / "config.yaml").read_text(encoding="utf-8").startswith(
        'datos_ficticios: "z_celda ficticia (500 m)"')
