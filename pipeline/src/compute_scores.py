"""Fase B paso 6: ranking de tramos viales candidatos a inversión (score compuesto MVP).

NO es optimización combinatoria: cada tramo se evalúa de forma independiente.
SUPUESTO CONOCIDO: la preselección (etapa 2) usa las rutas de costo mínimo actuales,
por lo que puede omitir un corredor que se volvería óptimo solo después de pavimentarse.
Aceptable para el MVP; resolverlo requeriría optimización combinatoria.
"""
import time
import logging
from collections import defaultdict

import networkx as nx
import pandas as pd

from . import config
from .compute_isochrones import tiempo_a_salud, _vulnerabilidad
from .seasonal import _es_vulnerable, _primer_valor

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Etapa 1 — Tramos candidatos
# ---------------------------------------------------------------------------

def extraer_tramos_candidatos(G) -> dict:
    """Agrupa aristas vulnerables por osmid (vía OSM original).

    Retorna {osmid_str: {'edges': [(u,v,k), ...], 'longitud_m': float}}.
    Solo incluye tramos con longitud >= config.MIN_LONGITUD_TRAMO_M.
    """
    tramos: dict = defaultdict(lambda: {"edges": [], "longitud_m": 0.0})

    for u, v, k, data in G.edges(data=True, keys=True):
        if not _es_vulnerable(data):
            continue
        osmid = data.get("osmid")
        if isinstance(osmid, list):
            osmid = osmid[0]
        osmid_str = str(osmid) if osmid is not None else f"_{u}_{v}"
        tramos[osmid_str]["edges"].append((u, v, k))
        tramos[osmid_str]["longitud_m"] += float(data.get("length", 0.0))
        # Nombre del camino (primer valor si lista; solo se fija una vez)
        if "nombre" not in tramos[osmid_str]:
            name = data.get("name")
            if isinstance(name, list):
                name = name[0]
            if name:
                tramos[osmid_str]["nombre"] = str(name)

    filtered = {
        oid: info
        for oid, info in tramos.items()
        if info["longitud_m"] >= config.MIN_LONGITUD_TRAMO_M
    }
    logger.info("Tramos candidatos: %d (de %d grupos antes del filtro de longitud)",
                len(filtered), len(tramos))
    return filtered


# ---------------------------------------------------------------------------
# Etapa 2 — Acumulación de demanda por camino mínimo
# ---------------------------------------------------------------------------

def _reconstruir_camino(pred: dict, source, target) -> list | None:
    """Reconstruye la lista de nodos [source, ..., target] desde el dict de predecesores."""
    path = []
    current = target
    while current != source:
        path.append(current)
        preds = pred.get(current)
        if not preds:
            return None  # nodo desconectado
        current = preds[0]
    path.append(source)
    return list(reversed(path))


def _mejor_key(G, u, v) -> int | None:
    """Devuelve la key de la arista (u,v) con menor tiempo_min en un MultiDiGraph."""
    if not G.has_edge(u, v):
        return None
    return min(G[u][v], key=lambda k: float(G[u][v][k].get("tiempo_min", float("inf"))))


def acumular_demanda(G, nodos_salud: list, ccpp_brecha: pd.DataFrame,
                     tramos: dict) -> dict:
    """Etapa 2: suma la vulnerabilidad de cada CCPP en brecha a los tramos de su ruta.

    Dirección del árbol: super_origen (hospitals) -> CCPP, es decir, los caminos se
    recorren en sentido hospital -> CCPP (dirección OSM hacia la comunidad). Para la
    atribución de demanda por osmid no importa la dirección; se anota para claridad.

    SUPUESTO: solo se ven las rutas actuales de costo mínimo. Un corredor que solo
    aparecería como óptimo tras mejorarse no es capturado en esta etapa.
    """
    super_origen = "__SALUD_DEMANDA__"
    G_temp = G.copy()
    for n in nodos_salud:
        if n in G_temp:
            G_temp.add_edge(super_origen, n, tiempo_min=0.0)

    logger.info("Construyendo árbol de predecesores (Dijkstra multi-origen)...")
    pred, _ = nx.dijkstra_predecessor_and_distance(
        G_temp, super_origen, weight="tiempo_min"
    )
    G_temp.remove_node(super_origen)

    # osmid de cada arista del grafo (caché para no recalcular en cada ruta)
    osmid_por_arista: dict = {}
    for u, v, k, data in G.edges(data=True, keys=True):
        osmid = data.get("osmid")
        if isinstance(osmid, list):
            osmid = osmid[0]
        osmid_por_arista[(u, v, k)] = str(osmid) if osmid is not None else f"_{u}_{v}"

    demanda: dict = defaultdict(float)
    ccpp_por_tramo: dict = defaultdict(int)

    for _, row in ccpp_brecha.iterrows():
        nodo_ccpp = row["nodo_osm"]
        vuln = float(row.get("vulnerabilidad", 1.0))

        camino = _reconstruir_camino(pred, super_origen, nodo_ccpp)
        if camino is None:
            continue

        for u, v in zip(camino[:-1], camino[1:]):
            if u == super_origen:
                continue  # saltar arista virtual
            k = _mejor_key(G, u, v)
            if k is None:
                continue
            oid = osmid_por_arista.get((u, v, k))
            if oid and oid in tramos:
                demanda[oid] += vuln
                ccpp_por_tramo[oid] += 1

    # Enriquecer tramos con demanda
    for oid in tramos:
        tramos[oid]["demanda"]          = demanda.get(oid, 0.0)
        tramos[oid]["ccpp_en_ruta"]     = ccpp_por_tramo.get(oid, 0)

    return tramos


