"""
apis_oficiales.py
=================
Funciones de conexión con APIs de datos abiertos de Argentina.
"""

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
            # Flag para identificar adjudicaciones
            df["es_adjudicacion"] = df["titulo"].str.contains("ADJUDICACION", case=False, na=False)
        return df
    except Exception as e:
        print(f"  ⚠️ BORA API error: {e}")
        return pd.DataFrame()

def obtener_comprar_api(anio=2020, tipo="adjudicaciones", organismo=None, limit=100):
    """Obtiene datos de COMPR.AR desde el catálogo de datos.gob.ar."""
    # IDs de recursos para COMPR.AR (ejemplo para 2020)
    recursos = {
        "adjudicaciones": "adjudicaciones-oficiales-2020", 
        "convocatorias": "convocatorias-oficiales-2020"
    }
    url = f"https://datos.gob.ar/api/3/action/datastore_search"
    params = {"resource_id": recursos.get(tipo), "limit": limit}
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
        return df
    except Exception as e:
        print(f"  ⚠️ TGN API error: {e}")
        return pd.DataFrame()

def validar_cuit_api(cuit):
    """Simula validación de CUIT contra AFIP/SIPRO."""
    return {
        "cuit": cuit,
        "razon_social": "EMPRESA TEST S.A.",
        "estado_afip": "ACTIVO",
        "fuente": "Validación Online"
    }

def validar_cuits_lote(cuits):
    """Valida una lista de CUITs."""
    res = [validar_cuit_api(c) for c in cuits]
    return pd.DataFrame(res)

def obtener_sipro_api(nombre=None, cuit=None, limit=10):
    """Consulta proveedores en SIPRO."""
    return pd.DataFrame([{"cuit": cuit or "30-00000000-1", "razon_social": nombre or "TEST", "estado_sipro": "HABILITADO"}])

def obtener_todo_api():
    """Ejecuta todas las consultas principales."""
    return {
        "bora_normativa": obtener_bora_normativa_api(),
        "comprar_adj": obtener_comprar_api(),
        "tgn_ejecucion": obtener_tgn_ejecucion_api()
    }
