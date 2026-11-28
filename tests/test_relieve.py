"""Pruebas de las teselas de relieve, sin red.

Los datos se fabrican en cada prueba: `data/` está en `.gitignore`, y un .hgt versionado no
llegaría al clon de nadie. El DEM fabricado es lineal en latitud y longitud, así que el
remuestreo bilineal lo recupera exacto, y la única pérdida es la de terrarium (1/256 m).
"""

import json
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
    assert relieve.read_hgt_pixel(path, 3600, 3600) == 258


def test_un_hgt_de_otro_tamano_no_se_lee(tmp_path):
    path = fake_zip(tmp_path, b"\x00" * (relieve.HGT_BYTES - 2))
    with pytest.raises(SystemExit):
        relieve.read_hgt(path)


def test_un_zip_fuera_del_repositorio_no_deja_salida(tmp_path):
    """tmp_path está fuera de la raíz del clon: generate sale antes de escribir nada."""
    path = fake_zip(tmp_path, b"")
    out = tmp_path / "salida"
    with pytest.raises(SystemExit, match="fuera del repositorio"):
        relieve.generate(path, 13.70, -89.12, 4.0, [14], out)
    assert not out.exists()


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


# El granulo, el recorte y la unión (#60)

@pytest.mark.parametrize("lat, lon, expected", [
    (13.97567, -89.34056, "NASADEM_HGT_n13w090"),   # norte y oeste: la 88118
    (35.68, 139.69, "NASADEM_HGT_n35e139"),         # norte y este
    (-33.45, -70.66, "NASADEM_HGT_s34w071"),        # sur y oeste
    (-0.5, 0.5, "NASADEM_HGT_s01e000"),             # sur y este, junto al cero
    (4.63279, -74.122, "NASADEM_HGT_n04w075"),      # las réplicas
    (10.67002, -71.62749, "NASADEM_HGT_n10w072"),
])
def test_el_nombre_del_granulo_sale_de_las_coordenadas(lat, lon, expected):
    assert relieve.granule_name(lat, lon) == expected


def test_un_recorte_que_cruza_un_borde_pide_los_dos_granulos():
    dentro = relieve.crop_cells(relieve.crop_bounds(13.5, -89.5, 4.0))
    assert relieve.granules_for(dentro) == ["NASADEM_HGT_n13w090"]
    borde = relieve.crop_cells(relieve.crop_bounds(13.5, -89.001, 4.0))
    assert relieve.granules_for(borde) == ["NASADEM_HGT_n13w089", "NASADEM_HGT_n13w090"]
    esquina = relieve.crop_cells(relieve.crop_bounds(13.999, -89.001, 4.0))
    assert len(relieve.granules_for(esquina)) == 4


def plano(top, left, cells=360, side=361):
    """Un granulo pequeño de enteros con una pendiente que sigue a través de los bordes."""
    rows, cols = np.mgrid[0:side, 0:side]
    i, j = round(top * cells) - rows, round(left * cells) + cols
    return relieve.Grid((3 * i - 2 * j - 20000).astype("int16"), top, left, 1.0 / cells)


def test_la_union_de_dos_granulos():
    oeste, este = plano(14.0, -90.0), plano(14.0, -89.0)
    # El recorte cruza el meridiano 89 °O.
    window = {"sur": 13 * 360 + 100, "norte": 13 * 360 + 140,
              "oeste": -89 * 360 - 30, "este": -89 * 360 + 30}
    grid = relieve.mosaic([oeste, este], window, cells=360)
    rows, cols = np.mgrid[0:41, 0:61]
    i, j = window["norte"] - rows, window["oeste"] + cols
    assert np.array_equal(grid.values, (3 * i - 2 * j - 20000).astype("int16"))
    assert relieve.grid_window(grid, cells=360) == window
    with pytest.raises(ValueError, match="otro granulo"):
        relieve.mosaic([oeste], window, cells=360)


def test_la_cuantizacion():
    heights = np.random.default_rng(60).uniform(-50.0, 3000.0, size=(256, 256))
    quantized = relieve.quantize(heights, 0.25)
    assert np.abs(quantized - heights).max() <= 0.125 + 1e-9
    rgb = relieve.terrarium_encode(quantized)
    assert set(np.unique(rgb[..., 2]).tolist()) <= {0, 64, 128, 192}
    assert np.array_equal(relieve.terrarium_decode(rgb), quantized)
    # Sin precisión, las alturas pasan como están.
    assert relieve.quantize(heights, None) is heights


def test_el_csv_del_recorte_ida_y_vuelta():
    grid = relieve.mosaic([plano(14.0, -90.0, cells=3600, side=40)],
                          {"sur": 13 * 3600 + 3575, "norte": 14 * 3600,
                           "oeste": -90 * 3600, "este": -90 * 3600 + 30})
    text = relieve.crop_to_csv(grid)
    assert text.splitlines()[0] == "lat,lon,altura_m"
    assert text.splitlines()[1] == f"14.0000000,-90.0000000,{grid.values[0, 0]}"
    back = relieve.grid_from_csv(text)
    assert np.array_equal(back.values, grid.values)
    assert (back.top, back.left, back.step) == (grid.top, grid.left, grid.step)
    with pytest.raises(ValueError, match="rectangular"):
        relieve.grid_from_csv("\n".join(text.splitlines()[:-1]))