# ---------------------------------------------------------------------------
# Etapa 3 — Simulación precisa del top N
# ---------------------------------------------------------------------------

def _tiempo_pavimentado(length_m: float) -> float:
    vel = config.VELOCIDAD_KMH["pavimentada"]
    return (length_m / 1000.0) / vel * 60.0


def simular_mejora(G, top_tramos: list, df_seco: pd.DataFrame,
                   nodos_salud: list, df_lluvias: pd.DataFrame | None = None) -> list:
    """Etapa 3: para cada corredor del top, simula pavimentación y mide impacto real.

    Devuelve lista de dicts con resultados por corredor, ordenada por pob_vulnerable_gana desc.
    """
    ccpp_brecha = df_seco[df_seco["en_brecha"]].copy()
    col_nom = config.COL_CCPP_NOMBRE
    col_pob = config.COL_CCPP_POBLACION

    # Mapa nodo_osm -> row para consultas rápidas
    ccpp_lluvias_brecha: set = set()
    if df_lluvias is not None and "en_brecha_lluvias" in df_lluvias.columns:
        ccpp_lluvias_brecha = set(
            df_lluvias.loc[df_lluvias["en_brecha_lluvias"], "nodo_osm"].tolist()
        )

    resultados = []

    for osmid, info in top_tramos:
        G_sim = G.copy()
        for u, v, k in info["edges"]:
            if G_sim.has_edge(u, v, k):
                length_m = float(G_sim[u][v][k].get("length", 0.0))
                G_sim[u][v][k]["tiempo_min"] = _tiempo_pavimentado(length_m)

        distancias_sim = tiempo_a_salud(G_sim, nodos_salud)

        ccpp_ganan = []
        for _, row in ccpp_brecha.iterrows():
            nodo = row["nodo_osm"]
            t_nuevo = distancias_sim.get(nodo, float("inf"))
            if t_nuevo <= config.UMBRAL_ACCESO_MIN:
                ccpp_ganan.append(row)

        pob_total_gana   = sum(int(r[col_pob]) for r in ccpp_ganan)
        pob_vuln_gana    = sum(float(r["vulnerabilidad"]) for r in ccpp_ganan)
        n_en_brecha_ll   = sum(1 for r in ccpp_ganan if r["nodo_osm"] in ccpp_lluvias_brecha)

        # Métrica principal: minutos ponderados ahorrados para CCPP en brecha.
        # NOTE: cruzar el umbral (pob_vuln_gana) puede ser 0 si el ahorro individual
        # no basta para bajar de 120 min — el acceso es sistémico, no de un solo tramo.
        # Los minutos ponderados capturan el impacto real independientemente del umbral.
        min_ponderados = 0.0
        ccpp_con_ahorro = 0
        pob_con_ahorro  = 0
        for _, row in ccpp_brecha.iterrows():
            nodo   = row["nodo_osm"]
            t_orig = float(row["tiempo_min"])
            t_new  = distancias_sim.get(nodo, float("inf"))
            ahorro = max(0.0, t_orig - t_new)
            if ahorro > 0.001:
                min_ponderados += ahorro * float(row["vulnerabilidad"])
                ccpp_con_ahorro += 1
                pob_con_ahorro  += int(row[col_pob])

        resultados.append({
            "osmid":                    osmid,
            "nombre":                   info.get("nombre", f"Corredor {osmid}"),
            "longitud_km":              info["longitud_m"] / 1000.0,
            "demanda":                  info["demanda"],
            "edges":                    info["edges"],      # para exportar en Fase C
            "ccpp_en_ruta":             info["ccpp_en_ruta"],
            "ccpp_con_ahorro":          ccpp_con_ahorro,
            "min_ponderados_ahorrados": min_ponderados,
            "pob_beneficiada":          pob_con_ahorro,    # pob de CCPP con ahorro > 0
            "ccpp_ganan_acceso":        len(ccpp_ganan),   # cruzan umbral (puede ser 0)
            "pob_total_gana":           pob_total_gana,
            "pob_vulnerable_gana":      pob_vuln_gana,
            "n_tambien_brecha_ll":      n_en_brecha_ll,
            "nombres_ccpp":             [r[col_nom] for r in ccpp_ganan],
        })

    # Orden principal: minutos ponderados ahorrados; desempate por pob_vulnerable
    resultados.sort(
        key=lambda x: (x["min_ponderados_ahorrados"], x["pob_vulnerable_gana"]),
        reverse=True,
    )
    return resultados


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------

