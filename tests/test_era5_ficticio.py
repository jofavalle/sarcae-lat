"""Pruebas de la copia de una serie real con z_celda ficticia, sin red."""

import numpy as np
import pandas as pd

import src.era5_ficticio as ef
import src.era5_recorte as er
from src.era5 import read_geopotential
from src.era5_checks import expected_hours

LAT, LON = 4.75, -74.0


def serie_real(ruta):
    """Una serie con la forma de la descarga de src.era5, en un zip con su CSV."""
    time = expected_hours("2024-02-28", "2024-03-01")
    pd.DataFrame({"valid_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                  "t2m": np.linspace(285.0, 290.0, len(time)),
                  "d2m": np.full(len(time), 280.0),
                  "tp": np.full(len(time), 0.0002),
                  "latitude": LAT, "longitude": LON}).to_csv(
        ruta, index=False, compression={"method": "zip", "archive_name": "serie.csv"})
    return ruta


def test_copia_identica_y_registro_ficticio(tmp_path):
    fuente = serie_real(tmp_path / "serie.zip")
    destino = tmp_path / "co-x"
    registro = ef.copiar_real(fuente, destino, 2555.8, "petición abc")

    assert (destino / "serie.zip").read_bytes() == fuente.read_bytes()
    assert registro["ficticio"] is True
    assert "Serie real de ERA5" in registro["nota_ficticio"]
    assert "2555.8 m" in registro["nota_ficticio"]
    assert "petición abc" in registro["nota_ficticio"]
    assert registro["punto_rejilla"] == {"lat": LAT, "lon": LON}
    assert registro["fuentes"][0]["sha256"] == registro["archivos"][0]["sha256"]


def test_geopotencial_ficticio_en_su_celda(tmp_path):
    fuente = serie_real(tmp_path / "serie.zip")
    destino = tmp_path / "co-x"
    ef.copiar_real(fuente, destino, 2555.8, "petición abc")

    geo_lat, geo_lon, z = read_geopotential(destino / "geopotencial.nc", LAT, LON)
    assert (geo_lat, geo_lon) == (LAT, LON)
    assert abs(z - 2555.8) < 1e-6


def test_el_recorte_lo_marca_ficticio(tmp_path):
    import json

    fuente = serie_real(tmp_path / "serie.zip")
    origen = tmp_path / "co-x"
    registro = ef.copiar_real(fuente, origen, 2555.8, "petición abc")
    registro["punto_pedido"] = {"lat": 4.63279, "lon": -74.122}
    (origen / "registro.json").write_text(json.dumps(registro), encoding="utf-8")

    celda = er.recortar("co-x", origen, tmp_path / "recorte")
    assert celda["ficticio"] is True
    assert celda["z_celda"]["valor"] == 2555.8
    assert celda["filas"] == 72
