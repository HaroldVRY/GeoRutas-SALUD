"""Endpoints de establecimientos de salud resolutivos."""
from fastapi import APIRouter

from app.services.data_loader import load_geojson

router = APIRouter()


@router.get("/hospitales")
def hospitales():
    """GeoJSON de establecimientos de salud resolutivos en la región piloto."""
    return load_geojson("hospitales.geojson")
