"""
tools/backfill_db.py
====================
Carga en PostgreSQL los reportes Excel de data/ (todo el histórico o un rango).
No modifica los Excel. Reemplaza las filas de cada fecha que carga.

Uso:
    python tools/backfill_db.py --dry-run                 # muestra qué cargaría
    DATABASE_URL=postgres://... python tools/backfill_db.py
    python tools/backfill_db.py --desde 2026-09-01 --hasta 2026-09-30

Ojo: cuando reportes_diarios tenga datos, el dashboard (main.py) deja de leer
el último Excel y pasa a mostrar los totales ACUMULADOS de la base
(SUM de todos los días). Ver MEJORAS.md.
"""
import argparse
import asyncio
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from extensiones.sincronizacion import cargar_dia, fechas_disponibles, leer_dia  # noqa: E402


def _fechas(data_dir, desde, hasta):
    return [f for f in fechas_disponibles(data_dir)
            if (not desde or f >= desde) and (not hasta or f <= hasta)]


async def _cargar(url, data_dir, fechas):
    import asyncpg
    pool = await asyncpg.create_pool(url, min_size=1, max_size=3)
    try:
        for f in fechas:
            r = await cargar_dia(pool, data_dir, f)
            print(f"  {'✅' if r.get('cargado') else '⚠️ '} {f}  cruce={r.get('total_cruce', 0)} "
                  f"alto={r.get('riesgo_alto', 0)} medio={r.get('riesgo_medio', 0)}")
    finally:
        await pool.close()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", default=os.path.join(RAIZ, "data"))
    p.add_argument("--desde")
    p.add_argument("--hasta")
    p.add_argument("--dry-run", action="store_true", help="no se conecta a la base: solo lista")
    a = p.parse_args()

    fechas = _fechas(a.data_dir, a.desde, a.hasta)
    print(f"📂 {len(fechas)} días con reporte en {a.data_dir}")
    if a.dry_run:
        for f in fechas:
            r = leer_dia(a.data_dir, f)["resumen"]
            print(f"  {f}  licit={r['total_licit']} adj={r['total_adj']} cruce={r['total_cruce']} "
                  f"comprar={r['total_comprar']} tgn={r['total_tgn']} alto={r['riesgo_alto']} medio={r['riesgo_medio']}")
        return 0

    url = os.getenv("DATABASE_URL", "")
    if not url:
        print("❌ Falta DATABASE_URL (o usá --dry-run)")
        return 1
    asyncio.run(_cargar(url, a.data_dir, fechas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
