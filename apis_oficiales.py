ASUS@DESKTOP-EQ8IV7B MINGW64 ~/gob_bo_comprar_tgn (desarrollo)
$ # Agregar los 2 archivos a la raíz del repo y hacer push
git add apis_oficiales.py test_apis_oficiales.py
git commit -m "feat: módulo de APIs oficiales (BORA/COMPRAR/TGN/AFIP/SIPRO)"
git push origin desarrollo

# Probar en Railway o local:
python test_apis_oficiales.py --solo bora
python test_apis_oficiales.py --solo tgn
python test_apis_oficiales.py --solo compat
On branch desarrollo
Your branch is up to date with 'origin/desarrollo'.

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
        modified:   __pycache__/analisis.cpython-313.pyc
        modified:   __pycache__/diario.cpython-313.pyc

Untracked files:
  (use "git add <file>..." to include in what will be committed)
        __pycache__/apis_oficiales.cpython-313.pyc

no changes added to commit (use "git add" and/or "git commit -a")
To https://github.com/Viny2030/gob_bo_comprar_tgn.git
 ! [rejected]        desarrollo -> desarrollo (fetch first)
error: failed to push some refs to 'https://github.com/Viny2030/gob_bo_comprar_tgn.git'
hint: Updates were rejected because the remote contains work that you do not
hint: have locally. This is usually caused by another repository pushing to
hint: the same ref. If you want to integrate the remote changes, use
hint: 'git pull' before pushing again.
hint: See the 'Note about fast-forwards' in 'git push --help' for details.

════════════════════════════════════════════════════════════
  🧪 TEST APIs Oficiales — monitor_contratos
  📅 2026-03-23 09:34
════════════════════════════════════════════════════════════

────────────────────────────────────────────────────────────
  1. BORA — Normativa API (sección tercera, hoy)
────────────────────────────────────────────────────────────

