"""
test_apis_oficiales.py
======================
Script de verificaci?n para las APIs oficiales.
Corre cada API, muestra resultado y diagn?stico de compatibilidad.
NO modifica ni altera archivos existentes del proyecto.

Uso:
    python test_apis_oficiales.py
    python test_apis_oficiales.py --solo bora
    python test_apis_oficiales.py --solo comprar --anio 2019
    python test_apis_oficiales.py --solo tgn
    python test_apis_oficiales.py --solo cuit --cuit 30-50000427-3
    python test_apis_oficiales.py --solo sipro --nombre "TECHINT"
    python test_apis_oficiales.py --solo compat
    python test_apis_oficiales.py --solo todo
"""

import sys
import argparse
import os
import pandas as pd
from datetime import datetime

# ?? Schema esperado por diario.py (para test de compatibilidad) ????????????????
# Cada key es el nombre del DataFrame en diario.py y el valor son las columnas
# m?nimas que deben existir para que cruzar_fuentes() funcione correctamente.
SCHEMA_DIARIO = {
    "df_bora_licitaciones": [
        "fecha_extraccion", "fecha_publicacion", "organismo",
        "tipo_proceso", "aviso_id", "es_adjudicacion", "link", "fuente",
    ],
    "df_adjudicaciones": [
        "fecha_extraccion", "fecha_publicacion", "organismo_contratante",
        "tipo_proceso", "aviso_id", "link",
        "proveedor_adjudicado", "cuit_proveedor", "monto_adjudicado", "fuente",
    ],
    "df_comprar": [
        "fecha_extraccion", "nro_proceso", "nombre_proceso",
        "tipo_proceso", "unidad_ejecutora", "link", "fuente",
    ],
    "df_tgn": [
        "fecha_extraccion", "anio", "cuit", "beneficiario",
        "unidad_ejecutora", "jurisdiccion", "monto_pagado",
        "monto_devengado", "organismo_norm", "fuente",
    ],
}

SEP  = "?" * 60
SEP2 = "?" * 60


def _titulo(texto: str):
    print(f"\n{SEP}")
    print(f"  {texto}")
    print(SEP)


def _resultado(df: pd.DataFrame, columnas_muestra: list = None):
    if df is None or df.empty:
        print("  ??  Sin datos ? API no disponible o sin resultados hoy")
        return
    print(f"  ? {len(df)} registros")
    print(f"     Columnas ({len(df.columns)}): {list(df.columns)}")
    cols = columnas_muestra or df.columns[:5].tolist()
    cols = [c for c in cols if c in df.columns]
    if cols:
        print()
        print(df[cols].head(3).to_string(index=False))


def _verificar_schema(df: pd.DataFrame, schema_key: str):
    """Verifica que df tenga todas las columnas requeridas por diario.py."""
    requeridas = SCHEMA_DIARIO.get(schema_key, [])
    if not requeridas:
        return
    faltantes  = [c for c in requeridas if c not in df.columns]
    presentes  = [c for c in requeridas if c in df.columns]
    if not faltantes:
        print(f"\n  ? Schema compatible con diario.py ({schema_key})")
    else:
        print(f"\n  ? Schema parcial para {schema_key}:")
        print(f"     Presentes  : {presentes}")
        print(f"     Faltantes  : {faltantes}")
        print(f"     ? Columnas extra disponibles: "
              f"{[c for c in df.columns if c not in requeridas]}")


# ?????????????????????????????????????????????????????????????????????????????
# Tests individuales
# ?????????????????????????????????????????????????????????????????????????????

def test_bora(texto: str = None):
    from apis_oficiales import obtener_bora_normativa_api

    _titulo("1. BORA ? Normativa API (secci?n tercera, hoy)")
    df = obtener_bora_normativa_api(seccion="tercera")
    _resultado(df, ["fecha_publicacion", "organismo", "tipo_proceso",
                    "es_adjudicacion", "fuente"])

    if not df.empty:
        adj  = df["es_adjudicacion"].sum()
        lici = len(df) - adj
        print(f"\n  ? Adjudicaciones: {adj} | Licitaciones: {lici}")
        _verificar_schema(df, "df_bora_licitaciones")

    if texto:
        _titulo(f"1b. BORA ? B?squeda por texto '{texto}'")
        df2 = obtener_bora_normativa_api(seccion="tercera", texto=texto, limit=20)
        _resultado(df2, ["fecha_publicacion", "organismo", "titulo"])

    return df


