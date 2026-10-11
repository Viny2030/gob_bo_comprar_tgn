import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
import time
import re
import io

from analisis import analizar_adjudicaciones

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9",
    "Connection": "keep-alive",
}

# ─────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────
def get_con_reintentos(url, intentos=3, timeout=60, espera=15, verify_ssl=False):
    for i in range(intentos):
        try:
            print(f"  🔄 Intento {i+1}: {url[:80]}...")
            r = requests.get(url, headers=HEADERS, timeout=timeout, verify=verify_ssl)
            r.raise_for_status()
            return r
        except Exception as e:
            print(f"  ⚠️ Error intento {i+1}: {e}")
            if i < intentos - 1:
                time.sleep(espera)
    raise Exception(f"❌ Fallaron todos los intentos: {url}")

# Extractores de los avisos de adjudicación (texto del PDF del BORA).
# Revisados contra 116 avisos reales de sep-oct 2026: el proveedor ya no se corta
# en el primer punto de "S.A." (antes quedaba "TUX S", "PERMAQUIM S"), se leen
# formatos como "Adjudicatario: X", "Adjudicar a la firma X" y "por un total de
# ... ($ N)", y los CUIT se validan con el dígito verificador (módulo 11).
_FIN_NOMBRE = (r'(?=\s*(?:[,;–\-\.\(]\s*)?(?:C\.?U\.?I\.?T|”|(?i:IMPORTE|MONTO|DOMICILIO|RENGL[OÓ]N)|el\s+Rengl|los\s+Rengl|la\s+totalidad|Rengl[oó]n|por\s+(?:un|el|la)\s|por\s+\$|,\s*por|\(\$|\$|\.\s+e\.\s|e\.\s+\d{2}/\d{2}/\d{4}|$))')
_SOC = r'(?:S\.?\s?A\.?\s?U\.?|S\.?\s?A\.?\s?S\.?|S\.?\s?R\.?\s?L\.?|S\.?\s?A\.?|S\.?\s?E\.?|S\.?\s?C\.?|LTDA\.?|S\.?\s?A\.?\s?C\.?\s?I\.?\s?F\.?(?:\s?I\.?)?)'
def _cuit_ok(c):
    d=re.sub(r'\D','',c)
    if len(d)!=11: return False
    s=sum(int(a)*m for a,m in zip(d[:10],[5,4,3,2,7,6,5,4,3,2])); v=11-s%11
    v={11:0,10:9}.get(v,v)
    return v==int(d[10])
def extraer_cuit(texto):
    if not texto: return ""
    t=re.sub(r'\s+',' ',texto)
    for m in re.finditer(r'\b(\d{2})\s?-\s?(\d{7,8})\s?-\s?(\d)\b|\b((?:20|23|24|27|30|33|34)\d{9})\b',t):
        c=m.group(0).replace(' ','')
        if _cuit_ok(c):
            return c
    return ""
def extraer_proveedor(texto):
    if not texto: return ""
    t=re.sub(r'\s+',' ',texto)
    i=t.find('Texto del Aviso'); cuerpo=t[i:] if i>=0 else t
    pats=[r'(?i:ADJUDICATARI[OA])\s*(?:\d+\s*)?[:\-]?\s*',
          r'PROVEEDOR(?:ES)?\s+ADJUDICADO\S*\s*[:\-]?\s*',
          r'(?i:adjudic\w*)[^:;]{0,140}?(?i:a\s+la\s+firma(?:\s+comercial)?(?:\s+que\s+a\s+continuaci[oó]n\s+se\s+detalla)?:?|al\s+oferente|a\s+la\s+empresa|la\s+empresa|al?\s+Sr\.?|a\s+la\s+Sra\.?)\s+',
          r'(?i:adjudic\w*)\s+a\s+(?!favor|la\s|los\s|las\s|el\s)',
          r'(?i:la\s+firma)\s+']
    for p in pats:
        for m in re.finditer(p,cuerpo):
            resto=cuerpo[m.end():m.end()+160]
            resto=re.sub(r'^(?i:Rengl[oó]n(?:es)?\s+N\S*\s*[\d\s,y]+(?:AL\s+\d+)?\s*:\s*)','',resto)
            n=re.match(r'([A-ZÁÉÍÓÚÑ0-9"“][^;]{2,120}?)'+_FIN_NOMBRE,resto)
            if not n: continue
            nom=n.group(1).strip(' ,.-–"“”')
            # conservar sufijo societario con su punto final
            msoc=re.match(r'(.*?\b'+_SOC+r')(?=[\s,\(–\-]|$)',n.group(1).strip())
            if msoc and len(msoc.group(1))>3: nom=msoc.group(1).strip(' ,-–')
            nom=nom.strip(' "“”')
            if len(nom)>3 and not re.match(r'(?i)(los|el|la)\s+rengl',nom):
                return re.sub(r'\s+',' ',nom)
    return ""
