"""
agentic_ai.py
=============
Prototipo de "agentic AI" sobre el sistema de reglas existente (MATRIZ_TEORICA
y MATRIZ_LICITACIONES en analisis.py). Esas matrices clasifican por keywords
fijas y umbrales numéricos: son auditables y deterministas, pero rígidas — un
aviso redactado con sinónimos no listados no dispara ninguna alerta (ver
test_auditoria.py::test_cobertura_demografica, que ya prueba casos límite de
este tipo).

Este módulo agrega una segunda opinión con Claude para:
  1) clasificar el texto de un aviso BORA en las 7 categorías de la Teoría de
     Fenómenos Corruptivos, con razonamiento en lenguaje natural, y
  2) redactar una explicación legible de por qué una adjudicación quedó
     marcada con riesgo Alto/Medio, citando los indicadores que YA calculó la
     matriz de reglas (no inventa indicadores nuevos).

No reemplaza la matriz de reglas — la complementa. La matriz sigue siendo la
fuente de verdad para el score numérico (auditable, reproducible); la IA
aporta cobertura de casos ambiguos y una narrativa entendible para el usuario
del dashboard.

Degrada sin romper nada si falta ANTHROPIC_API_KEY o el paquete `anthropic`:
las funciones devuelven {"disponible": False, "motivo": "..."} en vez de
lanzar una excepción, para que el resto de la app (scraping, matriz de
reglas, dashboard) siga funcionando igual sin IA configurada.
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

try:
    import anthropic
    _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
except ImportError:
    anthropic = None
    _client = None


def ia_disponible() -> bool:
    return _client is not None


CATEGORIAS_VALIDAS = [
    "Privatización / Concesión",
    "Obra Pública / Contratos",
    "Tarifas Servicios Públicos",
    "Precios de Consumo Regulados",
    "Salarios y Paritarias",
    "Jubilaciones / Pensiones",
    "Traslado de Impuestos",
    "No identificado",
]

_SYSTEM_PROMPT_CLASIFICAR = """Sos un asistente de auditoría que aplica la \
Teoría de Fenómenos Corruptivos del Ph.D. Vicente Humberto Monteverde \
(Journal of Financial Crime, 2020) sobre avisos oficiales del Estado \
argentino (BORA, Comprar.gob.ar, TGN).

Tu tarea es clasificar el texto en una de estas 7 categorías (o \
"No identificado" si no aplica ninguna), y explicar tu razonamiento en 2-3 \
oraciones en español, citando frases concretas del texto. No acuses a nadie \
de un delito: hablás de "fenómenos corruptivos legales" (transferencias \
regresivas de ingresos derivadas de decisiones discrecionales del Estado), \
no de corrupción penal ni de responsabilidad individual.

Categorías:
- Privatización / Concesión (Estado a Privados)
- Obra Pública / Contratos (Estado a Empresas)
- Tarifas Servicios Públicos (Usuarios a Concesionarias)
- Precios de Consumo Regulados (Consumidores a Productores)
- Salarios y Paritarias (Asalariados a Empleadores)
- Jubilaciones / Pensiones (Jubilados al Estado)
- Traslado de Impuestos (Contribuyentes al Estado)

Respondé ÚNICAMENTE con un JSON válido, sin texto adicional, con esta forma
exacta:
{"categoria": "...", "confianza": 0.0, "explicacion": "..."}
"""


def clasificar_aviso_ia(texto: str, clasificacion_reglas: str = "") -> dict:
    """
    Clasifica un aviso con Claude como segunda opinión sobre la matriz de
    keywords (MATRIZ_TEORICA en analisis.py). `clasificacion_reglas` es lo que
    ya determinaron las reglas — se lo pasamos al modelo como contexto (no
    como respuesta esperada) para que pueda coincidir o corregir.
    """
    if not ia_disponible():
        return {
            "disponible": False,
            "motivo": "ANTHROPIC_API_KEY no configurada o paquete 'anthropic' no instalado",
        }
    if not texto or not texto.strip():
        return {"disponible": False, "motivo": "texto vacío"}

    user_msg = (
        f"Clasificación previa por reglas (keywords): {clasificacion_reglas or 'No identificado'}\n\n"
        f"Texto del aviso:\n{texto[:4000]}"
    )
    try:
        resp = _client.messages.create(
            model=MODEL,
            max_tokens=400,
            system=_SYSTEM_PROMPT_CLASIFICAR,
            messages=[{"role": "user", "content": user_msg}],
        )
        bruto = resp.content[0].text.strip()
        if bruto.startswith("```"):
            bruto = bruto.strip("`")
            bruto = bruto[bruto.find("{"):]
        data = json.loads(bruto)
        categoria = data.get("categoria", "No identificado")
        if categoria not in CATEGORIAS_VALIDAS:
            categoria = "No identificado"
        return {
            "disponible": True,
            "categoria": categoria,
            "confianza": float(data.get("confianza", 0) or 0),
            "explicacion": data.get("explicacion", ""),
            "modelo": MODEL,
        }
    except Exception as e:
        logger.warning(f"⚠️ agentic_ai.clasificar_aviso_ia falló: {e}")
        return {"disponible": False, "motivo": str(e)}


def explicar_riesgo_licitacion(fila: dict) -> dict:
    """
    Redacta en lenguaje natural por qué una adjudicación quedó con nivel de
    riesgo Alto/Medio en la Matriz de Riesgo Licitatorio (analizar_adjudicaciones
    en analisis.py), a partir de los indicadores que YA calculó esa función.
    No inventa indicadores nuevos ni monto/organismo — solo explica los que
    recibe.
    """
    if not ia_disponible():
        return {
            "disponible": False,
            "motivo": "ANTHROPIC_API_KEY no configurada o paquete 'anthropic' no instalado",
        }

    resumen = (
        f"Organismo: {fila.get('organismo_contratante', 'n/a')}\n"
        f"Tipo de proceso BORA: {fila.get('tipo_proceso_bora', 'n/a')}\n"
        f"Monto adjudicado: {fila.get('monto_adjudicado_bora', 'n/a')}\n"
        f"Indicadores de riesgo detectados por la matriz de reglas: {fila.get('indicadores_riesgo', 'n/a')}\n"
        f"Índice de riesgo: {fila.get('indice_riesgo_licit', 'n/a')}/10 "
        f"({fila.get('nivel_riesgo_licit', 'n/a')})\n"
        f"Etapa del flujo: {fila.get('etapa', 'n/a')} | Alerta: {fila.get('alerta', 'n/a')}"
    )
    try:
        resp = _client.messages.create(
            model=MODEL,
            max_tokens=300,
            system=(
                "Redactá en español, en un párrafo breve (3-4 oraciones), por qué "
                "este proceso de contratación pública quedó marcado con ese nivel "
                "de riesgo, basándote ÚNICAMENTE en los indicadores que te paso — "
                "no inventes datos ni acuses de delitos, hablá de 'indicadores de "
                "riesgo' y 'fenómenos corruptivos legales', no de corrupción penal "
                "ni de responsabilidad individual."
            ),
            messages=[{"role": "user", "content": resumen}],
        )
        return {"disponible": True, "explicacion": resp.content[0].text.strip(), "modelo": MODEL}
    except Exception as e:
        logger.warning(f"⚠️ agentic_ai.explicar_riesgo_licitacion falló: {e}")
        return {"disponible": False, "motivo": str(e)}
