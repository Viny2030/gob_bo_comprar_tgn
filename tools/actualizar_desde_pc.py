"""
tools/actualizar_desde_pc.py
============================
Genera los reportes diarios que faltan, corriendo el mismo ciclo que el cron
(diario.py) desde una PC con conexión de Argentina, y opcionalmente los publica
en la rama `desarrollo` (igual que el paso "Guardar Reporte y Sincronizar" del
workflow). No modifica diario.py ni ningún reporte existente.

Por qué: desde el 22/10/2026 el BORA no responde a las IP de GitHub Actions ni
de Railway (ConnectTimeout en los tres intentos). El workflow igual termina en
verde porque diario.py sale con código 0 cuando no hay avisos, así que no se
generó ningún reporte del 22/10 en adelante. Desde Argentina el BORA responde
en 1-3 s.

Uso (desde la raíz del repo, en un checkout de `desarrollo`):

    python tools/actualizar_desde_pc.py --dry-run          # qué días faltan
    python tools/actualizar_desde_pc.py                    # genera los que faltan
    python tools/actualizar_desde_pc.py --publicar         # genera y hace push a desarrollo
    python tools/actualizar_desde_pc.py --desde 2026-10-22 --hasta 2026-10-30

Comprar.gob.ar y TGN solo tienen el estado actual: como en main.py, para días
pasados esas hojas quedan vacías salvo que se pase --incluir-actuales (usa el
estado de hoy, y el reporte lo indica en la hoja "ℹ️ Origen").
"""
import argparse
import contextlib
import os
import subprocess
import sys
from datetime import date, datetime, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)  # diario.py escribe en data/ relativo al directorio actual
for _flujo in (sys.stdout, sys.stderr):  # consola de Windows (cp1252): diario.py imprime emojis
    with contextlib.suppress(AttributeError):
        _flujo.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd  # noqa: E402

import diario  # noqa: E402
from extensiones.zona_horaria import ahora_ar  # noqa: E402

DESDE_POR_DEFECTO = "2026-10-21"  # último día con reporte del cron antes del bloqueo
RAMA = "desarrollo"


def _feriados(anios):
    try:
        import holidays
        return holidays.Argentina(years=anios)
    except ImportError:
        print("⚠️  Falta el paquete 'holidays': no se saltean feriados (el BORA no publica y se verá 'sin edición').")
        return {}


def ruta_reporte(fecha: str) -> str:
    return os.path.join("data", fecha[:7], f"reporte_{fecha}.xlsx")


def dias_faltantes(desde: str, hasta: str) -> list:
    d0 = datetime.strptime(desde, "%Y-%m-%d").date()
    d1 = datetime.strptime(hasta, "%Y-%m-%d").date()
    feriados = _feriados(range(d0.year, d1.year + 1))
    faltan = []
    d = d0
    while d <= d1:
        f = d.strftime("%Y-%m-%d")
        if d.weekday() < 5 and d not in feriados and not os.path.exists(ruta_reporte(f)):
            faltan.append(f)
        d += timedelta(days=1)
    return faltan


@contextlib.contextmanager
def reloj_en(fecha: str):
    """
    Hace que diario.datetime.now() devuelva la fecha pedida (a las 08:00, la hora
    del cron), para que guardar_excels escriba data/AAAA-MM/reporte_AAAA-MM-DD.xlsx
    con el mismo formato y fecha_extraccion que un reporte del cron.
    """
    real = diario.datetime
    objetivo = datetime.strptime(fecha, "%Y-%m-%d").replace(hour=8)

    class _Reloj(real):
        @classmethod
        def now(cls, tz=None):
            return objetivo if tz is None else objetivo.replace(tzinfo=tz)

    diario.datetime = _Reloj
    try:
        yield
    finally:
        diario.datetime = real