def escuela_fabricada(tmp_path):
    """Un data/raw, un escuelas.json y un recortes/ en tmp_path, con un granulo fabricado."""
    raw = tmp_path / "raw"
    raw.mkdir()
    rows, cols = np.mgrid[0:relieve.HGT_SIDE, 0:relieve.HGT_SIDE]
    values = (400 + rows // 7 + (cols // 5) % 90).astype(">i2")
    with zipfile.ZipFile(raw / "NASADEM_HGT_n13w090.zip", "w") as archive:
        archive.writestr("n13w090.hgt", values.tobytes())
    (raw / "registro.json").write_text('{"descargado_utc": "2026-11-28T10:00:00+00:00"}',
                                       encoding="utf-8")
    escuelas = tmp_path / "escuelas.json"
    escuelas.write_text('{"escuelas": [{"slug": "sv-prueba", "lat": 13.50013, "lon": -89.49987}]}',
                        encoding="utf-8")
    return {"escuelas": escuelas, "raw": raw, "recortes": tmp_path / "recortes"}, values


def test_desde_el_zip_y_desde_el_recorte_salen_los_mismos_bytes(tmp_path, capsys):
    rutas, values = escuela_fabricada(tmp_path)
    zooms = [12, 13, 14]
    a, b = tmp_path / "desde-zip", tmp_path / "desde-recorte"
    assert relieve.generate_school("sv-prueba", 4.0, zooms, 0.25, (0, 1000), False, a,
                                   "prueba", **rutas) == 0
    # Sin el zip: el recorte basta.
    (rutas["raw"] / "NASADEM_HGT_n13w090.zip").rename(tmp_path / "apartado.zip")
    assert relieve.generate_school("sv-prueba", 4.0, zooms, 0.25, (0, 1000), True, b,
                                   "prueba", **rutas) == 0
    teselas = sorted(p.relative_to(a).as_posix() for p in a.rglob("*.png"))
    assert teselas and teselas == sorted(p.relative_to(b).as_posix() for p in b.rglob("*.png"))
    for nombre in teselas:
        assert (a / nombre).read_bytes() == (b / nombre).read_bytes(), nombre

    # El recorte: enteros del .hgt, con su manifiesto, y un nodo es el mismo píxel.
    carpeta = rutas["recortes"] / "sv-prueba" / "nasadem"
    filas = (carpeta / "elevacion.csv").read_text(encoding="utf-8").splitlines()
    lat, lon, altura = filas[1].split(",")
    row = round((14.0 - float(lat)) * 3600)
    col = round((float(lon) + 90.0) * 3600)
    assert int(altura) == values[row, col]
    manifiesto = json.loads((carpeta / "manifiesto.json").read_text(encoding="utf-8"))
    assert manifiesto["licencia"]["spdx"] == "CC0-1.0"
    assert manifiesto["fecha_descarga"] == "2026-11-28"
    assert [f["nombre"] for f in manifiesto["archivos"]] == ["elevacion.csv"]

    datos = json.loads((a / "relieve.json").read_text(encoding="utf-8"))
    assert datos["escuela"] == "sv-prueba" and datos["granulos"] == ["n13w090"]
    assert (datos["minzoom"], datos["maxzoom"], datos["precision_m"]) == (12, 14, 0.25)
    oeste, sur, este, norte = datos["bounds"]
    assert oeste < -89.49987 < este and sur < 13.50013 < norte
    assert datos["altura_esperada_m"] == [0, 1000]
    # La altura de la escuela, bilineal a mano con los cuatro nodos que la rodean.
    r, c = (14.0 - 13.50013) * 3600, (-89.49987 + 90.0) * 3600
    r0, c0 = int(r), int(c)
    fr, fc = r - r0, c - c0
    v = values.astype(float)
    mano = ((v[r0, c0] * (1 - fc) + v[r0, c0 + 1] * fc) * (1 - fr)
            + (v[r0 + 1, c0] * (1 - fc) + v[r0 + 1, c0 + 1] * fc) * fr)
    assert abs(datos["altitud_escuela_m"] - mano) <= 0.05 + 1e-9


def test_la_salida_con_archivos_no_se_mezcla(tmp_path):
    rutas, _ = escuela_fabricada(tmp_path)
    out = tmp_path / "salida"
    out.mkdir()
    (out / "vieja.png").write_bytes(b"")
    with pytest.raises(SystemExit, match="ya tiene archivos"):
        relieve.generate_school("sv-prueba", 4.0, [14], 0.25, (0, 1000), False, out,
                                "prueba", **rutas)
