# =============================================================================
# DEPENDENCIAS DEL PROYECTO - Procesamiento de Documentos Legales
# =============================================================================
# Autor: Julian
# Fecha: Noviembre 2025
#
# Instalación:
#   pip install -r requirements.txt
#
# Nota: Algunas librerías requieren software adicional:
#   - Selenium requiere Google Chrome instalado
#   - tabula-py requiere Java JRE instalado
#   - pytesseract requiere Tesseract OCR instalado
# =============================================================================

# -----------------------------------------------------------------------------
# WEB SCRAPING (Etapa 1)
# -----------------------------------------------------------------------------
selenium>=4.0
webdriver-manager>=3.8
requests>=2.28

# -----------------------------------------------------------------------------
# PROCESAMIENTO DE PDF (Etapas 2 y 3)
# -----------------------------------------------------------------------------
PyPDF2>=3.0
pdfplumber>=0.9
PyMuPDF>=1.22
pdfminer.six>=20221105
tabula-py>=2.7

# -----------------------------------------------------------------------------
# OCR - Reconocimiento Óptico de Caracteres
# -----------------------------------------------------------------------------
easyocr>=1.7
pytesseract>=0.3.10
pdf2image>=1.16

# -----------------------------------------------------------------------------
# PROCESAMIENTO DE IMÁGENES
# -----------------------------------------------------------------------------
Pillow>=9.5
numpy>=1.24

# -----------------------------------------------------------------------------
# UTILIDADES (incluidas en Python estándar, no requieren instalación)
# -----------------------------------------------------------------------------
# json - Manejo de archivos JSON
# pathlib - Manejo de rutas
# logging - Sistema de logs
# difflib - SequenceMatcher para comparación de strings
# unicodedata - Normalización de texto
# re - Expresiones regulares
# collections - defaultdict, Counter
# datetime - Manejo de fechas
