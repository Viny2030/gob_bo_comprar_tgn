import requests
import pandas as pd
from io import StringIO

HEADERS = {"User-Agent": "MonitorContratos/1.0"}

def obtener_bora_normativa_api(seccion='tercera', texto=None, limit=50):
    url = 'https://api.boletinoficial.gob.ar/api/v1/avisos'
    params = {'seccion': seccion, 'limit': limit}
    if texto: params['texto'] = texto
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=20)
        data = r.json().get('data', [])
        df = pd.DataFrame(data)
        if not df.empty:
            df['fuente'] = 'BORA API'
            df['es_adjudicacion'] = df['titulo'].str.contains('ADJUDICACION', case=False, na=False)
        return df
    except: return pd.DataFrame()

def obtener_comprar_api(anio=2020, tipo='adjudicaciones', organismo=None, limit=100):
    return pd.DataFrame()

def obtener_tgn_ejecucion_api(jurisdiccion=None):
    return pd.DataFrame()

def obtener_contrat_ocds_api(limit=20):
    return pd.DataFrame()

def validar_cuit_api(cuit):
    return {'cuit': cuit, 'razon_social': 'TEST', 'estado_afip': 'ACTIVO'}

def validar_cuits_lote(cuits):
    return pd.DataFrame([validar_cuit_api(c) for c in cuits])

def obtener_sipro_api(nombre=None, cuit=None, limit=10):
    return pd.DataFrame([{'cuit': '30-00000000-1', 'razon_social': 'TEST', 'estado_sipro': 'HABILITADO'}])

def obtener_todo_api():
    return {'bora_normativa': obtener_bora_normativa_api()}
