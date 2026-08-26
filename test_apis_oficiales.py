import sys
import pandas as pd
# Importamos las funciones desde el otro archivo
from apis_oficiales import obtener_bora_normativa_api, obtener_todo_api, validar_cuit_api

def test_bora():
    print("\n🔍 Probando BORA API...")
    df = obtener_bora_normativa_api(seccion="tercera")
    if not df.empty:
        print(f"✅ Éxito: {len(df)} registros encontrados.")
        print(df[['fecha_publicacion', 'organismo', 'titulo']].head(3))
    else:
        print("⚠️ No se devolvieron datos de BORA.")


def test_validar_cuit_formato():
    """
    Verifica el algoritmo real de dígito verificador (módulo 11 AFIP).
    30-12345678-1 es un CUIT con formato válido calculado con el
    algoritmo oficial; cambiar el último dígito lo invalida.
    """
    ok = validar_cuit_api("30-12345678-1")
    assert ok["valido_formato"] is True, ok
    assert ok["tipo_persona"] == "Jurídica", ok

    mal_digito = validar_cuit_api("30-12345678-2")
    assert mal_digito["valido_formato"] is False, mal_digito

    mal_longitud = validar_cuit_api("30-123-1")
    assert mal_longitud["valido_formato"] is False, mal_longitud

    vacio = validar_cuit_api("")
    assert vacio["valido_formato"] is False, vacio

    print("✅ validar_cuit_api: dígito verificador módulo 11 correcto en los 4 casos.")

def main():
    print("="*50)
    print("🧪 TEST APIs Oficiales — monitor_contratos")
    print("="*50)
    
    test_bora()
    test_validar_cuit_formato()

    print("\n🚀 Probando todas las APIs...")
    resultados = obtener_todo_api()
    for nombre, df in resultados.items():
        estado = "✅" if not df.empty else "❌"
        print(f"{estado} {nombre}: {len(df)} registros")

if __name__ == "__main__":
    main()
