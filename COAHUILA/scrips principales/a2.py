import os

# Ruta de tu carpeta principal
ruta_principal = r"C:\Users\julii\Documents\COAHUILA DOF"

# Recorre las subcarpetas dentro de la ruta principal
subcarpetas = [nombre for nombre in os.listdir(ruta_principal) if os.path.isdir(os.path.join(ruta_principal, nombre))]

# Muestra los nombres de las subcarpetas
print("Subcarpetas encontradas:")
for carpeta in subcarpetas:
    print(carpeta)
