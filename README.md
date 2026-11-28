# sarcae-lat

SARCAE-LAT: sistema de aprendizaje sobre riesgos de calor y agua en escuelas latinoamericanas, con datos de ERA5, un mapa y una maqueta digital interactiva. Reto 10 de CoAfina 2026, equipo Itzpapálotl.

## Límites

Lo que la herramienta no hace y lo que sus datos no pueden decir:

- **No es un pronóstico ni una evaluación oficial de riesgo**: muestra cómo ha sido el clima del lugar desde 1940 y dónde se acumulan el calor y el agua; sus preguntas para conversar no califican a la escuela.
- **ERA5 describe la zona, no la escuela**: es un reanálisis que da un solo valor por celda de unos 28 km de lado; el detalle del entorno sale del modelo de elevación y de Landsat.
- **La temperatura de superficie no es la del aire**: Landsat mide el calor de techos y suelos a la hora en que pasa el satélite, en cuadros de 100 m; compara zonas del entorno y no separa el techo del patio de una escuela.
- **Las alturas de los edificios son estimaciones**: se calculan a partir de imágenes de satélite, con un error medio de 1,5 m, mayor en algunos edificios; bastan para ver la forma del conjunto, no para medir un edificio.
- **Los criterios de diseño son salvadoreños**: los de ventilación, sombra y agua de lluvia vienen del Manual de Diseño Mi Nueva Escuela; en Colombia y Venezuela se usan criterios generales mientras no se encuentren sus equivalentes.
- **La maqueta muestra volúmenes, no el interior**: relieve y edificios con su contorno, altura y techo, más el patio y el drenaje; nunca la distribución interior, las puertas ni los accesos de una escuela, por la seguridad de quienes la ocupan.

