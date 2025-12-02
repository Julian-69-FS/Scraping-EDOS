import os

# Lista de nombres para los scripts
nombres_scripts = [
    "Acta",
    "Acuerdo",
    "Adición",
    "Constitución Política del Estado  Estatuto de Gobierno",
    "Código",
    "Decreto Administrativo",
    "Decreto Legislativo",
    "Disposición General",
    "Fe de erratas",
    "Ley",
    "Lineamiento",
    "Manual",
    "Protocolo",
    "Reforma",
    "Reglamento"
]

# Ruta donde se crearán los archivos .py
ruta_scripts = r"C:\Users\julii\Documents\Practicas\drive\CAMPECHE\scrips"

# Crear carpeta destino si no existe
os.makedirs(ruta_scripts, exist_ok=True)

# Crear un archivo .py por cada nombre
for nombre in nombres_scripts:
    # Reemplaza caracteres no válidos para nombres de archivo en Windows
    nombre_limpio = nombre.replace(":", "").replace("/", "-").replace("\\", "-").strip()
    
    ruta_archivo = os.path.join(ruta_scripts, f"{nombre_limpio}.py")
    
    # Crear archivo vacío o con contenido inicial
    with open(ruta_archivo, "w", encoding="utf-8") as f:
        f.write(f"# Script generado automáticamente para: {nombre}\n")
        f.write("def main():\n")
        f.write(f"    print('Ejecutando script: {nombre}')\n\n")
        f.write("if __name__ == '__main__':\n")
        f.write("    main()\n")
    
    print(f"✅ Archivo creado: {ruta_archivo}")

print("\n🎉 ¡Todos los archivos .py se han creado correctamente!")
