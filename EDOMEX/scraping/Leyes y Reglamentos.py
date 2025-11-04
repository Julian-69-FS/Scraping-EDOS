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
    # Eliminar espacios m�ltiples y espacios al inicio/final
    nombre_limpio = re.sub(r'\s+', ' ', nombre_limpio).strip()
    return nombre_limpio


def descargar_pdf(url, ruta_destino, nombre_archivo):
    """
    Descarga un PDF desde una URL y lo guarda en la ruta especificada.
    """
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        ruta_completa = os.path.join(ruta_destino, nombre_archivo)
        with open(ruta_completa, 'wb') as f:
            f.write(response.content)
        print(f" Descargado: {nombre_archivo}")
        return True
    except Exception as e:
        print(f" Error descargando {nombre_archivo}: {str(e)}")
        return False


def crear_directorios():
    """
    Crea los directorios necesarios si no existen.
    """
    directorios = [
        r"C:\Users\julii\Documents\EDOMEX\LEYES FEDERALES",
        r"C:\Users\julii\Documents\EDOMEX\REGLAMENTOS DE LEYES FEDERALES",
        r"C:\Users\julii\Documents\EDOMEX\REGLAMENTOS FEDERALES",
        r"C:\Users\julii\Documents\Practicas\drive\EDOMEX\json"
    ]

    for directorio in directorios:
        os.makedirs(directorio, exist_ok=True)
        print(f"Directorio verificado: {directorio}")


def extraer_seccion(driver, titulo_seccion, ruta_carpeta, nombre_json):
    """
    Extrae los documentos de una secci�n espec�fica.

    Args:
        driver: WebDriver de Selenium
        titulo_seccion: Texto del t�tulo de la secci�n (ej: "LEYES FEDERALES")
        ruta_carpeta: Ruta donde se guardar�n los PDFs
        nombre_json: Nombre del archivo JSON a generar

    Returns:
        Lista de diccionarios con los metadatos de los documentos
    """
    print(f"\n{'='*60}")
    print(f"Procesando secci�n: {titulo_seccion}")
    print(f"{'='*60}")

    documentos = []

    try:
        # Buscar el p�rrafo con el t�tulo de la secci�n
        parrafos = driver.find_elements(By.XPATH, "//div[@class='article-body']//p/strong")

        seccion_encontrada = False
        for p in parrafos:
            if titulo_seccion in p.text:
                seccion_encontrada = True
                # Obtener el elemento <ul> siguiente al <p>
                ul_element = p.find_element(By.XPATH, "./ancestor::p/following-sibling::ul[1]")

                # Obtener todos los <li> dentro del <ul>
                items = ul_element.find_elements(By.TAG_NAME, "li")

                print(f"Encontrados {len(items)} documentos en {titulo_seccion}")

                for idx, item in enumerate(items, start=1):
                    try:
                        # Obtener el enlace <a>
                        enlace = item.find_element(By.TAG_NAME, "a")
                        url = enlace.get_attribute("href")
                        titulo = enlace.text.strip()

                        # Limpiar el nombre del archivo
                        nombre_limpio = limpiar_nombre_archivo(titulo)
                        nombre_archivo = f"{idx}. {nombre_limpio}.pdf"

                        # Descargar el PDF
                        print(f"\n[{idx}/{len(items)}] Descargando: {titulo}")
                        descargar_pdf(url, ruta_carpeta, nombre_archivo)

                        # Guardar metadatos
                        documentos.append({
                            "ID": idx,
                            "TITULO": titulo,
                            "URL": url
                        })

                        # Peque�a pausa para no sobrecargar el servidor
                        time.sleep(0.5)

                    except Exception as e:
                        print(f"Error procesando item {idx}: {str(e)}")
                        continue

                break

        if not seccion_encontrada:
            print(f"� No se encontr� la secci�n: {titulo_seccion}")

    except Exception as e:
        print(f"Error extrayendo secci�n {titulo_seccion}: {str(e)}")

    # Guardar JSON
    if documentos:
        ruta_json = os.path.join(r"C:\Users\julii\Documents\Practicas\drive\EDOMEX\json", nombre_json)
        with open(ruta_json, 'w', encoding='utf-8') as f:
            json.dump(documentos, f, ensure_ascii=False, indent=2)
        print(f"\n JSON guardado: {nombre_json} ({len(documentos)} documentos)")

    return documentos


def main():
    """
    Funci�n principal que ejecuta el scraping.
    """
    print("Iniciando scraping de Leyes y Reglamentos...")

    # Crear directorios necesarios
    crear_directorios()

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

        # Navegar a la p�gina
        url = "https://www.gob.mx/puertosymarinamercante/acciones-y-programas/leyes-y-reglamentos-79893"
        print(f"Navegando a: {url}")
        driver.get(url)

        # Esperar a que cargue el contenido
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "article-body")))
        print("P�gina cargada correctamente")

        # Extraer cada secci�n
        secciones = [
            {
                "titulo": "LEYES FEDERALES",
                "ruta": r"C:\Users\julii\Documents\EDOMEX\LEYES FEDERALES",
                "json": "leyes_federales.json"
            },
            {
                "titulo": "REGLAMENTOS DE LEYES FEDERALES",
                "ruta": r"C:\Users\julii\Documents\EDOMEX\REGLAMENTOS DE LEYES FEDERALES",
                "json": "reglamentos_leyes_federales.json"
            },
            {
                "titulo": "REGLAMENTOS FEDERALES",
                "ruta": r"C:\Users\julii\Documents\EDOMEX\REGLAMENTOS FEDERALES",
                "json": "reglamentos_federales.json"
            }
        ]

        resultados = {}
        for seccion in secciones:
            docs = extraer_seccion(
                driver,
                seccion["titulo"],
                seccion["ruta"],
                seccion["json"]
            )
            resultados[seccion["titulo"]] = len(docs)

        # Resumen final
        print("\n" + "="*60)
        print("RESUMEN DE DESCARGA")
        print("="*60)
        for seccion, cantidad in resultados.items():
            print(f"{seccion}: {cantidad} documentos")
        print("="*60)
        print("\n Proceso completado exitosamente!")

    except Exception as e:
        print(f"\n Error durante el scraping: {str(e)}")

    finally:
        if driver:
            driver.quit()
            print("\nNavegador cerrado.")


if __name__ == "__main__":
    main()
