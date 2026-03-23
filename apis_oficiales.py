"""
apis_oficiales.py
=================
Módulo adicional de fuentes oficiales para monitor_contratos.
NO modifica ningún archivo existente del proyecto.

Fuentes cubiertas:
  1. BORA — Normativa API (argentina.gob.ar/normativa)
  2. COMPR.AR — API CKAN (datos.gob.ar) — histórico 2015-2020
  3. CONTRAT.AR — OCDS obra pública (datos.gob.ar)
  4. TGN — /ejecucion con cuit_beneficiario (Presupuesto Abierto API v1)
  5. CUIT — Validación AFIP SOA público
  6. SIPRO — Proveedores habilitados del Estado (datos.gob.ar)

Todos los DataFrames devueltos son compatibles con los schemas
de diario.py para integrarse directamente al flujo de cruce.
"""

import os
import re
import time
import io
import logging
from datetime import datetime
from typing import Optional

import requests
import pandas as pd

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────
TGN_TOKEN = os.environ.get("TGN_TOKEN", "707cb8c8-83e6-4c4d-a202-3e49c14eda89")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
}

# CKAN base de datos.gob.ar
CKAN_BASE = "https://datos.gob.ar/api/3/action"

# IDs reales de los datasets en datos.gob.ar
DATASET_COMPRAR_ADJ  = "adjudicaciones-{anio}"   # resource name pattern
DATASET_COMPRAR_CONV = "convocatorias-{anio}"
DATASET_SIPRO        = "proveedores-contrataciones-estado"

# URLs directas de los CSV anuales de COMPR.AR publicados en datos.gob.ar
COMPRAR_CSV_URLS = {
    "adjudicaciones": {
        2020: "https://infra.datos.gob.ar/catalog/sspm/dataset/269/distribution/269.4/download/adjudicaciones-2020.csv",
        2019: "https://infra.datos.gob.ar/catalog/sspm/dataset/269/distribution/269.3/download/adjudicaciones-2019.csv",
        2018: "https://infra.datos.gob.ar/catalog/sspm/dataset/269/distribution/269.2/download/adjudicaciones-2018.csv",
        2017: "https://infra.datos.gob.ar/catalog/sspm/dataset/269/distribution/269.1/download/adjudicaciones-2017.csv",
    },
    "convocatorias": {
        2020: "https://infra.datos.gob.ar/catalog/sspm/dataset/269/distribution/269.8/download/convocatorias-2020.csv",
        2019: "https://infra.datos.gob.ar/catalog/sspm/dataset/269/distribution/269.7/download/convocatorias-2019.csv",
        2018: "https://infra.datos.gob.ar/catalog/sspm/dataset/269/distribution/269.6/download/convocatorias-2018.csv",
    },
}

# URL CSV SIPRO (proveedores habilitados)
SIPRO_CSV_URL = (
    "https://infra.datos.gob.ar/catalog/jgm/dataset/18/distribution/18.1"
    "/download/proveedores-contrataciones-estado.csv"
)


# ── Utilidades internas ───────────────────────────────────────────────────────

def _get(url: str, timeout: int = 30, verify: bool = False, **kwargs) -> requests.Response:
    """GET con reintentos silenciosos."""
    for intento in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout,
                             verify=verify, **kwargs)
            r.raise_for_status()
            return r
        except Exception as e:
            if intento < 2:
                time.sleep(5)
            else:
                raise e


def _post(url: str, json_body: dict, extra_headers: dict = None,
          timeout: int = 60, verify: bool = False) -> requests.Response:
    """POST con reintentos silenciosos."""
    h = {**HEADERS, **(extra_headers or {})}
    for intento in range(3):
        try:
            r = requests.post(url, headers=h, json=json_body,
                              timeout=timeout, verify=verify)
            r.raise_for_status()
            return r
        except Exception as e:
            if intento < 2:
                time.sleep(5)
            else:
                raise e


