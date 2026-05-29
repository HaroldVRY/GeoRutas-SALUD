"""Endpoint de rutas de acceso: trayectorias de red hospital→CCPP en brecha."""
from fastapi import APIRouter, Query

from app.services.data_loader import load_geojson

router = APIRouter()


@router.get("")
def rutas(escenario: str = Query("seco", pattern="^(seco|lluvias)$")):
    """GeoJSON con la ruta de red de cada CCPP en brecha hasta su hospital más cercano."""
    return load_geojson(f"rutas_{escenario}.geojson")
