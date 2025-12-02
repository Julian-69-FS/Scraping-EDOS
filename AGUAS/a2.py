import os

# Lista de nombres para los archivos .py
nombres_scripts = [
    "Acuerdo",
    "Base",
    "Constitución Política del Estado  Estatuto de Gobierno",
    "Convenio",
    "Código",
    "Declaratoria",
    "Decreto Legislativo",
    "Disposición Interna",
    "Estatuto",
    "Ley",
    "Lineamiento",
    "Manual",
    "Monto",
    "Plan",
    "Protocolo",
    "Regla",
    "Reglamento"
]

# Ruta donde se crearán los archivos .py
ruta_destino = r"C:\Users\julii\Documents\Practicas\drive\AGUAS\metadatos"

# Crear la carpeta destino si no existe
os.makedirs(ruta_destino, exist_ok=True)

# Crear un archivo .py por cada nombre
for nombre in nombres_scripts:
    # Limpiar caracteres no válidos para nombres de archivo en Windows
    nombre_limpio = nombre.replace(":", "").replace("/", "-").replace("\\", "-").strip()
    
    ruta_archivo = os.path.join(ruta_destino, f"{nombre_limpio}.py")
    
    # Crear archivo con contenido inicial
    with open(ruta_archivo, "w", encoding="utf-8") as f:
        f.write(f"# Archivo generado automáticamente para: {nombre}\n")
        f.write("# Este script puede ser usado para manejar metadatos relacionados.\n\n")
        f.write("def main():\n")
        f.write(f"    print('Ejecutando metadatos para: {nombre}')\n\n")
        f.write("if __name__ == '__main__':\n")
        f.write("    main()\n")
    
    print(f"✅ Archivo creado: {ruta_archivo}")

print("\n🎉 ¡Todos los archivos .py se crearon correctamente en la carpeta 'metadatos'!")
