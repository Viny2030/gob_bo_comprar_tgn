"""
Tests de extensiones/falla_rapida.py, salud_fuentes.py y tools/actualizar_desde_pc.py.

No agregan el middleware a main.app (lo haría para todos los tests de la sesión):
se prueba sobre una app mínima. Ningún test sale a la red.
"""
import asyncio
import os
import subprocess
import sys
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import main
from extensiones import falla_rapida, salud_fuentes

RAIZ = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
def job_limpio():
    main._analisis_job.clear()
    main._analisis_job.update({"corriendo": False, "fecha": None, "resultado": None,
                               "error": None, "iniciado_en": None})
    yield main._analisis_job


@pytest.fixture
def app_minima(monkeypatch):
    """Una app con el middleware y rutas que registran si llegaron a ejecutarse."""
    app = FastAPI()
    llegaron = []

    @app.post("/api/licitaciones/ejecutar")
    def ejecutar():
        llegaron.append("ejecutar")
        return {"status": "iniciado"}

    @app.post("/api/ia/explicar-riesgo")
    def ia():
        llegaron.append("ia")
        return {"disponible": True}

    app.add_middleware(falla_rapida.FallaRapida)
    return TestClient(app), llegaron


def _bora(ok):
    return lambda forzar=False: {"alcanzable": ok, "http": 200 if ok else None, "segundos": 0.1}


def test_bora_caido_responde_503_sin_lanzar_el_analisis(app_minima, job_limpio, monkeypatch):
    monkeypatch.setattr(falla_rapida, "bora_alcanzable", _bora(False))
    cliente, llegaron = app_minima
    r = cliente.post("/api/licitaciones/ejecutar")
    assert r.status_code == 503
    assert "Boletín Oficial" in r.json()["detail"]
    assert llegaron == []


def test_bora_disponible_deja_pasar(app_minima, job_limpio, monkeypatch):
    monkeypatch.setattr(falla_rapida, "bora_alcanzable", _bora(True))
    cliente, llegaron = app_minima
    assert cliente.post("/api/licitaciones/ejecutar").status_code == 200
    assert llegaron == ["ejecutar"]


def test_con_analisis_en_curso_no_prueba_el_bora(app_minima, job_limpio, monkeypatch):
    def no_llamar(forzar=False):
        raise AssertionError("no debía probar el BORA")
    monkeypatch.setattr(falla_rapida, "bora_alcanzable", no_llamar)
    job_limpio.update({"corriendo": True, "iniciado_en": datetime.now().isoformat()})
    cliente, llegaron = app_minima
    cliente.post("/api/licitaciones/ejecutar")
    assert llegaron == ["ejecutar"]  # main.py contesta su 409 propio


def test_clave_ia_invalida_responde_con_la_forma_del_frontend(app_minima, monkeypatch):
    monkeypatch.setattr(falla_rapida, "clave_ia_valida",
                        lambda forzar=False: {"valida": False, "motivo": "La clave fue rechazada (401)"})
    cliente, llegaron = app_minima
    r = cliente.post("/api/ia/explicar-riesgo", json={})
    assert r.status_code == 503
    assert r.json()["disponible"] is False and "401" in r.json()["motivo"]
    assert llegaron == []


def test_libera_analisis_colgado(job_limpio):
    inicio = datetime.now() - timedelta(minutes=falla_rapida.ANALISIS_MAX_MIN + 1)
    job_limpio.update({"corriendo": True, "iniciado_en": inicio.isoformat()})
    assert falla_rapida.liberar_analisis_colgado() is True
    assert job_limpio["corriendo"] is False and "no terminó" in job_limpio["error"]


def test_no_libera_analisis_reciente(job_limpio):
    job_limpio.update({"corriendo": True, "iniciado_en": datetime.now().isoformat()})
    assert falla_rapida.liberar_analisis_colgado() is False
    assert job_limpio["corriendo"] is True


