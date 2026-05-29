"""Exploración de capas GEO Perú de puntos. Ejecutar con: python -m src.explorar_capas"""
from pathlib import Path
import geopandas as gpd

from . import config

# El shapefile de salud tiene nombre real distinto al placeholder del config
_SHP_SALUD_REAL = config.RAW_DIR / "salud" / "20250730114336___Hospitales_jul25.shp"


def explorar(nombre: str, shp_path: Path, col_categoria: str | None = None) -> None:
    print(f"\n{'='*60}")
    print(f"CAPA: {nombre}")
    print(f"Archivo: {shp_path.name}")
    print(f"{'='*60}")

    if not shp_path.exists():
        print(f"  ERROR: archivo no encontrado en {shp_path}")
        return

    gdf = gpd.read_file(shp_path)

    print(f"\nShape        : {gdf.shape}  ({gdf.shape[0]} filas, {gdf.shape[1]} columnas)")
    print(f"CRS          : {gdf.crs}")
    print(f"Geometrías   : {gdf.geom_type.unique().tolist()}")
    print(f"\nColumnas ({len(gdf.columns)}):")
    for col in gdf.columns:
        dtype = gdf[col].dtype
        n_null = gdf[col].isna().sum()
        print(f"  {col:<30} dtype={str(dtype):<10} nulos={n_null}")

    print(f"\nPrimeras 3 filas:")
    print(gdf.head(3).to_string())

    if col_categoria and col_categoria in gdf.columns:
        print(f"\nValores únicos de '{col_categoria}' (value_counts):")
        print(gdf[col_categoria].value_counts().to_string())
    elif col_categoria:
        print(f"\nADVERTENCIA: columna '{col_categoria}' no existe. Columnas disponibles: {gdf.columns.tolist()}")
        # Intentar detectar columna de categoría automáticamente
        candidatas = [c for c in gdf.columns if any(k in c.upper() for k in ("CATEG", "TIPO", "NIVEL", "CLASS"))]
        if candidatas:
            print(f"  Posibles columnas de categoría: {candidatas}")
            for c in candidatas:
                print(f"\n  value_counts de '{c}':")
                print(f"  {gdf[c].value_counts().to_string()}")


if __name__ == "__main__":
    explorar(
        "Centros Poblados",
        config.SHP_CENTROS_POBLADOS,
    )
    explorar(
        "Establecimientos de Salud",
        _SHP_SALUD_REAL,
        col_categoria=config.COL_SALUD_CATEGORIA,
    )