"""Factor 3: escenario de lluvias. Penaliza tramos vulnerables y recalcula acceso.

El escenario de lluvias usa la jerarquía vial OSM (`highway`) como proxy de
vulnerabilidad ante precipitaciones (ver config.HIGHWAY_VULNERABLES). Esto es
un supuesto válido para el MVP, dado que las capas oficiales de peligro por
inundación/huaicos no estuvieron disponibles para descarga al momento del
desarrollo (GEO Perú capas 1184/1186 no disponibles; CENEPRED/INGEMMET/ANA
no verificados por tiempo). La integración de dichas capas queda como mejora
futura: permitiría marcar tramos intransitables (eliminación del arco) además
de la penalización de velocidad ya implementada.
"""
import logging

import osmnx as ox
import pandas as pd

from . import config
from .cargar_puntos import cargar_ccpp, cargar_salud, enganchar_al_grafo
from .compute_isochrones import tiempo_a_salud, marcar_brecha, _vulnerabilidad

logger = logging.getLogger(__name__)


def _primer_valor(raw) -> str:
    """Extrae el primer valor de un atributo OSM que puede ser escalar, lista real
    o lista serializada como string (p. ej. "['residential', 'unclassified']")."""
    if isinstance(raw, list):
        return str(raw[0]).lower()
    s = str(raw)
    if s.startswith("["):
        import ast
        try:
            parsed = ast.literal_eval(s)
            if isinstance(parsed, list) and parsed:
                return str(parsed[0]).lower()
        except (ValueError, SyntaxError):
            pass
    return s.lower()


def _es_vulnerable(edge_data: dict) -> bool:
    """True si la arista degrada por lluvia según surface u highway."""
    surface = _primer_valor(edge_data.get("surface", ""))
    highway = _primer_valor(edge_data.get("highway", ""))
    return (
        surface in config.SUPERFICIES_VULNERABLES
        or highway in config.HIGHWAY_VULNERABLES
    )


def _marcar_inundados(G_lluvia) -> set:
    """Elimina del grafo las aristas vulnerables que caen en zona de inundación.

    Si SHP_RIESGO_INUND no existe, no hace nada y lo registra.
    Devuelve el conjunto de aristas (u, v, key) eliminadas.
    """
    if not config.SHP_RIESGO_INUND.exists():
        logger.warning(
            "Capa de riesgo de inundacion no encontrada (%s). "
            "Se omite la eliminacion de aristas inundadas. "
            "MEJORA FUTURA: incluir esta capa para marcar tramos intransitables en lluvias.",
            config.SHP_RIESGO_INUND,
        )
        return set()

    import geopandas as gpd

    logger.info("Cargando capa de riesgo de inundacion...")
    riesgo = gpd.read_file(config.SHP_RIESGO_INUND).to_crs(config.CRS_WGS84)

    logger.info("Cruzando aristas vulnerables con zonas de inundacion...")
    edges_gdf = ox.graph_to_gdfs(G_lluvia, nodes=False)
    # solo considerar aristas ya marcadas vulnerables
    vuln_mask = edges_gdf.apply(lambda r: _es_vulnerable(r.to_dict()), axis=1)
    edges_vuln = edges_gdf[vuln_mask]

    # intersección espacial
    inundadas = edges_vuln.sjoin(riesgo[["geometry"]], how="inner", predicate="intersects")
    keys_inundadas = set(inundadas.index)  # índice es (u, v, key)

    eliminadas = set()
    for u, v, key in keys_inundadas:
        if G_lluvia.has_edge(u, v, key):
            G_lluvia.remove_edge(u, v, key)
            eliminadas.add((u, v, key))

    logger.info("%d aristas inundadas eliminadas del grafo.", len(eliminadas))
    return eliminadas


def penalizar_aristas(G):
    """Devuelve una copia del grafo con tiempo_min aumentado en aristas vulnerables.

    Las aristas vulnerables pasan al FACTOR_LLUVIA_VULNERABLE de su velocidad original
    (tiempo_min se divide por el factor → aumenta inversamente).
    Si existe SHP_RIESGO_INUND, las aristas inundadas se eliminan (intransitables).
    """
    G_lluvia = G.copy()  # NetworkX crea nuevos dicts de atributos — seguro modificar

    n_penalizadas = 0
    for u, v, key, data in G_lluvia.edges(data=True, keys=True):
        if _es_vulnerable(data):
            t = data.get("tiempo_min", 0.0)
            data["tiempo_min"] = t / config.FACTOR_LLUVIA_VULNERABLE
            n_penalizadas += 1

    logger.info("%d aristas penalizadas por lluvia (factor=%.2f).",
                n_penalizadas, config.FACTOR_LLUVIA_VULNERABLE)

    _marcar_inundados(G_lluvia)
    return G_lluvia


def calcular_acceso_lluvias(G_lluvia, ccpp_eng: pd.DataFrame, salud_eng: pd.DataFrame):
    """Calcula acceso en escenario lluvias reutilizando puntos ya enganchados.

    Recibe el grafo penalizado y los GeoDataFrames ya enganchados del escenario seco.
    Devuelve (df_lluvias, df_sin_ruta_lluvias).
    """
    nodos_salud = salud_eng["nodo_osm"].tolist()
    logger.info("Dijkstra multi-origen (lluvias) desde %d hospitales...", len(nodos_salud))
    distancias = tiempo_a_salud(G_lluvia, nodos_salud)

    df = ccpp_eng.copy()
    df["tiempo_min"] = df["nodo_osm"].map(distancias)

    sin_ruta  = df[df["tiempo_min"].isna()].copy()
    df_lluvia = df[df["tiempo_min"].notna()].copy()

    if len(sin_ruta):
        logger.warning("%d CCPP sin ruta en escenario lluvias.", len(sin_ruta))

    df_lluvia["en_brecha_lluvias"] = df_lluvia["tiempo_min"] > config.UMBRAL_ACCESO_MIN
    df_lluvia["vulnerabilidad"]    = df_lluvia.apply(_vulnerabilidad, axis=1)

    return df_lluvia, sin_ruta