def _num(s):
    s=s.strip().rstrip('.,')
    if re.search(r',\d{1,2}$',s): s=s.replace('.','').replace(',','.')
    elif re.search(r'\.\d{1,2}$',s) and s.count('.')==1 and ',' in s: s=s.replace(',','')
    else: s=s.replace('.','').replace(',','')
    try: return float(s)
    except: return None
def extraer_monto(texto):
    if not texto: return ""
    t=re.sub(r'\s+',' ',texto)
    m=re.search(r'(?:MONTO\s+TOTAL\s+ADJUDICADO|TOTAL\s+ADJUDICADO|IMPORTE\s+(?:TOTAL\s+)?ADJUDICADO|MONTO\s+ADJUDICADO|MONTO\s+TOTAL)[^\$\d]{0,40}\$?\s*([\d\.,]{4,})',t,re.I)
    if not m:
        i=t.upper().find('ADJUDIC')
        if i<0: return ""
        m=re.search(r'(?i:por\s+un\s+(?:monto\s+)?total\s+de|monto\s+total)[^\$]{0,200}\$\s*([\d\.]{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d{4,}(?:,\d{1,2})?)(?![\d])',t[i:])
        if not m: m=re.search(r'\$\s*([\d\.]{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d{4,}(?:,\d{1,2})?)(?!\s?\d)',t[i:])
    if m:
        v=_num(m.group(1))
        if v and v>=1000: return "$"+m.group(1).strip().rstrip('.')
    return ""

def normalizar_nombre(nombre):
    if not nombre:
        return ""
    n = nombre.upper().strip()
    for p in ["S.A.U.", "S.A.", "S.R.L.", "S.A.S.", "S.C.", "LTDA.", " SA ", " SRL ", " SE ", "S.E."]:
        n = n.replace(p, " ")
    return re.sub(r'\s+', ' ', n).strip()

def carpeta_mes():
    hoy = datetime.now()
    carpeta = os.path.join("data", hoy.strftime("%Y-%m"))
    os.makedirs(carpeta, exist_ok=True)
    return carpeta

# ─────────────────────────────────────────
# OBTENER TEXTO AVISO BORA
# ─────────────────────────────────────────
def obtener_texto_aviso_bora(aviso_id, fecha_pub):
    fecha_raw = fecha_pub.replace("-", "")
    urls = [
        f"https://www.boletinoficial.gob.ar/pdf/aviso/tercera/{aviso_id}/{fecha_raw}",
        f"https://www.boletinoficial.gob.ar/busqueda/texto?ids={aviso_id}&fecha={fecha_raw}",
        f"https://www.boletinoficial.gob.ar/detalleAviso/tercera/{aviso_id}/{fecha_raw}",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20, verify=False)
            if r.status_code != 200:
                continue
            content_type = r.headers.get("Content-Type", "")
            if "pdf" in content_type.lower():
                try:
                    from pdfminer.high_level import extract_text as pdf_extract
                    texto = pdf_extract(io.BytesIO(r.content))
                    if texto and len(texto) > 30:
                        return texto
                except Exception:
                    pass
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for selector in [
                {"id": "cuerpoAviso"},
                {"id": "textoAviso"},
                {"id": "aviso"},
                {"class": "aviso-cuerpo"},
                {"class": "texto-aviso"},
            ]:
                div = soup.find("div", selector)
                if div:
                    texto = div.get_text(separator=" ", strip=True)
                    if len(texto) > 50:
                        return texto
            texto_completo = soup.get_text(separator=" ", strip=True)
            if any(kw in texto_completo.upper() for kw in ["CUIT", "ADJUDIC", "PROVEEDOR"]):
                return texto_completo
        except Exception as e:
            print(f"  ⚠️ URL texto falló ({url[:60]}): {e}")
    return ""

