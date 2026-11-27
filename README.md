# sarcae-lat

SARCAE-LAT: sistema de aprendizaje sobre riesgos de calor y agua en escuelas latinoamericanas, con datos de ERA5, un mapa y una maqueta digital interactiva. Reto 10 de CoAfina 2026, equipo Itzpapálotl.

## Fuentes y licencias

Cada licencia se leyó en el sitio de quien produce el dato.

| Fuente | Productor | Licencia | Enlace | Consulta | Para qué |
|---|---|---|---|---|---|
| ERA5, niveles de superficie (`reanalysis-era5-single-levels`) | ECMWF, para el Servicio de Cambio Climático de Copernicus (C3S) | CC BY 4.0 | https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels | 2026-11-27 | Clima de la zona desde 1940 y altura de la celda |
| ERA5, serie horaria por punto (`reanalysis-era5-single-levels-timeseries`) | ECMWF, para el C3S | CC BY 4.0 | https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-timeseries | 2026-11-27 | Serie horaria de un punto desde 1940 |
| ERA5-Land (`reanalysis-era5-land`) | ECMWF, para el C3S | CC BY 4.0 | https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land | 2026-11-27 | Refinamiento de ERA5 a 0,1°, desde 1950 |
| NASADEM (NASADEM_HGT v001) | NASA JPL, distribuido por el LP DAAC | CC0 (política de datos de NASA: https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance) | https://www.earthdata.nasa.gov/data/catalog/lpcloud-nasadem-hgt-001 | 2026-11-27 | Corrección por altura y flujo del agua |
| Landsat 8 y 9, Collection 2, Level-2, temperatura de superficie | USGS, centro EROS | dominio público, sin restricciones de uso | https://www.usgs.gov/landsat-missions/landsat-collection-2-level-2-science-products | 2026-11-27 | Dónde se calienta más la superficie |
| ESA WorldCover | ESA y el consorcio WorldCover | CC BY 4.0 | https://esa-worldcover.org/en/data-access | 2026-11-27 | Cobertura del suelo |
| Google Open Buildings v3 | Google Research | CC BY 4.0 u ODbL, a elección; se usa con CC BY 4.0 | https://sites.research.google/gr/open-buildings/ | 2026-11-27 | Contornos de los edificios |
| Google Open Buildings 2.5D Temporal | Google Research | CC BY 4.0 u ODbL, a elección; se usa con CC BY 4.0 | https://sites.research.google/gr/open-buildings/temporal/ | 2026-11-27 | Alturas de los edificios, 2016 a 2023 |
| CHIRPS v2.0 y v3.0 | Climate Hazards Center, UCSB | v2.0: dominio público; v3.0: CC BY 4.0 | https://www.chc.ucsb.edu/data/chirps y https://www.chc.ucsb.edu/data/chirps3 | 2026-11-27 | Lluvia, para comparar con ERA5 |
| Manual de Diseño Mi Nueva Escuela (2022) | MINEDUCYT, El Salvador | sin licencia declarada: solo se usan sus medidas y criterios, citando la página, y no se copian sus figuras | https://www.mined.gob.sv/licitacion/2023/46-2023-SDO/anexo2/MANUAL%20DE%20DISE%C3%91O-MI%20NUEVA%20ESCUELA.pdf | 2026-11-27 | Medidas de aulas y criterios de ventilación, sombra y aguas lluvias (`docs/refs/manual-mi-nueva-escuela.md`) |

No se usa el Copernicus DEM GLO-30: su "ESA - User licence" (emitida el 21/02/2025) no es CC0,
CC BY ni dominio público. Solo permite publicar con fines no comerciales y redistribuir a quien
haya aceptado sus términos (cláusulas 3.5.1.6 y 3.5.1.11). Página y licencia:
https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM
y https://dataspace.copernicus.eu/sites/default/files/media/files/2025-06/copernicus_contributing_mission_data_access_v2_cop_dem_licenses.pdf,
consultadas el 2026-11-27.

## Verificación

`python3 .github/higiene.py`
