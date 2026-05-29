"""Endpoints del ranking de tramos viales a priorizar (factor 4)."""
from fastapi import APIRouter, Query

from app.services.data_loader import load_geojson, get_ranking

router = APIRouter()


@router.get("/ranking")
def ranking(limite: int = Query(20, ge=1, le=200)):
    """Ranking de tramos por impacto estimado (población vulnerable que ganaría acceso)."""
    return get_ranking(limite)


@router.get("/geometrias")
def geometrias():
    """GeoJSON con las geometrías de los tramos candidatos para dibujar en el mapa."""
    return load_geojson("tramos_candidatos.geojson")