# ─────────────────────────────────────────
# SCRAPER 1A: BORA - ÍNDICE SECCIÓN 3RA
# ─────────────────────────────────────────
def extraer_bora_licitaciones(fecha=None):
    """
    Índice de la Sección Tercera del BORA para una fecha (YYYY-MM-DD; hoy por defecto).
    Usa la URL con fecha (/seccion/tercera/AAAAMMDD) en lugar de la portada: la portada
    muestra la última edición publicada, así que un feriado o un día sin edición se
    guardaba como si fuera un día nuevo (17 días duplicados entre feb y ago 2026).
    Si esa fecha no tiene edición, devuelve vacío.
    """
    fecha = fecha or datetime.now().strftime("%Y-%m-%d")
    url = f"https://www.boletinoficial.gob.ar/seccion/tercera/{fecha.replace('-', '')}"
    print(f"\n📰 Extrayendo BORA - Sección Tercera (índice del {fecha})...")
    try:
        response = get_con_reintentos(url)
        soup = BeautifulSoup(response.text, "html.parser")

        datos = []
        categoria_actual = ""
        for elem in soup.find_all(["h5", "a"]):
            if elem.name == "h5":
                categoria_actual = elem.text.strip()
            elif elem.name == "a" and "/detalleAviso/tercera/" in elem.get("href", ""):
                href = elem["href"]
                partes = href.strip("/").split("/")
                aviso_id  = partes[-2] if len(partes) >= 2 else ""
                fecha_raw = partes[-1] if len(partes) >= 1 else ""
                fecha_pub = f"{fecha_raw[:4]}-{fecha_raw[4:6]}-{fecha_raw[6:]}" if len(fecha_raw) == 8 else fecha_raw

                lineas = [l.strip() for l in elem.text.strip().split("\n") if l.strip()]

                palabras_tipo = ["Licitación", "Contratación", "Concurso", "Adjudicación",
                                 "Subasta", "Compulsa", "Obra Pública"]

                tipo_proceso = ""
                lineas_organismo = []
                for linea in lineas:
                    if any(p.lower() in linea.lower() for p in palabras_tipo):
                        tipo_proceso = linea
                    else:
                        lineas_organismo.append(linea)

                organismo = " ".join(lineas_organismo).strip()
                organismo = re.sub(r'\s*-\s*$', '', organismo).strip()

                es_adj = "ADJUDICACION" in categoria_actual.upper()

                datos.append({
                    "fecha_extraccion":  datetime.now().strftime("%Y-%m-%d"),
                    "fecha_publicacion": fecha_pub,
                    "organismo":         organismo,
                    "tipo_proceso":      tipo_proceso,
                    "categoria":         categoria_actual,
                    "aviso_id":          aviso_id,
                    "es_adjudicacion":   es_adj,
                    "link":              "https://www.boletinoficial.gob.ar" + href,
                    "fuente":            "BORA Sección 3ra",
                })

        # Solo avisos publicados en la fecha pedida (si no hubo edición, queda vacío)
        datos = [d for d in datos if d["fecha_publicacion"] == fecha]
        if not datos:
            print(f"  ⚠️ El BORA no tiene edición de la Sección Tercera para {fecha}")
            return pd.DataFrame()
        adj = sum(1 for d in datos if d["es_adjudicacion"])
        print(f"  ✅ {len(datos)} avisos ({adj} adjudicaciones, {len(datos)-adj} licitaciones)")
        return pd.DataFrame(datos)

    except Exception as e:
        print(f"  ❌ Error BORA índice: {e}")
        return pd.DataFrame()

# ─────────────────────────────────────────
# SCRAPER 1B: BORA - DETALLE ADJUDICACIONES
# ─────────────────────────────────────────
def extraer_bora_adjudicaciones(df_bora_indice):
    print("\n🏆 Extrayendo detalle Adjudicaciones BORA...")

    if df_bora_indice.empty:
        return pd.DataFrame()

    adjudicaciones = df_bora_indice[df_bora_indice["es_adjudicacion"] == True]
    print(f"  📋 {len(adjudicaciones)} adjudicaciones a procesar")

    datos = []
    for _, row in adjudicaciones.iterrows():
        try:
            time.sleep(1)
            texto = obtener_texto_aviso_bora(row["aviso_id"], row["fecha_publicacion"])

            cuit      = extraer_cuit(texto)
            proveedor = extraer_proveedor(texto)
            monto     = extraer_monto(texto)

            datos.append({
                "fecha_extraccion":      datetime.now().strftime("%Y-%m-%d"),
                "fecha_publicacion":     row["fecha_publicacion"],
                "organismo_contratante": row["organismo"],
                "tipo_proceso":          row["tipo_proceso"],
                "aviso_id":              row["aviso_id"],
                "link":                  row["link"],
                "proveedor_adjudicado":  proveedor,
                "cuit_proveedor":        cuit,
                "monto_adjudicado":      monto,
                "texto_muestra":         texto[:300] if texto else "SIN TEXTO",
                "fuente":                "BORA Adjudicaciones",
            })

            estado = f"✅ CUIT:{cuit}" if cuit else "⚠️ sin CUIT"
            print(f"  {estado} | {proveedor[:40] if proveedor else 'sin proveedor'} | {monto}")

        except Exception as e:
            print(f"  ❌ Error aviso {row['aviso_id']}: {e}")
            datos.append({
                "fecha_extraccion":      datetime.now().strftime("%Y-%m-%d"),
                "fecha_publicacion":     row.get("fecha_publicacion", ""),
                "organismo_contratante": row.get("organismo", ""),
                "tipo_proceso":          row.get("tipo_proceso", ""),
                "aviso_id":              row.get("aviso_id", ""),
                "link":                  row.get("link", ""),
                "proveedor_adjudicado":  "",
                "cuit_proveedor":        "",
                "monto_adjudicado":      "",
                "texto_muestra":         f"ERROR: {e}",
                "fuente":                "BORA Adjudicaciones",
            })

    con_cuit = sum(1 for d in datos if d["cuit_proveedor"])
    print(f"  ✅ {len(datos)} procesadas | {con_cuit} con CUIT extraído")
    return pd.DataFrame(datos)