def test_sonda_bora_usa_timeout_corto_y_cachea(monkeypatch):
    llamadas = []

    def get(url, **kw):
        llamadas.append(kw["timeout"])
        raise ConnectionError("sin respuesta")
    monkeypatch.setattr(salud_fuentes.requests, "get", get)
    r1 = salud_fuentes.bora_alcanzable(forzar=True)
    r2 = salud_fuentes.bora_alcanzable()
    assert r1["alcanzable"] is False and r2["alcanzable"] is False
    assert len(llamadas) == 1 and llamadas[0][0] <= 10


def test_clave_ia_sin_configurar(monkeypatch):
    import agentic_ai
    monkeypatch.setattr(agentic_ai, "_client", None)
    r = salud_fuentes.clave_ia_valida(forzar=True)
    assert r["valida"] is False and "no configurada" in r["motivo"]


def test_clave_ia_revocada(monkeypatch):
    import anthropic
    import httpx2
    import agentic_ai

    class _Modelos:
        def retrieve(self, modelo):
            req = httpx2.Request("GET", "https://api.anthropic.com/v1/models/x")
            raise anthropic.AuthenticationError("invalid x-api-key",
                                                response=httpx2.Response(401, request=req), body=None)

    class _Cliente:
        models = _Modelos()

        def with_options(self, **kw):
            return self
    monkeypatch.setattr(agentic_ai, "_client", _Cliente())
    r = salud_fuentes.clave_ia_valida(forzar=True)
    assert r["valida"] is False and "revocada" in r["motivo"]


def test_diagnostico(monkeypatch, job_limpio):
    monkeypatch.setattr(falla_rapida, "bora_alcanzable", _bora(False))
    monkeypatch.setattr(falla_rapida, "clave_ia_valida", lambda forzar=False: {"valida": True})
    app = FastAPI()
    app.include_router(falla_rapida.router)
    d = TestClient(app).get("/api/diagnostico").json()
    assert d["bora"]["alcanzable"] is False and d["ia"]["valida"] is True
    assert "dias_habiles_sin_reporte_30d" in d and "analisis_en_vivo" in d


def test_app_extendida_v2_arranca():
    """En un proceso aparte, para no sumar el middleware a main.app de esta sesión."""
    codigo = ("import app_extendida_v2 as a; "
              "rutas = set(a.app.openapi()['paths']); "
              "assert '/api/diagnostico' in rutas and '/api/estado-sistema' in rutas; print('ok')")
    r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().endswith("ok")


def test_dias_faltantes_saltea_fines_de_semana_feriados_y_existentes(tmp_path, monkeypatch):
    sys.path.insert(0, os.path.join(RAIZ, "tools"))
    import actualizar_desde_pc as act
    monkeypatch.setattr(act, "ruta_reporte",
                        lambda f: str(tmp_path / f"reporte_{f}.xlsx"))
    (tmp_path / "reporte_2026-10-22.xlsx").write_text("x")
    # 21/10 mié (sin reporte en tmp), 22 jue (existe), 23 vie, 24-25 finde, 26 lun
    assert act.dias_faltantes("2026-10-21", "2026-10-26") == ["2026-10-21", "2026-10-23", "2026-10-26"]
    # 12/10/2026: feriado (Día del Respeto a la Diversidad Cultural)
    assert "2026-10-12" not in act.dias_faltantes("2026-10-12", "2026-10-12")


def test_reloj_en_fija_la_fecha_de_diario():
    sys.path.insert(0, os.path.join(RAIZ, "tools"))
    import actualizar_desde_pc as act
    import diario
    with act.reloj_en("2026-10-23"):
        assert diario.datetime.now().strftime("%Y-%m-%d") == "2026-10-23"
        assert diario.carpeta_mes().replace("\\", "/").endswith("data/2026-10")
    assert diario.datetime.now().date() == datetime.now().date()
