"""Factor 1: tiempo de acceso de cada centro poblado al establecimiento RESOLUTIVO más cercano.

Estrategia: Dijkstra multi-origen desde todos los establecimientos resolutivos
(equivale a calcular, para cada nodo, el tiempo al hospital más cercano).
"""
import logging
import statistics

import networkx as nx
import pandas as pd

from . import config
from .cargar_puntos import cargar_ccpp, cargar_salud, enganchar_al_grafo

logger = logging.getLogger(__name__)


def tiempo_a_salud(G, nodos_salud: list) -> dict:
    """Devuelve {nodo_osm: minutos_al_establecimiento_resolutivo_mas_cercano}.

    Usa un super-origen virtual conectado a todos los hospitales con coste 0,
    lo que equivale a un Dijkstra multi-origen en una sola pasada.
    """
    super_origen = "__SALUD__"
    for n in nodos_salud:
        if n in G:
            # MultiDiGraph: añadir la arista virtual con el atributo correcto
            G.add_edge(super_origen, n, tiempo_min=0.0)
    distancias = nx.single_source_dijkstra_path_length(
        G, super_origen, weight="tiempo_min"
    )
    G.remove_node(super_origen)
    distancias.pop(super_origen, None)
    return distancias


def marcar_brecha(distancias: dict) -> dict:
    """Marca qué nodos superan el umbral de acceso oportuno."""
    return {n: m > config.UMBRAL_ACCESO_MIN for n, m in distancias.items()}


def _vulnerabilidad(row: pd.Series) -> float:
    """Población ponderada sin doble conteo de franjas etarias."""
    pob_0_14 = float(row.get("GR_EDAD_1", 0) or 0)
    pob_65   = float(row.get("GR_EDAD_5", 0) or 0)
    pob_tot  = float(row.get(config.COL_CCPP_POBLACION, 0) or 0)
    resto    = max(pob_tot - pob_0_14 - pob_65, 0.0)
    return (
        pob_0_14 * config.PESO_0_14
        + pob_65  * config.PESO_65_MAS
        + resto   * config.PESO_GENERAL
    )


def calcular_rutas(G, nodos_salud: list, salud_eng, df_acceso, col_brecha: str):
    """Reconstruye la trayectoria de red (hospital → CCPP) para cada CCPP en brecha.

    Usa Dijkstra con predecesores desde un super-origen virtual conectado a todos los
    hospitales con coste 0. Tras reconstruir el camino de nodos, camino[0] es el nodo
    del hospital más cercano para ese CCPP específico; se mapea a su nombre real vía
    salud_eng["NOMBRE"] (no se asume el mismo hospital para todos).

    Propiedades de cada feature: ccpp, minutos, hospital_destino.
    Geometría simplificada (tolerancia 0.0001°, ≈11 m) para reducir tamaño del GeoJSON.
    """
    import geopandas as gpd
    from shapely.geometry import LineString

    # Mapa nodo_osm → nombre del hospital (del dato real de salud_eng)
    salud_nombre_map: dict = {}
    if "NOMBRE" in salud_eng.columns:
        for _, r in salud_eng.iterrows():
            salud_nombre_map[int(r["nodo_osm"])] = str(r["NOMBRE"])

    super_origen = "__RUTAS__"
    G_temp = G.copy()
    for n in nodos_salud:
        if n in G_temp:
            G_temp.add_edge(super_origen, n, tiempo_min=0.0)

    pred, _ = nx.dijkstra_predecessor_and_distance(G_temp, super_origen, weight="tiempo_min")
    G_temp.remove_node(super_origen)

    node_coords = {n: (d["x"], d["y"]) for n, d in G.nodes(data=True)}
    ccpp_brecha = df_acceso[df_acceso[col_brecha]].copy()

    rows = []
    for _, row in ccpp_brecha.iterrows():
        nodo_ccpp = row["nodo_osm"]

        # Reconstruir camino siguiendo predecesores hacia atrás desde nodo_ccpp
        # hasta llegar al super_origen. Resultado antes de invertir:
        #   [nodo_ccpp, ..., hospital_nodo]   (super_origen excluido del path)
        path: list = []
        current = nodo_ccpp
        while current != super_origen:
            path.append(current)
            preds = pred.get(current)
            if not preds:
                path = None
                break
            current = preds[0]

        if path is None or len(path) < 2:
            continue

        path.reverse()  # ahora: [hospital_nodo, ..., nodo_ccpp]
        hospital_nodo   = path[0]   # primer nodo real = hospital más cercano para este CCPP
        hospital_nombre = salud_nombre_map.get(int(hospital_nodo), f"Nodo {hospital_nodo}")

        coords = [node_coords[n] for n in path if n in node_coords]
        if len(coords) < 2:
            continue

        geom = LineString(coords).simplify(0.0001, preserve_topology=False)

        rows.append({
            "ccpp":             str(row.get(config.COL_CCPP_NOMBRE, "")),
            "minutos":          round(float(row["tiempo_min"]), 1),
            "hospital_destino": hospital_nombre,
            "geometry":         geom,
        })

    logger.info("Rutas reconstruidas: %d / %d CCPP en brecha (%s)",
                len(rows), len(ccpp_brecha), col_brecha)
    return gpd.GeoDataFrame(rows, crs=config.CRS_WGS84)


