# Verified source starting points (checked 13 Oct 2026)

The presence of a public layer does **not** mean it contains data at the selected property. Inspect coverage, actual schema, datum, timestamp, licences, and values before use.

- Council public Overland Flow Paths: https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/Overland_Flow_Paths/FeatureServer/0
- Council public Flood Plains: https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/Flood_Plains/FeatureServer/0
- Council public Flood Prone Areas: https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/Flood_Prone_Areas/FeatureServer/0
- Council public Stormwater Pipes: https://services1.arcgis.com/n4yPwebTjJCmXB6W/ArcGIS/rest/services/Stormwater_Pipe/FeatureServer/0
- Council public Catchpits: https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/Stormwater_Catchpit/FeatureServer/0
- Council public Manholes/Chambers: https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/Stormwater_Manhole_And_Chamber/FeatureServer/0
- Council public Stormwater Connections: https://services1.arcgis.com/n4yPwebTjJCmXB6W/arcgis/rest/services/Stormwater_Connection/FeatureServer/0
- LINZ NZ Addresses and buildings and parcels: https://data.linz.govt.nz/data/
- LINZ Auckland Part 2 2024 DEM spec: https://data.linz.govt.nz/layer/122580-auckland-part-2-lidar-1m-dem-2024/
- LINZ Auckland Part 2 2024 tile index: https://data.linz.govt.nz/layer/122590-auckland-part-2-lidar-index-tiles-2024/
- LINZ Part 2 raw point cloud: https://data.linz.govt.nz/layer/d3W9HT9YGf35Ph8/auckland-part-2-lidar-point-cloud-2024/
- LINZ national DEM: https://data.linz.govt.nz/layer/121859-new-zealand-lidar-1m-dem/
- NZ elevation STAC: https://nz-elevation.s3.ap-southeast-2.amazonaws.com/catalog.json
- OpenTopography: https://portal.opentopography.org/
- Official LINZ API key howto: https://www.linz.govt.nz/guidance/data-service/linz-data-service-guide/web-services/creating-api-key
- NIWA/Earth Sciences NZ HIRDS: https://niwa.co.nz/climate-and-weather/high-intensity-rainfall-design-system-hirds
- SFINCS: https://github.com/Deltares/SFINCS
- SFINCS weir and drainage: https://sfincs.readthedocs.io/en/latest/input_structures.html
- HydroMT-SFINCS: https://github.com/Deltares/hydromt_sfincs
- LINZ vertical grids: https://www.linz.govt.nz/guidance/geodetic-system/understanding-coordinate-conversions/height-datum-conversions/vertical-datum-relationship-grids
- Council region flood viewer context: https://ourauckland.aucklandcouncil.govt.nz/news/2026/03/understanding-auckland-s-regional-flood-maps/

**Important:** 2024 Auckland point cloud survey is split into Part 1 and Part 2; discover intersecting coverage instead of hardcoding Part 2. Council overland flow lines were mapped from ~2016/2017 surveys, not automatically updated to 2024. Stormwater asset mapping is indicative. LiDAR NZVD2016 may differ from legacy Auckland datum; never add an arbitrary vertical offset.
