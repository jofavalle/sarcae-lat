// Orden #62. Pegar en el editor de Earth Engine y ejecutar las tareas de Drive.
// Recortes de las tres sedes exportados el 2026-11-28 (UTC).
// Cambiar SEDE a uno de los otros slugs después de comprobar el primer recorte.
var SEDE = 'sv-88118';
var SEDES = {
  'sv-88118': {lon: -89.34056, lat: 13.97567, utm: 'EPSG:32616'},
  'co-nicolas-esguerra': {lon: -74.12200, lat: 4.63279, utm: 'EPSG:32618'},
  've-rafael-maria-baralt': {lon: -71.62749, lat: 10.67002, utm: 'EPSG:32619'}
};
var sede = SEDES[SEDE];
var WGS84 = 'EPSG:4326';
var DESDE = '2024-01-01';
var HASTA_EXCLUSIVO = '2026-01-01';
var LADO_CUADROS = 21;
var CUADRO_M = 100;
var MITAD_M = LADO_CUADROS * CUADRO_M / 2;
var DRIVE = 'sarcae-lat-orden-62';

var centro = ee.Geometry.Point([sede.lon, sede.lat]);
var centroUTM = centro.transform(sede.utm, 0.01).coordinates();
var oeste = ee.Number(centroUTM.get(0)).subtract(MITAD_M);
var norte = ee.Number(centroUTM.get(1)).add(MITAD_M);

function rectangulo(i, j, lado) {
  var x = oeste.add(ee.Number(i).multiply(CUADRO_M));
  var y = norte.subtract(ee.Number(j).multiply(CUADRO_M));
  return ee.Geometry.Rectangle([x, y.subtract(lado), x.add(lado), y], sede.utm, false);
}

function transformacion(resolucion) {
  return ee.List([resolucion, 0, oeste, 0, -resolucion, norte]);
}

var ventana = rectangulo(0, 0, 2 * MITAD_M);
var indices = ee.List.sequence(0, LADO_CUADROS - 1);
var malla = ee.FeatureCollection(indices.map(function (j) {
  return indices.map(function (i) {
    return ee.Feature(rectangulo(i, j, CUADRO_M), {
      cuadro: ee.Number(j).multiply(LADO_CUADROS).add(i)
    });
  });
}).flatten());

function temperatura(escena) {
  // QA_PIXEL, bits 1 a 4: nube dilatada, cirro, nube y sombra de nube.
  var despejado = escena.select('QA_PIXEL').bitwiseAnd(30).eq(0);
  return escena.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15)
    .updateMask(despejado).toDouble().rename('t_superficie_c')
    .set('system:index', escena.get('system:index'));
}

function landsat() {
  var escenas = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
    .merge(ee.ImageCollection('LANDSAT/LC09/C02/T1_L2'))
    .filterBounds(ventana)
    .filterDate(DESDE, HASTA_EXCLUSIVO)
    .filter(ee.Filter.gte('CLOUD_COVER', 0))
    .filter(ee.Filter.lt('CLOUD_COVER', 20))
    .filter(ee.Filter.eq('PROCESSING_LEVEL', 'L2SP'))
    .sort('system:time_start');

  // La banda vacía mantiene la estructura aunque ninguna escena pase los filtros.
  var vacia = ee.Image.constant(0).toDouble().rename('t_superficie_c').selfMask()
    .set('system:index', 'sin_escena');
  var termicas = escenas.map(temperatura).merge(ee.ImageCollection.fromImages([vacia]));
  var validez = termicas.map(function (imagen) {
    return imagen.mask().unmask(0, false).toByte().rename('valida')
      .set('system:index', imagen.get('system:index'));
  }).toBands();
  var bandasValidez = validez.bandNames();
  // El centro del píxel de 30 m decide a qué cuadro pertenece. Con las bandas
  // 0/1, una media positiva implica que la escena aporta al menos un píxel.
  var estadisticas = termicas.median().addBands(validez).reduceRegions({
    collection: malla,
    reducer: ee.Reducer.mean().unweighted(),
    crs: sede.utm,
    crsTransform: transformacion(30),
    tileScale: 4
  });
  var cuadros = estadisticas.map(function (cuadro) {
    var nEscenas = ee.Number(bandasValidez.map(function (banda) {
      return ee.Number(cuadro.get(ee.String(banda))).gt(0);
    }).reduce(ee.Reducer.sum()));
    return ee.Feature(cuadro.geometry().transform(WGS84, 0.01), {
      cuadro: cuadro.get('cuadro'),
      t_superficie_c: cuadro.get('t_superficie_c'),
      n_escenas: nEscenas
    });
  });

  var catalogo = ee.FeatureCollection(escenas.toList(escenas.size().max(1)).map(function (item) {
    var imagen = ee.Image(item);
    return ee.Feature(null, {
      id: imagen.get('LANDSAT_PRODUCT_ID'),
      fecha: imagen.date().format('yyyy-MM-dd', 'UTC'),
      hora_utc: imagen.date().format('HH:mm:ss', 'UTC'),
      nubosidad: imagen.get('CLOUD_COVER')
    });
  }));
  return {cuadros: cuadros.sort('cuadro'), escenas: catalogo};
}