def calcular_acceso_seco():
    """Calcula tiempo de acceso al hospital más cercano para cada CCPP (escenario seco).

    Devuelve (df_acceso, df_sin_ruta):
      - df_acceso: CCPP con ruta, columnas tiempo_min, en_brecha, vulnerabilidad
      - df_sin_ruta: CCPP cuyo nodo OSM queda en componente desconectada del grafo
    """
    from .build_graph import get_or_build_graph

    logger.info("Cargando grafo desde cache...")
    G = get_or_build_graph()

    logger.info("Cargando y enganchando capas de puntos...")
    ccpp  = enganchar_al_grafo(cargar_ccpp(),  G)
    salud = enganchar_al_grafo(cargar_salud(), G)

    nodos_salud = salud["nodo_osm"].tolist()
    logger.info("Ejecutando Dijkstra multi-origen desde %d hospitales...", len(nodos_salud))
    distancias = tiempo_a_salud(G, nodos_salud)

    # Unir tiempos al DataFrame de CCPP
    ccpp["tiempo_min"] = ccpp["nodo_osm"].map(distancias)

    # Separar CCPP sin ruta (nodo en componente desconectada)
    sin_ruta  = ccpp[ccpp["tiempo_min"].isna()].copy()
    df_acceso = ccpp[ccpp["tiempo_min"].notna()].copy()

    if len(sin_ruta):
        logger.warning("%d CCPP sin ruta al grafo principal (componente desconectada).",
                       len(sin_ruta))

    # Marcar brecha y calcular vulnerabilidad
    df_acceso["en_brecha"]     = df_acceso["tiempo_min"] > config.UMBRAL_ACCESO_MIN
    df_acceso["vulnerabilidad"] = df_acceso.apply(_vulnerabilidad, axis=1)

    return df_acceso, sin_ruta


def checkpoint_acceso(df: pd.DataFrame, df_sin_ruta: pd.DataFrame) -> None:
    """Imprime resumen del escenario seco para validar antes de exportar."""
    n_total   = len(df) + len(df_sin_ruta)
    n_ruta    = len(df)
    n_sin     = len(df_sin_ruta)
    n_brecha  = int(df["en_brecha"].sum())
    pct_brecha = 100 * n_brecha / n_ruta if n_ruta else 0

    pob_total_brecha = df.loc[df["en_brecha"], config.COL_CCPP_POBLACION].sum()
    vuln_brecha      = df.loc[df["en_brecha"], "vulnerabilidad"].sum()

    tiempos = df["tiempo_min"].tolist()
    t_sorted = sorted(tiempos)
    p95 = t_sorted[int(len(t_sorted) * 0.95)]

    top5 = (
        df.nlargest(5, "tiempo_min")
        [[config.COL_CCPP_NOMBRE, "tiempo_min"]]
        .values.tolist()
    )

    print("\n========== CHECKPOINT: ESCENARIO SECO ==========")
    print(f"CCPP totales          : {n_total}")
    print(f"  con ruta al grafo   : {n_ruta}")
    print(f"  sin ruta (aislados) : {n_sin}")
    if n_sin:
        nombres_sin = df_sin_ruta[config.COL_CCPP_NOMBRE].tolist()
        print(f"    -> {nombres_sin}")
    print()
    print(f"En brecha (> {config.UMBRAL_ACCESO_MIN} min): {n_brecha} / {n_ruta}  ({pct_brecha:.1f}%)")
    print(f"Poblacion total en brecha     : {int(pob_total_brecha):,}")
    print(f"Poblacion vulnerable en brecha: {int(vuln_brecha):,}")
    print()
    print(f"Tiempo de acceso (min):")
    print(f"  min={min(tiempos):.1f}  media={statistics.mean(tiempos):.1f}"
          f"  p95={p95:.1f}  max={max(tiempos):.1f}")
    print()
    print("Top 5 CCPP mas alejados:")
    for nombre, mins in top5:
        print(f"  {nombre:<35} {mins:.1f} min")
    print("=================================================")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    df_acceso, df_sin_ruta = calcular_acceso_seco()
    checkpoint_acceso(df_acceso, df_sin_ruta)