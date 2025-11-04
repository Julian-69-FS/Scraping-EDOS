from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
import time
import requests
import json

# ==============================
# CONFIGURACIÓN DEL NAVEGADOR
# ==============================
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--ignore-certificate-errors")
chrome_options.add_argument("--log-level=3")
chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

try:
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    print("✅ Navegador iniciado correctamente")
    driver.get("https://www.congresocdmx.gob.mx/marco-legal-cdmx-107-2.html")
except Exception as e:
    print(f"❌ Error al iniciar el navegador: {str(e)}")
    raise

wait = WebDriverWait(driver, 5)

# ==============================
# CONFIGURACIÓN DE DIRECTORIOS
# ==============================
ruta_base_guardado = r"C:\Users\julii\Documents\CDMX"
if not os.path.exists(ruta_base_guardado):
    print(f"📂 Creando directorio: {ruta_base_guardado}")
os.makedirs(ruta_base_guardado, exist_ok=True)

# ==============================
# CONFIGURACIÓN DE GOOGLE SHEETS
# ==============================
SERVICE_ACCOUNT_FILE = r"C:\Users\julii\Documents\Practicas\credentials\gcredential.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1PU4c2nB_xa_MFDS8-t11CM_lVX7s8WDRVj-W2MPEDu8"  # ← Agrega tu ID de hoja aquí
SHEET_NAME = "LEYES1"       # ← Agrega tu nombre de hoja aquí

# Cargar credenciales
try:
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
except Exception as e:
    print(f"❌ Error al cargar credenciales: {e}")
    raise

# Conectar con Google Sheets
try:
    service_sheets = build("sheets", "v4", credentials=creds)
    print("✅ Conexión con Google Sheets establecida correctamente")
except Exception as e:
    print(f"❌ Error al conectar con Google Sheets: {e}")
    raise

# ==============================
# SCRAPING DE DATOS
# ==============================
metadatos_lista = []