def test_comprar(anio: int = 2020, organismo: str = None):
    from apis_oficiales import obtener_comprar_api

    _titulo(f"2. COMPR.AR ? Adjudicaciones {anio} (datos.gob.ar)")
    df_adj = obtener_comprar_api(anio=anio, tipo="adjudicaciones",
                                 organismo=organismo, limit=20)
    _resultado(df_adj, ["nro_proceso", "nombre_proceso", "tipo_proceso",
                        "unidad_ejecutora", "monto", "cuit_proveedor"])
    if not df_adj.empty:
        _verificar_schema(df_adj, "df_comprar")

    _titulo(f"2b. COMPR.AR ? Convocatorias {anio}")
    df_conv = obtener_comprar_api(anio=anio, tipo="convocatorias", limit=10)
    _resultado(df_conv, ["nro_proceso", "nombre_proceso", "tipo_proceso", "unidad_ejecutora"])

    # A?os disponibles
    print(f"\n  ? A?os con datos en adjudicaciones: 2017, 2018, 2019, 2020")
    print(f"     Para datos recientes (2021+) usar extraer_comprar() de diario.py")

    return df_adj


def test_contrat():
    from apis_oficiales import obtener_contrat_ocds_api

    _titulo("3. CONTRAT.AR ? Obra P?blica OCDS (datos.gob.ar)")
    df = obtener_contrat_ocds_api(limit=20)
    _resultado(df, ["ocid", "titulo", "organismo", "monto_contrato",
                    "proveedor", "cuit_proveedor"])
    if not df.empty:
        con_monto = (df["monto_contrato"] != "").sum()
        con_cuit  = (df["cuit_proveedor"] != "").sum()
        print(f"\n  ? Con monto: {con_monto} | Con CUIT: {con_cuit}")
    return df


def test_tgn(jurisdiccion: str = None):
    from apis_oficiales import obtener_tgn_ejecucion_api

    _titulo("4. TGN ? /ejecucion (con cuit_beneficiario)")
    df = obtener_tgn_ejecucion_api(jurisdiccion=jurisdiccion)
    _resultado(df, ["anio", "jurisdiccion", "beneficiario",
                    "cuit_beneficiario", "monto_pagado"])

    if not df.empty:
        con_cuit_benef = (df.get("cuit_beneficiario", pd.Series()) != "").sum()
        total          = len(df)
        print(f"\n  ? Registros con cuit_beneficiario: {con_cuit_benef}/{total}")
        if con_cuit_benef > 0:
            print(f"     ? Mejora el cruce vs /credito: cuit_beneficiario disponible")
        else:
            print(f"     ??  cuit_beneficiario vac?o ? usando organismo_norm para cruce")
        _verificar_schema(df, "df_tgn")

    return df


def test_cuit(cuit: str = "30-50000427-3"):
    from apis_oficiales import validar_cuit_api

    _titulo(f"5. CUIT ? Validaci?n AFIP/SIPRO: {cuit}")
    info = validar_cuit_api(cuit)
    print()
    for k, v in info.items():
        icono = "?" if k == "estado_afip" and v == "ACTIVO" else "  "
        print(f"  {icono} {k:<25}: {v}")
    return info


def test_cuit_lote(cuits: list = None):
    from apis_oficiales import validar_cuits_lote

    cuits_test = cuits or [
        "30-50000427-3",
        "30-71547352-5",
        "20-12345678-9",
    ]
    _titulo(f"5b. CUIT ? Validaci?n en lote ({len(cuits_test)} CUITs)")
    df = validar_cuits_lote(cuits_test)
    _resultado(df, ["cuit_original", "razon_social", "estado_afip", "fuente"])
    return df


def test_sipro(nombre: str = "TECHINT", cuit: str = None):
    from apis_oficiales import obtener_sipro_api

    query = f"nombre='{nombre}'" if nombre else f"cuit={cuit}"
    _titulo(f"6. SIPRO ? Proveedor habilitado ({query})")
    df = obtener_sipro_api(nombre=nombre, cuit=cuit, limit=10)
    _resultado(df, ["cuit", "razon_social", "domicilio", "rubro", "estado_sipro"])
    return df


