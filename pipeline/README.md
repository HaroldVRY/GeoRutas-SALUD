# Pipeline de precálculo — GeoRutas SALUD

Corre OFFLINE. Lee las capas de GEO Perú en `data/raw/`, calcula isócronas, escenario
estacional y scores de priorización, y escribe los resultados ligeros en
`../backend/data/` (GeoJSON + SQLite) para que la API los sirva.

## Orden de ejecución

```bash
python src/run_pipeline.py
```

que ejecuta en cadena:

1. `build_graph.py`      — construye el grafo vial y asigna tiempo por arista (factor 1)
2. `compute_isochrones.py` — tiempo de acceso de cada centro poblado al establecimiento resolutivo más cercano
3. `seasonal.py`         — recalcula penalizando tramos vulnerables en lluvias (factor 2)
4. `compute_scores.py`   — score de priorización por tramo candidato (factor 4)
5. `export.py`           — vuelca GeoJSON + SQLite a ../backend/data/

## Capas esperadas en data/raw/ (descargar de GEO Perú)

| Archivo (sugerido)        | Capa | Fuente |
|---------------------------|------|--------|
| red_vial.shp/.geojson     | Red vial nacional/dep./vecinal | MTC |
| salud.geojson             | Establecimientos de salud + categoría | MINSA/RENIPRESS |
| centros_poblados.geojson  | Centros poblados | INEI |
| poblacion.csv             | Población (y vulnerable) por CCPP | INEI |
| riesgo_inundacion.geojson | Susceptibilidad a inundación (para escenario lluvias) | GEO Perú |

> Ajusta los nombres reales tras verificarlos en el Visor de GEO Perú.
