import os
import re
import unicodedata

# Ruta de tu carpeta
ruta = r"C:\Users\julii\Documents\INGLES"

def normalize_text(s):
    """Quita acentos y pasa a mayúsculas para comparar de forma estable."""
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return s.upper()

def natural_key(s):
    """Crea una clave para orden natural: divide en trozos texto/dígitos."""
    parts = re.split(r'(\d+)', s)
    key = []
    for p in parts:
        if p.isdigit():
            key.append(int(p))
        else:
            key.append(p)
    return key

def extract_lesson_number(orig_name):
    """
    Intenta extraer el número de 'LECCIÓN' o 'LECCION' cercano al inicio.
    Si no lo encuentra, devuelve None.
    """
    name = normalize_text(orig_name)
    # Primero busca patrones tipo "LECCION 12" o "LECCION12"
    m = re.search(r'LECCION\D*(\d{1,4})', name)
    if m:
        return int(m.group(1))
    # Si no, toma el primer número que aparezca (por si acaso)
    m2 = re.search(r'(\d{1,4})', name)
    if m2:
        return int(m2.group(1))
    return None

# Recolectar archivos .xlsx
archivos = []
for f in os.listdir(ruta):
    if f.lower().endswith('.xlsx'):
        archivos.append(f)

# Preparar lista con claves de orden
archivos_con_clave = []
for f in archivos:
    nombre_sin_ext = os.path.splitext(f)[0]
    lesson_num = extract_lesson_number(nombre_sin_ext)
    # Normalizamos para la ordenación natural (pero mantenemos el nombre original para mostrar)
    norm = normalize_text(nombre_sin_ext)
    nat_key = natural_key(norm)
    # La clave será (lesson_num or big, natural_key) -> así los con número van antes, en número asc.
    primary = lesson_num if lesson_num is not None else float('inf')
    archivos_con_clave.append((primary, nat_key, nombre_sin_ext))

# Ordenamos por la clave
archivos_con_clave.sort(key=lambda x: (x[0], x[1]))

# Extraemos solo los nombres ya ordenados
nombres_ordenados = [t[2] for t in archivos_con_clave]

# Mostrar por consola
print("Archivos .xlsx en orden 'humano':\n")
for nombre in nombres_ordenados:
    print(nombre)

# Guardar en nombres.txt
out_path = os.path.join(ruta, "nombres.txt")
with open(out_path, "w", encoding="utf-8") as f:
    for nombre in nombres_ordenados:
        f.write(nombre + "\n")

print(f"\nGuardado: {out_path}")