def test_compatibilidad_con_diario():
    """
    Verifica que las APIs devuelven DataFrames compatibles con
    cruzar_fuentes() de diario.py.
    Cruza comprar_api() con tgn_ejecucion_api() usando la misma
    l?gica que diario.py para detectar solapamientos.
    """
    from apis_oficiales import obtener_comprar_api, obtener_tgn_ejecucion_api

    _titulo("7. Test de compatibilidad con diario.py / cruzar_fuentes()")

    print("\n  Verificando schemas...\n")

    # Schema df_comprar
    df_comp = obtener_comprar_api(anio=2020, tipo="adjudicaciones", limit=5)
    if not df_comp.empty:
        _verificar_schema(df_comp, "df_comprar")
    else:
        print("  ??  df_comprar: sin datos para verificar")

    # Schema df_tgn
    df_tgn = obtener_tgn_ejecucion_api()
    if not df_tgn.empty:
        _verificar_schema(df_tgn, "df_tgn")
    else:
        print("  ??  df_tgn: sin datos para verificar")

    # Simular mini-cruce (mismo algoritmo que cruzar_fuentes en diario.py)
    print("\n  Simulando mini-cruce (misma l?gica que cruzar_fuentes)...")
    if not df_comp.empty and not df_tgn.empty:
        STOP_WORDS = {"NACIONAL","GENERAL","ARGENTINA","PUBLICA","ADMINISTRACION",
                      "DIRECCION","SECRETARIA","MINISTERIO","AGENCIA","INSTITUTO"}

        cruces = 0
        for _, row_c in df_comp.head(10).iterrows():
            org = str(row_c.get("unidad_ejecutora", "")).upper()
            palabras = [p for p in org.split() if len(p) > 3 and p not in STOP_WORDS]
            for _, row_t in df_tgn.head(50).iterrows():
                org_t = str(row_t.get("organismo_norm", "")).upper()
                if sum(1 for p in palabras if p in org_t) >= 2:
                    cruces += 1
                    break

        if cruces > 0:
            print(f"  ? Mini-cruce exitoso: {cruces}/10 registros de comprar cruzaron con TGN")
        else:
            print("  ??  Sin cruces en el mini-test (normal si son datos de a?os distintos)")
    else:
        print("  ??  No hay datos suficientes para el mini-cruce")

    # Verificar que las funciones originales de diario.py a?n funcionan
    print("\n  Verificando que diario.py no fue alterado...")
    try:
        import diario
        funcs = ["extraer_bora_licitaciones", "extraer_bora_adjudicaciones",
                 "extraer_comprar", "extraer_pagos_tgn", "cruzar_fuentes"]
        for f in funcs:
            assert hasattr(diario, f), f"??  Falta funci?n {f} en diario.py"
        print(f"  ? diario.py intacto ? {len(funcs)} funciones verificadas")
    except Exception as e:
        print(f"  ? Error verificando diario.py: {e}")


def test_enriquecimiento_reporte():
    """
    Demo: c?mo usar apis_oficiales para enriquecer un reporte
    existente generado por diario.py SIN pisarlo.
    """
    from apis_oficiales import validar_cuits_lote

    _titulo("8. Demo ? Enriquecer reporte existente con CUITs")

    # Buscar el reporte m?s reciente
    data_dir = "/app/data" if os.path.exists("/app") else "data"
    reportes = []
    for root, _, files in os.walk(data_dir):
        for f in files:
            if f.startswith("reporte_202") and f.endswith(".xlsx"):
                reportes.append(os.path.join(root, f))
    reportes.sort(key=os.path.getmtime, reverse=True)

    if not reportes:
        print("  ??  No hay reportes en data/ ? ejecut? diario.py primero")
        return

    ruta = reportes[0]
    print(f"  ? Usando: {ruta}")
    try:
        xl   = pd.ExcelFile(ruta)
        hoja = "? Adjudicaciones" if "? Adjudicaciones" in xl.sheet_names else xl.sheet_names[0]
        df   = xl.parse(hoja)
        print(f"  ? {len(df)} registros en hoja '{hoja}'")

        if "cuit_proveedor" not in df.columns:
            print("  ??  Columna 'cuit_proveedor' no encontrada ? usando datos demo")
            cuits_test = ["30-50000427-3", "30-71547352-5"]
        else:
            cuits_test = df["cuit_proveedor"].dropna().astype(str)
            cuits_test = [c for c in cuits_test if re.sub(r'[^0-9]','',c) != ""][:5]

        if not cuits_test:
            print("  ??  Sin CUITs v?lidos en el reporte")
            return

        print(f"  ? Validando {len(cuits_test)} CUITs de muestra: {cuits_test}")
        df_val = validar_cuits_lote(cuits_test)

        if not df_val.empty:
            _resultado(df_val, ["cuit_original", "razon_social", "estado_afip"])
            print(f"\n  ? Para guardar el reporte enriquecido:")
            print(f"     df_enr = df.merge(df_val[['cuit_original','razon_social','estado_afip']],")
            print(f"                       left_on='cuit_proveedor', right_on='cuit_original', how='left')")
            print(f"     df_enr.to_excel('data/adjudicaciones_enriquecidas.xlsx', index=False)")
    except Exception as e:
        print(f"  ? Error leyendo reporte: {e}")


