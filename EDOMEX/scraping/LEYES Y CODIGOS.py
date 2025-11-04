# -*- coding: utf-8 -*-
import os
import json
import time
import re
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def limpiar_nombre_archivo(nombre):
    """
    Limpia el nombre del archivo eliminando caracteres no permitidos en nombres de archivo.
    """
    # Caracteres no permitidos en Windows: \ / : * ? " < > |
    caracteres_invalidos = r'[\\/*?:"<>|]'
    nombre_limpio = re.sub(caracteres_invalidos, '', nombre)
    # Eliminar espacios múltiples y espacios al inicio/final
    nombre_limpio = re.sub(r'\s+', ' ', nombre_limpio).strip()
    return nombre_limpio


def descargar_pdf(url, ruta_destino, nombre_archivo):
    """
    Descarga un PDF desde una URL y lo guarda en la ruta especificada.
    """
    try:
        # Si la URL es relativa, construir la URL completa
        if not url.startswith('http'):
            url_base = "https://www.secretariadeasuntosparlamentarios.gob.mx/mainstream/Actividad/legislacion/"
            url = url_base + url

        # Headers para evitar bloqueo 403
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.secretariadeasuntosparlamentarios.gob.mx/',
            'Accept': 'application/pdf,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }

        response = requests.get(url, timeout=30, headers=headers)
        response.raise_for_status()

        ruta_completa = os.path.join(ruta_destino, nombre_archivo)
        with open(ruta_completa, 'wb') as f:
            f.write(response.content)
        print(f"✓ Descargado: {nombre_archivo}")
        return True
    except Exception as e:
        print(f"✗ Error descargando {nombre_archivo}: {str(e)}")
        return False


def verificar_directorios():
    """
    Verifica que los directorios necesarios existan.
    """
    ruta_json = r"C:\Users\julii\Documents\Practicas\drive\EDOMEX\json"
    if not os.path.exists(ruta_json):
        os.makedirs(ruta_json, exist_ok=True)


def extraer_documentos(driver):
    """
    Extrae todos los documentos de todas las tablas en la página.

    Args:
        driver: WebDriver de Selenium

    Returns:
        Lista de diccionarios con los metadatos de los documentos
    """
    print(f"\n{'='*60}")
    print("Extrayendo documentos de LEYES Y CÓDIGOS")
    print(f"{'='*60}\n")

    documentos = []
    ruta_carpeta = r"C:\Users\julii\Documents\EDOMEX\LEYES Y CÓDIGOS"
    contador = 1  # Contador continuo para todos los documentos

    try:
        # Buscar las tablas específicas que contienen los documentos usando XPATH
        # Las tablas están en: /html/body/center[1]/table/tbody/tr/td/center/table/tbody/tr[2]/td/table
        tablas = driver.find_elements(By.XPATH, "//body/center[1]/table/tbody/tr/td/center/table/tbody/tr[2]/td/table")

        for tabla in tablas:
            try:
                # Buscar todas las filas dentro de cada tabla
                filas = tabla.find_elements(By.TAG_NAME, "tr")

                for fila in filas:
                    # Obtener todas las celdas de la fila
                    celdas = fila.find_elements(By.TAG_NAME, "td")

                    # Verificar que haya exactamente 3 celdas (imagen, título, enlace)
                    if len(celdas) == 3:
                        # Segunda celda contiene el título
                        titulo_text = celdas[1].text.strip()

                        # Tercera celda contiene el enlace al PDF
                        enlaces = celdas[2].find_elements(By.TAG_NAME, "a")

                        # Verificar que haya título y enlace
                        if titulo_text and len(enlaces) > 0:
                            url_relativa = enlaces[0].get_attribute("href")

                            # Verificar que la URL sea de un PDF
                            if url_relativa and ".pdf" in url_relativa.lower():
                                # Limpiar el nombre del archivo
                                nombre_limpio = limpiar_nombre_archivo(titulo_text)
                                nombre_archivo = f"{contador}. {nombre_limpio}.pdf"

                                # Descargar el PDF
                                print(f"[{contador}] Descargando: {titulo_text}")
                                if descargar_pdf(url_relativa, ruta_carpeta, nombre_archivo):
                                    # Guardar metadatos solo si la descarga fue exitosa
                                    documentos.append({
                                        "ID": contador,
                                        "TITULO": titulo_text,
                                        "URL": url_relativa
                                    })
                                    contador += 1

                                # Pequeña pausa para no sobrecargar el servidor
                                time.sleep(0.5)

            except:
                # Ignorar tablas que no tengan contenido válido
                continue

        print(f"\n{'='*60}")
        print(f"✓ Total de documentos procesados: {len(documentos)}")
        print(f"{'='*60}")

    except Exception as e:
        print(f"Error extrayendo documentos: {str(e)}")

    return documentos


def guardar_json(documentos, nombre_json):
    """
    Guarda los metadatos en un archivo JSON.
    """
    if documentos:
        ruta_json = os.path.join(r"C:\Users\julii\Documents\Practicas\drive\EDOMEX\json", nombre_json)
        with open(ruta_json, 'w', encoding='utf-8') as f:
            json.dump(documentos, f, ensure_ascii=False, indent=2)
        print(f"\n✓ JSON guardado: {nombre_json} ({len(documentos)} documentos)")


def main():
    """
    Función principal que ejecuta el scraping.
    """
    print("Iniciando scraping de LEYES Y CÓDIGOS...")

    # Verificar directorios necesarios
    verificar_directorios()

    # Configurar Selenium
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

    driver = None

    try:
        # Inicializar el navegador
        print("\nInicializando navegador...")
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        print("✅ Navegador iniciado correctamente")

        # Navegar a la página
        url = "https://www.secretariadeasuntosparlamentarios.gob.mx/leyes_y_codigos.html"
        print(f"Navegando a: {url}")
        driver.get(url)

        # Esperar a que cargue la página
        time.sleep(5)
        print("Página cargada correctamente")

        # Cambiar al iframe que contiene el contenido
        print("\nCambiando al iframe con el contenido...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "root"))
        )
        iframe = driver.find_element(By.NAME, "root")
        driver.switch_to.frame(iframe)

        # Esperar a que las tablas se carguen dentro del iframe
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        time.sleep(2)
        print("✓ Iframe cargado correctamente")

        # Extraer todos los documentos
        documentos = extraer_documentos(driver)

        # Guardar JSON
        guardar_json(documentos, "leyes_y_codigos.json")

        # Resumen final
        print("\n" + "="*60)
        print("RESUMEN DE DESCARGA")
        print("="*60)
        print(f"Total de documentos descargados: {len(documentos)}")
        print("="*60)
        print("\n✓ Proceso completado exitosamente!")

    except Exception as e:
        print(f"\n❌ Error durante el scraping: {str(e)}")

    finally:
        if driver:
            driver.quit()
            print("\nNavegador cerrado.")


if __name__ == "__main__":
    main()
