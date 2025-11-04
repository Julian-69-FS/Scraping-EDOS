import os

# Ruta de la carpeta donde están los archivos .doc
ruta_carpeta = r"C:\Users\julii\Documents\AGUASCALIENTES DOF\Reglamento"

# Contador de archivos eliminados
eliminados = 0

# Recorre los archivos de la carpeta
for archivo in os.listdir(ruta_carpeta):
    if archivo.lower().endswith(".doc"):
        ruta_archivo = os.path.join(ruta_carpeta, archivo)
        try:
            os.remove(ruta_archivo)
            eliminados += 1
            print(f"🗑️ Eliminado: {archivo}")
        except Exception as e:
            print(f"⚠️ No se pudo eliminar {archivo}: {e}")

print(f"\n✅ Eliminación completa. Archivos eliminados: {eliminados}")
