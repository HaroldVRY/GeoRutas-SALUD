# CLAUDE.md — GeoRutas SALUD

> Instrucciones para Claude Code. Léelas completas antes de actuar.

## ⛔ ALCANCE — LÍMITE ESTRICTO

Trabaja en **`frontend/`**, **`backend/`** y **`pipeline/`**. Los tres directorios son editables.

**NO toques ningún archivo fuera de estos tres directorios.** Si una tarea parece requerir cambios en otro lugar, **detente y avísalo**.

## Contexto del proyecto

GeoRutas SALUD es una propuesta para la **GEOTÓN PERÚ 2026** (categoría Territorio Conectado, organiza la PCM de Perú). El problema: en el Perú rural, el tiempo de viaje al establecimiento de salud con capacidad resolutiva —no la distancia— determina quién sobrevive a una emergencia, y en temporada de lluvias muchas vías se vuelven intransitables.

El producto es un tablero de **priorización de inversión vial** para reducir muertes evitables. El alcance analítico tiene 3 factores:

1. **Isócronas reales** sobre la red vial (tiempo de viaje, no distancia en línea recta).
2. **Priorización de tramos**: ranking de qué tramos viales mejorar para que más población vulnerable gane acceso oportuno.
3. **Escenario estacional**: comparar acceso en seco vs. lluvias (tramos vulnerables penalizados).

## Fuentes de datos (DECISIÓN TOMADA — respétala)

- **Red para enrutar → OpenStreetMap (OSM) vía `osmnx`.** Región piloto: Huancavelica.
- **Centros poblados y establecimientos de salud → GEO Perú** (INEI / MINSA-RENIPRESS).
- **NO usar Google Maps API**: es de pago y sus términos prohíben almacenar/precalcular rutas.

## Arquitectura y flujo de datos

```
OSM (osmnx) ──────────────►  pipeline/ (offline, CONGELADO)  ◄──── GEO Perú
                                       │ escribe resultados
                                       ▼
                               backend/data/  (*.geojson + app.db)
                                       │
                               backend/ FastAPI (CONGELADO)
                               https://georutas-salud.onrender.com
                                       │
                               frontend/ React + Vite + Leaflet  ← TRABAJO ACTUAL
```

**Regla de oro:** el backend NO calcula nada. Solo sirve los datos precalculados por el pipeline. El frontend solo visualiza lo que el backend expone.

## Estado actual

Las Fases A–D están completas y desplegadas:

- **`pipeline/`**: genera isócronas, ranking de tramos y escenario lluvias para Huancavelica (471 CCPP, 5 hospitales resolutivos). Ejecutado offline; resultados en `backend/data/`. **Congelado.**
- **`backend/`**: FastAPI desplegado en Render (`https://georutas-salud.onrender.com`). Expone 4 endpoints con datos reales:
  - `GET /api/accesibilidad/centros-poblados?escenario=seco|lluvias` — GeoJSON de puntos
  - `GET /api/accesibilidad/metricas?escenario=seco|lluvias` — población desatendida, tiempo medio, aislados
  - `GET /api/tramos/ranking?limite=N` — top corredores por score
  - `GET /api/tramos/geometrias` — GeoJSON de líneas de corredores
  - **Congelado.**
- **`frontend/`**: React + Vite + Leaflet. Esqueleto funcional con los 4 componentes y `api.js` ya conectado a `VITE_API_URL`. **Pendiente: completar el mapa, la UI y el manejo del cold-start.**

## Trabajo a completar (Fase E — Frontend)

1. **`.env.local`**: `VITE_API_URL=https://georutas-salud.onrender.com` para apuntar al backend real.

2. **`App.jsx`**: cargar `geometriasTramos()` una sola vez (no depende del escenario). Agregar estado de carga para el cold-start de Render (~50 s): overlay "Despertando el servidor…" mientras la primera petición está en vuelo.

3. **`MapView.jsx`**: centrar en Huancavelica (`[-12.85, -74.90]`, zoom 8). Pintar CCPP (rojo = en brecha, verde = con acceso). Agregar capa de tramos (líneas azul; top 3 en rojo/gruesas). Popups con nombre y minutos.

4. **`TramoRanking.jsx`**: mostrar `longitud_km` y `score` (minutos ponderados ahorrados) además de nombre.

5. **`MetricsBar.jsx`**: formato con separador de miles en población. Texto de etiquetas más descriptivo.

6. **`styles.css`**: agregar `.loading-overlay` y `.spinner` para el cold-start.

7. Correr `npm install` y `npm run dev`. Verificar que el mapa carga datos reales desde `https://georutas-salud.onrender.com`.

## Convenciones

- JavaScript/React (no TypeScript). Componentes funcionales, hooks, español en textos de UI.
- **`VITE_API_URL` es el único parámetro de configuración.** No hardcodees URLs del backend.
- Paleta: azul institucional `#0b5394`, rojo brecha `#b03a3a`, verde acceso `#1a8a5a`. Sobria.
- Antes de un cambio grande, explica brevemente el plan.
- **No toques `backend/` ni `pipeline/`** bajo ninguna circunstancia.

## Comandos útiles

```bash
# Frontend — desde frontend/
npm install
npm run dev        # http://localhost:5173 (apunta a VITE_API_URL del .env.local)
npm run build      # build de producción para Netlify
```

## Definición de "terminado" (frontend)

- El mapa centra en Huancavelica y pinta los 471 CCPP con colores correctos en ambos escenarios.
- Las líneas de corredores se ven sobre el mapa; top 3 visualmente diferenciados.
- El conmutador seco/lluvias recarga puntos y métricas sin recargar la página.
- `MetricsBar` muestra datos reales con formato correcto.
- `TramoRanking` muestra top corredores con nombre, km y score.
- El cold-start de Render (~50 s) muestra un mensaje claro, no una pantalla en blanco.
- `backend/` y `pipeline/` quedaron intactos.
