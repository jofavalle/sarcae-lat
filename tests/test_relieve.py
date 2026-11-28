"""Pruebas de las teselas de relieve, sin red.

Los datos se fabrican en cada prueba: `data/` está en `.gitignore`, y un .hgt versionado no
llegaría al clon de nadie. El DEM fabricado es lineal en latitud y longitud, así que el
remuestreo bilineal lo recupera exacto, y la única pérdida es la de terrarium (1/256 m).
"""

import zipfile
import zlib

import numpy as np
import pytest

import src.relieve as relieve


def test_terrarium_ida_y_vuelta():
    heights = np.linspace(-100.0, 3000.0, 100_001)
    decoded = relieve.terrarium_decode(relieve.terrarium_encode(heights))
    assert np.abs(decoded - heights).max() <= 1.0 / 256.0
    # Terrarium trunca: lo decodificado nunca queda por encima de lo codificado.
    assert (decoded <= heights + 1e-9).all()


def test_terrarium_valores_conocidos():
    assert relieve.terrarium_encode(np.array([0.0])).tolist() == [[128, 0, 0]]
    assert relieve.terrarium_encode(np.array([615.5])).tolist() == [[130, 103, 128]]


@pytest.mark.parametrize("lon, lat, zoom, expected", [
    (0.0, 0.0, 1, (1, 1)),
    (0.0, 0.0, 0, (0, 0)),
    (-179.999, 85.0, 3, (0, 0)),
    (179.999, -85.0, 3, (7, 7)),
    # El punto de prueba: x = 4136,05 e y = 7562,47, calculados aparte con
    # y = (1 - ln(tan φ + sec φ)/π)/2 · 2^z, y no con el asinh del módulo.
    (-89.12, 13.70, 14, (4136, 7562)),
])
def test_coordenadas_de_tesela(lon, lat, zoom, expected):
    assert relieve.tile_of(lon, lat, zoom) == expected


def test_proyeccion_ida_y_vuelta():
    lon, lat = np.array([-89.12, 0.0, 120.5]), np.array([13.70, 0.0, -45.25])
    x, y = relieve.lonlat_to_tile(lon, lat, 14)
    back_lon, back_lat = relieve.tile_to_lonlat(x, y, 14)
    assert np.allclose(back_lon, lon, atol=1e-9) and np.allclose(back_lat, lat, atol=1e-9)


def test_las_teselas_cubren_el_recorte():
    bounds = relieve.crop_bounds(13.70, -89.12, 4.0)
    assert bounds["norte"] - bounds["sur"] == pytest.approx(4.0 / 111.195, rel=1e-3)
    for zoom in range(10, 15):
        tiles = relieve.tiles_for(bounds, zoom)
        corners = [relieve.tile_of(lon, lat, zoom)
                   for lat in (bounds["sur"], bounds["norte"])
                   for lon in (bounds["oeste"], bounds["este"])]
        assert set(corners) <= set(tiles)
        xs, ys = {x for x, _ in tiles}, {y for _, y in tiles}
        assert len(tiles) == len(xs) * len(ys)


def sloped_grid(top=14.0, left=-90.0, step=1.0 / 3600.0, side=3601):
    """Pendiente conocida: 600 m en la esquina noroeste, +2000 m por grado hacia el este y
    -1500 m por grado hacia el sur."""
    rows, cols = np.mgrid[0:side, 0:side]
    lat, lon = top - rows * step, left + cols * step
    values = 600.0 + 2000.0 * (lon - left) - 1500.0 * (top - lat)
    return relieve.Grid(values, top, left, step), (lambda la, lo:
                                                   600.0 + 2000.0 * (lo - left) - 1500.0 * (top - la))


@pytest.mark.parametrize("zoom", [10, 14])
def test_la_pendiente_se_recupera_en_la_tesela(zoom):
    grid, truth = sloped_grid()
    x, y = relieve.tile_of(-89.5, 13.5, zoom)
    height, outside = relieve.render_tile(grid, zoom, x, y)
    decoded = relieve.terrarium_decode(relieve.terrarium_encode(height))
    lon, lat = relieve.pixel_centers(zoom, x, y)
    assert outside == 0
    assert np.abs(decoded - truth(lat, lon)).max() <= 1.0 / 256.0 + 1e-6
    # La pendiente va en el sentido correcto: sube hacia el este y baja hacia el sur.
    assert decoded[128, -1] > decoded[128, 0] and decoded[-1, 128] < decoded[0, 128]