def _hoy() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _normalizar_cuit(texto: str) -> str:
    """Extrae y normaliza CUIT del texto. Retorna '' si no encuentra."""
    if not texto:
        return ""
    # Formato XX-XXXXXXXX-X
    m = re.search(r'\b(\d{2}-\d{7,8}-\d{1})\b', str(texto))
    if m:
        return m.group(1)
    # Formato numérico puro 11 dígitos
    m = re.search(r'\b(20|23|24|27|30|33|34)\d{9}\b', str(texto))
    if m:
        raw = m.group(0)
        return f"{raw[:2]}-{raw[2:-1]}-{raw[-1]}"
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# 1. BORA — Normativa API
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_bora_normativa_api(
    seccion: str = "tercera",
    fecha_desde: str = None,
    fecha_hasta: str = None,
    texto: str = None,
    limit: int = 100,
) -> pd.DataFrame:
    """
    Consulta la API JSON de normativa de argentina.gob.ar.
    Es más estable que el scraping directo del HTML de boletinoficial.gob.ar.

    Esquema de salida compatible con extraer_bora_licitaciones() de diario.py:
        fecha_extraccion, fecha_publicacion, organismo, tipo_proceso,
        categoria, aviso_id, es_adjudicacion, link, fuente, titulo

    Parámetros
    ----------
    seccion      : "primera" | "segunda" | "tercera"
    fecha_desde  : "YYYY-MM-DD"  (default: hoy)
    fecha_hasta  : "YYYY-MM-DD"  (default: hoy)
    texto        : filtro de búsqueda libre
    limit        : máximo de resultados
    """
    hoy = _hoy()
    fecha_desde = fecha_desde or hoy
    fecha_hasta = fecha_hasta or hoy

    # Endpoint oficial de búsqueda de normativa
    url = "https://www.argentina.gob.ar/normativa/buscar"
    params = {
        "seccion":      seccion,
        "desde":        fecha_desde.replace("-", "/"),
        "hasta":        fecha_hasta.replace("-", "/"),
        "limit":        limit,
        "offset":       0,
    }
    if texto:
        params["texto"] = texto

    print(f"\n📡 BORA Normativa API | sección={seccion} | {fecha_desde} → {fecha_hasta}")
    try:
        r = _get(url, params=params, timeout=30)
        data = r.json()

        # La API puede devolver lista directa o {"results": [...]}
        registros = data if isinstance(data, list) else data.get("results", data.get("normas", []))

        if not registros:
            print("  ⚠️  Sin resultados en la API de normativa")
            return pd.DataFrame()

        filas = []
        for item in registros:
            titulo    = item.get("titulo", item.get("name", ""))
            organismo = item.get("organismo", item.get("jurisdiccion", ""))
            tipo      = item.get("tipo_norma", item.get("tipo", ""))
            fecha_pub = item.get("fecha_publicacion", item.get("fecha", hoy))
            aviso_id  = str(item.get("id", item.get("numero", "")))
            link      = item.get("url", item.get("link", ""))
            if not link and aviso_id:
                link = f"https://www.boletinoficial.gob.ar/detalleAviso/tercera/{aviso_id}/{fecha_pub.replace('-','')}"

            es_adj = any(kw in titulo.upper() for kw in
                         ["ADJUDICACI", "ADJUDICACION"])

            filas.append({
                "fecha_extraccion":  _hoy(),
                "fecha_publicacion": fecha_pub[:10] if fecha_pub else hoy,
                "organismo":         organismo,
                "tipo_proceso":      tipo,
                "categoria":         f"Sección {seccion.capitalize()}",
                "aviso_id":          aviso_id,
                "es_adjudicacion":   es_adj,
                "link":              link,
                "fuente":            "BORA Normativa API",
                "titulo":            titulo,
            })

        df = pd.DataFrame(filas)
        adj = df["es_adjudicacion"].sum()
        print(f"  ✅ {len(df)} normas ({adj} adjudicaciones, {len(df)-adj} licitaciones)")
        return df

    except Exception as e:
        print(f"  ❌ BORA Normativa API falló: {e}")
        print("  💡 Usando scraping directo de boletinoficial.gob.ar como fallback...")
        # Fallback al scraper original de diario.py
        try:
            from diario import extraer_bora_licitaciones
            return extraer_bora_licitaciones()
        except Exception as e2:
            print(f"  ❌ Fallback también falló: {e2}")
            return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. COMPR.AR — API CKAN / CSVs datos.gob.ar
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_comprar_api(
    anio: int = 2020,
    tipo: str = "adjudicaciones",
    organismo: str = None,
    limit: int = 500,
) -> pd.DataFrame:
    """
    Descarga adjudicaciones o convocatorias de COMPR.AR desde datos.gob.ar.
    Datos disponibles: 2017–2020. Para años recientes usá extraer_comprar() de diario.py.

    Esquema de salida compatible con extraer_comprar() de diario.py:
        fecha_extraccion, nro_proceso, nombre_proceso, tipo_proceso,
        fecha_apertura, estado, unidad_ejecutora, link, fuente,
        cuit_proveedor, monto, organismo_contratante

    Parámetros
    ----------
    anio       : 2017 | 2018 | 2019 | 2020
    tipo       : "adjudicaciones" | "convocatorias"
    organismo  : filtro parcial por nombre de organismo (case-insensitive)
    limit      : máximo de filas a retornar
    """
    print(f"\n📡 COMPR.AR API | tipo={tipo} | año={anio}")

    urls_tipo = COMPRAR_CSV_URLS.get(tipo, {})
    csv_url   = urls_tipo.get(anio)

    if not csv_url:
        print(f"  ⚠️  No hay URL configurada para {tipo} {anio}")
        print(f"     Años disponibles: {sorted(urls_tipo.keys())}")
        return pd.DataFrame()

    try:
        r = _get(csv_url, timeout=60)
        df = pd.read_csv(
            io.StringIO(r.text),
            sep=",",
            on_bad_lines="skip",
            dtype=str,
        ).fillna("")

        print(f"  📥 {len(df)} registros descargados | columnas: {list(df.columns[:6])}")

        # Mapeo flexible de columnas según variación de los CSV de cada año
        col_map = {
            # nro_proceso
            "nro_proceso":       ["nro_proceso", "numero_proceso", "proceso_id", "id_proceso"],
            # nombre_proceso
            "nombre_proceso":    ["nombre_proceso", "descripcion", "objeto", "nombre"],
            # tipo_proceso
            "tipo_proceso":      ["tipo_proceso", "modalidad", "tipo_contratacion", "tipo"],
            # fecha_apertura
            "fecha_apertura":    ["fecha_apertura", "fecha_acto_apertura", "fecha"],
            # estado
            "estado":            ["estado", "estado_proceso"],
            # unidad_ejecutora / organismo
            "unidad_ejecutora":  ["unidad_ejecutora", "organismo_contratante", "organismo",
                                  "reparticion", "entidad"],
            # CUIT proveedor (solo en adjudicaciones)
            "cuit_proveedor":    ["cuit_proveedor", "cuit", "cuit_adjudicatario",
                                  "cuit_empresa", "cuit_contratista"],
            # monto
            "monto":             ["monto", "monto_adjudicado", "monto_contrato",
                                  "importe_total", "monto_total"],
            # link
            "link":              ["link", "url", "enlace"],
        }

        df_out = pd.DataFrame()
        for col_destino, candidatos in col_map.items():
            for c in candidatos:
                matches = [x for x in df.columns if x.lower().strip() == c.lower()]
                if matches:
                    df_out[col_destino] = df[matches[0]].astype(str)
                    break
            if col_destino not in df_out.columns:
                df_out[col_destino] = ""

        # Filtro por organismo
        if organismo:
            mask = df_out["unidad_ejecutora"].str.upper().str.contains(
                organismo.upper(), na=False
            )
            df_out = df_out[mask].copy()
            print(f"  🔍 Filtrado por organismo '{organismo}': {len(df_out)} registros")

        # Completar campos de compatibilidad con diario.py
        df_out["fecha_extraccion"] = _hoy()
        df_out["fuente"]           = f"COMPR.AR datos.gob.ar {tipo} {anio}"

        # Link genérico si no viene en el CSV
        df_out["link"] = df_out.apply(
            lambda r: r["link"] if r["link"] else
            f"https://comprar.gob.ar/Compras.aspx?qs={r['nro_proceso']}",
            axis=1,
        )

        df_out = df_out.head(limit)
        print(f"  ✅ {len(df_out)} registros listos")
        return df_out

    except Exception as e:
        print(f"  ❌ COMPR.AR API falló: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════════
# 3. CONTRAT.AR — OCDS Obra Pública
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_contrat_ocds_api(
    organismo: str = None,
    limit: int = 200,
) -> pd.DataFrame:
    """
    Descarga datos de obra pública de CONTRAT.AR en formato OCDS desde datos.gob.ar.

    Esquema de salida:
        fecha_extraccion, ocid, titulo, organismo, monto_contrato,
        proveedor, cuit_proveedor, estado, fecha_publicacion,
        link, fuente
    """
    print("\n📡 CONTRAT.AR OCDS API")

    # Buscar el dataset en CKAN
    try:
        r_pkg = _get(
            f"{CKAN_BASE}/package_search",
            params={"q": "contrat obras publicas ocds", "rows": 5},
            timeout=20,
        )
        resultados = r_pkg.json().get("result", {}).get("results", [])
        csv_url = None
        for pkg in resultados:
            for res in pkg.get("resources", []):
                url_res = res.get("url", "")
                if url_res.endswith(".csv") and "contrat" in url_res.lower():
                    csv_url = url_res
                    break
            if csv_url:
                break
    except Exception:
        csv_url = None

    # URL de fallback conocida
    if not csv_url:
        csv_url = (
            "https://infra.datos.gob.ar/catalog/jgm/dataset/30/distribution/30.1"
            "/download/contratos-obras-ocds.csv"
        )

    try:
        r = _get(csv_url, timeout=60)
        df = pd.read_csv(io.StringIO(r.text), sep=",", on_bad_lines="skip", dtype=str).fillna("")
        print(f"  📥 {len(df)} registros | columnas: {list(df.columns[:6])}")

        # Mapeo de columnas OCDS
        col_map = {
            "ocid":            ["ocid", "id", "release_id"],
            "titulo":          ["title", "titulo", "nombre", "description"],
            "organismo":       ["buyer_name", "organismo", "comprador", "buyer"],
            "monto_contrato":  ["awards_value_amount", "monto", "valor_contrato", "amount"],
            "proveedor":       ["suppliers_name", "proveedor", "contratista", "supplier"],
            "cuit_proveedor":  ["suppliers_identifier", "cuit_proveedor", "cuit", "rut"],
            "estado":          ["status", "estado"],
            "fecha_publicacion": ["date", "fecha_publicacion", "published_date"],
            "link":            ["url", "link"],
        }

        df_out = pd.DataFrame()
        for col_destino, candidatos in col_map.items():
            for c in candidatos:
                matches = [x for x in df.columns if x.lower().strip() == c.lower()]
                if matches:
                    df_out[col_destino] = df[matches[0]].astype(str)
                    break
            if col_destino not in df_out.columns:
                df_out[col_destino] = ""

        if organismo:
            mask = df_out["organismo"].str.upper().str.contains(organismo.upper(), na=False)
            df_out = df_out[mask].copy()
            print(f"  🔍 Filtrado por organismo '{organismo}': {len(df_out)} registros")

        df_out["fecha_extraccion"] = _hoy()
        df_out["fuente"]           = "CONTRAT.AR OCDS datos.gob.ar"
        df_out = df_out.head(limit)
        print(f"  ✅ {len(df_out)} registros listos")
        return df_out

    except Exception as e:
        print(f"  ❌ CONTRAT.AR OCDS falló: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. TGN — /ejecucion (agrega cuit_beneficiario)
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_tgn_ejecucion_api(
    anio: int = None,
    jurisdiccion: str = None,
) -> pd.DataFrame:
    """
    Endpoint /ejecucion de Presupuesto Abierto.
    Complementa al /credito de diario.py porque incluye el campo
    'cuit_beneficiario', que mejora significativamente el cruce con BORA.

    Esquema de salida compatible con extraer_pagos_tgn() de diario.py:
        fecha_extraccion, anio, cuit, beneficiario, unidad_ejecutora,
        jurisdiccion, monto_pagado, monto_devengado, organismo_norm, fuente
        + cuit_beneficiario (columna adicional, clave del enriquecimiento)

    Parámetros
    ----------
    anio         : año presupuestario (default: año actual)
    jurisdiccion : filtro por nombre de jurisdicción (parcial, case-insensitive)
    """
    anio = anio or datetime.now().year
    print(f"\n📡 TGN /ejecucion API | año={anio}")

    url = "https://www.presupuestoabierto.gob.ar/api/v1/ejecucion"
    headers_api = {
        "Authorization": f"Bearer {TGN_TOKEN}",
        "Content-Type":  "application/json",
        "Accept":        "text/csv",
    }
    body = {
        "columns": [
            "ejercicio_presupuestario",
            "jurisdiccion_desc",
            "entidad_desc",
            "unidad_ejecutora_desc",
            "cuit_beneficiario",
            "beneficiario_desc",
            "gasto_pagado",
            "gasto_devengado",
        ]
    }

    try:
        r = _post(url, json_body=body, extra_headers=headers_api, timeout=60)
        df = pd.read_csv(io.StringIO(r.text), sep=",", on_bad_lines="skip")

        # Filtrar año
        if "ejercicio_presupuestario" in df.columns:
            df = df[df["ejercicio_presupuestario"] == anio].copy()

        if df.empty:
            print(f"  ⚠️  Sin datos de ejecución para {anio}")
            return pd.DataFrame()

        if jurisdiccion:
            mask = df["jurisdiccion_desc"].fillna("").str.upper().str.contains(
                jurisdiccion.upper(), na=False
            )
            df = df[mask].copy()
            print(f"  🔍 Filtrado por jurisdicción '{jurisdiccion}': {len(df)} registros")

        # Normalizar organismo para cruce (igual que diario.py)
        df["organismo_norm"] = (
            df["entidad_desc"].fillna("").str.upper().str.strip()
            + " "
            + df["unidad_ejecutora_desc"].fillna("").str.upper().str.strip()
        ).str.strip()

        # CUIT beneficiario — columna extra clave
        cuit_col = "cuit_beneficiario" if "cuit_beneficiario" in df.columns else None

        df_out = pd.DataFrame({
            "fecha_extraccion":  _hoy(),
            "anio":              anio,
            "cuit":              "",                                          # organismo pagador
            "cuit_beneficiario": df[cuit_col].fillna("").astype(str) if cuit_col else "",
            "beneficiario":      df.get("beneficiario_desc", df.get("entidad_desc", pd.Series([""] * len(df)))).fillna(""),
            "unidad_ejecutora":  df["unidad_ejecutora_desc"].fillna(""),
            "jurisdiccion":      df["jurisdiccion_desc"].fillna(""),
            "monto_pagado":      pd.to_numeric(df.get("gasto_pagado",   0), errors="coerce").fillna(0),
            "monto_devengado":   pd.to_numeric(df.get("gasto_devengado", 0), errors="coerce").fillna(0),
            "organismo_norm":    df["organismo_norm"],
            "fuente":            f"TGN Presupuesto Abierto /ejecucion {anio}",
        })

        con_cuit = (df_out["cuit_beneficiario"] != "").sum()
        print(f"  ✅ {len(df_out)} registros | {con_cuit} con cuit_beneficiario")
        return df_out

    except Exception as e:
        print(f"  ⚠️  TGN /ejecucion no disponible: {e}")
        print("  💡 Intentando con /credito (fallback de diario.py)...")
        try:
            from diario import extraer_pagos_tgn
            df_fallback = extraer_pagos_tgn()
            if not df_fallback.empty:
                df_fallback["cuit_beneficiario"] = ""  # no disponible en /credito
            return df_fallback
        except Exception as e2:
            print(f"  ❌ Fallback también falló: {e2}")
            return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. CUIT — Validación AFIP SOA público
# ═══════════════════════════════════════════════════════════════════════════════

def validar_cuit_api(cuit: str) -> dict:
    """
    Valida un CUIT contra el servicio público de AFIP.
    Retorna un dict con razon_social, estado_afip, domicilio_fiscal, etc.

    Parámetros
    ----------
    cuit : CUIT en formato "XX-XXXXXXXX-X" o numérico puro
    """
    # Normalizar formato
    cuit_limpio = re.sub(r'[^0-9]', '', str(cuit))
    cuit_fmt    = f"{cuit_limpio[:2]}-{cuit_limpio[2:-1]}-{cuit_limpio[-1]}" if len(cuit_limpio) == 11 else cuit

    resultado_base = {
        "cuit_original":    cuit,
        "cuit_normalizado": cuit_fmt,
        "razon_social":     "No disponible",
        "domicilio_fiscal": "No disponible",
        "estado_afip":      "No consultado",
        "actividad":        "",
        "fuente":           "AFIP SOA",
    }

    # Endpoint 1: API pública AFIP (sería.afip.gov.ar/sr-padron-a4/...)
    # Por restricciones de red en Railway, usamos el proxy datos.gob.ar
    urls_intentar = [
        f"https://soa.afip.gob.ar/sr-padron/v2/persona/{cuit_limpio}",
        f"https://datos.gob.ar/api/3/action/datastore_search?resource_id=a_recurso&q={cuit_limpio}",
    ]

    for url in urls_intentar:
        try:
            r = _get(url, timeout=15)
            data = r.json()

            # Respuesta del servicio SOA de AFIP
            persona = data.get("data", data)
            if isinstance(persona, dict) and persona.get("idPersona"):
                resultado_base.update({
                    "razon_social":     persona.get("razonSocial",
                                        f"{persona.get('apellido','')} {persona.get('nombre','')}".strip()),
                    "domicilio_fiscal": _formatear_domicilio(persona.get("domicilio", [])),
                    "estado_afip":      "ACTIVO" if persona.get("estadoClave") == "ACTIVO" else
                                        persona.get("estadoClave", "DESCONOCIDO"),
                    "actividad":        persona.get("actividad", {}).get("descripcionActividad", ""),
                })
                return resultado_base
        except Exception:
            continue

    # Fallback: buscar en SIPRO (no requiere AFIP)
    try:
        df_sipro = obtener_sipro_api(cuit=cuit_fmt, limit=1)
        if not df_sipro.empty:
            row = df_sipro.iloc[0]
            resultado_base.update({
                "razon_social":     row.get("razon_social", ""),
                "domicilio_fiscal": row.get("domicilio", ""),
                "estado_afip":      row.get("estado_sipro", "HABILITADO"),
                "fuente":           "SIPRO datos.gob.ar",
            })
    except Exception:
        pass

    return resultado_base


def _formatear_domicilio(domicilios: list) -> str:
    """Formatea la lista de domicilios de AFIP en string."""
    if not domicilios or not isinstance(domicilios, list):
        return ""
    d = domicilios[0] if domicilios else {}
    partes = [
        d.get("direccion", ""),
        d.get("localidad", ""),
        d.get("descripcionProvincia", ""),
    ]
    return ", ".join(p for p in partes if p)


def validar_cuits_lote(cuits: list, pausa: float = 0.5) -> pd.DataFrame:
    """
    Valida una lista de CUITs y devuelve un DataFrame con los resultados.
    Útil para enriquecer df_adjudicaciones con datos de AFIP/SIPRO.

    Ejemplo de uso:
        df_adj = pd.read_excel("data/2026-03/reporte_2026-03-22.xlsx",
                               sheet_name="🏆 Adjudicaciones")
        cuits  = df_adj["cuit_proveedor"].dropna().unique().tolist()
        df_val = validar_cuits_lote(cuits)
        df_enr = df_adj.merge(df_val[["cuit_original","razon_social","estado_afip"]],
                              left_on="cuit_proveedor", right_on="cuit_original", how="left")
    """
    print(f"\n📡 Validando {len(cuits)} CUITs...")
    resultados = []
    for i, cuit in enumerate(cuits, 1):
        if not cuit or str(cuit).strip() in ("", "nan", "None"):
            continue
        info = validar_cuit_api(str(cuit).strip())
        resultados.append(info)
        if i % 10 == 0:
            print(f"  {i}/{len(cuits)} validados...")
        time.sleep(pausa)

    df = pd.DataFrame(resultados)
    activos = (df["estado_afip"] == "ACTIVO").sum() if not df.empty else 0
    print(f"  ✅ {len(df)} CUITs validados | {activos} ACTIVOS en AFIP")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# 6. SIPRO — Proveedores habilitados del Estado
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_sipro_api(
    nombre: str = None,
    cuit: str = None,
    limit: int = 50,
) -> pd.DataFrame:
    """
    Consulta el padrón de proveedores habilitados del Estado (SIPRO)
    desde datos.gob.ar.

    Esquema de salida:
        cuit, razon_social, domicilio, rubro, estado_sipro,
        fecha_alta, fuente

    Parámetros
    ----------
    nombre : filtro parcial por razón social (case-insensitive)
    cuit   : búsqueda exacta por CUIT
    limit  : máximo de resultados
    """
    print(f"\n📡 SIPRO Proveedores | nombre={nombre} | cuit={cuit}")

    # Intentar primero la API CKAN datastore (filtrado server-side)
    try:
        params = {"resource_id": "18.1", "limit": limit}
        filters = {}
        if cuit:
            cuit_limpio = re.sub(r'[^0-9]', '', str(cuit))
            filters["cuit"] = cuit_limpio
        if filters:
            import json
            params["filters"] = json.dumps(filters)
        if nombre and not cuit:
            params["q"] = nombre

        r = _get(f"{CKAN_BASE}/datastore_search", params=params, timeout=20)
        data = r.json()
        registros = data.get("result", {}).get("records", [])

        if registros:
            df = pd.DataFrame(registros)
            df = _normalizar_sipro(df)
            if nombre and "razon_social" in df.columns:
                df = df[df["razon_social"].str.upper().str.contains(nombre.upper(), na=False)]
            df = df.head(limit)
            print(f"  ✅ {len(df)} proveedores encontrados (CKAN datastore)")
            return df
    except Exception:
        pass

    # Fallback: descargar CSV completo y filtrar localmente
    try:
        r = _get(SIPRO_CSV_URL, timeout=60)
        df = pd.read_csv(io.StringIO(r.text), sep=",", on_bad_lines="skip",
                         dtype=str).fillna("")
        print(f"  📥 CSV SIPRO: {len(df)} proveedores totales")

        if cuit:
            cuit_limpio = re.sub(r'[^0-9]', '', str(cuit))
            cols_cuit = [c for c in df.columns if "cuit" in c.lower()]
            if cols_cuit:
                df = df[df[cols_cuit[0]].str.replace("-", "").str.strip() == cuit_limpio]

        if nombre:
            cols_nombre = [c for c in df.columns if "razon" in c.lower() or "nombre" in c.lower()]
            if cols_nombre:
                df = df[df[cols_nombre[0]].str.upper().str.contains(nombre.upper(), na=False)]

        df = _normalizar_sipro(df).head(limit)
        print(f"  ✅ {len(df)} proveedores encontrados (CSV)")
        return df

    except Exception as e:
        print(f"  ❌ SIPRO no disponible: {e}")
        return pd.DataFrame()


def _normalizar_sipro(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza columnas del CSV/API de SIPRO a schema estándar."""
    col_map = {
        "cuit":         ["cuit", "nro_cuit", "cuit_proveedor"],
        "razon_social": ["razon_social", "nombre", "denominacion", "nombre_proveedor"],
        "domicilio":    ["domicilio", "direccion", "domicilio_legal"],
        "rubro":        ["rubro", "actividad", "rubro_principal"],
        "estado_sipro": ["estado", "estado_sipro", "habilitacion", "condicion"],
        "fecha_alta":   ["fecha_alta", "fecha_inscripcion", "fecha_registro"],
    }
    df_out = pd.DataFrame()
    for col_dest, candidatos in col_map.items():
        for c in candidatos:
            matches = [x for x in df.columns if x.lower().strip() == c.lower()]
            if matches:
                df_out[col_dest] = df[matches[0]].astype(str)
                break
        if col_dest not in df_out.columns:
            df_out[col_dest] = ""
    df_out["fuente"] = "SIPRO datos.gob.ar"
    return df_out


# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIÓN COMBINADA
# ═══════════════════════════════════════════════════════════════════════════════

def obtener_todo_api(anio_comprar: int = 2020) -> dict:
    """
    Ejecuta todas las APIs y devuelve un dict de DataFrames.

    Retorna
    -------
    {
        "bora_normativa": df,
        "comprar_adj":    df,
        "comprar_conv":   df,
        "contrat_ocds":   df,
        "tgn_ejecucion":  df,
    }
    """
    print("\n" + "═" * 55)
    print("  OBTENER TODO — APIs Oficiales")
    print("═" * 55)

    resultados = {}

    try:
        resultados["bora_normativa"] = obtener_bora_normativa_api(seccion="tercera")
    except Exception as e:
        print(f"  ❌ bora_normativa: {e}")
        resultados["bora_normativa"] = pd.DataFrame()

    try:
        resultados["comprar_adj"] = obtener_comprar_api(anio=anio_comprar, tipo="adjudicaciones")
    except Exception as e:
        print(f"  ❌ comprar_adj: {e}")
        resultados["comprar_adj"] = pd.DataFrame()

    try:
        resultados["comprar_conv"] = obtener_comprar_api(anio=anio_comprar, tipo="convocatorias")
    except Exception as e:
        print(f"  ❌ comprar_conv: {e}")
        resultados["comprar_conv"] = pd.DataFrame()

    try:
        resultados["contrat_ocds"] = obtener_contrat_ocds_api()
    except Exception as e:
        print(f"  ❌ contrat_ocds: {e}")
        resultados["contrat_ocds"] = pd.DataFrame()

    try:
        resultados["tgn_ejecucion"] = obtener_tgn_ejecucion_api()
    except Exception as e:
        print(f"  ❌ tgn_ejecucion: {e}")
        resultados["tgn_ejecucion"] = pd.DataFrame()

    print("\n" + "─" * 55)
    print("  Resumen:")
    for nombre, df in resultados.items():
        n = len(df) if not df.empty else 0
        icono = "✅" if n > 0 else "⚠️ "
        print(f"  {icono} {nombre:<25} {n:>6} registros")
    print("─" * 55)
    return resultados
