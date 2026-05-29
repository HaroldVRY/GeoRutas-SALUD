"""Vuelca resultados precalculados a backend/data/ (GeoJSON + SQLite)."""
import sqlite3
import logging

import geopandas as gpd
import osmnx as ox
import pandas as pd
from shapely.geometry import LineString
from shapely.ops import linemerge

from . import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GeoJSON helpers
# ---------------------------------------------------------------------------

def _geojson_path(filename: str):
    config.BACKEND_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return config.BACKEND_DATA_DIR / filename


def export_acceso(df: pd.DataFrame, escenario: str) -> None:
    """Exporta acceso_{escenario}.geojson con propiedades que el backend espera.

    Renombra columnas al esquema acordado: nombre, minutos, en_brecha + extras.
    """
    col_brecha = "en_brecha" if escenario == "seco" else "en_brecha_lluvias"

    cols_rename = {
        config.COL_CCPP_NOMBRE:    "nombre",
        "tiempo_min":               "minutos",
        col_brecha:                 "en_brecha",
        config.COL_CCPP_POBLACION: "pob_total",
        "vulnerabilidad":           "vulnerabilidad",
    }
    available = {k: v for k, v in cols_rename.items() if k in df.columns}
    gdf = df[list(available.keys()) + ["geometry"]].copy()
    gdf = gdf.rename(columns=available)

    gdf = gdf.to_crs(config.CRS_WGS84)
    gdf["en_brecha"] = gdf["en_brecha"].astype(bool)

    filename = f"acceso_{escenario}.geojson"
    gdf.to_file(_geojson_path(filename), driver="GeoJSON")
    logger.info("Exportado %s (%d features)", filename, len(gdf))


def export_tramos(G, ranking: list) -> None:
    """Exporta tramos_candidatos.geojson con geometrías reconstruidas desde el grafo."""
    logger.info("Construyendo GeoDataFrame de aristas para geometrias de tramos...")
    edges_gdf = ox.graph_to_gdfs(G, nodes=False)
    # Normalizar índice a MultiIndex (u, v, key)
    edges_gdf.index = pd.MultiIndex.from_tuples(
        list(edges_gdf.index), names=["u", "v", "key"]
    )

    node_coords = {n: (d["x"], d["y"]) for n, d in G.nodes(data=True)}

    rows = []
    for r in ranking:
        geoms = []
        for u, v, k in r["edges"]:
            try:
                geom = edges_gdf.loc[(u, v, k), "geometry"]
                if geom is not None and not geom.is_empty:
                    geoms.append(geom)
                    continue
            except KeyError:
                pass
            # Fallback: segmento recto desde posiciones de nodos
            if u in node_coords and v in node_coords:
                geoms.append(LineString([node_coords[u], node_coords[v]]))

        if not geoms:
            continue

        merged = linemerge(geoms)  # LineString o MultiLineString si no es contiguo

        rows.append({
            "tramo_id":    r["osmid"],
            "nombre":      r.get("nombre", f"Corredor {r['osmid']}"),
            "longitud_km": round(r["longitud_km"], 2),
            "score":       round(r["min_ponderados_ahorrados"], 1),
            "ccpp_en_ruta": r["ccpp_en_ruta"],
            "geometry":    merged,
        })

    gdf = gpd.GeoDataFrame(rows, crs=config.CRS_WGS84)
    gdf.to_file(_geojson_path("tramos_candidatos.geojson"), driver="GeoJSON")
    logger.info("Exportado tramos_candidatos.geojson (%d tramos)", len(gdf))


def export_rutas(gdf: gpd.GeoDataFrame, escenario: str) -> None:
    """Exporta rutas_{escenario}.geojson con trayectorias de red hospital→CCPP en brecha."""
    filename = f"rutas_{escenario}.geojson"
    gdf.to_file(_geojson_path(filename), driver="GeoJSON")
    logger.info("Exportado %s (%d rutas)", filename, len(gdf))


