"""
Tests de extensiones/dataset.py, extensiones/marco_normativo.py y del arreglo de
agentic_ai.py (respuestas que empiezan con un bloque de razonamiento).

Ningún test sale a la red: GitHub y la API de Anthropic se reemplazan por dobles.
Los routers se montan en una app mínima con DATA_DIR en una carpeta temporal.
"""
import io
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import agentic_ai
import main
from extensiones import dataset, marco_normativo


def _xlsx(hojas: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for nombre, filas in hojas.items():
            pd.DataFrame(filas).to_excel(w, sheet_name=nombre, index=False)
    return buf.getvalue()


REPORTE = _xlsx({
    "📰 BORA Licitaciones": [
        {"organismo": "ARMADA ARGENTINA", "tipo_proceso": "Licitación Pública 0502/2026",
         "categoria": "OBRAS - CIVILES", "aviso_id": "1"},
        {"organismo": "EMPRESA ARGENTINA DE NAVEGACIÓN AÉREA S.E.",
         "tipo_proceso": "Contratación Directa (MODO V) 05/2026", "categoria": "SUMINISTROS - EFECTOS VARIOS",
         "aviso_id": "2"},
    ],
    "🏆 Adjudicaciones": [
        {"organismo_contratante": "MINISTERIO DE SALUD", "tipo_proceso": "Contratación Directa 10/2026",
         "proveedor_adjudicado": "X S.A.", "cuit_proveedor": "30-71593557-7",
         "monto_adjudicado": "$46.440.000,00", "aviso_id": "3"},
    ],
})


@pytest.fixture
def datos(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(main, "ADMIN_KEY", "clave-test")
    monkeypatch.setenv("RESPALDOS_DIR", str(tmp_path / "respaldos"))
    dataset._estado.update({"corriendo": False, "ultima": None, "_t": 0.0})
    return tmp_path / "data"


@pytest.fixture
def cliente(datos):
    app = FastAPI()
    app.include_router(dataset.router)
    app.include_router(marco_normativo.router)
    return TestClient(app)


def _github(monkeypatch, archivos: dict, rotos=()):
    """Simula el árbol de la rama y raw.githubusercontent.com con `archivos` {ruta: bytes}."""
    def listar(desde=None):
        out = []
        for ruta, contenido in archivos.items():
            m = dataset._RUTA_DATASET.match(ruta)
            if m and (not desde or m.group(3) >= desde):
                out.append({"ruta": ruta, "mes": m.group(1), "nombre": m.group(2),
                            "fecha": m.group(3), "sha": dataset.sha_blob(contenido)})
        return out
    bajados = []

    def descargar(ruta):
        bajados.append(ruta)
        return b"corrupto" if ruta in rotos else archivos[ruta]
    monkeypatch.setattr(dataset, "listar_publicados", listar)
    monkeypatch.setattr(dataset, "_descargar", descargar)
    return bajados


# ── Dataset ──────────────────────────────────────────────────────────────────
def test_sha_blob_coincide_con_git():
    # `git hash-object` de un archivo con "hola\n"
    assert dataset.sha_blob(b"hola\n") == "5c1b14949828006ed75a3e8858957f86a2f7e2eb"


def test_sincroniza_solo_lo_que_falta_y_no_vuelve_a_bajar(datos, monkeypatch):
    ruta = "data/2026-11/reporte_2026-11-02.xlsx"
    bajados = _github(monkeypatch, {ruta: REPORTE, "data/otra_cosa.xlsx": b"x"})
    r = dataset.sincronizar_desde_github(str(datos))
    assert r["nuevos"] == ["reporte_2026-11-02.xlsx"] and r["ultimo_dia_publicado"] == "2026-11-02"
    assert (datos / "2026-11" / "reporte_2026-11-02.xlsx").read_bytes() == REPORTE
    r2 = dataset.sincronizar_desde_github(str(datos))
    assert r2["nuevos"] == [] and r2["actualizados"] == [] and bajados == [ruta]


def test_archivo_que_no_coincide_con_el_publicado_no_se_guarda(datos, monkeypatch):
    ruta = "data/2026-11/reporte_2026-11-02.xlsx"
    _github(monkeypatch, {ruta: REPORTE}, rotos={ruta})
    r = dataset.sincronizar_desde_github(str(datos))
    assert r["nuevos"] == [] and r["errores"][0]["archivo"] == "reporte_2026-11-02.xlsx"
    assert not (datos / "2026-11").exists() or not any((datos / "2026-11").iterdir())


def test_archivo_cambiado_se_respalda_y_reemplaza(datos, monkeypatch, tmp_path):
    (datos / "2026-11").mkdir(parents=True)
    (datos / "2026-11" / "reporte_2026-11-02.xlsx").write_bytes(b"version vieja")
    _github(monkeypatch, {"data/2026-11/reporte_2026-11-02.xlsx": REPORTE})
    r = dataset.sincronizar_desde_github(str(datos))
    assert r["actualizados"] == ["reporte_2026-11-02.xlsx"]
    assert any((tmp_path / "respaldos" / "2026-11").iterdir())


def test_endpoint_actualizar_devuelve_resumen_y_respeta_la_espera(cliente, monkeypatch):
    bajados = _github(monkeypatch, {"data/2026-11/reporte_2026-11-02.xlsx": REPORTE})
    r = cliente.post("/api/datos/actualizar")
    assert r.status_code == 200
    d = r.json()
    assert d["fecha"] == "2026-11-02"
    assert d["resumen"]["licitaciones_bora"] == 2 and d["resumen"]["adjudicaciones_con_cuit"] == 1
    r2 = cliente.post("/api/datos/actualizar")
    assert r2.json()["reciente"] is True and len(bajados) == 1


def test_endpoint_actualizar_informa_si_github_falla(cliente, monkeypatch):
    def falla(desde=None):
        raise RuntimeError("sin red")
    monkeypatch.setattr(dataset, "listar_publicados", falla)
    r = cliente.post("/api/datos/actualizar")
    assert r.status_code == 502 and "sin red" in r.json()["detail"]


def test_subir_reporte_pide_clave_y_valida_el_excel(cliente, datos):
    url = "/api/admin/subir-reporte?fecha=2026-11-02&tipo=reporte"
    assert cliente.post(url, content=REPORTE).status_code == 403
    malo = cliente.post(url, content=b"no es excel", headers={"X-Admin-Key": "clave-test"})
    assert malo.status_code == 422
    otro = _xlsx({"Hoja1": [{"a": 1}]})
    assert cliente.post(url, content=otro, headers={"X-Admin-Key": "clave-test"}).status_code == 422
    ok = cliente.post(url, content=REPORTE, headers={"X-Admin-Key": "clave-test"})
    assert ok.status_code == 200 and ok.json()["reemplazado"] is False
    assert (datos / "2026-11" / "reporte_2026-11-02.xlsx").read_bytes() == REPORTE
    assert cliente.post(url, content=REPORTE, headers={"X-Admin-Key": "clave-test"}).json()["reemplazado"] is True


# ── Marco normativo ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("valor,esperado", [
    ("$25.771.802,52", 25771802.52), ("1.234.567", 1234567.0), ("$ 1500", 1500.0), ("", None), ("s/d", None),
])
def test_parsear_monto(valor, esperado):
    assert marco_normativo.parsear_monto(valor) == esperado