El detalle de cada límite, en los tres registros, está en [docs/material/limites.md](docs/material/limites.md), y los términos técnicos, en [docs/material/glosario.md](docs/material/glosario.md).

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
| CHIRPS v3.0 | Climate Hazards Center, UCSB | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | https://www.chc.ucsb.edu/data/chirps3 | 2026-11-27 | Lluvia terrestre a 0,05°, de 60° S a 60° N, en todas las longitudes y desde 1981 hasta fechas recientes, para comparar con ERA5 |
| GHCNh v1, El Dorado (Bogotá, Colombia, `COI0000SKBO`) y La Chinita (Maracaibo, Venezuela, `VEI0000SVMC`) | NOAA NCEI | CC0 según la ficha del conjunto, pero el inventario sub-diario v3.0.0 de C3S y NCEI marca las dos estaciones como `non_commercial`: las series no se versionan y solo se publica la métrica (#46) | [Ficha de NCEI](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc%3AC01688) · [Lista de estaciones](https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh-station-list.txt) | 2026-11-27 | Contraste de ERA5 contra estaciones de las réplicas |
| Observaciones in situ de superficie terrestre v3.0.0 (`insitu-observations-surface-land`), Santa Ana/El Palmar (El Salvador, `ESI0000MSSA`) | C3S y NOAA NCEI; los datos de la estación son reportes de aeropuerto de la OACI (fuente 223) | CC BY 4.0 el conjunto, con su política de datos v3.0. El inventario sub-diario v3.0.0 marca la estación como `non_commercial`: la serie no se versiona y solo se publica la métrica (#39) | https://cds.climate.copernicus.eu/datasets/insitu-observations-surface-land | 2026-11-27 | Contraste horario de ERA5 en la escuela ancla, en el horario escolar |
| Manual de Diseño Mi Nueva Escuela (2022) | MINEDUCYT, El Salvador | sin licencia declarada: solo se usan sus medidas y criterios, citando la página, y no se copian sus figuras | https://www.mined.gob.sv/licitacion/2023/46-2023-SDO/anexo2/MANUAL%20DE%20DISE%C3%91O-MI%20NUEVA%20ESCUELA.pdf | 2026-11-27 | Medidas de aulas y criterios de ventilación, sombra y aguas lluvias (`docs/refs/manual-mi-nueva-escuela.md`) |

No se usa el Copernicus DEM GLO-30. La licencia de su instancia pública, COP-DEM-GLO-30-F
("Full, Free & Open", p. 22 del PDF), permite reproducir, distribuir y adaptar gratis (art. 4 y
5), pero es una licencia propia y no CC0, CC BY ni dominio público. Su art. 6 exige un aviso que
termina en "all rights reserved" y una cláusula de exención de responsabilidad, y obliga a los
usuarios posteriores. Página y licencia:
https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM
y https://dataspace.copernicus.eu/sites/default/files/media/files/2025-06/copernicus_contributing_mission_data_access_v2_cop_dem_licenses.pdf,
consultadas el 2026-11-27.

### Atribución

Textos consultados el 2026-11-27. El control de atribución del mapa muestra el crédito de cada
capa. En los recortes con CC BY 4.0 se indica también la licencia y qué se modificó.

- **Mistral Small 3.1 24B Instruct 2503**. Modelo de Mistral AI bajo Apache 2.0, usado en la
  prueba del asistente en Workers AI, con una ficha ficticia. [Ficha del modelo](https://huggingface.co/mistralai/Mistral-Small-3.1-24B-Instruct-2503)
  · [ADR-002](docs/decisiones/ADR-002-proveedor-asistente.md).

- **ERA5 y ERA5-Land (C3S)**. Para datos publicados tal cual, «Generated using Copernicus Climate
  Change Service information [Year]». Para datos adaptados, «Contains modified Copernicus Climate
  Change Service information [Year]». [Textos de C3S](https://cds.climate.copernicus.eu/licences/licence-to-use-copernicus-products).
  En ambos casos se añade «Neither the European Commission nor ECMWF is responsible for any use
  that may be made of the Copernicus information or data it contains.» También se cita la entrada
  del CDS. [Guía de atribución](https://confluence.ecmwf.int/pages/viewpage.action?pageId=197704114) ·
  [ERA5, niveles de superficie](https://doi.org/10.24381/cds.adbb2d47) ·
  [ERA5, serie por punto](https://doi.org/10.24381/1cf1ad76) ·
  [ERA5-Land](https://doi.org/10.24381/cds.e2161bac).
- **NASADEM**. «NASA JPL. NASADEM Merged DEM Global 1 arc second V001. 2020, distributed by NASA
  EOSDIS Land Processes Distributed Active Archive Center, https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001».
  [Cita sugerida por NASA Earthdata](https://forum.earthdata.nasa.gov/viewtopic.php?t=5421).
- **Landsat 8 y 9**. «Landsat Collection 2 Level-2 image courtesy of the U.S. Geological Survey.»
  [Crédito del USGS](https://www.usgs.gov/landsat-missions/landsat-collection-2-level-2-science-products) ·
  [Cita de los datos Landsat 8-9](https://doi.org/10.5066/P9OGBGM6).
- **ESA WorldCover**. «© ESA WorldCover project [year] / Contains modified Copernicus Sentinel data
  ([year]) processed by ESA WorldCover consortium». Se sustituye `[year]` por 2020 o 2021 según la
  versión de la capa. [Texto de ESA](https://esa-worldcover.org/en/data-access) ·
  [Datos de 2020](https://doi.org/10.5281/zenodo.5571936) ·
  [Datos de 2021](https://doi.org/10.5281/zenodo.7254221).
- **Google Open Buildings v3**. Crédito a Google Research con CC BY 4.0. Google sugiere citar
  «W. Sirko, S. Kashubin, M. Ritter, A. Annkah, Y.S.E. Bouchareb, Y. Dauphin, D. Keysers,
  M. Neumann, M. Cisse, J.A. Quinn. Continental-scale building detection from high resolution
  satellite imagery. arXiv:2107.12283, 2021.» [Cita de Google Research](https://sites.research.google/gr/open-buildings/).
- **Google Open Buildings 2.5D Temporal**. Crédito a Google Research con CC BY 4.0. Google
  sugiere citar «W. Sirko, E.A. Brempong, J.T.C. Marcos, A. Annkah, A. Korme, M.A. Hassen,
  K. Sapkota, T. Shekel, A. Diack, S. Nevo, J. Hickey, J.A. Quinn. High-Resolution Building and
  Road Detection from Sentinel-2. arXiv:2310.11622, 2023.»
  [Cita de Google Research](https://sites.research.google/gr/open-buildings/temporal/).
- **CHIRPS v3.0**. «Climate Hazards Center Infrared Precipitation with Stations version 3
  (CHIRPS3) Data Repository: https://doi.org/10.15780/G2JQ0P (2025). Data was accessed on [DATE].»
  [Cita del Climate Hazards Center](https://www.chc.ucsb.edu/data/chirps3).
- **NOAA GHCNh**. «Menne, Matthew J.; Noone, Simon; Casey, Nancy W.; Dunn, Robert H.; McNeill,
  Shelley; Kantor, Diana; Thorne, Peter W.; Orcutt, Karen; Cunningham, Sam; Risavi, Nicholas.
  2023. Global Historical Climatology Network-Hourly (GHCNh). [indicate subset used]. NOAA
  National Centers for Environmental Information. https://doi.org/10.25921/jp3d-3v19. [access date]».
  [Cita de NCEI](https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc%3AC01688/html).

Para sus observaciones horarias internacionales históricas, NCEI advierte «These data and
products may have conditions placed on their international commercial use.» NCEI remite a la
Resolución 40 de la OMM, sustituida en 2021 por la Resolución 1. La ficha CC0 de GHCNh declara
la renuncia de NOAA a sus posibles derechos. El inventario de estaciones sub-diarias v3.0.0
de C3S y NCEI, consultado el 2026-11-27, marca El Dorado y La Chinita como `non_commercial`.
Por eso sus series no se versionan: se bajan a `data/raw/`, y en el repositorio entran el
script que las baja y la métrica (#46). [Aviso histórico de NCEI](https://www.ncei.noaa.gov/nespls/olstore.prodspecific?prodnum=4851) ·
[Ficha de GHCNh](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc%3AC01688) ·
[Política de la OMM](https://wmo.int/wmo-unified-data-policy).

- **Observaciones in situ de superficie terrestre (C3S y NCEI), v3.0.0**. Como en ERA5, «Contains
  modified Copernicus Climate Change Service information [Year]», con la exención de
  responsabilidad de C3S y la entrada del CDS, https://doi.org/10.24381/cds.cf5f3bac. Para la
  estación Santa Ana/El Palmar, la fuente 223 pide «International Civil Aviation Organisation
  USAF : National Climatic Data Center/NESDIS/NOAA/U.S. Department of Commerce. 1982.AWS TD13
  Global Surface Observations, daily 1901-1973. Research Data Archive at the National Center
  for Atmospheric Research, Computational and Information Systems Laboratory.
  https://rda.ucar.edu/datasets/ds467.0/. Accesseddd mmm yyyy.», con la fecha de acceso.
  [Archivo de fuentes v3.0.0](https://confluence.ecmwf.int/download/attachments/656869601/sources_v3.0.0.psv?version=1&modificationDate=1776783749760&api=v2) ·
  [Inventario sub-diario v3.0.0](https://confluence.ecmwf.int/download/attachments/656869601/Sub_daily_inventory_v3.0.0.psv?version=1&modificationDate=1776783749830&api=v2) ·
  [Política de datos v3.0](https://object-store.os-api.cci2.ecmwf.int:443/cci2-prod-catalogue/licences/global-land-observations-data-policy/global-land-observations-data-policyv3_cf677c7ab8cdb21b137de1946b62f7fdd4c65c950d1ca19e82383da7a404ea3e.pdf).

### Código de terceros

- **MapLibre GL JS 6.20.0** (BSD-3-Clause). «Copyright (c) 2023, MapLibre contributors».
  [Versión en npm](https://www.npmjs.com/package/maplibre-gl/v/6.20.0) ·
  [Archivos y procedencia](web/vendor/maplibre-gl-6.20.0/ORIGEN.md).
- El [LICENSE.txt distribuido con MapLibre](web/vendor/maplibre-gl-6.20.0/LICENSE.txt) conserva
  los avisos de **mapbox-gl-js v1.13 y anteriores** (BSD-3-Clause, «Copyright (c) 2020, Mapbox»),
  **glfx.js** (MIT, «Copyright (C) 2011 by Evan Wallace») y **d3-color** (BSD-3-Clause,
  «Copyright 2010-2016 Mike Bostock»). El paquete incluye dependencias con licencias ISC, MIT,
  BSD-2-Clause, BSD-3-Clause y Apache-2.0. [Dependencias del paquete](https://registry.npmjs.org/maplibre-gl/6.20.0).

### Tipografía

| Fuente | Productor | Licencia | Enlace | Consulta | Para qué |
|---|---|---|---|---|---|
| IBM Plex Sans e IBM Plex Mono, en los paquetes `@fontsource/ibm-plex-sans` e `@fontsource/ibm-plex-mono` 5.3.0 | IBM Corp.; reempaquetadas por Fontsource | SIL OFL 1.1 (`web/fonts/OFL-ibm-plex-sans.txt` y `web/fonts/OFL-ibm-plex-mono.txt`) | https://github.com/IBM/plex | 2026-11-28 | Texto, cifras y rótulos del front (`web/fonts/ORIGEN.md`) |

## Verificación

`python3 .github/higiene.py`

## Licencia

- **El código propio** (los scripts, las pruebas y el código del sitio) va con la licencia MIT:
  [LICENSE](LICENSE).
- **La documentación, el material educativo y los modelos propios** (`docs/`, este README y las
  maquetas que genere el proyecto) van con CC BY 4.0:
  [texto legal](LICENSE-CC-BY-4.0.txt) ·
  [traducción oficial al español](https://creativecommons.org/licenses/by/4.0/legalcode.es).
- **Los datos y el código de terceros conservan su licencia**: la de cada fuente, en
  [Fuentes y licencias](#fuentes-y-licencias), y la de MapLibre, en
  [web/vendor/maplibre-gl-6.20.0/LICENSE.txt](web/vendor/maplibre-gl-6.20.0/LICENSE.txt).

Para citar el material:

> equipo Itzpapálotl (2026). *SARCAE-LAT: sistema de aprendizaje sobre riesgos de calor y agua
> en escuelas latinoamericanas*. CC BY 4.0. https://github.com/jofavalle/sarcae-lat
