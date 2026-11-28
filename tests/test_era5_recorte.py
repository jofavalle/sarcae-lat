"""Pruebas del recorte de ERA5, sin red: la descarga se fabrica en una carpeta temporal."""

import json

import numpy as np
import pandas as pd
import pytest

import src.era5_recorte as er
from src.era5 import LEVELS_DATASET, SERIES_DATASET
from src.era5_checks import G0, expected_hours
from src.recortes import comprobar

LAT, LON = 14.0, -89.25


def fabricar(carpeta, z=500.0, geo_lon=LON, ficticio=False):
    """Una descarga como la de src.era5: serie en CSV, geopotencial en NetCDF y registro."""
    from netCDF4 import Dataset

    carpeta.mkdir(parents=True)
    time = expected_hours("2024-02-28", "2024-03-01")
    pd.DataFrame({"valid_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                  "t2m": np.linspace(295.0, 300.0, len(time)),
                  "d2m": np.full(len(time), 290.0),
                  "tp": np.full(len(time), 0.0001),
                  "latitude": LAT, "longitude": LON}).to_csv(carpeta / "serie.csv", index=False)
    with Dataset(carpeta / "geopotencial.nc", "w") as ds:
        ds.createDimension("latitude", 3)
        ds.createDimension("longitude", 3)
        ds.createVariable("latitude", "f8", ("latitude",))[:] = [LAT + 0.25, LAT, LAT - 0.25]
        ds.createVariable("longitude", "f8", ("longitude",))[:] = \
            [geo_lon - 0.25, geo_lon, geo_lon + 0.25]
        ds.createVariable("z", "f8", ("latitude", "longitude"))[:] = np.full((3, 3), z * G0)
    registro = {"descargado_utc": "2026-11-28T16:00:00+00:00", "licencia": "CC-BY-4.0",
                "periodo": {"inicio": "2024-02-28", "fin": "2024-03-01"},
                "punto_pedido": {"lat": 13.97567, "lon": -89.34056},
                "archivos": [{"ruta": "data/raw/era5/x/serie.csv", "dataset": SERIES_DATASET},
                             {"ruta": "data/raw/era5/x/geopotencial.nc",
                              "dataset": LEVELS_DATASET}]}
    if ficticio:
        registro.update(ficticio=True, nota_ficticio="z_celda ficticia")
    (carpeta / "registro.json").write_text(json.dumps(registro), encoding="utf-8")
    return carpeta


def test_recorte_con_su_celda_y_su_manifiesto(tmp_path):
    origen = fabricar(tmp_path / "raw" / "sv-x")
    destino = tmp_path / "recortes" / "sv-x" / "era5"
    celda = er.recortar("sv-x", origen, destino)

    tabla = pd.read_parquet(destino / "serie.parquet")
    assert list(tabla.columns) == ["time", "t2m", "tp"]
    assert str(tabla["time"].dt.tz) == "UTC"
    assert len(tabla) == 3 * 24 and celda["filas"] == 72      # 2024 es bisiesto: 28, 29 y 1
    assert tabla["time"].iloc[0] == pd.Timestamp("2024-02-28 00:00", tz="UTC")
    assert tabla["t2m"].iloc[-1] == pytest.approx(300.0)
    assert tabla["tp"].iloc[0] == pytest.approx(0.0001)

    guardada = json.loads((destino / "celda.json").read_text(encoding="utf-8"))
    assert guardada["punto_rejilla"] == {"lat": LAT, "lon": LON}
    assert guardada["z_celda"]["valor"] == pytest.approx(500.0)
    assert "ficticio" not in guardada

    comprobar(destino)
    manifiesto = json.loads((destino / "manifiesto.json").read_text(encoding="utf-8"))
    assert manifiesto["licencia"]["spdx"] == "CC-BY-4.0"
    assert manifiesto["atribucion"].startswith(
        "Contains modified Copernicus Climate Change Service information 2026.")
    assert {a["nombre"] for a in manifiesto["archivos"]} == {"serie.parquet", "celda.json"}
    with open(destino / "serie.parquet", "rb") as f:
        assert f.read(4) == b"PAR1"


def test_la_nota_ficticia_pasa_a_la_celda(tmp_path):
    origen = fabricar(tmp_path / "raw" / "sv-x", ficticio=True)
    celda = er.recortar("sv-x", origen, tmp_path / "recortes" / "sv-x" / "era5")
    assert celda["ficticio"] is True and celda["nota_ficticio"] == "z_celda ficticia"


def test_geopotencial_de_otra_celda_no_se_recorta(tmp_path):
    origen = fabricar(tmp_path / "raw" / "sv-x", geo_lon=LON + 1.0)
    with pytest.raises(ValueError):
        er.recortar("sv-x", origen, tmp_path / "recortes" / "sv-x" / "era5")