@pytest.mark.parametrize("organismo,propio", [
    ("EMPRESA ARGENTINA DE NAVEGACIÓN AÉREA S.E.", True),
    ("FABRICACIONES MILITARES SOCIEDAD ANÓNIMA UNIPERSONAL", True),
    ("HOSPITAL DE PEDIATRÍA S.A.M.I.C. “PROF. DR. JUAN P. GARRAHAN”", True),
    ("PODER JUDICIAL DE LA NACIÓN - CONSEJO DE LA MAGISTRATURA", True),
    ("UNIVERSIDAD NACIONAL DEL LITORAL", True),
    ("ARMADA ARGENTINA", False),
    ("MINISTERIO DE SALUD", False),
    ("AGENCIA DE ADMINISTRACIÓN DE BIENES DEL ESTADO", False),
])
def test_ambito_subjetivo(organismo, propio):
    assert bool(marco_normativo.regimen_propio(organismo)) is propio


def test_regimen_y_procedimiento():
    obra = marco_normativo.evaluar_aviso({"organismo": "ARMADA ARGENTINA", "categoria": "OBRAS - CIVILES",
                                          "tipo_proceso": "Licitación Pública 0502/2026"})
    assert obra["regimen"] == "obra_publica" and obra["plataforma"] == "CONTRAT.AR"
    assert "Ley 13.064" in obra["normas"] and obra["alertas"] == []
    venta = marco_normativo.evaluar_aviso({"categoria": "VENTAS Y OFRECIMIENTOS DEL ESTADO - VARIOS",
                                           "tipo_proceso": "Subasta Pública 392-0055-SPU26"})
    assert venta["regimen"] == "venta_estado" and venta["procedimiento"] == "subasta"
    directa = marco_normativo.evaluar_aviso({"organismo_contratante": "MINISTERIO DE SALUD",
                                             "tipo_proceso": "Contratación Directa 10/2026",
                                             "monto_adjudicado": "$46.440.000,00"})
    assert directa["procedimiento"] == "contratacion_directa"
    assert directa["monto_modulos"] == round(46440000 / marco_normativo.VALOR_MODULO, 1)
    assert any("causal" in a for a in directa["alertas"])


