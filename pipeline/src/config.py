"""Parámetros del análisis. Centraliza umbrales y supuestos para defenderlos en el pitch."""
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
BACKEND_DATA_DIR = Path(__file__).resolve().parents[2] / "backend" / "data"

# --- Región piloto (la red OSM nacional es inviable en el plazo) ---
REGION_PILOTO = "Huancavelica, Peru"

# Caché del grafo OSM descargado (evita re-descargar en cada corrida)
GRAFO_CACHE_PATH = PROCESSED_DIR / "grafo_huancavelica.graphml"

# Bbox de respaldo si graph_from_place falla por geocodificación (N, S, O, E)
BBOX_HUANCAVELICA = (-11.85, -14.10, -75.80, -74.35)  # (north, south, west, east)

# --- Rutas a los shapefiles de PUNTOS de GEO Perú ---
# GeoPandas lee el .shp y toma solos los .shx/.dbf/.prj que estén al lado.
SHP_CENTROS_POBLADOS = RAW_DIR / "centros_poblados" / "peru_ccpp_mayor_.shp"
# LIMITACIÓN CONOCIDA: la capa es "centros poblados mayores" (INEI 2017); puede excluir
# caseríos pequeños, que son precisamente la población más vulnerable y dispersa.
SHP_SALUD        = RAW_DIR / "salud" / "20250730114336___Hospitales_jul25.shp"
SHP_RIESGO_INUND = RAW_DIR / "riesgo_inundacion" / "riesgo_inundacion.shp"
# MEJORA FUTURA: integrar capa oficial de peligro por inundación/huaicos. Las capas
# GEO Perú 1184/1186 no estuvieron disponibles para descarga al momento del desarrollo;
# CENEPRED/INGEMMET/ANA no se verificaron por limitación de tiempo. Sin esta capa,
# seasonal.py usa el tipo de vía OSM (highway) como proxy de vulnerabilidad en lluvias.
# Con la capa real se podría marcar aristas como intransitables (no solo más lentas).
# NOTA: la red vial ya NO se lee de shapefile; el grafo se construye desde OSM (osmnx).

# --- Nombres de COLUMNAS dentro de cada .dbf (confirmados con gdf.columns) ---
# Centros poblados (peru_ccpp_mayor_.shp)
COL_CCPP_NOMBRE    = "NOM_CCPP"   # nombre del centro poblado
COL_CCPP_POBLACION = "POB_TOTAL"  # población total (campo confirmado)
COL_CCPP_DPTO      = "NOM_DPTO"   # nombre del departamento (para filtrar a región piloto)

# Salud (20250730114336___Hospitales_jul25.shp)
COL_SALUD_CATEGORIA = "CATEGORIA"   # categoría MINSA del establecimiento
COL_SALUD_DPTO      = "DEPARTAMEN"  # nombre del departamento (para filtrar a región piloto)

# Valores de departamento para filtrar ambas capas nacionales a la región piloto
NOM_DPTO_PILOTO       = "HUANCAVELICA"  # valor en COL_CCPP_DPTO
NOM_SALUD_DPTO_PILOTO = "HUANCAVELICA"  # valor en COL_SALUD_DPTO
# DECISIÓN DE DISEÑO: filtro departamental estricto (grafo y hospitales son ambos
# Huancavelica). Coherente porque el grafo OSM solo cubre el departamento; incluir
# un hospital de Ayacucho requeriría también su red vial. NOTA PARA EL PITCH: un CCPP
# en el límite departamental que aparezca como "muy aislado" podría tener un hospital
# vecino más cercano — mencionarlo como limitación acotada del MVP.

# CRS métrico para Perú (UTM 18S cubre gran parte del país; ajustar por zona si hace falta)
CRS_METRICO = "EPSG:32718"
CRS_WGS84 = "EPSG:4326"

# Umbral clínico: acceso "oportuno" en minutos
UMBRAL_ACCESO_MIN = 120

# Scoring de tramos (Fase B paso 6)
MIN_LONGITUD_TRAMO_M = 200   # descartar segmentos < 200 m (ruido OSM)
TOP_CORREDORES       = 30    # cuántos corredores pasan a simulación precisa