def generar_dia(fecha: str, es_hoy: bool, incluir_actuales: bool, cache_actuales: dict) -> dict:
    if es_hoy or incluir_actuales:
        if "comprar" not in cache_actuales:  # se bajan una sola vez por corrida, con la fecha real
            cache_actuales["comprar"] = diario.extraer_comprar()
            cache_actuales["tgn"] = diario.extraer_pagos_tgn()
        df_comprar, df_tgn = cache_actuales["comprar"].copy(), cache_actuales["tgn"].copy()
    else:
        df_comprar, df_tgn = pd.DataFrame(), pd.DataFrame()

    with reloj_en(fecha):
        df_bora = diario.extraer_bora_licitaciones(fecha)
        if df_bora.empty:
            return {"fecha": fecha, "estado": "sin edición del BORA (o no respondió)"}
        df_adj = diario.extraer_bora_adjudicaciones(df_bora)
        df_licit = df_bora[df_bora["es_adjudicacion"] == False].copy().reset_index(drop=True)  # noqa: E712
        df_cruce = diario.cruzar_fuentes(df_adj, df_comprar, df_tgn)
        archivo1, _ = diario.guardar_excels(df_cruce, df_adj, df_licit, df_comprar, df_tgn)

    if not es_hoy:
        origen = ("Comprar y TGN con el estado del " + ahora_ar().strftime("%Y-%m-%d")
                  if incluir_actuales else "Sin Comprar ni TGN (solo tienen el estado actual)")
        with pd.ExcelWriter(archivo1, engine="openpyxl", mode="a") as w:
            pd.DataFrame({
                "generado": [ahora_ar().strftime("%Y-%m-%d %H:%M")],
                "por": ["tools/actualizar_desde_pc.py (recuperación desde PC en Argentina)"],
                "comprar_tgn": [origen],
            }).to_excel(w, sheet_name="ℹ️ Origen", index=False)

    return {"fecha": fecha, "estado": "ok", "licitaciones": len(df_licit),
            "adjudicaciones": len(df_adj), "comprar": len(df_comprar), "tgn": len(df_tgn),
            "cruce": len(df_cruce)}


def _git(*args, check=True):
    print("   $ git " + " ".join(args))
    return subprocess.run(["git", *args], cwd=RAIZ, check=check, text=True, capture_output=True)


def publicar(fechas: list):
    _git("add", "data/")
    if _git("diff", "--staged", "--quiet", check=False).returncode == 0:
        print("Sin cambios en data/, nada que publicar.")
        return
    rango = fechas[0] if len(fechas) == 1 else f"{fechas[0]} a {fechas[-1]}"
    _git("commit", "-m", f"Reporte Integrado BORA-COMPRAR-TGN: {rango} (desde PC en Argentina)")
    _git("pull", "--rebase", "--autostash", "origin", RAMA)
    _git("push", "origin", f"HEAD:{RAMA}")
    print(f"✅ Publicado en {RAMA}.")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--desde", default=DESDE_POR_DEFECTO)
    p.add_argument("--hasta", default=None, help="por defecto, hoy (hora de Argentina)")
    p.add_argument("--dry-run", action="store_true", help="solo lista los días hábiles sin reporte")
    p.add_argument("--publicar", action="store_true", help=f"commit de data/ y push a {RAMA}")
    p.add_argument("--incluir-actuales", action="store_true",
                   help="usar el estado actual de Comprar y TGN también en días pasados")
    a = p.parse_args(argv)

    hoy = ahora_ar().strftime("%Y-%m-%d")
    hasta = a.hasta or hoy
    if a.publicar and not a.dry_run:
        _git("pull", "--rebase", "--autostash", "origin", RAMA)  # traer lo que haya generado el cron

    faltan = dias_faltantes(a.desde, hasta)
    print(f"📅 Días hábiles sin reporte entre {a.desde} y {hasta}: {faltan or 'ninguno'}")
    if a.dry_run or not faltan:
        return 0

    sonda = diario.requests.get("https://www.boletinoficial.gob.ar/", headers=diario.HEADERS,
                                timeout=(10, 20), verify=False)
    print(f"🔌 BORA responde desde esta conexión (HTTP {sonda.status_code}).")

    cache, resultados = {}, []
    for f in faltan:
        print(f"\n════════ {f} ════════")
        resultados.append(generar_dia(f, f == hoy, a.incluir_actuales, cache))

    print("\n📊 RESUMEN")
    for r in resultados:
        print("  ", r)
    generados = [r["fecha"] for r in resultados if r["estado"] == "ok"]
    if a.publicar and generados:
        publicar(generados)
    elif generados:
        print(f"\nGenerados {len(generados)} reportes en data/. Para publicarlos: --publicar "
              f"(o git add data/ && git commit && git push origin HEAD:{RAMA}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