# ─────────────────────────────────────────
# SCRAPER 2: COMPRAR.GOB.AR
# ─────────────────────────────────────────
def extraer_comprar():
    url = "https://comprar.gob.ar/Compras.aspx?qs=W1HXHGHtH10="
    print("\n🛒 Extrayendo Comprar.gob.ar...")
    try:
        response = get_con_reintentos(url, timeout=60)
        soup  = BeautifulSoup(response.text, "html.parser")
        tabla = soup.find("table", {"id": "ctl00_CPH1_GridListaPliegosAperturaProxima"})

        if not tabla:
            print("  ⚠️ Tabla no encontrada")
            return pd.DataFrame()

        rows  = tabla.find_all("tr")
        datos = []
        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) > 4:
                link_tag  = cols[0].find("a") or cols[1].find("a") or cols[2].find("a")
                href      = link_tag["href"] if link_tag else ""
                link_real = "https://comprar.gob.ar" + href if href.startswith("/") else url

                datos.append({
                    "fecha_extraccion": datetime.now().strftime("%Y-%m-%d"),
                    "nro_proceso":      cols[0].text.strip(),
                    "nombre_proceso":   cols[1].text.strip(),
                    "tipo_proceso":     cols[2].text.strip(),
                    "fecha_apertura":   cols[3].text.strip(),
                    "estado":           cols[4].text.strip(),
                    "unidad_ejecutora": cols[5].text.strip() if len(cols) > 5 else "",
                    "link":             link_real,
                    "fuente":           "Comprar.gob.ar",
                })

        print(f"  ✅ {len(datos)} procesos extraídos")
        return pd.DataFrame(datos)

    except Exception as e:
        print(f"  ❌ Error Comprar: {e}")
        return pd.DataFrame()

# ─────────────────────────────────────────
# SCRAPER 3: PRESUPUESTO ABIERTO (TGN)
# ─────────────────────────────────────────
def extraer_pagos_tgn():
    """
    Extrae pagos TGN usando la API v1 de Presupuesto Abierto.
    Cruce por organismo_norm ya que la API no expone CUIT beneficiario.
    Requiere variable de entorno TGN_TOKEN (Bearer token de presupuestoabierto.gob.ar).
    """
    anio = datetime.now().year
    print("\n💰 Extrayendo Pagos TGN (Presupuesto Abierto API v1)...")

    token = os.environ.get("TGN_TOKEN", "")
    if not token:
        print("  ⚠️ TGN_TOKEN no configurado — omitiendo TGN del cruce")
        print("     Para activar: configurar TGN_TOKEN en GitHub Secrets y Railway")
        return pd.DataFrame()

    url = "https://www.presupuestoabierto.gob.ar/api/v1/credito"
    headers_api = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/csv",
    }
    body = {
        "columns": [
            "ejercicio_presupuestario",
            "jurisdiccion_desc",
            "entidad_desc",
            "unidad_ejecutora_desc",
            "credito_pagado",
            "credito_devengado",
        ]
    }

    try:
        r = requests.post(url, headers=headers_api, json=body, timeout=60, verify=False)
        if r.status_code in (401, 403):
            print(f"  ❌ TGN respondió {r.status_code}: el TGN_TOKEN está vencido o es inválido.")
            print("     Renovarlo en presupuestoabierto.gob.ar y actualizar el secret TGN_TOKEN (GitHub) y la variable en Railway.")
            return pd.DataFrame()
        r.raise_for_status()

        df = pd.read_csv(io.StringIO(r.text), sep=",", on_bad_lines="skip")

        if "ejercicio_presupuestario" in df.columns:
            df = df[df["ejercicio_presupuestario"] == anio].copy()

        if df.empty:
            print(f"  ⚠️ Sin datos para {anio} en TGN")
            return pd.DataFrame()

        # Normalizar nombre organismo para cruce con BORA
        df["organismo_norm"] = (
            df["entidad_desc"].fillna("").str.upper().str.strip()
            + " " +
            df["unidad_ejecutora_desc"].fillna("").str.upper().str.strip()
        ).str.strip()

        df_out = pd.DataFrame({
            "fecha_extraccion": datetime.now().strftime("%Y-%m-%d"),
            "anio":             anio,
            "cuit":             "",   # API v1 no expone CUIT — cruce por organismo
            "beneficiario":     df["entidad_desc"].fillna(""),
            "unidad_ejecutora": df["unidad_ejecutora_desc"].fillna(""),
            "jurisdiccion":     df["jurisdiccion_desc"].fillna(""),
            "monto_pagado":     pd.to_numeric(df["credito_pagado"], errors="coerce").fillna(0),
            "monto_devengado":  pd.to_numeric(df.get("credito_devengado", 0), errors="coerce").fillna(0),
            "organismo_norm":   df["organismo_norm"],
            "fuente":           f"Presupuesto Abierto TGN API v1 {anio}",
        })

        # Deduplicar TGN por organismo_norm (sumar montos si hay duplicados)
        df_out = (
            df_out.groupby("organismo_norm", as_index=False)
            .agg({
                "fecha_extraccion": "first",
                "anio":             "first",
                "cuit":             "first",
                "beneficiario":     "first",
                "unidad_ejecutora": "first",
                "jurisdiccion":     "first",
                "monto_pagado":     "sum",
                "monto_devengado":  "sum",
                "fuente":           "first",
            })
        )

        print(f"  ✅ {len(df_out)} organismos TGN (deduplicados por nombre)")
        return df_out

    except Exception as e:
        print(f"  ❌ TGN API v1 falló: {e}")
        print("  ⚠️ TGN no disponible, se omite del cruce")
        return pd.DataFrame()

