# EPSG Quick Reference

A working reference of the CRS codes you will actually encounter in
GeoAI work, organised by purpose. The agent should call
`geoai_get_crs_info` to verify any code before reprojection — but
for fast mental dispatch, this list is the cheat-sheet.

## Geographic (degrees)

| EPSG | Name | Use |
|---|---|---|
| 4326 | WGS84 | Default exchange format. Storage, GeoJSON, GPS. **Never** for analysis. |
| 4269 | NAD83 | US federal data. Storage only. |
| 4258 | ETRS89 | European federal data. Storage only. |

## Web tile output

| EPSG | Name | Use |
|---|---|---|
| 3857 | Web Mercator | Tile output for OpenLayers, Leaflet, MapLibre. Distorts area badly above 60° lat — never use for analysis. |

## United Kingdom

| EPSG | Name | Use |
|---|---|---|
| 27700 | British National Grid | Default working CRS for all UK projects. Metres, suitable for distance and area. |
| 7405 | OSGB36 with vertical | When working with Ordnance Survey heights. |

## Continental Europe

| EPSG | Name | Use |
|---|---|---|
| 3035 | ETRS89-LAEA | Equal-area, default for pan-European analysis. |
| 3034 | ETRS89-LCC | Conformal, default for navigation/aviation in Europe. |

## United States

| EPSG | Name | Use |
|---|---|---|
| 5070 | NAD83 CONUS Albers | Default working CRS for continental US analysis. Equal area. |
| 3338 | NAD83 Alaska Albers | Alaska. |
| 6635 | NAD83 Hawaii Albers | Hawaii. |

## Universal Transverse Mercator

UTM zones are the reliable fallback when the locale is unfamiliar.
The zone is determined by longitude:

- Zone N = floor((longitude + 180) / 6) + 1
- Northern hemisphere: EPSG = 32600 + zone
- Southern hemisphere: EPSG = 32700 + zone

| Region | Zone | EPSG |
|---|---|---|
| London | 30N | 32630 |
| Paris | 31N | 32631 |
| Tokyo | 54N | 32654 |
| New York | 18N | 32618 |
| Sydney | 56S | 32756 |

## Global equal-area

| EPSG | Name | Use |
|---|---|---|
| 54009 | Mollweide | Global area calculations, world maps. |
| 6933 | NSIDC EASE-Grid 2.0 | Polar / global remote sensing. |

## Quick decision tree

```
Is the data going to a web map?
├── Yes  → output CRS = 3857
└── No
    ├── Is it for distance/area calc?
    │   ├── Yes
    │   │   ├── UK?      → 27700
    │   │   ├── Europe?  → 3035
    │   │   ├── CONUS?   → 5070
    │   │   ├── Global?  → 54009 (area) or appropriate UTM (distance)
    │   │   └── Unsure?  → call geoai_get_crs_info first
    │   └── No
    │       └── Storage / exchange? → 4326 is fine
```
