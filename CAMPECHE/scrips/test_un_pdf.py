# -*- coding: utf-8 -*-
"""
Script de prueba para procesar UN solo PDF y verificar saltos de línea
"""

import sys
import io
import json
from pathlib import Path

# Configurar la salida estándar para usar UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Importar funciones desde Acta.py
from Acta import extraer_contenido_pdf

def main():
    # Ruta del PDF de prueba
    ruta_pdf = r"C:\Users\julii\Documents\CAMPECHE DOF\Acta\Acta No. 36 de la XXII Sesión Extraordinaria de Cabildo. Aprobación de Adición al bando de policía y.pdf"

    print("="*80)
    print("🔍 PRUEBA DE EXTRACCIÓN Y CORRECCIÓN DE SALTOS DE LÍNEA")
    print("="*80)
    print(f"\n📄 Archivo: {Path(ruta_pdf).name}")
    print(f"📂 Ruta completa: {ruta_pdf}")
    print("\n" + "-"*80)
    print("Procesando...")
    print("-"*80 + "\n")

    # Procesar el PDF
    resultado = extraer_contenido_pdf(ruta_pdf)

    if resultado:
        print("\n" + "="*80)
        print("✅ EXTRACCIÓN COMPLETADA")
        print("="*80)

        print(f"\n📌 Título: {resultado['Titulo']}")
        print(f"\n📊 Longitud del contenido: {len(resultado['contenido'])} caracteres")

        # Mostrar las primeras 2000 caracteres para verificar formato
        print("\n" + "-"*80)
        print("📝 PRIMEROS 2000 CARACTERES DEL CONTENIDO:")
        print("-"*80)
        contenido_preview = resultado['contenido'][:2000]
        print(contenido_preview)

        if len(resultado['contenido']) > 2000:
            print("\n[... contenido truncado para visualización ...]")

        # Buscar palabras cortadas (buscar patrón problemático)
        print("\n" + "-"*80)
        print("🔍 ANÁLISIS DE PALABRAS CORTADAS:")
        print("-"*80)

        lineas = resultado['contenido'].split('\n')
        palabras_cortadas_encontradas = []

        for i, linea in enumerate(lineas[:50]):  # Revisar primeras 50 líneas
            # Buscar patrones como "los\nCiudadanos" (minúscula seguida de Mayúscula sin espacio lógico)
            if i > 0:
                linea_anterior = lineas[i-1].strip()
                linea_actual = linea.strip()

                # Si la anterior termina con palabra minúscula y la actual empieza con mayúscula
                # y no hay puntuación final, podría ser palabra cortada (pero ya debería estar corregida)
                if (linea_anterior and linea_actual and
                    linea_anterior[-1].islower() and
                    linea_actual[0].isupper() and
                    linea_anterior[-1] not in '.,;:!?'):

                    # Verificar si parece palabra cortada
                    ultima_palabra_anterior = linea_anterior.split()[-1] if linea_anterior.split() else ""
                    primera_palabra_actual = linea_actual.split()[0] if linea_actual.split() else ""

                    if len(ultima_palabra_anterior) <= 4 and len(primera_palabra_actual) <= 10:
                        palabras_cortadas_encontradas.append({
                            'linea': i,
                            'anterior': linea_anterior[-50:] if len(linea_anterior) > 50 else linea_anterior,
                            'actual': linea_actual[:50] if len(linea_actual) > 50 else linea_actual
                        })

        if palabras_cortadas_encontradas:
            print(f"⚠️  Se encontraron {len(palabras_cortadas_encontradas)} posibles palabras cortadas:")
            for idx, caso in enumerate(palabras_cortadas_encontradas[:5], 1):  # Mostrar máximo 5
                print(f"\n  {idx}. Línea {caso['linea']}:")
                print(f"     Anterior: ...{caso['anterior']}")
                print(f"     Actual:   {caso['actual']}...")
        else:
            print("✅ ¡No se detectaron palabras cortadas! La corrección funcionó correctamente.")

        # Verificar saltos de línea en estructuras
        print("\n" + "-"*80)
        print("📋 ANÁLISIS DE ESTRUCTURA (primeros bloques):")
        print("-"*80)

        bloques = resultado['contenido'].split('\n\n')[:5]  # Primeros 5 bloques
        for idx, bloque in enumerate(bloques, 1):
            print(f"\n🔹 Bloque {idx}:")
            print(f"   Líneas: {bloque.count(chr(10)) + 1}")
            print(f"   Caracteres: {len(bloque)}")
            preview = bloque[:200] + "..." if len(bloque) > 200 else bloque
            print(f"   Contenido: {preview}")

        # Guardar resultado en archivo JSON de prueba
        archivo_salida = r"C:\Users\julii\Documents\Practicas\drive\CAMPECHE\scrips\test_salida.json"

        print("\n" + "-"*80)
        print("💾 GUARDANDO RESULTADO...")
        print("-"*80)

        with open(archivo_salida, 'w', encoding='utf-8') as f:
            json.dump([resultado], f, ensure_ascii=False, indent=2)

        print(f"✅ Resultado guardado en: {archivo_salida}")
        print(f"   Puedes revisar el archivo completo para verificar el formato")

    else:
        print("\n❌ ERROR: No se pudo procesar el PDF")

    print("\n" + "="*80)
    print("🏁 PRUEBA FINALIZADA")
    print("="*80)
    print("\n💡 RECOMENDACIONES:")
    print("  1. Revisa el archivo 'test_salida.json' para ver el resultado completo")
    print("  2. Verifica que no haya palabras cortadas tipo 'los\\nCiudadanos'")
    print("  3. Confirma que los saltos de línea estén en lugares lógicos")
    print("  4. Si todo se ve bien, ejecuta Acta.py para procesar todos los PDFs")
    print()

if __name__ == "__main__":
    main()