def test_todo():
    from apis_oficiales import obtener_todo_api

    _titulo("COMPLETO ? Todas las APIs")
    resultados = obtener_todo_api()
    print("\n  Resumen de compatibilidad con diario.py:")
    mapeo_schema = {
        "bora_normativa": "df_bora_licitaciones",
        "comprar_adj":    "df_comprar",
        "tgn_ejecucion":  "df_tgn",
    }
    for nombre, schema_key in mapeo_schema.items():
        df = resultados.get(nombre, pd.DataFrame())
        if not df.empty:
            requeridas = SCHEMA_DIARIO.get(schema_key, [])
            faltantes  = [c for c in requeridas if c not in df.columns]
            if faltantes:
                print(f"  ? {nombre}: faltan {faltantes}")
            else:
                print(f"  ? {nombre}: schema compatible con diario.py")
    return resultados


# ?????????????????????????????????????????????????????????????????????????????
# MAIN
# ?????????????????????????????????????????????????????????????????????????????

def main():
    import re as _re

    parser = argparse.ArgumentParser(
        description="Test APIs oficiales ? monitor_contratos"
    )
    parser.add_argument(
        "--solo",
        choices=["bora","comprar","contrat","tgn","cuit","sipro","compat","enrich","todo"],
        help="Correr solo una API/test espec?fico",
    )
    parser.add_argument("--cuit",      default="30-50000427-3",
                        help="CUIT a validar (default: 30-50000427-3)")
    parser.add_argument("--nombre",    default="TECHINT",
                        help="Nombre para SIPRO (default: TECHINT)")
    parser.add_argument("--anio",      type=int, default=2020,
                        help="A?o para COMPR.AR (2017-2020, default: 2020)")
    parser.add_argument("--organismo", default=None,
                        help="Filtro por organismo en COMPR.AR")
    parser.add_argument("--texto",     default=None,
                        help="Texto libre para b?squeda en BORA API")
    parser.add_argument("--jurisdiccion", default=None,
                        help="Jurisdicci?n para TGN")
    args = parser.parse_args()

    print(f"\n{SEP2}")
    print(f"  ? TEST APIs Oficiales ? monitor_contratos")
    print(f"  ? {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(SEP2)

    if args.solo == "bora":
        test_bora(texto=args.texto)
    elif args.solo == "comprar":
        test_comprar(anio=args.anio, organismo=args.organismo)
    elif args.solo == "contrat":
        test_contrat()
    elif args.solo == "tgn":
        test_tgn(jurisdiccion=args.jurisdiccion)
    elif args.solo == "cuit":
        test_cuit(args.cuit)
        test_cuit_lote()
    elif args.solo == "sipro":
        test_sipro(nombre=args.nombre, cuit=None)
        if args.cuit:
            test_sipro(nombre=None, cuit=args.cuit)
    elif args.solo == "compat":
        test_compatibilidad_con_diario()
    elif args.solo == "enrich":
        test_enriquecimiento_reporte()
    elif args.solo == "todo":
        test_todo()
    else:
        # Corre todo en orden
        test_bora(texto=args.texto)
        test_comprar(anio=args.anio, organismo=args.organismo)
        test_contrat()
        test_tgn(jurisdiccion=args.jurisdiccion)
        test_cuit(args.cuit)
        test_sipro(nombre=args.nombre)
        test_compatibilidad_con_diario()
        test_enriquecimiento_reporte()

    print(f"\n{SEP}")
    print("  Fin del test")
    print(f"  ? Recordar: apis_oficiales.py NO modifica diario.py ni los reportes existentes")
    print(SEP + "\n")


if __name__ == "__main__":
    import re
    main()