try:
    # Esperar a que cargue el artículo principal
    article = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "article.g-mb-60")))
    print("✅ Article encontrado")

    # Buscar el contenedor principal
    row_div = article.find_element(By.CSS_SELECTOR, "div.row")
    print("✅ Div.row encontrado")

    # Obtener todos los elementos col-lg-12
    items = row_div.find_elements(By.CSS_SELECTOR, "div.col-lg-12")
    print(f"📄 Total de archivos encontrados: {len(items)}")

    # Procesar cada elemento
    for index, item in enumerate(items, start=1):
        try:
            # Extraer URL del PDF
            pdf_link = item.find_element(By.CSS_SELECTOR, "div.d-flex.g-mr-15 a").get_attribute("href")

            # Extraer nombre y última reforma
            strong_element = item.find_element(By.CSS_SELECTOR, "div.media-body p.m-0 strong")
            texto_completo = strong_element.text.strip()

            # Buscar patrones de separación (en orden de prioridad)
            nombre_archivo = texto_completo
            ultima_reforma = "N/A"

            # Intentar separar por "- Última" o "- Publicada"
            if " - Última" in texto_completo:
                partes = texto_completo.split(" - Última", 1)
                nombre_archivo = partes[0].strip()
                ultima_reforma_texto = partes[1].strip()

                # Extraer solo la fecha después de "el"
                if " el " in ultima_reforma_texto:
                    ultima_reforma = ultima_reforma_texto.split(" el ", 1)[1].strip()
                else:
                    ultima_reforma = ultima_reforma_texto

            elif " - Publicada" in texto_completo:
                partes = texto_completo.split(" - Publicada", 1)
                nombre_archivo = partes[0].strip()
                ultima_reforma_texto = partes[1].strip()

                # Extraer solo la fecha después de "el"
                if " el " in ultima_reforma_texto:
                    ultima_reforma = ultima_reforma_texto.split(" el ", 1)[1].strip()
                else:
                    ultima_reforma = ultima_reforma_texto

            elif " - " in texto_completo:
                # Separación genérica por " - "
                partes = texto_completo.split(" - ", 1)
                nombre_archivo = partes[0].strip()
                ultima_reforma = partes[1].strip()

                # Si tiene "el ", extraer la fecha
                if " el " in ultima_reforma:
                    ultima_reforma = ultima_reforma.split(" el ", 1)[1].strip()

            elif ". " in texto_completo and texto_completo.count(". ") == 1:
                # Separación por punto seguido de espacio (solo si hay uno)
                partes = texto_completo.split(". ", 1)
                nombre_archivo = partes[0].strip()
                ultima_reforma = partes[1].strip()

                # Si tiene "el ", extraer la fecha
                if " el " in ultima_reforma:
                    ultima_reforma = ultima_reforma.split(" el ", 1)[1].strip()

            # Extraer fecha de publicación
            span_fecha = item.find_element(By.CSS_SELECTOR, "div.media-body span.g-font-size-12")
            fecha_publicacion_texto = span_fecha.text.strip()

            if ":" in fecha_publicacion_texto:
                fecha_publicacion = fecha_publicacion_texto.split(":", 1)[1].strip()
                if "|" in fecha_publicacion:
                    fecha_publicacion = fecha_publicacion.split("|", 1)[0].strip()
            else:
                fecha_publicacion = fecha_publicacion_texto

            # Mostrar datos en consola
            print(f"\n--- Archivo {index} ---")
            print(f"Nombre: {nombre_archivo}")
            print(f"Última reforma: {ultima_reforma}")
            print(f"Fecha publicación: {fecha_publicacion}")
            print(f"URL: {pdf_link}")

            # Descargar el PDF
            try:
                response = requests.get(pdf_link, timeout=30)
                response.raise_for_status()

                nombre_pdf = f"{index}. {nombre_archivo}.pdf"
                ruta_completa = os.path.join(ruta_base_guardado, nombre_pdf)

                with open(ruta_completa, "wb") as f:
                    f.write(response.content)

                print(f"✅ PDF descargado: {nombre_pdf}")
            except Exception as e:
                print(f"❌ Error al descargar PDF {index}: {str(e)}")

            # Guardar metadatos
            metadatos = {
                "ID": index,
                "NOMBRE_ARCHIVO": nombre_archivo,
                "ULTIMA_REFORMA": ultima_reforma,
                "FECHA_PUBLICACION": fecha_publicacion,
                "URL_PDF": pdf_link,
            }
            metadatos_lista.append(metadatos)
            time.sleep(1)

        except Exception as e:
            print(f"❌ Error procesando item {index}: {str(e)}")
            continue

    print(f"\n{'=' * 50}")
    print(f"✅ Total de archivos procesados: {len(metadatos_lista)}")
    print(f"{'=' * 50}\n")

except Exception as e:
    print(f"❌ Error general durante scraping: {str(e)}")
    raise

# ==============================
# GUARDAR EN GOOGLE SHEETS
# ==============================
if SPREADSHEET_ID and SHEET_NAME:
    try:
        headers = [["ID", "NOMBRE DEL ARCHIVO", "ULTIMA REFORMA PUBLICADA", "FECHA DE PUBLICACION", "URL DEL PDF"]]
        rows = [
            [m["ID"], m["NOMBRE_ARCHIVO"], m["ULTIMA_REFORMA"], m["FECHA_PUBLICACION"], m["URL_PDF"]]
            for m in metadatos_lista
        ]

        body = {"values": headers + rows}
        result = (
            service_sheets.spreadsheets()
            .values()
            .update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{SHEET_NAME}!A1",
                valueInputOption="RAW",
                body=body,
            )
            .execute()
        )

        print(f"✅ Datos guardados en Google Sheets: {result.get('updatedCells')} celdas actualizadas")
    except Exception as e:
        print(f"❌ Error al guardar en Google Sheets: {str(e)}")
else:
    print("⚠ SPREADSHEET_ID o SHEET_NAME no configurados. Omitiendo Google Sheets.")

# ==============================
# GUARDAR EN JSON
# ==============================
try:
    json_directory = r"C:\Users\julii\Documents\Practicas\drive\CDMX\json"
    os.makedirs(json_directory, exist_ok=True)
    json_path = os.path.join(json_directory, "metadatos.json")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metadatos_lista, f, ensure_ascii=False, indent=4)

    print(f"✅ Metadatos guardados en JSON: {json_path}")
except Exception as e:
    print(f"❌ Error al guardar JSON: {str(e)}")

# ==============================
# FINALIZAR
# ==============================
finally:
    driver.quit()
    print("\n🚪 Navegador cerrado correctamente.")