def test_fuera_del_granulo_se_cuenta():
    grid, _ = sloped_grid(side=361, step=1.0 / 360.0)
    x, y = relieve.tile_of(-89.01, 13.99, 9)  # la tesela de zoom 9 se sale por el este
    _, outside = relieve.render_tile(grid, 9, x, y)
    assert outside > 0


def test_png_ida_y_vuelta(tmp_path):
    rng = np.random.default_rng(11)
    smooth = relieve.terrarium_encode(np.add.outer(np.arange(64.0), np.arange(80.0)) * 3.7 + 400)
    noisy = rng.integers(0, 256, size=(40, 30, 3), dtype="uint8")
    for name, rgb in (("suave.png", smooth), ("ruido.png", noisy)):
        path = tmp_path / name
        relieve.write_png(path, rgb)
        assert np.array_equal(relieve.read_png(path), rgb)


def test_png_se_lee_con_zlib_sin_el_lector_propio(tmp_path):
    """El PNG escrito se abre a mano: firma, IHDR, IDAT descomprimido con zlib y filtros."""
    rgb = relieve.terrarium_encode(np.linspace(500.0, 700.0, 256 * 256).reshape(256, 256))
    path = tmp_path / "t.png"
    relieve.write_png(path, rgb)
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR" and data[16:24] == (256).to_bytes(4, "big") * 2
    assert data[24:26] == bytes([8, 2])  # 8 bits, RGB
    length = int.from_bytes(data[33:37], "big")
    assert data[37:41] == b"IDAT"
    raw = np.frombuffer(zlib.decompress(data[41:41 + length]), dtype="uint8").reshape(256, -1)
    rows = np.zeros((256, 256 * 3), dtype="int64")
    for i, (kind, line) in enumerate(zip(raw[:, 0], raw[:, 1:].astype("int64"))):
        if kind == 1:
            line = line.reshape(256, 3).cumsum(axis=0).reshape(-1)
        elif kind == 2 and i > 0:
            line = line + rows[i - 1]
        rows[i] = line & 0xFF
    assert np.array_equal(rows.reshape(256, 256, 3), rgb)


def fake_zip(tmp_path, data: bytes, name="n13w090.hgt"):
    path = tmp_path / "NASADEM_HGT_n13w090.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(name, data)
    return path


def test_el_hgt_se_lee_big_endian_y_de_norte_a_sur(tmp_path):
    values = np.zeros((3601, 3601), dtype=">i2")
    values[0, 0] = 1000      # esquina noroeste: 14 °N, 90 °O
    values[3600, 3600] = 258  # esquina sureste: 13 °N, 89 °O; en little-endian sería 513
    path = fake_zip(tmp_path, values.tobytes())
    grid = relieve.read_hgt(path)
    assert (grid.top, grid.left, grid.bottom, grid.right) == (14.0, -90.0, 13.0, -89.0)
    assert relieve.bilinear(grid, np.array([14.0]), np.array([-90.0]))[0][0] == 1000
    assert relieve.bilinear(grid, np.array([13.0]), np.array([-89.0]))[0][0] == 258


def test_un_hgt_de_otro_tamano_no_se_lee(tmp_path):
    path = fake_zip(tmp_path, b"\x00" * (relieve.HGT_BYTES - 2))
    with pytest.raises(SystemExit):
        relieve.read_hgt(path)


def test_los_vacios_se_cuentan():
    values = np.full((361, 361), 500, dtype="int16")
    values[100:103, 200] = relieve.VOID
    grid = relieve.Grid(values, 14.0, -90.0, 1.0 / 360.0)
    lat = np.array([14.0 - 101 / 360.0])
    lon = np.array([-90.0 + 200 / 360.0])
    assert relieve.voids_under(grid, lat, lon) >= 1
    assert relieve.voids_under(grid, np.array([13.5]), np.array([-89.2])) == 0


def test_celda_del_granulo():
    assert relieve.cell_corner("n13w090.hgt") == (13, -90)
    assert relieve.cell_corner("NASADEM_HGT_s05e120") == (-5, 120)
