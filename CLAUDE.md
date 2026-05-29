# CLAUDE.md — GeoRutas SALUD (BACKEND + PIPELINE)

> Instrucciones para Claude Code. Léelas completas antes de actuar.

## ⛔ ALCANCE — LÍMITE ESTRICTO

Trabaja **ÚNICAMENTE** en `pipeline/` y `backend/`.

**NO toques la carpeta `frontend/`** bajo ninguna circunstancia (ni leas para "ayudar", ni edites, ni instales dependencias, ni la despliegues). El frontend lo maneja otra persona. Si una tarea parece requerir tocar el frontend, **detente y avísalo** en vez de hacerlo.

## Contexto del proyecto

GeoRutas SALUD es una propuesta para la **GEOTÓN PERÚ 2026** (categoría Territorio Conectado, organiza la PCM de Perú). El problema: en el Perú rural, el tiempo de viaje al establecimiento de salud con capacidad resolutiva —no la distancia— determina quién sobrevive a una emergencia, y en temporada de lluvias muchas vías se vuelven intransitables.

El producto es un tablero de **priorización de inversión vial** para reducir muertes evitables. El alcance analítico tiene 3 factores:

1. **Isócronas reales** sobre la red vial (tiempo de viaje, no distancia en línea recta).
2. **Priorización de tramos**: ranking de qué tramos viales mejorar para que más población vulnerable gane acceso oportuno.
3. **Escenario estacional**: comparar acceso en seco vs. lluvias (tramos vulnerables penalizados).

## Fuentes de datos (DECISIÓN TOMADA — respétala)

Tras revisar las capas viales de GEO Perú, se confirmó que están partidas por nivel
(Nacional/Departamental/Vecinal) y por superficie, y NO están nodadas topológicamente,
así que **no sirven como red para enrutar**. Decisión:

- **Red para enrutar (el grafo) → OpenStreetMap (OSM) vía `osmnx`.** Trae una red conectada
  y lista para grafo, con atributos `highway`, `surface`, `maxspeed`. Es abierta y reproducible.
- **Centros poblados y establecimientos de salud → GEO Perú** (INEI / MINSA-RENIPRESS).
  Estas son el **dataset obligatorio del concurso** y el valor real del análisis.
- **Capas viales de GEO Perú → solo como evidencia oficial / corroboración** en el pitch,
  o para etiquetar superficie por cruce espacial. NO como grafo.
- **NO usar Google Maps API**: es de pago y sus términos PROHÍBEN almacenar/precalcular rutas,
  lo que choca con nuestra arquitectura de precálculo offline; además no es dato abierto.

**Trabajar sobre un DEPARTAMENTO PILOTO**, no todo el Perú (OSM nacional es inviable en el plazo).
Elegir una región rural y dispersa con dolor de acceso fuerte. Dejar "escalable a todo el país"
como cierre de valor público. La región piloto se fija en `config.py` (variable `REGION_PILOTO`,
por defecto `"Huancavelica, Peru"`).

**Cómo obtener la red OSM (IMPORTANTE):** descargar SIEMPRE con `osmnx` por nombre, NO usar
exportaciones manuales del sitio web de OSM (tienen límite de tamaño y fallan con un departamento).

```python
import osmnx as ox
G = ox.graph_from_place(config.REGION_PILOTO, network_type="drive")
```

Cachear el grafo descargado en `pipeline/data/processed/grafo_<region>.graphml` (con
`ox.save_graphml` / `ox.load_graphml`) y reusarlo si ya existe, para no re-descargar en cada corrida.
Si `graph_from_place` fallara por geocodificación, usar `graph_from_bbox` con el bbox de Huancavelica
(N −11.85, S −14.10, O −75.80, E −74.35) como respaldo.

## Arquitectura y flujo de datos (NO romper esto)

```
OSM (osmnx) ──────────────►  pipeline/ (GeoPandas + NetworkX, OFFLINE)  ◄──── GEO Perú
  (red para enrutar)                 │ escribe resultados ligeros          (CCPP + salud)
                                     ▼
                             backend/data/  (*.geojson + app.db SQLite)
                                     │
                             backend/ FastAPI  ── solo SIRVE los datos ──►  (frontend, fuera de alcance)
```

**Regla de oro:** el backend NO calcula isócronas ni scores. Todo el cómputo pesado vive en `pipeline/` y se ejecuta offline. El backend solo lee `backend/data/` y lo expone por la API. Esto mantiene la API rápida y dentro del plan gratuito de Render.

## Estado actual (punto de partida)

Ya existe el esqueleto. Lo que está hecho:

- `backend/`: FastAPI funcional con CORS, `/api/health`, routers `accesibilidad` y `tramos`, y `services/data_loader.py` que lee GeoJSON + SQLite. **Sirve datos pero aún no hay datos reales generados.**
- `pipeline/src/`: módulos con la lógica esbozada y TODOs:
  - `config.py` — rutas de shapefiles, nombres de columnas, umbrales y supuestos (umbral 120 min, velocidades por superficie, categorías MINSA resolutivas, pesos de vulnerabilidad). **Centraliza aquí todo parámetro configurable.**
  - `build_graph.py` — **debe reescribirse para construir el grafo desde OSM con `osmnx`** (no desde el shapefile vial). Descargar la red del departamento piloto (`ox.graph_from_place` o por bbox), quedarse con la red de conducción, y asignar a cada arista el TIEMPO en minutos a partir de longitud + velocidad (de `maxspeed`/`highway`/`surface`, con fallback a `config.VELOCIDAD_KMH`). La función actual que lee `config.SHP_RED_VIAL` queda obsoleta.
  - `compute_isochrones.py` — Dijkstra multi-origen desde establecimientos resolutivos. **Falta cargar centros poblados y salud reales.**
  - `seasonal.py` — recalcula penalizando aristas vulnerables (escenario lluvias).
  - `compute_scores.py` — score de priorización por tramo (MVP: score compuesto, NO optimización combinatoria).
  - `export.py` — vuelca GeoJSON + SQLite a `backend/data/`.
  - `run_pipeline.py` — orquestador (imports comentados, hay que encadenar los pasos).
