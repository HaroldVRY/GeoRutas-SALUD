"""Orquesta el pipeline completo de precálculo.

Ejecutar desde pipeline/:
    python -m src.run_pipeline
"""
import logging
import time

from . import config
from .build_graph import get_or_build_graph
from .cargar_puntos import cargar_ccpp, cargar_salud, enganchar_al_grafo
from .compute_isochrones import tiempo_a_salud, _vulnerabilidad
from .seasonal import penalizar_aristas
from .compute_scores import calcular_ranking
from .export import export_acceso, export_tramos, export_sqlite

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    t_total = time.time()

    # ------------------------------------------------------------------
    # [1/6] Grafo OSM + puntos enganchados
    # ------------------------------------------------------------------
    print("[1/6] Grafo OSM y carga de puntos...")
    G = get_or_build_graph()
    ccpp_eng  = enganchar_al_grafo(cargar_ccpp(),  G)
    salud_eng = enganchar_al_grafo(cargar_salud(), G)
    nodos_salud = salud_eng["nodo_osm"].tolist()
    print(f"      {G.number_of_nodes():,} nodos | "
          f"{len(ccpp_eng)} CCPP | {len(salud_eng)} hospitales resolutivos")

    # ------------------------------------------------------------------
    # [2/6] Acceso seco
    # ------------------------------------------------------------------
    print("[2/6] Calculando acceso seco...")
    dist_seco = tiempo_a_salud(G, nodos_salud)

    df_seco = ccpp_eng.copy()
    df_seco["tiempo_min"]    = df_seco["nodo_osm"].map(dist_seco)
    df_sin_ruta_seco         = df_seco[df_seco["tiempo_min"].isna()].copy()
    df_seco                  = df_seco[df_seco["tiempo_min"].notna()].copy()
    df_seco["en_brecha"]     = df_seco["tiempo_min"] > config.UMBRAL_ACCESO_MIN
    df_seco["vulnerabilidad"] = df_seco.apply(_vulnerabilidad, axis=1)

    n_brecha_seco = int(df_seco["en_brecha"].sum())
    print(f"      En brecha (seco): {n_brecha_seco}/{len(df_seco)} CCPP"
          f" | sin ruta: {len(df_sin_ruta_seco)}")

    # ------------------------------------------------------------------
    # [3/6] Acceso lluvias
    # ------------------------------------------------------------------
    print("[3/6] Calculando acceso lluvias...")
    G_lluvia  = penalizar_aristas(G)
    dist_lluv = tiempo_a_salud(G_lluvia, nodos_salud)

    df_lluvias = ccpp_eng.copy()
    df_lluvias["tiempo_min"]         = df_lluvias["nodo_osm"].map(dist_lluv)
    df_sin_ruta_lluvias              = df_lluvias[df_lluvias["tiempo_min"].isna()].copy()
    df_lluvias                       = df_lluvias[df_lluvias["tiempo_min"].notna()].copy()
    df_lluvias["en_brecha_lluvias"]  = df_lluvias["tiempo_min"] > config.UMBRAL_ACCESO_MIN
    df_lluvias["vulnerabilidad"]     = df_lluvias.apply(_vulnerabilidad, axis=1)

    n_brecha_lluv = int(df_lluvias["en_brecha_lluvias"].sum())
    print(f"      En brecha (lluvias): {n_brecha_lluv}/{len(df_lluvias)} CCPP"
          f" | sin ruta: {len(df_sin_ruta_lluvias)}")

    # ------------------------------------------------------------------
    # [4/6] Ranking de tramos
    # ------------------------------------------------------------------
    print("[4/6] Calculando ranking de tramos...")
    ranking, n_cand, t_scores = calcular_ranking(G, df_seco, salud_eng, df_lluvias)
    print(f"      {n_cand:,} candidatos | top {len(ranking)} simulados | {t_scores:.1f} s")
    print(f"      Corredor #1: {ranking[0]['nombre']} "
          f"({ranking[0]['longitud_km']:.1f} km, score={ranking[0]['min_ponderados_ahorrados']:.0f})")

    # ------------------------------------------------------------------
    # [5/6] Exportar a backend/data/
    # ------------------------------------------------------------------
    print("[5/6] Exportando a backend/data/...")
    export_acceso(df_seco,    "seco")
    export_acceso(df_lluvias, "lluvias")
    export_tramos(G, ranking)
    export_sqlite(df_seco, df_sin_ruta_seco, df_lluvias, df_sin_ruta_lluvias, ranking)

    # ------------------------------------------------------------------
    # [6/6] Verificacion
    # ------------------------------------------------------------------
    print("[6/6] Verificando archivos en backend/data/...")
    esperados = ["acceso_seco.geojson", "acceso_lluvias.geojson",
                 "tramos_candidatos.geojson", "app.db"]
    for fname in esperados:
        p = config.BACKEND_DATA_DIR / fname
        status = f"{p.stat().st_size:,} bytes" if p.exists() else "FALTA"
        print(f"      {fname:<30} {status}")

    print(f"\nPipeline completado en {time.time() - t_total:.1f} s")


if __name__ == "__main__":
    main()
