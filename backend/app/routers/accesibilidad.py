"""Endpoints de accesibilidad: brecha de acceso por centro poblado y métricas."""
from fastapi import APIRouter, Query

from app.services.data_loader import load_geojson, get_metrics

router = APIRouter()


@router.get("/centros-poblados")
def centros_poblados(escenario: str = Query("seco", pattern="^(seco|lluvias)$")):
    """GeoJSON de centros poblados con su tiempo de acceso y flag de brecha.

    `escenario`: 'seco' o 'lluvias' (con tramos vulnerables penalizados).
    """
    return load_geojson(f"acceso_{escenario}.geojson")


@router.get("/metricas")
def metricas(escenario: str = Query("seco", pattern="^(seco|lluvias)$")):
    """Métricas de cabecera: población desatendida, tiempo medio, nº aislados."""
    return get_metrics(escenario)
