"""Carga ligera de resultados precalculados por el pipeline.

El backend NO calcula isócronas ni scores: solo sirve lo que `pipeline/` generó
en backend/data/. Esto mantiene la API rápida y barata en Render.
"""
import json
import sqlite3
from pathlib import Path

from fastapi import HTTPException

from app.config import settings

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_geojson(filename: str) -> dict:
    path = DATA_DIR / filename
    if not path.exists():
        return {"type": "FeatureCollection", "features": [], "_warning": f"falta {filename}"}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=503, detail=f"Error leyendo {filename}: {exc}")


def _connect() -> sqlite3.Connection:
    db_path = DATA_DIR.parent / settings.database_path
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_metrics(escenario: str) -> dict:
    """Lee métricas agregadas de SQLite (tabla 'metricas')."""
    try:
        conn = _connect()
        row = conn.execute(
            "SELECT * FROM metricas WHERE escenario = ?", (escenario,)
        ).fetchone()
        conn.close()
        return dict(row) if row else {"escenario": escenario, "_warning": "sin datos"}
    except sqlite3.Error as e:
        return {"escenario": escenario, "_error": str(e)}


def get_ranking(limite: int) -> list[dict]:
    """Lee el ranking de tramos desde SQLite (tabla 'tramos_ranking')."""
    try:
        conn = _connect()
        rows = conn.execute(
            "SELECT * FROM tramos_ranking ORDER BY score DESC LIMIT ?", (limite,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        return [{"_error": str(e)}]
