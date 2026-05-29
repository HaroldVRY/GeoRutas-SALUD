# GeoRutas SALUD

Tablero de priorización de inversión vial para reducir muertes evitables por falta de acceso oportuno a salud de emergencia.

**GEOTÓN PERÚ 2026 · Categoría 3: Territorio Conectado**

Alcance del MVP: **isócronas reales sobre red vial (1) + priorización de tramos a intervenir (4) + escenario estacional seco/lluvias (2)**.

## Arquitectura

```
GeoRutas-SALUD/
├── pipeline/     # Precálculo OFFLINE (Python): grafo vial, isócronas, scores → genera datos
├── backend/      # API FastAPI que SIRVE los datos precalculados  → Render
└── frontend/     # SPA React + Vite + Leaflet                     → Netlify
```

Flujo de datos:

```
GEO Perú (capas) ─► pipeline/ (GeoPandas, NetworkX) ─► backend/data/*.geojson + app.db (SQLite)
                                                              │
                                              backend FastAPI │ expone /api/...
                                                              ▼
                                              frontend React  ◄─ fetch ─► mapa Leaflet
```

## Por qué precálculo offline

El cálculo de isócronas y scores es pesado (grafo de miles de aristas). Se corre **una vez** en `pipeline/`, se versionan los resultados ligeros, y el backend en Render solo los entrega. Así la API arranca rápido y no se cae por timeout/memoria en el plan gratuito.

## Puesta en marcha local

```bash
# 1. Pipeline (genera los datos) — solo cuando cambian los datos fuente
cd pipeline
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/run_pipeline.py            # escribe resultados en ../backend/data/

# 2. Backend
cd ../backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload         # http://localhost:8000/docs

# 3. Frontend
cd ../frontend
npm install
npm run dev                           # http://localhost:5173
```

## Despliegue

- **Backend → Render:** ver `backend/render.yaml`.
- **Frontend → Netlify:** ver `frontend/netlify.toml`. Configurar `VITE_API_URL` con la URL del backend en Render.
- **BD (opcional) → Supabase:** si se migra de SQLite a Postgres/PostGIS, ver `backend/.env.example`.

## Datos (GEO Perú)

Capas fuente se descargan en `pipeline/data/raw/` (no versionadas). Capas mínimas: red vial (MTC), establecimientos de salud con categoría (MINSA/RENIPRESS), centros poblados y población (INEI), vulnerabilidad/riesgo de inundación.