def checkpoint_comparativo(
    df_seco: pd.DataFrame,
    df_sin_ruta_seco: pd.DataFrame,
    df_lluvias: pd.DataFrame,
    df_sin_ruta_lluvias: pd.DataFrame,
) -> None:
    """Imprime comparativa seco vs. lluvias con el delta de impacto."""
    import statistics

    col_nom = config.COL_CCPP_NOMBRE
    col_pob = config.COL_CCPP_POBLACION

    n_seco_ruta    = len(df_seco)
    n_lluvias_ruta = len(df_lluvias)

    brecha_seco    = int(df_seco["en_brecha"].sum())
    brecha_lluvias = int(df_lluvias["en_brecha_lluvias"].sum())

    # CCPP que pasan de "sin brecha en seco" a "en brecha en lluvias"
    seco_sin_brecha = df_seco[~df_seco["en_brecha"]][[col_nom, "nodo_osm", col_pob,
                                                        "GR_EDAD_1", "GR_EDAD_5"]]
    lluvia_en_brecha = df_lluvias[df_lluvias["en_brecha_lluvias"]][["nodo_osm", "tiempo_min"]]
    delta = seco_sin_brecha.merge(lluvia_en_brecha, on="nodo_osm", how="inner")

    # Añadir tiempo seco al delta para comparar
    delta = delta.merge(
        df_seco[[col_nom, "nodo_osm", "tiempo_min"]].rename(
            columns={"tiempo_min": "tiempo_seco"}
        ),
        on=["nodo_osm", col_nom], how="left",
    )

    pob_delta  = int(delta[col_pob].sum())
    vuln_delta = int(delta.apply(_vulnerabilidad, axis=1).sum())

    t_ll = df_lluvias["tiempo_min"].tolist()
    t_sorted = sorted(t_ll)
    p95 = t_sorted[int(len(t_sorted) * 0.95)]

    print("\n======= CHECKPOINT: SECO vs. LLUVIAS =======")
    print(f"{'':35} {'SECO':>8}  {'LLUVIAS':>8}")
    print(f"{'CCPP con ruta':35} {n_seco_ruta:>8}  {n_lluvias_ruta:>8}")
    print(f"{'En brecha (> '+str(config.UMBRAL_ACCESO_MIN)+' min)':35} "
          f"{brecha_seco:>8}  {brecha_lluvias:>8}  "
          f"(+{brecha_lluvias - brecha_seco})")
    print(f"{'Sin ruta':35} {len(df_sin_ruta_seco):>8}  {len(df_sin_ruta_lluvias):>8}")
    print()
    print(f"Tiempo acceso (min) - lluvias:")
    print(f"  min={min(t_ll):.1f}  media={statistics.mean(t_ll):.1f}"
          f"  p95={p95:.1f}  max={max(t_ll):.1f}")
    print()
    print(f"DELTA: {len(delta)} CCPP nuevos en brecha por lluvias")
    print(f"  Poblacion total afectada    : {pob_delta:,}")
    print(f"  Poblacion vulnerable afectada: {vuln_delta:,}")
    if len(delta):
        print(f"  Detalle (t_seco -> t_lluvia):")
        for _, row in delta.sort_values("tiempo_min", ascending=False).iterrows():
            print(f"    {row[col_nom]:<35} {row['tiempo_seco']:.0f} -> {row['tiempo_min']:.0f} min")
    if len(df_sin_ruta_lluvias):
        print()
        print(f"CCPP que pierden ruta en lluvias:")
        for nom in df_sin_ruta_lluvias[col_nom].tolist():
            print(f"  - {nom}")
    print("=============================================")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from .build_graph import get_or_build_graph
    from .compute_isochrones import calcular_acceso_seco, checkpoint_acceso

    print("Cargando grafo y puntos (seco)...")
    G = get_or_build_graph()
    ccpp_eng  = enganchar_al_grafo(cargar_ccpp(),  G)
    salud_eng = enganchar_al_grafo(cargar_salud(), G)

    print("\nEscenario SECO...")
    from .compute_isochrones import tiempo_a_salud as _ts
    distancias_seco = _ts(G, salud_eng["nodo_osm"].tolist())
    df_seco = ccpp_eng.copy()
    df_seco["tiempo_min"]    = df_seco["nodo_osm"].map(distancias_seco)
    df_sin_ruta_seco         = df_seco[df_seco["tiempo_min"].isna()].copy()
    df_seco                  = df_seco[df_seco["tiempo_min"].notna()].copy()
    df_seco["en_brecha"]     = df_seco["tiempo_min"] > config.UMBRAL_ACCESO_MIN
    df_seco["vulnerabilidad"] = df_seco.apply(_vulnerabilidad, axis=1)

    print("\nPenalizando grafo para lluvias...")
    G_lluvia = penalizar_aristas(G)

    print("\nEscenario LLUVIAS...")
    df_lluvias, df_sin_ruta_lluvias = calcular_acceso_lluvias(G_lluvia, ccpp_eng, salud_eng)

    checkpoint_comparativo(df_seco, df_sin_ruta_seco, df_lluvias, df_sin_ruta_lluvias)