import os

# Lista de nombres de carpetas
nombres_carpetas = [
"Acta",
"Acuerdo",
"Coordinación",
"Convenio",
"Código",
"Lineamiento",
"Manual",
"Plan",
"Programa",
"Protocolo",
"Regla",
"Reglamento",
]

# Ruta donde se crearán las carpetas
ruta_destino = r"C:\Users\julii\Documents\Practicas\drive\GUERRERO\contenido"

# Crea las carpetas si no existen
for nombre in nombres_carpetas:
    ruta_carpeta = os.path.join(ruta_destino, nombre)
    os.makedirs(ruta_carpeta, exist_ok=True)
    print(f"✅ Carpeta creada o ya existente: {ruta_carpeta}")

print("\n🎉 ¡Todas las carpetas han sido creadas correctamente!")
