"""Pruebas de la descarga y la lectura de GHCNh, sin red.

Los PSV se fabrican en cada prueba con la cabecera y el separador de los archivos anuales de
NCEI: las series de las estaciones no se versionan (#46), tampoco como muestra.
"""

import json
from datetime import datetime, timezone

import pandas as pd
import pytest

import src.ghcnh as ghcnh

HEADER = ("STATION|Station_name|DATE|Year|Month|Day|Hour|Minute|LATITUDE|LONGITUDE|ELEVATION|"
          "temperature|temperature_Measurement_Code|temperature_Quality_Code|"
          "temperature_Report_Type|temperature_Source_Code|temperature_Source_Station_ID|"
          "dew_point_temperature")


def row(time: str, temperature: str, quality: str, source: str = "223") -> str:
    date = pd.Timestamp(time)
    return (f"VEI0000SVMC|LA CHINITA|{date:%Y-%m-%dT%H:%M:%S}|{date:%Y}|{date:%m}|{date:%d}|"
            f"{date:%H}|{date:%M}|10.5582|-71.7279|71.6|{temperature}||{quality}|FM-15|"
            f"{source}|SVMC|20.0")


ROWS = [
    row("2024-01-11 18:00", "34.9", "1"),
    row("2024-01-11 18:03", "35.0", "1"),
    row("2024-01-11 19:03", "33.0", "2"),
    row("2024-01-11 20:03", "33.5", "4"),
    row("2024-01-11 21:00", "", ""),
    row("2024-01-11 22:00", "31.0", "", source="999"),
]


def write_psv(path, rows=ROWS):
    path.write_text("\n".join([HEADER] + rows) + "\n", encoding="ascii")
    return path


def test_reader_keeps_utc_and_codes_as_text(tmp_path):
    frame = ghcnh.read_psv(write_psv(tmp_path / "x.psv"))
    assert list(frame.columns) == ["time", "temperature", "quality", "source"]
    assert str(frame["time"].dt.tz) == "UTC"
    assert frame["time"].iloc[1] == pd.Timestamp("2024-01-11 18:03", tz="UTC")
    assert frame["temperature"].iloc[0] == pytest.approx(34.9)
    assert frame["quality"].tolist() == ["1", "1", "2", "4", "", ""]
    assert frame["temperature"].isna().tolist() == [False] * 4 + [True, False]


def test_only_code_one_with_a_value_survives(tmp_path):
    kept, discarded = ghcnh.filter_quality(ghcnh.read_psv(write_psv(tmp_path / "x.psv")))
    assert kept["temperature"].tolist() == pytest.approx([34.9, 35.0])
    assert discarded == {"sin_temperatura": 1, "codigo_vacio": 1, "otro_codigo": 2}
    assert len(kept) + sum(discarded.values()) == len(ROWS)


def test_empty_code_is_not_taken_for_good(tmp_path):
    # Si el código vacío se leyera como NaN y luego se rellenara, o el texto "1.0" como 1,
    # la fila de la fuente 999 entraría.
    rows = [row("2025-08-01 12:00", "14.0", "", source="999")]
    kept, discarded = ghcnh.filter_quality(ghcnh.read_psv(write_psv(tmp_path / "x.psv", rows)))
    assert kept.empty
    assert discarded["codigo_vacio"] == 1


def test_existing_destination_is_not_touched(tmp_path, monkeypatch):
    monkeypatch.setattr(ghcnh, "ROOT", tmp_path)
    (tmp_path / "ya").mkdir()
    with pytest.raises(SystemExit, match="inmutable"):
        ghcnh.ensure_new(tmp_path / "ya")


@pytest.fixture
def offline(tmp_path, monkeypatch):
    """Descarga sin red: cada URL pedida se anota y recibe un PSV fabricado."""
    asked = []

    def fake_fetch(url, target):
        asked.append(url)
        write_psv(target)

    monkeypatch.setattr(ghcnh, "ROOT", tmp_path)
    monkeypatch.setattr(ghcnh, "RAW", tmp_path / "data" / "raw" / "ghcnh")
    monkeypatch.setattr(ghcnh, "fetch", fake_fetch)
    return asked


def test_download_record_and_check_end_to_end(tmp_path, offline, capsys):
    final = ghcnh.download("VEI0000SVMC", (2024, 2025, 2026))
    assert offline == [
        "https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/access/"
        f"by-year/{year}/psv/GHCNh_VEI0000SVMC_{year}.psv" for year in (2024, 2025, 2026)]

    record = json.loads((final / "registro.json").read_text(encoding="utf-8"))
    assert [f["ruta"] for f in record["archivos"]] == [
        f"data/raw/ghcnh/VEI0000SVMC/GHCNh_VEI0000SVMC_{y}.psv" for y in (2024, 2025, 2026)]
    assert str(tmp_path) not in json.dumps(record)
    assert all(len(f["sha256"]) == 64 for f in record["archivos"])
    assert "non_commercial" in record["licencia"]
    assert "10.25921/jp3d-3v19" in record["cita"]
    # El año en curso todavía crece: el registro lo dice, y solo de él.
    this_year = datetime.now(timezone.utc).year
    assert ["nota" in f for f in record["archivos"]] == [
        y >= this_year for y in (2024, 2025, 2026)]
    assert not list(final.parent.glob(".parcial-*"))

    assert len(ghcnh.read_station(final)) == 3 * len(ROWS)
    assert ghcnh.check(final) == 0
    assert "comprobación en orden" in capsys.readouterr().out

    with pytest.raises(SystemExit, match="inmutable"):
        ghcnh.download("VEI0000SVMC", (2024,))


def test_check_fails_when_a_file_changed(tmp_path, offline, capsys):
    final = ghcnh.download("VEI0000SVMC", (2024, 2025))
    write_psv(final / "GHCNh_VEI0000SVMC_2025.psv", ROWS[:2])
    assert ghcnh.check(final) == 1
    out = capsys.readouterr().out
    assert "[FALLA] GHCNh_VEI0000SVMC_2025.psv" in out
    assert "[OK] GHCNh_VEI0000SVMC_2024.psv" in out