# ─────────────────────────────────────────
# CRUCE: Licitaciones → Adjudicadas → Pagos
# Fix: cruce TGN por organismo + deduplicación
# ─────────────────────────────────────────
def cruzar_fuentes(df_adjudicaciones, df_comprar, df_tgn):
    print("\n🔗 Cruzando: Licitaciones → Adjudicadas → Pagos...")

    if df_adjudicaciones.empty:
        print("  ⚠️ Sin adjudicaciones para cruzar")
        return pd.DataFrame()

    # ── Índice TGN por CUIT (si existe) y por organismo_norm ──────────────
    tgn_idx_cuit = {}
    tgn_idx_org  = {}
    if not df_tgn.empty:
        for _, r in df_tgn.iterrows():
            cuit_tgn = str(r.get("cuit", "")).strip()
            org_norm = str(r.get("organismo_norm", "")).strip()
            if cuit_tgn:
                tgn_idx_cuit[cuit_tgn] = r
            if org_norm and org_norm not in tgn_idx_org:
                tgn_idx_org[org_norm] = r

    comprar_lista = df_comprar.to_dict("records") if not df_comprar.empty else []

    STOP_WORDS = {
        "NACIONAL", "GENERAL", "ARGENTINA", "PUBLICA", "ADMINISTRACION",
        "DIRECCION", "SECRETARIA", "MINISTERIO", "AGENCIA", "INSTITUTO",
        "FEDERAL", "REPUBLICA", "ESTADO", "SERVICIO", "OFICINA", "SOCIAL",
    }

    def buscar_tgn_por_organismo(organismo):
        """Busca en TGN por similitud de nombre — retorna el mejor match único."""
        if not organismo or not tgn_idx_org:
            return None
        palabras = [
            p for p in normalizar_nombre(organismo).split()
            if len(p) > 3 and p not in STOP_WORDS
        ]
        if not palabras:
            return None
        mejor_match = None
        mejor_score = 0
        for org_norm, row in tgn_idx_org.items():
            coincidencias = sum(1 for p in palabras if p in org_norm)
            if coincidencias > mejor_score and coincidencias >= 2:
                mejor_score = coincidencias
                mejor_match = row
        return mejor_match

    resultados = []
    for _, adj in df_adjudicaciones.iterrows():
        cuit      = str(adj.get("cuit_proveedor", "")).strip()
        proveedor = adj.get("proveedor_adjudicado", "")
        organismo = adj.get("organismo_contratante", "")

        # ── Cruce Comprar ──────────────────────────────────────────────────
        comprar_matches = []
        if organismo:
            palabras = [
                p for p in normalizar_nombre(organismo).split()
                if len(p) > 3 and p not in STOP_WORDS
            ]
            for c in comprar_lista:
                unidad_norm   = normalizar_nombre(c.get("unidad_ejecutora", ""))
                coincidencias = sum(1 for p in palabras if p in unidad_norm)
                if coincidencias >= 2:
                    comprar_matches.append(c)

        # ── Cruce TGN: primero por CUIT, luego por organismo ──────────────
        tgn_match = None
        metodo_cruce = ""
        if cuit:
            tgn_match = tgn_idx_cuit.get(cuit)
            if tgn_match is not None:
                metodo_cruce = "CUIT"
        if tgn_match is None:
            tgn_match = buscar_tgn_por_organismo(organismo)
            if tgn_match is not None:
                metodo_cruce = "organismo"

        en_comprar = len(comprar_matches) > 0
        en_tgn     = tgn_match is not None

        # El cruce con TGN es casi siempre por ORGANISMO (la API de Presupuesto Abierto
        # no trae CUIT del beneficiario): indica que el organismo contratante tiene
        # pagos ejecutados en el año, no que este proveedor haya cobrado.
        if cuit and en_tgn and metodo_cruce == "CUIT":
            etapa = "💰 ADJUDICADO + COBRÓ"
        elif cuit and en_tgn:
            etapa = "💰 ADJUDICADO + ORGANISMO CON PAGOS TGN"
        elif cuit and en_comprar:
            etapa = "📋 ADJUDICADO + EN COMPRAR"
        elif cuit:
            etapa = "✅ ADJUDICADO (sin pago aún)"
        else:
            etapa = "⚠️ SIN CUIT EXTRAÍDO"

        if en_comprar and en_tgn and cuit:
            alerta = "🚨 FLUJO COMPLETO: BORA→COMPRAR→TGN"
        elif en_tgn and cuit and metodo_cruce == "CUIT":
            alerta = "🔶 BORA + TGN (cobró)"
        elif en_tgn:
            alerta = "🔶 BORA + TGN (por organismo)"
        elif en_comprar:
            alerta = "🔷 BORA + COMPRAR"
        else:
            alerta = "📋 SOLO BORA"

        resultados.append({
            "fecha":                    adj.get("fecha_publicacion") or adj.get("fecha_extraccion"),
            "organismo_contratante":    organismo,
            "tipo_proceso_bora":        adj.get("tipo_proceso"),
            "link_bora":                adj.get("link"),
            "proveedor_adjudicado":     proveedor,
            "cuit_proveedor":           cuit,
            "monto_adjudicado_bora":    adj.get("monto_adjudicado"),
            "en_comprar":               "✅ SÍ" if en_comprar else "❌ NO",
            "procesos_comprar":         len(comprar_matches),
            "unidad_comprar":           comprar_matches[0].get("unidad_ejecutora", "") if comprar_matches else "",
            "nro_proceso_comprar":      comprar_matches[0].get("nro_proceso", "") if comprar_matches else "",
            "cobro_en_tgn":             "✅ SÍ" if en_tgn else "❌ NO",
            "beneficiario_tgn":         tgn_match["beneficiario"] if en_tgn else "",
            # Crédito pagado del ORGANISMO en el año, en millones de pesos (Presupuesto Abierto)
            "monto_cobrado_tgn":        tgn_match["monto_pagado"] if en_tgn else "",
            "metodo_cruce_tgn":         metodo_cruce,
            "etapa":                    etapa,
            "alerta":                   alerta,
        })

    df = pd.DataFrame(resultados)

    # ── Deduplicar: un organismo+cuit no debe aparecer más de una vez ──────
    if not df.empty:
        # Se incluye el link del aviso: sin él, dos adjudicaciones distintas del mismo
        # organismo sin CUIT extraído se fusionaban (≈79 avisos perdidos feb-oct 2026).
        df = df.drop_duplicates(
            subset=["organismo_contratante", "cuit_proveedor", "fecha", "link_bora"],
            keep="first"
        ).reset_index(drop=True)

    if not df.empty:
        orden = {
            "🚨 FLUJO COMPLETO: BORA→COMPRAR→TGN": 0,
            "🔶 BORA + TGN (cobró)":               1,
            "🔶 BORA + TGN (por organismo)":        2,
            "🔷 BORA + COMPRAR":                   3,
            "📋 SOLO BORA":                        4,
        }
        df["_orden"] = df["alerta"].map(orden).fillna(9)
        df = df.sort_values("_orden").drop(columns=["_orden"]).reset_index(drop=True)

    print(f"  ✅ {len(df)} registros en el flujo (deduplicados)")
    if not df.empty:
        for alerta, count in df["alerta"].value_counts().items():
            print(f"     {alerta}: {count}")
    return df

