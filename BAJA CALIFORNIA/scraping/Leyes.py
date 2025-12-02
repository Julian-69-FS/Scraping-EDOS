# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
import json
import os
import re
import requests
import time

# Configuraci�n de rutas
PDF_DOWNLOAD_PATH = r"C:\Users\julii\Documents\BAJA CALIFORNIA\Leyes"
JSON_METADATA_PATH = r"C:\Users\julii\Documents\Practicas\drive\BAJA CALIFORNIA\json_metadatos"
URL = "https://www.congresobc.gob.mx/TrabajoLegislativo/Leyes"

# Crear directorios si no existen
os.makedirs(PDF_DOWNLOAD_PATH, exist_ok=True)
os.makedirs(JSON_METADATA_PATH, exist_ok=True)

def limpiar_nombre_archivo(nombre):
    """Limpia el nombre del archivo eliminando caracteres no v�lidos y limitando la longitud"""
    nombre_limpio = re.sub(r'[<>:"/\\|?*]', '', nombre)
    nombre_limpio = re.sub(r'\s+', ' ', nombre_limpio).strip()
    if len(nombre_limpio) > 100:
        nombre_limpio = nombre_limpio[:100].strip()
    return nombre_limpio

def descargar_pdf(url, nombre_archivo, ruta_destino):
    """Descarga un PDF desde una URL"""
    try:
        if not url.startswith('http'):
            url = 'https://www.congresobc.gob.mx' + url

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

wait = WebDriverWait(driver, 15)

try:
    # PASO 1: Esperar 3 segundos después de entrar
    time.sleep(3)

    # PASO 2: Seleccionar "100" registros del dropdown (máximo disponible)
    select_div = wait.until(EC.presence_of_element_located((By.ID, "MainContent_gv_Leyes_length")))
    select_element = select_div.find_element(By.NAME, "MainContent_gv_Leyes_length")
    select = Select(select_element)
    select.select_by_value("100")  # Seleccionar 100 registros por página

    # PASO 3: Esperar 3 segundos para que cargue
    time.sleep(3)

    # PASO 4: Leer JSON existente para agregar nuevos metadatos
    json_filepath = os.path.join(JSON_METADATA_PATH, "metadatos_leyes.json")
    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            metadatos_lista = json.load(f)
    except FileNotFoundError:
        metadatos_lista = []

    pagina_actual = 1  # Empezamos desde página 1

    while True:
        # Esperar a que la tabla est� presente
        tabla = wait.until(EC.presence_of_element_located((By.ID, "MainContent_gv_Leyes")))
        tbody = tabla.find_element(By.TAG_NAME, "tbody")

        # Obtener todas las filas (odd y even)
        filas = tbody.find_elements(By.TAG_NAME, "tr")

        for fila in filas:
            try:
                celdas = fila.find_elements(By.TAG_NAME, "td")

                if len(celdas) >= 7:
                    # Extraer datos
                    nombre = celdas[0].text.strip()
                    fecha_per_ofic = celdas[3].text.strip()  # Columna correcta
                    estatus = celdas[4].text.strip()
                    tomo = celdas[5].text.strip()

                    # Buscar el enlace del PDF en la celda 1
                    try:
                        enlace = celdas[1].find_element(By.TAG_NAME, "a")
                        url_pdf = enlace.get_attribute("href")

                        if url_pdf:
                            # Limpiar nombre para el archivo
                            nombre_archivo = limpiar_nombre_archivo(nombre)

                            # Asegurar que tenga extensi�n .pdf
                            if not nombre_archivo.lower().endswith('.pdf'):
                                nombre_archivo += '.pdf'

                            # Descargar el PDF
                            descargar_pdf(url_pdf, nombre_archivo, PDF_DOWNLOAD_PATH)

                            # Crear objeto de metadatos
                            metadato = {
                                "NOMBRE": nombre,
                                "FECHA PER OFIC": fecha_per_ofic,
                                "ESTATUS": estatus,
                                "TOMO": tomo,
                                "URL": url_pdf
                            }

                            metadatos_lista.append(metadato)

                    except Exception as e:
                        continue

            except Exception as e:
                continue

        # Buscar el bot�n "Siguiente" para paginaci�n
        try:
            boton_siguiente = wait.until(EC.presence_of_element_located((By.ID, "MainContent_gv_Leyes_next")))

            # Verificar si el bot�n est� deshabilitado (�ltima p�gina)
            clases = boton_siguiente.get_attribute("class")
            if clases and "disabled" in clases:
                break

            # Hacer clic en "Siguiente" usando JavaScript
            enlace_siguiente = boton_siguiente.find_element(By.TAG_NAME, "a")
            driver.execute_script("arguments[0].click();", enlace_siguiente)

            # Esperar 5 segundos para que recargue la tabla
            time.sleep(5)

            # Esperar a que la tabla se actualice
            wait.until(EC.staleness_of(tbody))
            pagina_actual += 1

        except Exception as e:
            # No hay m�s p�ginas o error
            break

    # Guardar metadatos en JSON
    json_filepath = os.path.join(JSON_METADATA_PATH, "metadatos_leyes.json")
    with open(json_filepath, 'w', encoding='utf-8') as f:
        json.dump(metadatos_lista, f, ensure_ascii=False, indent=2)

finally:
    driver.quit()
 