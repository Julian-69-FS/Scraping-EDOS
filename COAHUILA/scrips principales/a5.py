import os

# Lista de nombres de carpetas
nombres_carpetas = [
       "Constitución",
"Código",
"Decreto",
"Estatuto",
"Ley",
"Reglamento",
]

# Ruta base donde se crearán las carpetas
ruta_destino = r"C:\Users\julii\Documents\Practicas\drive\COAHUILA\json"

# Crear carpeta base si no existe
os.makedirs(ruta_destino, exist_ok=True)

# Crear una carpeta por cada nombre
for nombre in nombres_carpetas:
    # Limpia caracteres no válidos para Windows
    nombre_limpio = nombre.replace(":", "").replace("/", "-").replace("\\", "-").strip()
    
    ruta_carpeta = os.path.join(ruta_destino, nombre_limpio)
    os.makedirs(ruta_carpeta, exist_ok=True)
    print(f"✅ Carpeta creada o ya existente: {ruta_carpeta}")

print("\n🎉 ¡Todas las carpetas fueron creadas correctamente en la ruta JSON!")