# ─────────────────────────────────────────
# GUARDAR DOS EXCELS
# ─────────────────────────────────────────
def guardar_excels(df_cruce, df_adjudicaciones, df_licitaciones, df_comprar, df_tgn):
    carpeta = carpeta_mes()
    hoy     = datetime.now().strftime("%Y-%m-%d")

    df_cruce_con_riesgo = pd.DataFrame()
    if not df_cruce.empty:
        print("\n🔬 Aplicando Matriz de Riesgo Licitatorio...")
        df_cruce_con_riesgo = analizar_adjudicaciones(df_cruce, df_tgn)

    # ── Excel 1: Reporte operativo completo ──
    archivo1 = os.path.join(carpeta, f"reporte_{hoy}.xlsx")
    with pd.ExcelWriter(archivo1, engine="openpyxl") as writer:
        hojas_e1 = 0
        if not df_cruce_con_riesgo.empty:
            df_cruce_con_riesgo.to_excel(writer, sheet_name="🚨 Flujo Completo", index=False)
        elif not df_cruce.empty:
            df_cruce.to_excel(writer, sheet_name="🚨 Flujo Completo", index=False)
        if not df_adjudicaciones.empty:
            df_adjudicaciones.to_excel(writer, sheet_name="🏆 Adjudicaciones", index=False)
            hojas_e1 += 1
        if not df_licitaciones.empty:
            df_licitaciones.to_excel(writer, sheet_name="📰 BORA Licitaciones", index=False)
            hojas_e1 += 1
        if not df_comprar.empty:
            df_comprar.to_excel(writer, sheet_name="🛒 Comprar", index=False)
            hojas_e1 += 1
        if not df_tgn.empty:
            df_tgn.to_excel(writer, sheet_name="💰 TGN", index=False)
            hojas_e1 += 1
        if not df_cruce_con_riesgo.empty:
            cols_riesgo = [
                "fecha", "organismo_contratante", "tipo_proceso_bora",
                "cuit_proveedor", "monto_adjudicado_bora",
                "indicadores_riesgo", "score_riesgo_licit",
                "indice_riesgo_licit", "nivel_riesgo_licit",
                "etapa", "alerta", "link_bora",
            ]
            cols_presentes = [c for c in cols_riesgo if c in df_cruce_con_riesgo.columns]
            df_alertas = df_cruce_con_riesgo[cols_presentes].sort_values(
                "indice_riesgo_licit", ascending=False
            )
            df_alertas.to_excel(writer, sheet_name="⚠️ Riesgo Licitatorio", index=False)
            hojas_e1 += 1
        if hojas_e1 == 0:
            pd.DataFrame({
                "estado":  ["Sin datos — todos los servicios externos fallaron"],
                "fecha":   [datetime.now().strftime("%Y-%m-%d %H:%M")],
                "detalle": ["BORA / Comprar / TGN no respondieron. Reintentar mañana."],
            }).to_excel(writer, sheet_name="Sin Datos", index=False)
            print("  ⚠️  Todos los scrapers fallaron — hoja de estado guardada")
    print(f"  ✅ Reporte completo: {archivo1}")

    # ── Excel 2: Flujo Licitación→Adjudicación→Pago ──
    archivo2 = os.path.join(carpeta, f"flujo_licitaciones_{hoy}.xlsx")
    df_flujo = df_cruce_con_riesgo if not df_cruce_con_riesgo.empty else df_cruce
    with pd.ExcelWriter(archivo2, engine="openpyxl") as writer:
        if not df_adjudicaciones.empty:
            df_con_cuit = df_adjudicaciones[
                df_adjudicaciones["cuit_proveedor"].astype(bool)
            ].copy()
            if not df_con_cuit.empty:
                df_con_cuit.to_excel(writer, sheet_name="✅ Adjudicados con CUIT", index=False)

        if not df_flujo.empty:
            df_flujo.to_excel(writer, sheet_name="🔗 Flujo Cruzado", index=False)

        if not df_flujo.empty:
            df_cobro = df_flujo[df_flujo["cobro_en_tgn"] == "✅ SÍ"].copy()
            if not df_cobro.empty:
                df_cobro.to_excel(writer, sheet_name="💰 Cobraron en TGN", index=False)

        if not df_comprar.empty:
            df_comprar.to_excel(writer, sheet_name="⏳ Licitaciones Abiertas", index=False)

        if not df_cruce_con_riesgo.empty:
            df_alto_riesgo = df_cruce_con_riesgo[
                df_cruce_con_riesgo["nivel_riesgo_licit"].isin(["Alto", "Medio"])
            ].copy()
            if not df_alto_riesgo.empty:
                df_alto_riesgo = df_alto_riesgo.sort_values("indice_riesgo_licit", ascending=False)
                df_alto_riesgo.to_excel(writer, sheet_name="⚠️ Alertas Riesgo", index=False)

        hojas_e2 = sum([
            not df_adjudicaciones.empty and df_adjudicaciones["cuit_proveedor"].astype(bool).any(),
            not df_flujo.empty,
            not df_comprar.empty,
        ])
        if hojas_e2 == 0:
            pd.DataFrame({
                "estado":  ["Sin datos — todos los servicios externos fallaron"],
                "fecha":   [datetime.now().strftime("%Y-%m-%d %H:%M")],
                "detalle": ["BORA / Comprar / TGN no respondieron. Reintentar mañana."],
            }).to_excel(writer, sheet_name="Sin Datos", index=False)

    print(f"  ✅ Flujo licitaciones: {archivo2}")
    return archivo1, archivo2

