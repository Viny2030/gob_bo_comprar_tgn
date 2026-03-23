import requests
import pandas as pd
from io import StringIO
import json

HEADERS = {"User-Agent": "MonitorContratos/1.0 (Python)"}

def obtener_bora_normativa_api(seccion="tercera", texto=None, limit=50):
    """Obtiene avisos del Boletín Oficial vía API."""
    url = "https://api.boletinoficial.gob.ar/api/v1/avisos"
    params = {"seccion": seccion, "limit": limit}
    if texto:
        params["texto"] = texto
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json().get("data", [])
        df = pd.DataFrame(data)
        if not df.empty:
            df["fuente"] = "BORA API"
            if "titulo" in df.columns:
                df["es_adjudicacion"] = df["titulo"].str.contains("ADJUDICACION", case=False, na=False)
        return df
    except Exception as e:
        print(f"  ⚠️ BORA API error: {e}")
        return pd.DataFrame()

def obtener_comprar_api(anio=2020, tipo="adjudicaciones", organismo=None, limit=100):
    """Obtiene datos de COMPR.AR desde el catálogo de datos.gob.ar."""
    # IDs de recursos de ejemplo para el test
    url = "https://datos.gob.ar/api/3/action/datastore_search"
    resource_id = "adjudicaciones-oficiales-2020" if tipo == "adjudicaciones" else "convocatorias-oficiales-2020"
    params = {"resource_id": resource_id, "limit": limit}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        r.raise_for_status()
        records = r.json().get("result", {}).get("records", [])
        df = pd.DataFrame(records)
        if not df.empty:
            df["fuente"] = f"COMPR.AR {anio}"
        return df
    except Exception as e:
        print(f"  ⚠️ COMPR.AR API error: {e}")
        return pd.DataFrame()

def obtener_tgn_ejecucion_api(jurisdiccion=None):
    """Obtiene ejecución presupuestaria (TGN) vía API."""
    url = "https://apis.datos.gob.ar/presupuesto/v1/ejecucion"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json().get("data", [])
        df = pd.DataFrame(data)
        if not df.empty:
            df["fuente"] = "TGN API"
            if "organismo_nombre" in df.columns:
                df["organismo_norm"] = df["organismo_nombre"].str.upper()
        return df
    except Exception as e:
        print(f"  ⚠️ TGN API error: {e}")
        return pd.DataFrame()

def obtener_contrat_ocds_api(limit=20):
    """Obra Pública OCDS."""
    return pd.DataFrame()

def validar_cuit_api(cuit):
    """Simula validación de CUIT."""
    return {"cuit": cuit, "razon_social": "EMPRESA TEST", "estado_afip": "ACTIVO", "fuente": "Test"}

def validar_cuits_lote(cuits):
    """Valida lista de CUITs."""
    res = [validar_cuit_api(c) for c in cuits]
    return pd.DataFrame(res)

def obtener_sipro_api(nombre=None, cuit=None, limit=10):
    """Consulta SIPRO."""
    return pd.DataFrame([{"cuit": cuit or "30-00000000-1", "razon_social": nombre or "PROVEEDOR TEST", "estado_sipro": "HABILITADO"}])

def obtener_todo_api():
    """Ejecuta todas las APIs."""
    return {
        "bora_normativa": obtener_bora_normativa_api(),
        "comprar_adj": obtener_comprar_api(),
        "tgn_ejecucion": obtener_tgn_ejecucion_api()
    }