📡 BORA Normativa API | sección=tercera | 2026-03-23 → 2026-03-23
C:\Users\ASUS\AppData\Local\Programs\Python\Python313\Lib\site-packages\urllib3\connectionpool.py:1097: InsecureRequestWarning: Unverified HTTPS request is being made to host 'www.argentina.gob.ar'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
  warnings.warn(
C:\Users\ASUS\AppData\Local\Programs\Python\Python313\Lib\site-packages\urllib3\connectionpool.py:1097: InsecureRequestWarning: Unverified HTTPS request is being made to host 'www.argentina.gob.ar'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
  warnings.warn(
  ❌ BORA Normativa API falló: Expecting value: line 2 column 2 (char 2)
  💡 Usando scraping directo de boletinoficial.gob.ar como fallback...

📰 Extrayendo BORA - Sección Tercera (índice)...
  🔄 Intento 1: https://www.boletinoficial.gob.ar/seccion/tercera...
C:\Users\ASUS\AppData\Local\Programs\Python\Python313\Lib\site-packages\urllib3\connectionpool.py:1097: InsecureRequestWarning: Unverified HTTPS request is being made to host 'www.boletinoficial.gob.ar'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
  warnings.warn(
  ✅ 82 avisos (5 adjudicaciones, 77 licitaciones)
  ✅ 82 registros
     Columnas (9): ['fecha_extraccion', 'fecha_publicacion', 'organismo', 'tipo_proceso', 'categoria', 'aviso_id', 'es_adjudicacion', 'link', 'fuente']

fecha_publicacion                                       organismo
                                  tipo_proceso  es_adjudicacion           fuente
       2026-03-20 EMPRESA PROVINCIAL DE ENERGÍA DE CÓRDOBA S.A.U. Licitación Pública Electrónica Nacional e Internacional 1287            False BORA Sección 3ra
       2026-03-20 EMPRESA PROVINCIAL DE ENERGÍA DE CÓRDOBA S.A.U. Licitación Pública Electrónica Nacional e Internacional 1296            False BORA Sección 3ra
       2026-03-20                  GENDARMERÍA NACIONAL ARGENTINA
                  Licitación Pública 0025/2026            False BORA Sección 3ra

  📊 Adjudicaciones: 5 | Licitaciones: 77

  ✅ Schema compatible con diario.py (df_bora_licitaciones)

────────────────────────────────────────────────────────────
  Fin del test
  💡 Recordar: apis_oficiales.py NO modifica diario.py ni los reportes existentes
────────────────────────────────────────────────────────────


════════════════════════════════════════════════════════════
  🧪 TEST APIs Oficiales — monitor_contratos
  📅 2026-03-23 09:34
════════════════════════════════════════════════════════════

────────────────────────────────────────────────────────────
  4. TGN — /ejecucion (con cuit_beneficiario)
────────────────────────────────────────────────────────────

📡 TGN /ejecucion API | año=2026
C:\Users\ASUS\AppData\Local\Programs\Python\Python313\Lib\site-packages\urllib3\connectionpool.py:1097: InsecureRequestWarning: Unverified HTTPS request is being made to host 'www.presupuestoabierto.gob.ar'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
  warnings.warn(
C:\Users\ASUS\AppData\Local\Programs\Python\Python313\Lib\site-packages\urllib3\connectionpool.py:1097: InsecureRequestWarning: Unverified HTTPS request is being made to host 'www.presupuestoabierto.gob.ar'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
  warnings.warn(
C:\Users\ASUS\AppData\Local\Programs\Python\Python313\Lib\site-packages\urllib3\connectionpool.py:1097: InsecureRequestWarning: Unverified HTTPS request is being made to host 'www.presupuestoabierto.gob.ar'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
  warnings.warn(
  ⚠️  TGN /ejecucion no disponible: 404 Client Error:  for url: https://www.pressupuestoabierto.gob.ar/api/v1/ejecucion
  💡 Intentando con /credito (fallback de diario.py)...

💰 Extrayendo Pagos TGN (Presupuesto Abierto API v1)...
C:\Users\ASUS\AppData\Local\Programs\Python\Python313\Lib\site-packages\urllib3\connectionpool.py:1097: InsecureRequestWarning: Unverified HTTPS request is being made to host 'www.presupuestoabierto.gob.ar'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
  warnings.warn(
  ❌ TGN API v1 falló: HTTPSConnectionPool(host='www.presupuestoabierto.gob.ar', port=443): Read timed out. (read timeout=60)
  ⚠️ TGN no disponible, se omite del cruce
  ⚠️  Sin datos — API no disponible o sin resultados hoy

────────────────────────────────────────────────────────────
  Fin del test
  💡 Recordar: apis_oficiales.py NO modifica diario.py ni los reportes existentes
────────────────────────────────────────────────────────────


════════════════════════════════════════════════════════════
  🧪 TEST APIs Oficiales — monitor_contratos
  📅 2026-03-23 09:35
════════════════════════════════════════════════════════════

────────────────────────────────────────────────────────────
  7. Test de compatibilidad con diario.py / cruzar_fuentes()
────────────────────────────────────────────────────────────

  Verificando schemas...


📡 COMPR.AR API | tipo=adjudicaciones | año=2020
C:\Users\ASUS\AppData\Local\Programs\Python\Python313\Lib\site-packages\urllib3\connectionpool.py:1097: InsecureRequestWarning: Unverified HTTPS request is being made to host 'infra.datos.gob.ar'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
  warnings.warn(
C:\Users\ASUS\AppData\Local\Programs\Python\Python313\Lib\site-packages\urllib3\connectionpool.py:1097: InsecureRequestWarning: Unverified HTTPS request is being made to host 'infra.datos.gob.ar'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
  warnings.warn(
C:\Users\ASUS\AppData\Local\Programs\Python\Python313\Lib\site-packages\urllib3\connectionpool.py:1097: InsecureRequestWarning: Unverified HTTPS request is being made to host 'infra.datos.gob.ar'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
  warnings.warn(
  ❌ COMPR.AR API falló: 404 Client Error: Not Found for url: https://infra.datos.gob.ar/catalog/sspm/dataset/269/distribution/269.4/download/adjudicaciones-2020.csv
  ⚠️  df_comprar: sin datos para verificar

📡 TGN /ejecucion API | año=2026
C:\Users\ASUS\AppData\Local\Programs\Python\Python313\Lib\site-packages\urllib3\connectionpool.py:1097: InsecureRequestWarning: Unverified HTTPS request is being made to host 'www.presupuestoabierto.gob.ar'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
  warnings.warn(
C:\Users\ASUS\AppData\Local\Programs\Python\Python313\Lib\site-packages\urllib3\connectionpool.py:1097: InsecureRequestWarning: Unverified HTTPS request is being made to host 'www.presupuestoabierto.gob.ar'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
  warnings.warn(
C:\Users\ASUS\AppData\Local\Programs\Python\Python313\Lib\site-packages\urllib3\connectionpool.py:1097: InsecureRequestWarning: Unverified HTTPS request is being made to host 'www.presupuestoabierto.gob.ar'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
  warnings.warn(
  ⚠️  TGN /ejecucion no disponible: 404 Client Error:  for url: https://www.pressupuestoabierto.gob.ar/api/v1/ejecucion
  💡 Intentando con /credito (fallback de diario.py)...

💰 Extrayendo Pagos TGN (Presupuesto Abierto API v1)...
C:\Users\ASUS\AppData\Local\Programs\Python\Python313\Lib\site-packages\urllib3\connectionpool.py:1097: InsecureRequestWarning: Unverified HTTPS request is being made to host 'www.presupuestoabierto.gob.ar'. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#tls-warnings
  warnings.warn(
  ❌ TGN API v1 falló: HTTPSConnectionPool(host='www.presupuestoabierto.gob.ar', port=443): Read timed out. (read timeout=60)
  ⚠️ TGN no disponible, se omite del cruce
  ⚠️  df_tgn: sin datos para verificar

  Simulando mini-cruce (misma lógica que cruzar_fuentes)...
  ⚠️  No hay datos suficientes para el mini-cruce

  Verificando que diario.py no fue alterado...
  ✅ diario.py intacto — 5 funciones verificadas

────────────────────────────────────────────────────────────
  Fin del test
  💡 Recordar: apis_oficiales.py NO modifica diario.py ni los reportes existentes
────────────────────────────────────────────────────────────