# ─────────────────────────────────────────
# EJECUCIÓN PRINCIPAL
# ─────────────────────────────────────────
if __name__ == "__main__":
    hoy = datetime.now()

    try:
        import holidays
        feriados_ar = holidays.Argentina(years=hoy.year)
        es_feriado = hoy.date() in feriados_ar
        nombre_feriado = feriados_ar.get(hoy.date(), "")
    except ImportError:
        es_feriado = False
        nombre_feriado = ""

    if hoy.weekday() >= 5:
        dia = "sábado" if hoy.weekday() == 5 else "domingo"
        print(f"⏭️  Hoy es {dia} {hoy.strftime('%Y-%m-%d')} — los organismos no publican en fin de semana.")
        print("   Script finalizado sin ejecutar scrapers.")
        exit(0)

    if es_feriado:
        print(f"⏭️  Hoy es feriado nacional: '{nombre_feriado}' ({hoy.strftime('%Y-%m-%d')}) — los organismos no publican.")
        print("   Script finalizado sin ejecutar scrapers.")
        exit(0)

    # Segunda corrida del día (reintento): si el reporte de hoy ya tiene datos del BORA, no rehacer
    _rep_hoy = os.path.join("data", hoy.strftime("%Y-%m"), f"reporte_{hoy.strftime('%Y-%m-%d')}.xlsx")
    if os.path.exists(_rep_hoy):
        print(f"✅ El reporte de hoy ya existe ({_rep_hoy}) — nada que reintentar.")
        exit(0)

    print("🚀 Ciclo Integrado: BORA + Comprar + TGN")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    try:
        import pdfminer
    except ImportError:
        print("📦 Instalando pdfminer.six...")
        os.system("pip install pdfminer.six -q")

    df_bora_indice    = extraer_bora_licitaciones()
    if df_bora_indice.empty:
        # Sin edición del BORA (feriado) o el sitio no respondió: no se guarda un reporte
        # vacío; la segunda corrida programada del día vuelve a intentar.
        print("⏭️  Sin avisos del BORA para hoy — no se genera reporte.")
        exit(0)
    df_adjudicaciones = extraer_bora_adjudicaciones(df_bora_indice)

    df_licitaciones = pd.DataFrame()
    if not df_bora_indice.empty:
        df_licitaciones = df_bora_indice[
            df_bora_indice["es_adjudicacion"] == False
        ].copy().reset_index(drop=True)

    df_comprar = extraer_comprar()
    df_tgn     = extraer_pagos_tgn()
    df_cruce   = cruzar_fuentes(df_adjudicaciones, df_comprar, df_tgn)

    guardar_excels(df_cruce, df_adjudicaciones, df_licitaciones, df_comprar, df_tgn)

    con_cuit = 0
    if not df_adjudicaciones.empty:
        con_cuit = df_adjudicaciones["cuit_proveedor"].astype(bool).sum()

    alto_riesgo = medio_riesgo = 0
    if not df_cruce.empty and "nivel_riesgo_licit" in df_cruce.columns:
        alto_riesgo  = (df_cruce["nivel_riesgo_licit"] == "Alto").sum()
        medio_riesgo = (df_cruce["nivel_riesgo_licit"] == "Medio").sum()

    print("\n📊 RESUMEN FINAL:")
    print(f"   Licitaciones BORA:  {len(df_licitaciones)}")
    print(f"   Adjudicaciones:     {len(df_adjudicaciones)} ({con_cuit} con CUIT)")
    print(f"   Procesos Comprar:   {len(df_comprar)}")
    print(f"   Beneficiarios TGN:  {len(df_tgn)}")
    print(f"   Flujo cruzado:      {len(df_cruce)}")
    print(f"   ⚠️  Riesgo Alto:    {alto_riesgo}")
    print(f"   🟡 Riesgo Medio:   {medio_riesgo}")

    # ── Persistir en PostgreSQL ──────────────────────────────────────────────
    try:
        from db_reportes import guardar_en_db
        indice_prom = 0.0
        if not df_cruce.empty and "indice_riesgo_licit" in df_cruce.columns:
            import pandas as _pd
            indice_prom = round(float(_pd.to_numeric(
                df_cruce["indice_riesgo_licit"], errors="coerce").mean() or 0), 2)
        guardar_en_db(
            fecha_str   = hoy.strftime("%Y-%m-%d"),
            resumen     = {
                "total_licit":     len(df_licitaciones),
                "total_adj":       len(df_adjudicaciones),
                "adj_con_cuit":    int(con_cuit),
                "total_comprar":   len(df_comprar),
                "total_tgn":       len(df_tgn),
                "total_cruce":     len(df_cruce),
                "flujo_completo":  int((df_cruce["alerta"] == "🚨 FLUJO COMPLETO: BORA→COMPRAR→TGN").sum())
                                   if not df_cruce.empty and "alerta" in df_cruce.columns else 0,
                "riesgo_alto":     int(alto_riesgo),
                "riesgo_medio":    int(medio_riesgo),
                "riesgo_bajo":     int((df_cruce["nivel_riesgo_licit"] == "Bajo").sum())
                                   if not df_cruce.empty and "nivel_riesgo_licit" in df_cruce.columns else 0,
                "indice_promedio": indice_prom,
            },
            df_cruce    = df_cruce    if not df_cruce.empty    else None,
            df_bora     = df_bora_indice if not df_bora_indice.empty else None,
            df_comprar  = df_comprar  if not df_comprar.empty  else None,
        )
    except Exception as _e:
        print(f"⚠️  DB no disponible (xlsx guardados igualmente): {_e}")