function worldcover() {
  var proyeccion = ee.Projection(sede.utm, transformacion(10));
  var mapa = ee.Image(ee.ImageCollection('ESA/WorldCover/v200').first())
    .select('Map').rename('clase').unmask(0, false);
  // Se exportan las posiciones de los centros de píxel, de 0,5 a 209,5.
  var indicesPixel = ee.Image.pixelCoordinates(proyeccion).rename(['i', 'j']);
  var celdas = indicesPixel.addBands(mapa).sample({
    region: ventana,
    projection: proyeccion,
    geometries: false,
    tileScale: 4
  });
  var este = oeste.add(2 * MITAD_M);
  var sur = norte.subtract(2 * MITAD_M);
  // Se ordenan al importar el GeoJSON por el campo orden para escribir esquinas.json.
  var esquinas = ee.FeatureCollection([
    [oeste, norte], [este, norte], [este, sur], [oeste, sur]
  ].map(function (xy, orden) {
    var punto = ee.Geometry.Point(xy, sede.utm).transform(WGS84, 0.01);
    return ee.Feature(punto, {orden: orden});
  }));
  return {celdas: celdas, esquinas: esquinas};
}

function edificios() {
  var radio = centro.buffer(300, ee.ErrorMargin(0.01, 'projected'), sede.utm);
  var contornos = ee.FeatureCollection('GOOGLE/Research/open-buildings/v3/polygons')
    .filterBounds(radio)
    .filter(ee.Filter.gte('confidence', 0.70));
  var temporal = ee.ImageCollection('GOOGLE/Research/open-buildings-temporal/v1')
    .filterBounds(ventana)
    .filterDate('2023-01-01', '2024-01-01').mosaic();
  // Google recomienda enmascarar alturas con presencia baja. Para América Latina,
  // 0,37 maximiza la coincidencia de contornos en su evaluación (tabla 11 de 2310.11622).
  var alturas = temporal.select('building_height').rename('altura_m')
    .updateMask(temporal.select('building_presence').gte(0.37));
  return alturas.reduceRegions({
    collection: contornos,
    reducer: ee.Reducer.mean().setOutputs(['altura_m']),
    crs: sede.utm,
    scale: 0.5,
    tileScale: 4
  }).map(function (edificio) {
    return ee.Feature(edificio.geometry().transform(WGS84, 0.01), {
      id: edificio.id(),
      confianza: edificio.get('confidence'),
      area_m2: edificio.get('area_in_meters'),
      altura_m: edificio.get('altura_m')
    });
  }).sort('id');
}

function exportar(coleccion, archivo, formato, campos) {
  var nombre = SEDE + '_' + archivo;
  Export.table.toDrive({
    collection: coleccion,
    description: nombre,
    folder: DRIVE,
    fileNamePrefix: nombre,
    fileFormat: formato,
    selectors: campos
  });
}

var calor = landsat();
var cobertura = worldcover();
exportar(calor.cuadros, 'cuadros', 'GeoJSON', ['cuadro', 't_superficie_c', 'n_escenas', '.geo']);
exportar(calor.escenas, 'escenas', 'CSV', ['id', 'fecha', 'hora_utc', 'nubosidad']);
exportar(cobertura.celdas, 'celdas', 'CSV', ['i', 'j', 'clase']);
exportar(cobertura.esquinas, 'esquinas', 'GeoJSON', ['orden', '.geo']);
exportar(edificios(), 'edificios', 'GeoJSON', ['id', 'confianza', 'area_m2', 'altura_m', '.geo']);

var cuadroCentral = calor.cuadros.filter(ee.Filter.eq('cuadro', 220));
Map.centerObject(centro, 15);
Map.addLayer(cuadroCentral, {color: '6cc8e0'}, 'Cuadro central (100 m)');
Map.addLayer(centro, {color: 'ffffff'}, 'Escuela');
Map.addLayer(calor.cuadros.filter(ee.Filter.notNull(['t_superficie_c']))
  .reduceToImage(['t_superficie_c'], ee.Reducer.first())
  .rename('t_superficie_c'), {min: 15, max: 45}, 'Media por cuadro de la mediana Landsat', false);
print('Fecha de la corrida UTC', new Date().toISOString().slice(0, 10));
print('Cuadro central', cuadroCentral.first());
