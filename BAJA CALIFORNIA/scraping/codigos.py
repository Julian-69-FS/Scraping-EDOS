from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import json
import os
import re
import requests
from pathlib import Path

# Configuraci�n de rutas
PDF_DOWNLOAD_PATH = r"C:\Users\julii\Documents\BAJA CALIFORNIA\Codigos"
JSON_METADATA_PATH = r"C:\Users\julii\Documents\Practicas\drive\BAJA CALIFORNIA\json_metadatos"
URL = "https://transparencia.pjbc.gob.mx/paginas/MarcoJuridico.aspx?opc=1"

# Crear directorios si no existen
os.makedirs(PDF_DOWNLOAD_PATH, exist_ok=True)
os.makedirs(JSON_METADATA_PATH, exist_ok=True)

def limpiar_nombre_archivo(nombre):
    """Limpia el nombre del archivo eliminando caracteres no v�lidos y limitando la longitud"""
    # Eliminar caracteres no v�lidos para nombres de archivo
    nombre_limpio = re.sub(r'[<>:"/\\|?*]', '', nombre)
    # Eliminar espacios m�ltiples
    nombre_limpio = re.sub(r'\s+', ' ', nombre_limpio).strip()
    # Limitar a 100 caracteres
    if len(nombre_limpio) > 100:
        nombre_limpio = nombre_limpio[:100].strip()
    return nombre_limpio

def descargar_pdf(url, nombre_archivo, ruta_destino):
    """Descarga un PDF desde una URL"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        filepath = os.path.join(ruta_destino, nombre_archivo)
        with open(filepath, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        return False

# Configuraci�n de Chrome
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument('--ignore-certificate-errors')
chrome_options.add_argument('--log-level=3')
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

try:
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    driver.get(URL)
except Exception as e:
    raise

wait = WebDriverWait(driver, 10)

try:
    # Esperar a que la tabla est� presente
    tabla = wait.until(EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_gvInformacion")))

    # Obtener el tbody
    tbody = tabla.find_element(By.TAG_NAME, "tbody")

    # Obtener todas las filas
    filas = tbody.find_elements(By.TAG_NAME, "tr")

    metadatos_lista = []

    for fila in filas:
        try:
            # Obtener todas las celdas de la fila
            celdas = fila.find_elements(By.TAG_NAME, "td")

            if len(celdas) >= 5:
                # Extraer datos
                denominacion = celdas[0].text.strip()
                fecha_modificacion = celdas[1].text.strip()
                fecha_publicacion = celdas[3].text.strip()

                # Buscar el enlace del PDF en la columna 4 (índice 4)
                try:
                    enlace = celdas[4].find_element(By.TAG_NAME, "a")
                    url_pdf = enlace.get_attribute("href")

                    if url_pdf:
                        # Limpiar nombre para el archivo
                        nombre_archivo = limpiar_nombre_archivo(denominacion)

                        # Asegurar que tenga extensi�n .pdf
                        if not nombre_archivo.lower().endswith('.pdf'):
                            nombre_archivo += '.pdf'

                        # Descargar el PDF
                        descargar_pdf(url_pdf, nombre_archivo, PDF_DOWNLOAD_PATH)

                        # Crear objeto de metadatos
                        metadato = {
                            "titulo": denominacion,
                            "Fecha de �ltima modificaci�n": fecha_modificacion,
                            "Fecha de publicaci�n": fecha_publicacion,
                            "url": url_pdf
                        }

                        metadatos_lista.append(metadato)

                except Exception as e:
                    continue

        except Exception as e:
            continue

    # Guardar metadatos en JSON
    json_filepath = os.path.join(JSON_METADATA_PATH, "metadatos_codigos.json")
    with open(json_filepath, 'w', encoding='utf-8') as f:
        json.dump(metadatos_lista, f, ensure_ascii=False, indent=2)

finally:
    driver.quit()