- Datos crudos esperados en `pipeline/data/raw/{centros_poblados,red_vial,salud,riesgo_inundacion}/` (shapefiles, NO versionados).

## Trabajo a completar (en orden)

### Fase A — Datos reales
1. Fijar `REGION_PILOTO` en `config.py`. Reescribir `build_graph.py` para bajar la red de OSM
   de esa región con `osmnx`, asignar TIEMPO por arista (longitud / velocidad) y devolver el grafo.
   Cachear el grafo descargado en `pipeline/data/processed/` para no re-descargar en cada corrida.
2. Verificar las capas GEO Perú de puntos: cargar centros poblados y salud con GeoPandas,
   imprimir `gdf.columns` y `gdf.crs`, y **actualizar en `config.py`** los `SHP_*` y `COL_*`.
   No adivines nombres: confírmalos contra los datos. (Las variables `SHP_RED_VIAL`/`COL_VIA_*`
   ya no aplican, puedes eliminarlas.)
3. En `compute_isochrones.py`: cargar centros poblados (orígenes) y salud (destinos), reproyectar,
   **filtrar salud por `config.CATEGORIAS_RESOLUTIVAS`** usando `config.COL_SALUD_CATEGORIA`,
   recortar puntos a la región piloto, y enganchar cada punto al nodo OSM más cercano
   (usar `ox.distance.nearest_nodes`).

### Fase B — Análisis (los 3 factores)
4. Calcular tiempo de acceso de cada CCPP al establecimiento resolutivo más cercano (factor 1) y marcar brecha (> umbral).
5. Generar escenario seco y lluvias con `seasonal.py` (factor 3). Para marcar aristas `vulnerable=True`, cruzar la red vial con `riesgo_inundacion` (intersección espacial); si esa capa no está, dejar el flag configurable y documentarlo.
6. Calcular el ranking de tramos con `compute_scores.py` (factor 2). Definir qué es un "tramo candidato" (p. ej. aristas no pavimentadas en zonas con brecha). Mantener el MVP de score compuesto.

### Fase C — Exportar y servir
7. En `export.py`/`run_pipeline.py`: producir y escribir en `backend/data/`:
   - `acceso_seco.geojson` y `acceso_lluvias.geojson` (CCPP con `nombre`, `minutos`, `en_brecha`).
   - `tramos_candidatos.geojson` (geometrías de tramos).
   - `app.db` con tablas `metricas` (por escenario) y `tramos_ranking`.
   Respeta los nombres de archivo/tablas/columnas que el backend ya espera (ver `backend/app/services/data_loader.py` y los routers).
8. Verificar la API: levantar `uvicorn app.main:app --reload` y comprobar que `/api/accesibilidad/centros-poblados`, `/api/accesibilidad/metricas`, `/api/tramos/ranking` y `/api/tramos/geometrias` devuelven los datos reales (no los `_warning` de "falta archivo").

### Fase D — Robustez y despliegue (Render)
9. Manejo de errores en endpoints (datos faltantes → respuesta clara, no 500).
10. Confirmar que `requirements.txt` del backend NO incluye geopandas/osmnx (el backend no los necesita; son solo del pipeline). Mantener el backend liviano.
11. Verificar `backend/render.yaml` (rootDir backend, start con `$PORT`) y que `backend/data/` (los GeoJSON + app.db ya generados) quede versionado para que Render lo sirva sin correr el pipeline.
12. Probar el arranque en frío como lo haría Render: `uvicorn app.main:app --host 0.0.0.0 --port 8000` desde `backend/`.

## Convenciones

- Python 3.11+. Sigue el estilo existente (funciones pequeñas, type hints, español en comentarios y nombres de dominio).
- **Todo parámetro/umbral va en `config.py`**, nunca hardcodeado en la lógica. Son los supuestos que defenderemos ante el jurado.
- No inventes datos geográficos ni cifras: todo sale de las capas reales. Si una capa falta, deja el paso parametrizado y documsenta el supuesto.
- Dos entornos virtuales independientes: uno en `pipeline/`, otro en `backend/`. No mezcles sus dependencias.
- Antes de un cambio grande, explica brevemente el plan.

## Comandos útiles

```bash
# Pipeline (genera datos) — desde pipeline/
python -m venv .venv && source .venv/bin/activate   # Win: .venv\Scripts\activate
pip install -r requirements.txt
python src/run_pipeline.py

# Backend (sirve datos) — desde backend/
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload     # http://localhost:8000/docs
```

## Definición de "terminado" (backend)

- `python src/run_pipeline.py` corre de principio a fin con las capas reales y escribe todos los archivos en `backend/data/`.
- Los 4 endpoints devuelven datos reales y coherentes en los dos escenarios.
- El backend arranca limpio con el comando de Render y `backend/data/` está versionado.
- `frontend/` quedó intacto.