def export_hospitales(salud_eng: gpd.GeoDataFrame) -> None:
    """Exporta hospitales.geojson con los establecimientos resolutivos de la región piloto.

    Columnas de salida: nombre (de NOMBRE), categoria (de CATEGORIA).
    Confirmadas en cargar_puntos._SALUD_COLS = ["NOMBRE", config.COL_SALUD_CATEGORIA].
    """
    cols_rename = {"NOMBRE": "nombre", config.COL_SALUD_CATEGORIA: "categoria"}
    available = {k: v for k, v in cols_rename.items() if k in salud_eng.columns}
    gdf = salud_eng[list(available.keys()) + ["geometry"]].copy()
    gdf = gdf.rename(columns=available)
    gdf = gdf.to_crs(config.CRS_WGS84)
    filename = "hospitales.geojson"
    gdf.to_file(_geojson_path(filename), driver="GeoJSON")
    logger.info("Exportado %s (%d establecimientos)", filename, len(gdf))


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

def _metricas_row(escenario: str, df: pd.DataFrame,
                  df_sin_ruta: pd.DataFrame) -> dict:
    col_brecha = "en_brecha" if escenario == "seco" else "en_brecha_lluvias"
    col_pob    = config.COL_CCPP_POBLACION

    pob_desatendida = int(df.loc[df[col_brecha], col_pob].sum())
    tiempo_medio    = round(float(df["tiempo_min"].mean()), 1)
    ccpp_aislados   = len(df_sin_ruta)

    return {
        "escenario":             escenario,
        "poblacion_desatendida": pob_desatendida,
        "tiempo_medio_min":      tiempo_medio,
        "ccpp_aislados":         ccpp_aislados,
    }


def export_sqlite(df_seco: pd.DataFrame, df_sin_ruta_seco: pd.DataFrame,
                  df_lluvias: pd.DataFrame, df_sin_ruta_lluvias: pd.DataFrame,
                  ranking: list) -> None:
    """Escribe app.db con tablas metricas y tramos_ranking."""
    db_path = config.BACKEND_DATA_DIR / "app.db"
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    # --- metricas ---
    cur.execute("DROP TABLE IF EXISTS metricas")
    cur.execute("""CREATE TABLE metricas (
        escenario             TEXT,
        poblacion_desatendida  INTEGER,
        tiempo_medio_min       REAL,
        ccpp_aislados          INTEGER
    )""")
    metricas = [
        _metricas_row("seco",    df_seco,    df_sin_ruta_seco),
        _metricas_row("lluvias", df_lluvias, df_sin_ruta_lluvias),
    ]
    cur.executemany(
        "INSERT INTO metricas VALUES (:escenario,:poblacion_desatendida,"
        ":tiempo_medio_min,:ccpp_aislados)",
        metricas,
    )

    # --- tramos_ranking (7 columnas: esquema ampliado, backward compatible) ---
    cur.execute("DROP TABLE IF EXISTS tramos_ranking")
    cur.execute("""CREATE TABLE tramos_ranking (
        tramo_id        TEXT,
        nombre          TEXT,
        region          TEXT,
        score           REAL,
        pob_beneficiada  INTEGER,
        longitud_km     REAL,
        ccpp_en_ruta    INTEGER
    )""")
    tramos_rows = [
        {
            "tramo_id":        r["osmid"],
            "nombre":          r.get("nombre", f"Corredor {r['osmid']}"),
            "region":          config.NOM_DPTO_PILOTO,
            "score":           round(r["min_ponderados_ahorrados"], 2),
            "pob_beneficiada": r["pob_beneficiada"],
            "longitud_km":     round(r["longitud_km"], 2),
            "ccpp_en_ruta":    r["ccpp_en_ruta"],
        }
        for r in ranking
    ]
    cur.executemany(
        "INSERT INTO tramos_ranking VALUES "
        "(:tramo_id,:nombre,:region,:score,:pob_beneficiada,:longitud_km,:ccpp_en_ruta)",
        tramos_rows,
    )

    conn.commit()
    conn.close()
    logger.info("app.db: %d metricas, %d tramos", len(metricas), len(tramos_rows))