# Velocidades por tipo de superficie vial (km/h) -> tiempo por arista
# Claves propias usadas como fallback final y en seasonal.py
VELOCIDAD_KMH = {
    "pavimentada": 60,
    "afirmada": 35,
    "trocha": 18,
    "default": 25,
}

# Velocidades según atributo OSM `highway` (tipo de vía)
VELOCIDAD_HIGHWAY: dict[str, float] = {
    "motorway": 100,
    "trunk": 80,
    "primary": 70,
    "secondary": 60,
    "tertiary": 40,
    "unclassified": 30,
    "residential": 25,
    "service": 20,
    "track": 18,
    "path": 12,
}

# Velocidades según atributo OSM `surface` (material de la vía)
VELOCIDAD_SURFACE: dict[str, float] = {
    "asphalt": 60,
    "paved": 60,
    "concrete": 55,
    "cobblestone": 30,
    "gravel": 35,
    "unpaved": 25,
    "compacted": 35,
    "fine_gravel": 35,
    "dirt": 18,
    "earth": 18,
    "grass": 12,
    "mud": 10,
    "sand": 12,
}

# Categorías MINSA consideradas "resolutivas" para emergencia.
# Confirmadas contra los datos reales (value_counts sobre CATEGORIA):
#   II-E=221, II-1=195, II-2=80, III-1=28, III-E=11 → presentes y resolutivas
#   I-3=6, I-4=15 → atención primaria, NO resolutivas
#   "0"=11 → inválidos, descartar antes de filtrar
#   III-2=0 → no aparece en los datos; eliminada del set
CATEGORIAS_RESOLUTIVAS = {"II-1", "II-2", "II-E", "III-1", "III-E"}
# Valor centinela de categoría inválida a descartar al cargar la capa de salud
CATEGORIA_INVALIDA = "0"

# Valores OSM `surface` que degradan significativamente en temporada de lluvias.
# NOTA: el grafo descargado con network_type="drive" NO preserva el atributo `surface`
# en las aristas; este set queda para uso futuro si se re-descarga con filtro personalizado
# o se enriquece el grafo con datos de superficie por cruce espacial.
SUPERFICIES_VULNERABLES: set[str] = {
    "unpaved", "ground", "dirt", "earth", "grass",
    "mud", "sand", "gravel", "fine_gravel", "compacted",
}

# Valores OSM `highway` usados como PROXY de superficie en lluvias.
# En Huancavelica rural, `residential` y `unclassified` corresponden mayoritariamente
# a trochas y caminos sin afirmar. `track` y `path` se incluyen por completitud aunque
# el grafo `drive` los excluye. SUPUESTO DEFENSA: jerarquía vial como indicador de
# estado de superficie en ausencia de datos directos de surface.
HIGHWAY_VULNERABLES: set[str] = {"track", "path", "residential", "unclassified"}

# Multiplicador de velocidad en aristas vulnerables durante lluvias (0 < factor <= 1).
# 0.3 -> la vía queda al 30% de su velocidad normal (~3.3x más lento).
# Solo la capa de inundación (SHP_RIESGO_INUND) puede marcar aristas como intransitables.
FACTOR_LLUVIA_VULNERABLE = 0.3

# Pesos de vulnerabilidad para ponderar la demanda por CCPP.
# Columnas disponibles en los datos: GR_EDAD_1 (0-14 años) y GR_EDAD_5 (65+ años).
# No existe columna de gestantes ni menores de 5 exactos en la capa INEI 2017.
# NARRATIVA DEL PITCH: enmarcar como "acceso oportuno para niñez y adultos mayores",
# usando mortalidad materna como ejemplo del costo de la desconexión, no como métrica exacta.
#
# Fórmula sin doble conteo (POB_0_14 y POB_65 ya están dentro de POB_TOTAL):
#   vulnerabilidad = POB_0_14 * PESO_0_14
#                  + POB_65  * PESO_65_MAS
#                  + (POB_TOTAL - POB_0_14 - POB_65) * PESO_GENERAL
PESO_0_14    = 2.0   # niñez 0-14 años (GR_EDAD_1)
PESO_65_MAS  = 2.5   # adultos mayores 65+ años (GR_EDAD_5)
PESO_GENERAL = 1.0   # resto de la población