def test_topes_solo_si_se_configuran(monkeypatch):
    fila = {"organismo": "MINISTERIO DE SALUD", "tipo_proceso": "Contratación Directa 1/2026",
            "monto_adjudicado": "$46.440.000,00"}
    assert not any("tope" in a for a in marco_normativo.evaluar_aviso(fila)["alertas"])
    monkeypatch.setenv("NORMATIVA_TOPES_MODULOS", '{"contratacion_directa": 100}')
    assert any("tope" in a for a in marco_normativo.evaluar_aviso(fila)["alertas"])
    monkeypatch.setenv("NORMATIVA_TOPES_MODULOS", "no es json")
    assert marco_normativo._topes() == {}


def test_catalogo_con_correcciones_y_estado():
    normas = {n["id"]: n for n in marco_normativo.NORMAS}
    assert "CONTRAT.AR" in normas["dec-1336-2016"]["nombre"]
    assert normas["ley-27437"]["estado"] == "parcialmente derogada"
    assert all(n["estado"] in ("verificada", "parcialmente derogada", "sin verificar") for n in normas.values())


def test_endpoint_normativa_del_dia(cliente, datos):
    (datos / "2026-11").mkdir(parents=True)
    (datos / "2026-11" / "reporte_2026-11-02.xlsx").write_bytes(REPORTE)
    d = cliente.get("/api/licitaciones/normativa").json()
    assert d["fecha"] == "2026-11-02" and d["resumen"]["avisos"] == 3
    assert d["resumen"]["regimen_propio"] == 1
    assert cliente.get("/api/licitaciones/normativa?fecha=2026-01-01").json()["sin_datos"] is True
    assert cliente.get("/api/licitaciones/normativa?fecha=mal").status_code == 400
    assert cliente.get("/api/marco-normativo").json()["modulo"]["valor"] == marco_normativo.VALOR_MODULO


def test_pagina_marco_normativo(cliente):
    r = cliente.get("/marco-normativo")
    assert r.status_code == 200 and "Decreto 1336/2016" in r.text


# ── IA: respuestas con bloque de razonamiento ────────────────────────────────
class _ClienteFalso:
    def __init__(self, contenido, stop_reason="end_turn"):
        self.pedidos = []
        self.messages = SimpleNamespace(create=self._crear)
        self._resp = SimpleNamespace(content=contenido, stop_reason=stop_reason)

    def _crear(self, **kwargs):
        self.pedidos.append(kwargs)
        return self._resp


def _bloque(tipo, **campos):
    return SimpleNamespace(type=tipo, **campos)


def test_explicar_riesgo_ignora_el_bloque_de_razonamiento(monkeypatch):
    falso = _ClienteFalso([_bloque("thinking", thinking=""), _bloque("text", text=" Explicación. ")])
    monkeypatch.setattr(agentic_ai, "_client", falso)
    monkeypatch.setattr(agentic_ai, "MODEL", "claude-sonnet-5-5")
    r = agentic_ai.explicar_riesgo_licitacion({"organismo_contratante": "X"})
    assert r == {"disponible": True, "explicacion": "Explicación.", "modelo": "claude-sonnet-5-5"}
    assert falso.pedidos[0]["thinking"] == {"type": "between_tools"}
    assert agentic_ai.ULTIMA_CONSULTA["ok"] is True


def test_clasificar_lee_json_y_otro_modelo_no_recibe_thinking(monkeypatch):
    texto = '{"categoria": "Obra Pública / Contratos", "confianza": 0.8, "explicacion": "x"}'
    falso = _ClienteFalso([_bloque("thinking", thinking=""), _bloque("text", text=texto)])
    monkeypatch.setattr(agentic_ai, "_client", falso)
    monkeypatch.setattr(agentic_ai, "MODEL", "claude-opus-5-5")
    r = agentic_ai.clasificar_aviso_ia("aviso de obra")
    assert r["disponible"] is True and r["categoria"] == "Obra Pública / Contratos"
    assert "thinking" not in falso.pedidos[0]


def test_respuesta_sin_texto_o_rechazada_queda_registrada(monkeypatch):
    monkeypatch.setattr(agentic_ai, "_client", _ClienteFalso([_bloque("thinking", thinking="")], "max_tokens"))
    r = agentic_ai.explicar_riesgo_licitacion({})
    assert r["disponible"] is False and "sin texto" in r["motivo"]
    assert agentic_ai.ULTIMA_CONSULTA["ok"] is False
    monkeypatch.setattr(agentic_ai, "_client", _ClienteFalso([], "refusal"))
    assert "declinó" in agentic_ai.explicar_riesgo_licitacion({})["motivo"]
