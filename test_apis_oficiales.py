import sys
import pandas as pd
# Importamos las funciones desde el otro archivo
from apis_oficiales import obtener_bora_normativa_api, obtener_todo_api

def test_bora():
    print("\n🔍 Probando BORA API...")
    df = obtener_bora_normativa_api(seccion="tercera")
    if not df.empty:
        print(f"✅ Éxito: {len(df)} registros encontrados.")
        print(df[['fecha_publicacion', 'organismo', 'titulo']].head(3))
    else:
        print("⚠️ No se devolvieron datos de BORA.")

def main():
    print("="*50)
    print("🧪 TEST APIs Oficiales — monitor_contratos")
    print("="*50)
    
    test_bora()
    
    print("\n🚀 Probando todas las APIs...")
    resultados = obtener_todo_api()
    for nombre, df in resultados.items():
        estado = "✅" if not df.empty else "❌"
        print(f"{estado} {nombre}: {len(df)} registros")

if __name__ == "__main__":
    main()