def calcular_ranking(G, df_seco: pd.DataFrame, salud_eng: pd.DataFrame,
                     df_lluvias: pd.DataFrame | None = None):
    """Orquesta las 3 etapas y devuelve (ranking, n_candidatos, t_total_s)."""
    t0 = time.time()

    nodos_salud = salud_eng["nodo_osm"].tolist()
    ccpp_brecha = df_seco[df_seco["en_brecha"]].copy()

    logger.info("Etapa 1: extrayendo tramos candidatos...")
    tramos = extraer_tramos_candidatos(G)
    n_candidatos = len(tramos)

    logger.info("Etapa 2: acumulando demanda en %d CCPP en brecha...", len(ccpp_brecha))
    tramos = acumular_demanda(G, nodos_salud, ccpp_brecha, tramos)

    top_items = sorted(tramos.items(), key=lambda x: x[1]["demanda"], reverse=True)
    top_items = top_items[: config.TOP_CORREDORES]
    logger.info("Etapa 3: simulando %d corredores preseleccionados...", len(top_items))

    ranking = simular_mejora(G, top_items, df_seco, nodos_salud, df_lluvias)

    t_total = time.time() - t0
    return ranking, n_candidatos, t_total


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

def checkpoint_ranking(ranking: list, n_candidatos: int, t_total: float) -> None:
    """Imprime el top 10 del ranking.

    Métrica principal: min_ponderados_ahorrados — minutos de viaje evitados en total
    para CCPP en brecha, ponderados por vulnerabilidad. Refleja impacto real sin
    depender de cruzar el umbral (que requeriría mejora sistémica, no un solo tramo).
    """
    tiene_lluvias = any(r["n_tambien_brecha_ll"] > 0 for r in ranking)
    n_cruzan = sum(r["ccpp_ganan_acceso"] for r in ranking[:10])

    print("\n========== CHECKPOINT: RANKING DE TRAMOS ==========")
    print(f"Candidatos totales evaluados : {n_candidatos:,}")
    print(f"Simulados (top {config.TOP_CORREDORES})           : {min(len(ranking), config.TOP_CORREDORES)}")
    print(f"Tiempo total de computo      : {t_total:.1f} s")
    if n_cruzan == 0:
        print("NOTA: ninguna mejora individual baja un CCPP bajo el umbral de 120 min.")
        print("      El acceso es sistemico. Metrica: minutos ponderados ahorrados.")
    print()

    header = (f"{'#':<3} {'osmid':<14} {'km':>5} {'CCPP_ahorro':>11} "
              f"{'min*vuln':>10} {'cruzan_120':>10}")
    if tiene_lluvias:
        header += f" {'tb_lluvia':>9}"
    print(header)
    print("-" * len(header))

    for i, r in enumerate(ranking[:10], 1):
        line = (
            f"{i:<3} {str(r['osmid'])[:14]:<14} "
            f"{r['longitud_km']:>5.1f} "
            f"{r['ccpp_con_ahorro']:>11} "
            f"{r['min_ponderados_ahorrados']:>10,.0f} "
            f"{r['ccpp_ganan_acceso']:>10}"
        )
        if tiene_lluvias:
            line += f" {r['n_tambien_brecha_ll']:>9}"
        print(line)
        # CCPP cuya ruta pasa por este corredor (en brecha)
        print(f"    en ruta: {r['ccpp_en_ruta']} CCPP en brecha  "
              f"demanda acumulada: {r['demanda']:,.0f}")

    print("====================================================")


# ---------------------------------------------------------------------------
# __main__
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from .build_graph import get_or_build_graph
    from .cargar_puntos import cargar_ccpp, cargar_salud, enganchar_al_grafo
    from .compute_isochrones import calcular_acceso_seco
    from .seasonal import penalizar_aristas, calcular_acceso_lluvias

    print("Cargando grafo y datos...")
    G = get_or_build_graph()
    ccpp_eng  = enganchar_al_grafo(cargar_ccpp(),  G)
    salud_eng = enganchar_al_grafo(cargar_salud(), G)

    print("Calculando acceso seco...")
    df_seco, df_sin_ruta_seco = calcular_acceso_seco()

    print("Calculando acceso lluvias...")
    G_lluvia = penalizar_aristas(G)
    df_lluvias, _ = calcular_acceso_lluvias(G_lluvia, ccpp_eng, salud_eng)

    print("Calculando ranking de tramos...")
    ranking, n_cand, t = calcular_ranking(G, df_seco, salud_eng, df_lluvias)

    checkpoint_ranking(ranking, n_cand, t)