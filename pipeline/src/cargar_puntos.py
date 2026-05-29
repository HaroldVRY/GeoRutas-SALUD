"""Carga, filtra y engancha al grafo OSM las capas de puntos de GEO Perú."""
import logging
import statistics

import geopandas as gpd
import osmnx as ox
from shapely.geometry import Point

from . import config

logger = logging.getLogger(__name__)

# Columnas a retener de cada capa (geometry se añade siempre)
_CCPP_COLS  = [config.COL_CCPP_NOMBRE, config.COL_CCPP_POBLACION, "GR_EDAD_1", "GR_EDAD_5"]
_SALUD_COLS = ["NOMBRE", config.COL_SALUD_CATEGORIA]

UMBRAL_ALERTA_M = 2_000  # puntos a más de 2 km de cualquier vía son sospechosos


def cargar_ccpp() -> gpd.GeoDataFrame:
    """Carga centros poblados filtrados al departamento piloto."""
    gdf = gpd.read_file(config.SHP_CENTROS_POBLADOS)
    gdf = gdf[gdf[config.COL_CCPP_DPTO] == config.NOM_DPTO_PILOTO].copy()
    cols = [c for c in _CCPP_COLS if c in gdf.columns] + ["geometry"]
    gdf = gdf[cols].reset_index(drop=True)
    logger.info("CCPP cargados: %d puntos en %s", len(gdf), config.NOM_DPTO_PILOTO)
    return gdf


def cargar_salud() -> gpd.GeoDataFrame:
    """Carga establecimientos resolutivos filtrados al departamento piloto.

    Descarta registros con categoría inválida ('0') antes de filtrar.
    """
    gdf = gpd.read_file(config.SHP_SALUD)
    gdf = gdf[gdf[config.COL_SALUD_CATEGORIA] != config.CATEGORIA_INVALIDA]
    gdf = gdf[gdf[config.COL_SALUD_CATEGORIA].isin(config.CATEGORIAS_RESOLUTIVAS)]
    gdf = gdf[gdf[config.COL_SALUD_DPTO] == config.NOM_SALUD_DPTO_PILOTO].copy()
    cols = [c for c in _SALUD_COLS if c in gdf.columns] + ["geometry"]
    gdf = gdf[cols].reset_index(drop=True)
    logger.info("Hospitales resolutivos cargados: %d en %s", len(gdf), config.NOM_SALUD_DPTO_PILOTO)
    return gdf


def enganchar_al_grafo(gdf: gpd.GeoDataFrame, G) -> gpd.GeoDataFrame:
    """Añade `nodo_osm` y `dist_enganche_m` a cada fila.

    `ox.nearest_nodes` requiere coordenadas en WGS84 (lon/lat).
    La distancia de enganche se calcula reproyectando a CRS métrico.
    """
    gdf = gdf.copy()

    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(config.CRS_WGS84)

    nodos = ox.nearest_nodes(G, X=gdf.geometry.x.to_numpy(), Y=gdf.geometry.y.to_numpy())
    gdf["nodo_osm"] = nodos

    # Geometrías de los nodos enganchados para medir la distancia de snap
    node_attrs = dict(G.nodes(data=True))
    geoms_nodo = [Point(node_attrs[n]["x"], node_attrs[n]["y"]) for n in nodos]
    gdf_nodos = gpd.GeoDataFrame(geometry=geoms_nodo, crs=config.CRS_WGS84)

    # Distancia en metros
    gdf_m     = gdf.to_crs(config.CRS_METRICO)
    nodos_m   = gdf_nodos.to_crs(config.CRS_METRICO)
    gdf["dist_enganche_m"] = gdf_m.geometry.distance(nodos_m.geometry).to_numpy()

    return gdf


def sanity_check_enganche(nombre: str, gdf: gpd.GeoDataFrame) -> None:
    """Imprime estadísticas de distancia de enganche para detectar problemas."""
    dists = sorted(gdf["dist_enganche_m"].dropna().tolist())
    n = len(dists)
    if n == 0:
        print(f"\n[{nombre}] Sin datos de distancia de enganche.")
        return

    p95 = dists[int(n * 0.95)]
    n_alertas = sum(1 for d in dists if d > UMBRAL_ALERTA_M)

    print(f"\n--- Sanity check: {nombre} ({n} puntos) ---")
    print(f"  Nodos OSM únicos enganchados : {gdf['nodo_osm'].nunique()}")
    print(f"  dist_enganche_m  "
          f"min={min(dists):.0f}  "
          f"media={statistics.mean(dists):.0f}  "
          f"p95={p95:.0f}  "
          f"max={max(dists):.0f}")
    print(f"  Puntos a > {UMBRAL_ALERTA_M} m de cualquier vía OSM: "
          f"{n_alertas} ({100 * n_alertas / n:.1f}%)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from .build_graph import get_or_build_graph

    print("Cargando grafo desde caché...")
    G = get_or_build_graph()

    print("\nCargando centros poblados...")
    ccpp = cargar_ccpp()
    print(f"  -> {len(ccpp)} CCPP en Huancavelica")

    print("\nCargando establecimientos de salud resolutivos...")
    salud = cargar_salud()
    print(f"  -> {len(salud)} hospitales resolutivos en Huancavelica")
    print(f"  Distribución de categorías:\n{salud[config.COL_SALUD_CATEGORIA].value_counts().to_string()}")

    print("\nEnganchando CCPP al grafo...")
    ccpp_eng = enganchar_al_grafo(ccpp, G)
    sanity_check_enganche("Centros Poblados", ccpp_eng)

    print("\nEnganchando hospitales al grafo...")
    salud_eng = enganchar_al_grafo(salud, G)
    sanity_check_enganche("Establecimientos de Salud", salud_eng)

    print("\n--- Columnas de vulnerabilidad disponibles en CCPP ---")
    candidatas = ["GR_EDAD_1", "GR_EDAD_5", "P_GE_0A14", "P_GE_65YM"]
    for col in candidatas:
        if col in ccpp.columns:
            nulos = ccpp[col].isna().sum()
            print(f"  {col:<12} presente  nulos={nulos}")
        else:
            print(f"  {col:<12} AUSENTE")
    print("  (No existe columna de gestantes ni menores de 5 exactos en los datos)")