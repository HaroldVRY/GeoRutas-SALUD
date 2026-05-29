from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import accesibilidad, tramos, salud, rutas

app = FastAPI(
    title="GeoRutas SALUD API",
    description="Acceso oportuno a salud de emergencia y priorización de inversión vial.",
    version="0.1.0",
)

# FRONTEND_ORIGIN puede ser un valor único o varios separados por coma.
# Se eliminan espacios y barras finales para evitar mismatches de CORS.
_allowed_origins = [
    o.strip().rstrip("/")
    for o in settings.frontend_origin.split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    # Red de seguridad: cualquier subdominio *.netlify.app (p. ej. si cambia el nombre del sitio)
    allow_origin_regex=r"https://.*\.netlify\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accesibilidad.router, prefix="/api/accesibilidad", tags=["accesibilidad"])
app.include_router(tramos.router, prefix="/api/tramos", tags=["tramos"])
app.include_router(salud.router, prefix="/api/salud", tags=["salud"])
app.include_router(rutas.router, prefix="/api/rutas", tags=["rutas"])


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}
