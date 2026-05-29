from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import accesibilidad, tramos

app = FastAPI(
    title="GeoRutas SALUD API",
    description="Acceso oportuno a salud de emergencia y priorización de inversión vial.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accesibilidad.router, prefix="/api/accesibilidad", tags=["accesibilidad"])
app.include_router(tramos.router, prefix="/api/tramos", tags=["tramos"])


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}
