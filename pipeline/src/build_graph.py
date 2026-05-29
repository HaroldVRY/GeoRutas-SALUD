"""Factor 1: construye el grafo de red vial desde OSM y asigna TIEMPO de viaje a cada arista."""
import re
import logging

import osmnx as ox
from shapely.geometry import box as shapely_box

from . import config

logger = logging.getLogger(__name__)


def _velocidad_kmh(edge_data: dict) -> float:
    """Devuelve velocidad en km/h para una arista OSM.

    Prioridad: maxspeed > surface > highway > default.
    """
    # 1. maxspeed (puede ser "60", "60 mph", lista si hay varios valores)
    maxspeed = edge_data.get("maxspeed")
    if maxspeed:
        raw = maxspeed[0] if isinstance(maxspeed, list) else maxspeed
        # extrae el primer número entero del string
        match = re.search(r"\d+", str(raw))
        if match:
            kmh = float(match.group())
            # convierte millas si el tag lo indica
            if "mph" in str(raw).lower():
                kmh *= 1.609
            if 5 < kmh < 150:
                return kmh

    # 2. surface
    surface = edge_data.get("surface")
    if surface:
        raw = surface[0] if isinstance(surface, list) else surface
        vel = config.VELOCIDAD_SURFACE.get(str(raw).lower())
        if vel:
            return vel

    # 3. highway
    highway = edge_data.get("highway")
    if highway:
        raw = highway[0] if isinstance(highway, list) else highway
        vel = config.VELOCIDAD_HIGHWAY.get(str(raw).lower())
        if vel:
            return vel

    return float(config.VELOCIDAD_KMH["default"])


def _asignar_tiempos(G) -> None:
    """Añade el atributo `tiempo_min` a cada arista del grafo (in-place)."""
    for u, v, data in G.edges(data=True):
        longitud_m = data.get("length", 0.0)  # osmnx provee longitud en metros
        vel_kmh = _velocidad_kmh(data)
        data["tiempo_min"] = (longitud_m / 1000.0) / vel_kmh * 60.0


def _descargar_grafo():
    """Descarga la red vial de OSM. Intenta por nombre; fallback a polígono bbox."""
    try:
        logger.info("Descargando red OSM para '%s'...", config.REGION_PILOTO)
        G = ox.graph_from_place(config.REGION_PILOTO, network_type="drive")
        logger.info("Descarga por nombre exitosa.")
        return G
    except Exception as exc:
        logger.warning("graph_from_place falló (%s). Usando bbox de respaldo.", exc)
        north, south, west, east = config.BBOX_HUANCAVELICA
        # shapely_box(minx, miny, maxx, maxy) = (west, south, east, north)
        poly = shapely_box(west, south, east, north)
        G = ox.graph_from_polygon(poly, network_type="drive")
        logger.info("Descarga por bbox (polygon) exitosa.")
        return G


def get_or_build_graph():
    """Carga el grafo desde caché o lo descarga desde OSM y lo cachea.

    Devuelve un MultiDiGraph de osmnx con `tiempo_min` en cada arista.
    """
    cache = config.GRAFO_CACHE_PATH
    if cache.exists():
        logger.info("Cargando grafo desde caché: %s", cache)
        G = ox.load_graphml(cache)
        sample = next(iter(G.edges(data=True)), (None, None, {}))
        if "tiempo_min" not in sample[2]:
            _asignar_tiempos(G)
            ox.save_graphml(G, cache)
        else:
            # graphml serializa todo como string; reconvertir a float
            for _, _, data in G.edges(data=True):
                if "tiempo_min" in data:
                    data["tiempo_min"] = float(data["tiempo_min"])
        return G

    cache.parent.mkdir(parents=True, exist_ok=True)
    G = _descargar_grafo()
    _asignar_tiempos(G)
    ox.save_graphml(G, cache)
    logger.info("Grafo guardado en caché: %s", cache)
    return G


def verificar_grafo(G) -> None:
    """Imprime un resumen del grafo para validar que la descarga fue correcta."""
    import statistics

    tiempos = [d["tiempo_min"] for _, _, d in G.edges(data=True) if "tiempo_min" in d]

    print(f"Nodos  : {G.number_of_nodes():,}")
    print(f"Aristas: {G.number_of_edges():,}")
    if tiempos:
        tiempos_sorted = sorted(tiempos)
        n = len(tiempos_sorted)
        p95 = tiempos_sorted[int(n * 0.95)]
        print(f"tiempo_min — min={min(tiempos):.2f}  media={statistics.mean(tiempos):.2f}"
              f"  p95={p95:.2f}  max={max(tiempos):.2f}  (minutos)")
    else:
        print("ADVERTENCIA: ninguna arista tiene tiempo_min asignado.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    G = get_or_build_graph()
    verificar_grafo(G)
