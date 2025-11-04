import os
import json
import pdfplumber
import re
from pathlib import Path
from typing import List, Dict, Tuple
import sys

# Imports para OCR
try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image
    OCR_DISPONIBLE = True
except ImportError:
    OCR_DISPONIBLE = False
    print("⚠ OCR no disponible. Instala: pip install pytesseract pdf2image pillow")
    print("   También necesitas Tesseract-OCR: https://github.com/tesseract-ocr/tesseract")
    print("   Y poppler-utils para pdf2image")

def limpiar_texto(texto: str) -> str:
    """Limpia y normaliza el texto extraído"""
    # Eliminar espacios múltiples y normalizar saltos de línea
    texto = re.sub(r'\s+', ' ', texto)
    texto = re.sub(r'\n+', '\n', texto)
    return texto.strip()

def detectar_y_eliminar_texto_fragmentado(texto: str) -> str:
    """Elimina líneas con texto fragmentado letra por letra (cintas laterales)

    Detecta patrones como:
    - L Í T (letras sueltas con espacios)
    - I C (2-3 letras separadas)
    - Líneas muy cortas repetitivas
    - Texto muy espaciado como "C O N S T I T U C I Ó N"
    """
    lineas = texto.split('\n')
    lineas_limpias = []

    # Patrones específicos de cintas laterales comunes en documentos legales
    patrones_cinta_lateral = [
        r'^CONSTITUCIÓN\s+POLÍTICA',
        r'^POLÍTICA\s+DEL\s+ESTADO',
        r'^DEL\s+ESTADO\s+LIBRE',
        r'^ESTADO\s+LIBRE\s+Y',
        r'^LIBRE\s+Y\s+SOBERANO',
        r'^Y\s+SOBERANO\s+DE',
        r'^SOBERANO\s+DE\s+MÉXICO',
        r'^DE\s+MÉXICO\s*$',  # "DE MÉXICO" solo
        r'^MÉXICO\s*$',  # "MÉXICO" solo
        r'^C\s+O\s+N\s+S\s+T',  # Letras muy espaciadas
        r'^P\s+O\s+L\s+Í\s+T',
        r'^D\s+E\s+L',
        r'^E\s+S\s+T\s+A\s+D\s+O',
        r'^L\s+I\s+B\s+R\s+E',
    ]

    for linea in lineas:
        linea_stripped = linea.strip()

        # Saltar líneas vacías
        if not linea_stripped:
            continue

        # Verificar patrones de cinta lateral específicos
        es_cinta_lateral = False
        for patron in patrones_cinta_lateral:
            if re.match(patron, linea_stripped, re.IGNORECASE):
                es_cinta_lateral = True
                break

        if es_cinta_lateral:
            continue

        # Detectar si es texto fragmentado (letras sueltas)
        # Contar espacios vs caracteres
        num_espacios = linea_stripped.count(' ')
        num_caracteres = len(linea_stripped.replace(' ', ''))

        # Si hay más espacios que caracteres útiles, es fragmentado
        if num_caracteres > 0 and num_espacios >= num_caracteres * 0.4:
            # Es muy probable que sea texto fragmentado
            continue

        # Detectar líneas con solo 1-3 caracteres (posible fragmento)
        # CUIDADO: No eliminar líneas cortas que pueden ser contenido válido
        if len(linea_stripped) <= 3:
            # Solo eliminar si es SOLO mayúsculas o SOLO números
            # Y no es parte de una enumeración (I, II, III, etc.)
            if linea_stripped.isupper() and not re.match(r'^[IVX]+$', linea_stripped):
                # No es número romano, puede ser fragmento
                if len(linea_stripped) <= 2:
                    continue
            elif linea_stripped.isdigit() and len(linea_stripped) == 1:
                # Solo eliminar dígitos individuales
                continue

        # Detectar líneas con patrón "A B C" (letras separadas por espacios)
        palabras = linea_stripped.split()
        if len(palabras) >= 3:
            # Si más del 80% de las "palabras" son de 1-2 caracteres, es fragmentado
            palabras_cortas = sum(1 for p in palabras if len(p) <= 2)
            if palabras_cortas / len(palabras) >= 0.8:
                continue

        # Detectar líneas que son combinaciones raras de letras (CC OO NN SS)
        if re.match(r'^([A-ZÁÉÍÓÚÑ]{1,2}\s+){3,}[A-ZÁÉÍÓÚÑ]{1,2}\s*$', linea_stripped):
            continue

        # Si pasó todas las validaciones, mantener la línea
        lineas_limpias.append(linea)

    return '\n'.join(lineas_limpias)

def corregir_saltos_linea(texto: str) -> str:
    """Une palabras del mismo bloque, pero separa bloques diferentes agresivamente

    FILOSOFÍA CORRECTA:
    - UNIR todas las líneas que pertenecen al MISMO BLOQUE (evitar: son\ntextos)
    - SEPARAR bloques cuando detectemos FIN de bloque

    Un bloque termina cuando:
    1. Línea vacía después
    2. Línea con puntuación final (. ; : ! ?) Y la siguiente NO es minúscula
    3. Línea corta (≤6 palabras) sin puntuación de continuación (sin coma)
    4. Inicio de elemento estructural (Artículo, I., a), etc.)
    5. Cambio de MAYÚSCULAS a normal

    Se mantiene el bloque abierto (UNIR) cuando:
    - Guión al final (palabra cortada)
    - Línea sin puntuación final seguida de minúscula o más texto
    - Línea con coma seguida de minúscula
    - Líneas largas (>6 palabras) sin puntuación final
    """
    if not texto:
        return texto

    lineas = texto.split('\n')
    bloques = []
    bloque_actual = []

    # Patrones de inicio de bloque estructural
    patrones_inicio_bloque = [
        r'^(Artículo|ARTÍCULO|Art\.|ART\.)\s+\d+',
        r'^(Fracción|FRACCIÓN|Fracc\.|FRACC\.)\s*[IVX\d]*',
        r'^(Capítulo|CAPÍTULO|Cap\.|CAP\.)\s+[IVX\d]+',
        r'^(Título|TÍTULO|Tít\.|TÍT\.)\s+[IVX\d]+',
        r'^(Sección|SECCIÓN|Secc\.|SECC\.)',
        r'^[IVX]+\.',  # I. II. III.
        r'^[IVXLCDM]+\)',  # I) II) III)
        r'^\d+\.',  # 1. 2. 3.
        r'^\d+\)',  # 1) 2) 3)
        r'^[a-z]\)',  # a) b) c)
        r'^[A-Z]\)',  # A) B) C)
    ]

    def es_inicio_bloque_estructural(linea: str) -> bool:
        """Detecta inicio de elementos estructurales"""
        for patron in patrones_inicio_bloque:
            if re.match(patron, linea.strip()):
                return True
        return False

    def es_linea_corta(linea: str) -> bool:
        """Línea con 6 palabras o menos"""
        palabras = linea.strip().split()
        return len(palabras) <= 6

    def es_mayormente_mayusculas(linea: str) -> bool:
        """Detecta si una línea es mayormente MAYÚSCULAS (título)"""
        linea_limpia = linea.strip().replace(' ', '')
        if len(linea_limpia) < 3:
            return False
        letras = [c for c in linea_limpia if c.isalpha()]
        if not letras:
            return False
        mayusculas = [c for c in letras if c.isupper()]
        return len(mayusculas) / len(letras) >= 0.7  # 70% mayúsculas

    i = 0
    while i < len(lineas):
        linea = lineas[i]
        linea_stripped = linea.strip()

        # Si es línea vacía, cerrar bloque actual
        if not linea_stripped:
            if bloque_actual:
                bloques.append(' '.join(bloque_actual))
                bloque_actual = []
            i += 1
            continue

        # Palabra cortada con guión - UNIR sin espacio
        if linea_stripped.endswith('-') and i + 1 < len(lineas):
            siguiente = lineas[i + 1].strip()
            if siguiente:
                linea_stripped = linea_stripped[:-1] + siguiente
                i += 2
            else:
                i += 1
        else:
            i += 1

        # Si es inicio de bloque estructural Y ya hay contenido, cerrar bloque anterior
        if es_inicio_bloque_estructural(linea_stripped) and bloque_actual:
            bloques.append(' '.join(bloque_actual))
            bloque_actual = []

        # Si el bloque anterior era MAYÚSCULAS y esta línea no, cerrar
        if bloque_actual and es_mayormente_mayusculas(' '.join(bloque_actual)) and not es_mayormente_mayusculas(linea_stripped):
            bloques.append(' '.join(bloque_actual))
            bloque_actual = []

        # Agregar línea al bloque actual
        bloque_actual.append(linea_stripped)

        # Determinar si debemos cerrar el bloque
        debe_cerrar = False

        # Obtener siguiente línea no vacía
        siguiente_no_vacia = None
        if i < len(lineas):
            for j in range(i, len(lineas)):
                if lineas[j].strip():
                    siguiente_no_vacia = lineas[j].strip()
                    break

        # Si no hay siguiente línea, cerrar
        if siguiente_no_vacia is None:
            debe_cerrar = True
        else:
            # Verificar condiciones de cierre

            # 1. Puntuación final Y siguiente NO es minúscula
            if linea_stripped[-1] in '.;:!?':
                if siguiente_no_vacia[0].isupper() or es_inicio_bloque_estructural(siguiente_no_vacia):
                    debe_cerrar = True

            # 2. Línea corta (≤6 palabras) SIN coma ni puntuación de continuación
            elif es_linea_corta(linea_stripped) and not linea_stripped.endswith(','):
                # Si siguiente también es corta, cerrar (probablemente lista)
                if es_linea_corta(siguiente_no_vacia):
                    debe_cerrar = True
                # Si siguiente es inicio de bloque, cerrar
                elif es_inicio_bloque_estructural(siguiente_no_vacia):
                    debe_cerrar = True
                # Si esta línea es MAYÚSCULAS, cerrar
                elif es_mayormente_mayusculas(linea_stripped):
                    debe_cerrar = True

        # Aplicar decisión
        if debe_cerrar:
            bloques.append(' '.join(bloque_actual))
            bloque_actual = []

    # Agregar último bloque
    if bloque_actual:
        bloques.append(' '.join(bloque_actual))

    # Unir bloques
    texto_final = '\n'.join(bloques)

    # Limpiar espacios
    texto_final = re.sub(r'  +', ' ', texto_final)
    texto_final = re.sub(r' +([.,;:?!)\]}>])', r'\1', texto_final)
    texto_final = re.sub(r'([\[({<])\s+', r'\1', texto_final)
    texto_final = re.sub(r'\n{3,}', '\n\n', texto_final)

    return texto_final.strip()

def limpiar_titulo_pdf(nombre_archivo: str) -> str:
    """Elimina prefijos numéricos del nombre del archivo PDF"""
    # Eliminar extensión primero si existe
    titulo = nombre_archivo.replace('.pdf', '').replace('.PDF', '')

    # Eliminar varios patrones de prefijos numéricos
    patrones = [
        r'^\d+[_\-\.\s]+',      # Números seguidos de _, -, . o espacio
        r'^\(\d+\)[\s_\-]*',     # (1) o (01) al inicio
        r'^\d+\)[\s_\-]*',        # 1) o 01) al inicio
        r'^[A-Za-z]\d+[\-\.\s]+',  # A1, B02- etc.
        r'^\d+\s*[\-–—]\s*',     # Números con guiones
    ]

    for patron in patrones:
        titulo = re.sub(patron, '', titulo)

    # Limpiar espacios extras y guiones bajos al inicio/final
    titulo = titulo.strip('_- ')

    return titulo if titulo else nombre_archivo  # Si queda vacío, devolver original

def convertir_tabla_a_json_string(tabla: List[List], numero_tabla: int) -> str:
    """Convierte una tabla extraída en un string JSON preservando TODO el contenido exacto"""
    if not tabla or len(tabla) < 2:
        return ""

    # Primera fila = encabezados de columnas
    columnas = []
    for col in tabla[0]:
        if col is not None:
            # Preservar el contenido exacto, solo quitar espacios extremos
            texto = str(col).strip()
            # Reemplazar múltiples espacios por uno solo pero mantener saltos de línea
            texto = re.sub(r' {2,}', ' ', texto)
            columnas.append(texto if texto else "(sin encabezado)")
        else:
            columnas.append("(sin encabezado)")

    # Resto de filas = datos
    filas = []
    for fila in tabla[1:]:
        fila_dict = {}
        tiene_contenido = False

        for i, celda in enumerate(fila):
            clave = f"columna_{i+1}"
            if celda is not None:
                # Preservar contenido exacto incluyendo saltos de línea
                texto = str(celda).strip()
                # Reemplazar múltiples espacios horizontales por uno solo
                texto = re.sub(r' {2,}', ' ', texto)

                if texto:
                    fila_dict[clave] = texto
                    tiene_contenido = True
                else:
                    fila_dict[clave] = "(sin dato)"
            else:
                fila_dict[clave] = "(sin dato)"

        # Solo agregar fila si tiene al menos un dato real
        if tiene_contenido:
            filas.append(fila_dict)

    if not filas:
        return ""

    # Crear estructura de tabla
    tabla_estructura = {
        f"tabla_{numero_tabla}": {
            "columnas": columnas,
            "filas": filas
        }
    }

    # Convertir a JSON string compacto (sin espacios ni saltos de línea)
    return json.dumps(tabla_estructura, ensure_ascii=False, separators=(',', ':'))

def extraer_tablas_ocr(imagen) -> List[List]:
    """Intenta detectar y extraer tablas de una imagen usando OCR"""
    try:
        # Usar pytesseract con configuración para detectar estructura de tabla
        texto_tsv = pytesseract.image_to_data(imagen, lang='spa+eng', output_type=pytesseract.Output.DICT)

        # Agrupar texto por líneas basándose en coordenadas Y
        lineas = {}
        for i in range(len(texto_tsv['text'])):
            if texto_tsv['text'][i].strip():
                # Agrupar por número de línea
                line_num = texto_tsv['line_num'][i]
                block_num = texto_tsv['block_num'][i]
                key = f"{block_num}_{line_num}"

                if key not in lineas:
                    lineas[key] = []

                lineas[key].append({
                    'text': texto_tsv['text'][i],
                    'left': texto_tsv['left'][i],
                    'top': texto_tsv['top'][i],
                    'width': texto_tsv['width'][i],
                    'height': texto_tsv['height'][i]
                })

        # Intentar detectar estructura tabular basándose en alineación
        tablas_detectadas = []

        # Ordenar líneas por posición vertical
        lineas_ordenadas = sorted(lineas.items(), key=lambda x: min(item['top'] for item in x[1]))

        # Buscar grupos de líneas con múltiples elementos alineados horizontalmente
        tabla_actual = []
        for key, elementos in lineas_ordenadas:
            # Si hay más de 2 elementos en la línea, podría ser parte de una tabla
            if len(elementos) > 2:
                # Ordenar elementos por posición horizontal
                elementos_ordenados = sorted(elementos, key=lambda x: x['left'])
                fila = [elem['text'] for elem in elementos_ordenados]
                tabla_actual.append(fila)
            elif tabla_actual and len(tabla_actual) > 1:
                # Si teníamos una tabla y encontramos una línea sin estructura tabular,
                # guardar la tabla actual
                tablas_detectadas.append(tabla_actual)
                tabla_actual = []

        # Guardar última tabla si existe
        if tabla_actual and len(tabla_actual) > 1:
            tablas_detectadas.append(tabla_actual)

        return tablas_detectadas

    except Exception as e:
        print(f"    ⚠ No se pudieron detectar tablas en OCR: {str(e)}")
        return []

def es_pdf_escaneado(ruta_pdf: str) -> bool:
    """Detecta si un PDF es escaneado (sin texto seleccionable)"""
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            # Revisar las primeras 3 páginas (o todas si hay menos)
            paginas_a_revisar = min(3, len(pdf.pages))
            texto_total = ""

            for i in range(paginas_a_revisar):
                texto = pdf.pages[i].extract_text()
                if texto:
                    texto_total += texto

            # Si hay muy poco texto o ninguno, probablemente es escaneado
            # Umbral: menos de 50 caracteres en las primeras páginas
            return len(texto_total.strip()) < 50
    except:
        return False

def extraer_texto_con_ocr(ruta_pdf: str) -> str:
    """Extrae texto de un PDF escaneado usando OCR, incluyendo detección de tablas"""
    if not OCR_DISPONIBLE:
        return "Error: OCR no está disponible. Instala pytesseract y pdf2image."

    texto_completo = []
    contador_tablas_global = 0

    try:
        print("  🔍 PDF escaneado detectado. Aplicando OCR (esto puede tardar)...")

        # Convertir PDF a imágenes
        imagenes = convert_from_path(ruta_pdf, dpi=200)  # DPI más alto = mejor calidad OCR

        total_paginas = len(imagenes)
        for i, imagen in enumerate(imagenes, 1):
            print(f"    OCR: Página {i}/{total_paginas}...")

            # Extraer texto de la página
            texto_pagina = pytesseract.image_to_string(imagen, lang='spa+eng')

            # Intentar detectar tablas en la imagen
            tablas_detectadas = extraer_tablas_ocr(imagen)

            # Si se detectaron tablas, procesarlas
            if tablas_detectadas:
                # Para cada tabla detectada, insertarla en el texto
                for tabla in tablas_detectadas:
                    contador_tablas_global += 1
                    tabla_json = convertir_tabla_a_json_string(tabla, contador_tablas_global)
                    if tabla_json:
                        # Insertar la tabla al final del texto de la página
                        texto_pagina += f" {tabla_json} "

            if texto_pagina.strip():
                texto_completo.append(texto_pagina)

        print("  ✅ OCR completado")
        return '\n\n'.join(texto_completo)

    except Exception as e:
        print(f"  ❌ Error en OCR: {str(e)}")
        return f"Error al aplicar OCR: {str(e)}"

def detectar_texto_rotado_margenes(page) -> List[str]:
    """Detecta texto rotado en márgenes laterales (cintas identificativas)

    Args:
        page: Objeto página de pdfplumber

    Returns:
        Lista de textos que están rotados y probablemente son márgenes laterales
    """
    textos_rotados = []

    try:
        # Obtener todos los caracteres con sus propiedades
        chars = page.chars

        if not chars:
            return []

        # Obtener dimensiones de la página
        page_width = page.width
        page_height = page.height

        # Definir zonas de margen (10% de cada lado)
        margen_izquierdo = page_width * 0.10
        margen_derecho = page_width * 0.90

        # Agrupar caracteres por líneas de texto
        lineas_rotadas = []

        for char in chars:
            x = char.get('x0', 0)
            # Detectar rotación: pdfplumber marca la matriz de transformación
            # Texto rotado típicamente tiene 'matrix' diferente de [1,0,0,1,x,y]
            # O está en las zonas de margen

            # Verificar si está en zona de margen lateral
            en_margen_lateral = x < margen_izquierdo or x > margen_derecho

            if en_margen_lateral:
                texto = char.get('text', '')
                if texto.strip():
                    lineas_rotadas.append(texto)

        # Unir caracteres consecutivos en el margen
        if lineas_rotadas:
            texto_margen = ''.join(lineas_rotadas).strip()
            if len(texto_margen) > 3:  # Solo si tiene contenido significativo
                textos_rotados.append(texto_margen)

    except Exception as e:
        # Si hay error, retornar lista vacía
        pass

    return textos_rotados


def detectar_encabezado_pie(paginas_texto: List[str]) -> Tuple[List[str], List[str]]:
    """Detecta patrones comunes de encabezados y pies de página

    Retorna listas de patrones que aparecen consistentemente en las primeras/últimas líneas
    de múltiples páginas, indicando que son encabezados/pies de página.
    """
    encabezados = []
    pies = []

    if len(paginas_texto) < 2:  # Reducido a 2 páginas mínimo
        return [], []

    # Analizar las primeras y últimas líneas de cada página
    for pagina in paginas_texto:
        lineas = [l.strip() for l in pagina.split('\n') if l.strip()]
        if len(lineas) >= 5:  # Solo analizar páginas con contenido suficiente
            # Primeras 3 líneas (posible encabezado) - aumentado para capturar más
            encabezados.extend(lineas[:3])
            # Últimas 3 líneas (posible pie) - aumentado para capturar más
            pies.extend(lineas[-3:])

    # Encontrar líneas repetitivas (aparecen en más del 30% de las páginas)
    from collections import Counter

    encabezado_counter = Counter(encabezados)
    pie_counter = Counter(pies)

    # Reducir umbral al 30% para ser más agresivos en la detección
    umbral = len(paginas_texto) * 0.30

    # Filtrar candidatos que sean realmente repetitivos
    encabezados_comunes = [
        texto for texto, count in encabezado_counter.items()
        if count > umbral
        and len(texto.strip()) > 2  # Líneas muy cortas también
        and len(texto.strip()) < 200  # Aumentado el límite
        and not re.search(r'^(TÍTULO|CAPÍTULO|Capítulo|SECCIÓN|Sección|Artículo\s+\d+)', texto)  # Títulos estructurales con número
    ]

    pies_comunes = [
        texto for texto, count in pie_counter.items()
        if count > umbral
        and len(texto.strip()) > 2
        and len(texto.strip()) < 200
        and not re.search(r'^(TÍTULO|CAPÍTULO|Capítulo|SECCIÓN|Sección|Artículo\s+\d+)', texto)
    ]

    return encabezados_comunes, pies_comunes


def eliminar_encabezados_pies_contextual(paginas_texto: List[str], encabezados: List[str], pies: List[str], margenes_laterales: List[str] = None) -> List[str]:
    """Elimina encabezados, pies de página y márgenes laterales de forma AGRESIVA

    Elimina:
    - Encabezados detectados automáticamente
    - Pies de página detectados automáticamente
    - Márgenes laterales y cintas identificativas
    - Patrones comunes: DIARIO OFICIAL, fechas, números de página, instituciones, etc.
    """
    if margenes_laterales is None:
        margenes_laterales = []

    paginas_limpiadas = []

    # Patrones GENÉRICOS y MUY AGRESIVOS de encabezados/pies/márgenes a eliminar
    patrones_eliminar = [
        # Patrones de texto fragmentado (cintas laterales)
        r'^[A-ZÁÉÍÓÚÑ]\s+[A-ZÁÉÍÓÚÑ]\s+[A-ZÁÉÍÓÚÑ]',  # Letras separadas: L Í T
        r'^[A-ZÁÉÍÓÚÑ]{1,2}\s*$',  # 1-2 letras solas
        r'^\d\s*$',  # Un solo dígito

        # Patrones específicos de EDOMEX
        r'CONSTITUCIÓN\s+POLÍTICA\s+DEL\s+ESTADO',
        r'ESTADO\s+LIBRE\s+Y\s+SOBERANO',
        r'LIBRE\s+Y\s+SOBERANO\s+DE\s+MÉXICO',
        r'DE\s+MÉXICO',
        r'CC\s+OO\s+N\s+S',  # Texto muy espaciado
        r'[A-Z]\s+[A-Z]\s+[A-Z]\s+[A-Z]',  # 4+ letras espaciadas

        # Patrones de Diario Oficial
        r'DIARIO OFICIAL',
        r'Diario Oficial',
        r'(Primera|Segunda|Tercera|Cuarta|Quinta|Sexta|Séptima|Octava)\s+(Sección|SECCIÓN|Seccion)',

        # Fechas en encabezados (más patrones)
        r'(Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+\d+\s+de\s+\w+\s+de\s+\d{4}',
        r'DOF\s+\d{2}[-/]\d{2}[-/]\d{4}',
        r'\d{2}\s+de\s+\w+\s+de\s+\d{4}',
        r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',
        r'(Enero|Febrero|Marzo|Abril|Mayo|Junio|Julio|Agosto|Septiembre|Octubre|Noviembre|Diciembre)\s+de\s+\d{4}',

        # Números de página (más variantes)
        r'^\d+\s*$',  # Solo números
        r'^-\s*\d+\s*-$',  # -1-, -2-
        r'^Página\s+\d+',
        r'^Page\s+\d+',
        r'^Pág\.\s*\d+',
        r'^\d+\s+de\s+\d+\s*$',  # "1 de 21"
        r'^\d+\s*/\s*\d+\s*$',  # "1/21"
        r'^\d+\s+\(\w+\s+(Sección|SECCIÓN)\)',

        # Patrones de instituciones (más completos)
        r'CÁMARA DE DIPUTADOS',
        r'CÁMARA DE SENADORES',
        r'CONGRESO DE LA UNIÓN',
        r'H\.\s*CONGRESO',
        r'HONORABLE CONGRESO',
        r'^Secretaría\s+(General|de\s+\w+)',
        r'^Secretaría\s+de\s+Servicios',
        r'PODER EJECUTIVO',
        r'PODER LEGISLATIVO',
        r'PODER JUDICIAL',
        r'GOBIERNO\s+(FEDERAL|DEL ESTADO|DE\s+)',
        r'GACETA\s+(OFICIAL|PARLAMENTARIA)',

        # Patrones de leyes/reglamentos en encabezados
        r'^(Nuevo\s+)?Reglamento\s+DOF',
        r'REGLAMENTO\s+(DE\s+LA\s+)?LEY',
        r'^LEY\s+FEDERAL\s+DE',
        r'^CÓDIGO\s+(CIVIL|PENAL|FEDERAL)',
        r'GUBERNAMENTAL\s*$',
        r'TRANSPARENCIA\s+Y\s+ACCESO',
        r'ÚLTIMA\s+REFORMA',
        r'PUBLICADA?\s+EN\s+EL\s+DOF',
        r'PUBLICADA?\s+EN\s+(LA\s+)?GACETA',

        # Patrones de títulos largos en mayúsculas
        r'^[A-ZÁÉÍÓÚÑ\s]{45,}$',  # Líneas de solo mayúsculas muy largas

        # Patrones de márgenes laterales / cintas identificativas
        r'^[A-ZÁÉÍÓÚÑ]{1,3}\s*$',  # 1-3 letras mayúsculas solas (posible cinta)
        r'^\d{1,4}\s*$',  # Solo números cortos (año en margen)
        r'^[IVXLCDM]+\s*$',  # Números romanos solos

        # Patrones específicos de encabezados repetitivos
        r'^Al margen un sello',
        r'^TEXTO VIGENTE',
        r'^Nueva Ley publicada',
        r'^\d+\s+\(.*?(Sección|Edición)\)',

        # URLs y referencias web (a veces en pies)
        r'www\.',
        r'http[s]?://',
        r'\.gob\.mx',
        r'\.com\.mx',

        # Firmas y sellos (típicos en pies)
        r'Firma\s+electrónica',
        r'Sello\s+digital',
        r'Cadena\s+original',
    ]

    for pagina in paginas_texto:
        lineas = pagina.split('\n')
        lineas_mantener = []

        for i, linea in enumerate(lineas):
            linea_stripped = linea.strip()

            # Saltar líneas vacías
            if not linea_stripped:
                continue

            es_eliminar = False

            # PRIMERO: Verificar patrones de texto fragmentado EN TODA LA PÁGINA
            # (no solo en encabezado/pie, porque las cintas laterales están en todo el margen)
            for patron in patrones_eliminar:
                # Patrones de texto fragmentado se verifican en TODA la página
                if patron.startswith(r'^[A-ZÁÉÍÓÚÑ]') or r'CC\s+OO' in patron or 'CONSTITUCIÓN' in patron or 'LIBRE' in patron:
                    if re.search(patron, linea_stripped, re.IGNORECASE):
                        es_eliminar = True
                        break

            # Si ya se marcó para eliminar, pasar a la siguiente línea
            if es_eliminar:
                continue

            # Verificar patrones agresivos en las primeras 10 líneas
            if i < 10:
                for patron in patrones_eliminar:
                    if re.search(patron, linea_stripped, re.IGNORECASE):
                        es_eliminar = True
                        break

            # Verificar patrones agresivos en las últimas 10 líneas
            if i >= len(lineas) - 10:
                for patron in patrones_eliminar:
                    if re.search(patron, linea_stripped, re.IGNORECASE):
                        es_eliminar = True
                        break

            # Verificar encabezados detectados automáticamente (primeras 10 líneas)
            if i < 10:
                for encabezado in encabezados:
                    # Comparación exacta o similitud alta
                    if linea_stripped == encabezado or encabezado in linea_stripped:
                        es_eliminar = True
                        break

            # Verificar pies detectados automáticamente (últimas 10 líneas)
            if i >= len(lineas) - 10:
                for pie in pies:
                    if linea_stripped == pie or pie in linea_stripped:
                        es_eliminar = True
                        break

            # Verificar márgenes laterales detectados
            if margenes_laterales:
                for margen in margenes_laterales:
                    if margen in linea_stripped:
                        es_eliminar = True
                        break

            # Mantener la línea solo si NO debe eliminarse
            if not es_eliminar:
                lineas_mantener.append(linea)

        # Reconstruir la página sin encabezados/pies/márgenes
        paginas_limpiadas.append('\n'.join(lineas_mantener))

    return paginas_limpiadas

def _tiene_cuadricula_completa(page, table_bbox) -> bool:
    """
    Verifica que haya una cuadrícula COMPLETA y CERRADA dentro del bbox de la tabla.
    Rechaza texto alineado, firmas, y líneas decorativas.

    Args:
        page: Objeto página de pdfplumber
        table_bbox: Bounding box de la tabla (x0, top, x1, bottom)

    Returns:
        True si hay cuadrícula real, False si es texto alineado
    """
    try:
        x0, top, x1, bottom = table_bbox

        # Obtener líneas dentro del área de la tabla
        edges = page.edges
        if not edges or len(edges) < 8:
            return False

        # Filtrar líneas que están dentro del bbox de la tabla
        h_lines = [e for e in edges
                  if e.get('orientation') == 'h'
                  and e.get('y0', 0) >= top
                  and e.get('y0', 0) <= bottom
                  and e.get('x0', 0) >= x0 - 10
                  and e.get('x1', 0) <= x1 + 10
                  and (e.get('x1', 0) - e.get('x0', 0)) > 50]  # Líneas significativas

        v_lines = [e for e in edges
                  if e.get('orientation') == 'v'
                  and e.get('x0', 0) >= x0 - 10
                  and e.get('x0', 0) <= x1 + 10
                  and e.get('y0', 0) >= top - 10
                  and e.get('y1', 0) <= bottom + 10
                  and (e.get('y1', 0) - e.get('y0', 0)) > 20]  # Líneas significativas

        # CRÍTICO: Debe tener líneas verticales Y horizontales
        if len(v_lines) < 2:  # Al menos 2 verticales (inicio y fin de columnas)
            return False

        if len(h_lines) < 3:  # Al menos 3 horizontales (encabezado + 2 filas)
            return False

        # Verificar RATIO: debe haber equilibrio
        ratio = len(h_lines) / len(v_lines) if len(v_lines) > 0 else 999
        if ratio > 6.0 or ratio < 0.15:  # Muy desbalanceado = líneas decorativas
            return False

        # Verificar intersecciones (cuadrícula real)
        intersections = 0
        tolerance = 15

        for h in h_lines:
            for v in v_lines:
                h_x0, h_x1, h_y = h.get('x0', 0), h.get('x1', 0), h.get('y0', 0)
                v_x, v_y0, v_y1 = v.get('x0', 0), v.get('y0', 0), v.get('y1', 0)

                if (h_x0 - tolerance <= v_x <= h_x1 + tolerance and
                    v_y0 - tolerance <= h_y <= v_y1 + tolerance):
                    intersections += 1

        # Requiere al menos 4 intersecciones (mínimo 2x2)
        if intersections < 4:
            return False

        return True

    except Exception as e:
        return False


def _es_tabla_real(tabla_data: List[List], page, table_bbox) -> bool:
    """
    Valida que sea una tabla REAL con datos tabulares.
    Rechaza:
    - Texto alineado sin bordes
    - Firmas y nombres alineados
    - Listas con viñetas espaciadas
    - Secciones centradas

    Args:
        tabla_data: Datos extraídos de la tabla
        page: Página de pdfplumber
        table_bbox: Bounding box de la tabla

    Returns:
        True si es tabla real, False si es texto formateado
    """
    if not tabla_data or len(tabla_data) < 2:
        return False

    # PASO 1: Verificar cuadrícula física
    if not _tiene_cuadricula_completa(page, table_bbox):
        return False

    # PASO 2: Verificar estructura mínima
    # Al menos 2 columnas con contenido
    primera_fila = tabla_data[0]
    columnas_con_contenido = sum(1 for c in primera_fila if c and str(c).strip())
    if columnas_con_contenido < 2:
        return False

    # Al menos 2 filas (encabezado + 1 dato)
    if len(tabla_data) < 2:
        return False

    # PASO 3: Verificar densidad de celdas llenas
    filled = sum(1 for row in tabla_data for cell in row if cell and str(cell).strip())
    total = sum(len(row) for row in tabla_data)

    if total == 0 or filled < 4:  # Mínimo 4 celdas con contenido
        return False

    # Al menos 30% de celdas llenas
    if (filled / total) < 0.30:
        return False

    # PASO 4: Detectar patrones de NO-tabla
    todo_texto = ' '.join([str(c).lower() for row in tabla_data for c in row if c])

    # Patrón 1: Firmas (palabras clave comunes)
    firmas_palabras = ['firma', 'firmó', 'rubrica', 'rúbrica', 'sello', 'presente',
                       'testigo', 'secretario', 'presidente', 'titular', 'director',
                       'fecha:', 'lugar:', 'ciudad de méxico', 'cd. de méxico']
    firmas_count = sum(1 for palabra in firmas_palabras if palabra in todo_texto)

    # Si tiene muchas palabras de firma Y pocas filas, probablemente es firma
    if firmas_count >= 2 and len(tabla_data) <= 4:
        return False

    # Patrón 2: Encabezados repetitivos muy cortos (posible texto centrado)
    if len(tabla_data[0]) <= 2:
        palabras_primera_fila = [str(c).split() for c in tabla_data[0] if c]
        if all(len(palabras) <= 2 for palabras in palabras_primera_fila):
            # Si todas las celdas del encabezado tienen ≤2 palabras, verificar contenido
            palabras_datos = []
            for row in tabla_data[1:]:
                for celda in row:
                    if celda:
                        palabras_datos.extend(str(celda).split())

            # Si las celdas de datos también son muy cortas, es texto alineado
            if len(palabras_datos) > 0 and sum(len(p) for p in palabras_datos) / len(palabras_datos) < 8:
                return False

    # Patrón 3: Detectar si la "tabla" es solo una lista vertical
    # (una sola columna significativa)
    columnas_significativas = 0
    for col_idx in range(len(tabla_data[0])):
        contenido_col = [row[col_idx] for row in tabla_data if col_idx < len(row) and row[col_idx]]
        if len(contenido_col) >= 2:
            columnas_significativas += 1

    if columnas_significativas < 2:
        return False

    # PASO 5: Verificar que el encabezado sea diferente de los datos
    encabezado_texto = ' '.join([str(c).lower() for c in tabla_data[0] if c])
    datos_texto = ' '.join([str(c).lower() for row in tabla_data[1:] for c in row if c])

    # Si el encabezado es idéntico a los datos, no es tabla
    if encabezado_texto == datos_texto:
        return False

    # Si pasó todas las validaciones, es una tabla real
    return True


def extraer_contenido_pdf(ruta_pdf: str) -> Dict[str, str]:
    """Extrae el contenido de un PDF incluyendo tablas como JSON embebido en el texto.
    Detecta automáticamente si el PDF es escaneado y aplica OCR si es necesario.
    """

    # Limpiar el título del PDF (quitar prefijos numéricos)
    titulo = limpiar_titulo_pdf(Path(ruta_pdf).stem)
    contenido_completo = []
    es_escaneado = False
    contador_tablas_global = 0
    todos_margenes_laterales = []  # Lista para acumular márgenes laterales detectados

    # Primero verificar si es un PDF escaneado
    if es_pdf_escaneado(ruta_pdf):
        es_escaneado = True
        print(f"  📸 Tipo: PDF escaneado")

        # Usar OCR para extraer el texto (ya incluye detección de tablas)
        texto_ocr = extraer_texto_con_ocr(ruta_pdf)

        if texto_ocr.startswith("Error"):
            return {
                "Titulo": titulo,
                "contenido": texto_ocr
            }

        # El texto OCR ya contiene las tablas embebidas como JSON
        contenido_completo.append(texto_ocr)

    else:
        print(f"  📄 Tipo: PDF con texto digital")

        try:
            with pdfplumber.open(ruta_pdf) as pdf:
                # Procesar cada página
                for num_pagina, pagina in enumerate(pdf.pages):
                    contenido_pagina_partes = []

                    # Detectar texto rotado en márgenes laterales
                    margenes_pagina = detectar_texto_rotado_margenes(pagina)
                    if margenes_pagina:
                        todos_margenes_laterales.extend(margenes_pagina)

                    # Detectar tablas con configuración optimizada para máxima precisión
                    tablas_encontradas = pagina.find_tables(table_settings={
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                        "explicit_vertical_lines": pagina.curves + pagina.edges,
                        "explicit_horizontal_lines": pagina.curves + pagina.edges,
                        "snap_tolerance": 3,
                        "join_tolerance": 3,
                        "edge_min_length": 3,
                        "min_words_vertical": 3,
                        "min_words_horizontal": 1,
                        "intersection_tolerance": 3,
                        "text_tolerance": 3,
                        "text_x_tolerance": 2,
                        "text_y_tolerance": 2,
                    })

                    if tablas_encontradas:
                        # Si hay tablas, procesarlas y eliminar su texto del contenido

                        # Primero, extraer y procesar todas las tablas con su información de posición
                        tablas_info = []  # Lista con toda la información de las tablas
                        textos_celdas_tabla = set()  # Usar set para evitar duplicados
                        lineas_tabla_completas = []  # Guardar líneas completas de tabla para mejor detección

                        for table_obj in tablas_encontradas:
                            # Extraer con configuración mejorada que preserva TODO el contenido
                            tabla_data = table_obj.extract(
                                x_tolerance=2,
                                y_tolerance=2,
                            )
                            if tabla_data and len(tabla_data) > 0:
                                # VALIDACIÓN ESTRICTA: Verificar que sea una tabla real
                                table_bbox = table_obj.bbox if hasattr(table_obj, 'bbox') else None
                                if not table_bbox or not _es_tabla_real(tabla_data, pagina, table_bbox):
                                    # No es una tabla real, saltar esta detección
                                    print(f"    ⚠ Falso positivo detectado en página {num_pagina+1} - Ignorando (probablemente texto alineado/firmas)")
                                    continue

                                contador_tablas_global += 1
                                print(f"    ✓ Tabla real validada en página {num_pagina+1}")
                                tabla_json = convertir_tabla_a_json_string(tabla_data, contador_tablas_global)
                                if tabla_json:
                                    # Guardar información de la tabla incluyendo su posición
                                    tabla_info = {
                                        'json': tabla_json,
                                        'bbox': table_obj.bbox if hasattr(table_obj, 'bbox') else None,
                                        'primera_linea': None,  # Se determinará después
                                        'ultima_linea': None,    # Se determinará después
                                        'textos_celdas': set(),
                                        'filas_completas': []
                                    }

                                    # Recopilar TODOS los textos de las celdas, INCLUYENDO ENCABEZADOS
                                    for i, fila in enumerate(tabla_data):
                                        if fila:
                                            fila_textos = []
                                            for celda in fila:
                                                if celda is not None and str(celda).strip():
                                                    texto_celda = str(celda).strip()
                                                    fila_textos.append(texto_celda)

                                                    # Si la celda tiene saltos de línea, dividirla
                                                    if '\n' in texto_celda:
                                                        # Cada línea dentro de la celda es un texto a buscar
                                                        for linea_celda in texto_celda.split('\n'):
                                                            if linea_celda.strip():
                                                                textos_celdas_tabla.add(linea_celda.strip())
                                                                tabla_info['textos_celdas'].add(linea_celda.strip())
                                                    else:
                                                        textos_celdas_tabla.add(texto_celda)
                                                        tabla_info['textos_celdas'].add(texto_celda)

                                            # Guardar combinaciones de celdas de la misma fila
                                            if len(fila_textos) > 1:
                                                # Diferentes formas en que podría aparecer la fila
                                                fila_espacios = ' '.join(fila_textos)
                                                fila_tabs = '\t'.join(fila_textos)
                                                lineas_tabla_completas.append(fila_espacios)
                                                lineas_tabla_completas.append(fila_tabs)
                                                tabla_info['filas_completas'].append(fila_espacios)
                                                tabla_info['filas_completas'].append(fila_tabs)

                                    tablas_info.append(tabla_info)

                        # Obtener el texto completo de la página
                        texto_completo_pagina = pagina.extract_text() or ""

                        # Procesar líneas e identificar dónde están las tablas
                        lineas_originales = texto_completo_pagina.split('\n')

                        # Primera pasada: identificar qué líneas pertenecen a cada tabla
                        for i, linea in enumerate(lineas_originales):
                            linea_stripped = linea.strip()

                            if linea_stripped:
                                # Verificar a qué tabla pertenece esta línea (si es que pertenece a alguna)
                                for tabla_info in tablas_info:
                                    es_de_esta_tabla = False

                                    # Verificar si la línea es parte de esta tabla específica
                                    # 1. Verificar filas completas
                                    for fila_completa in tabla_info['filas_completas']:
                                        if linea_stripped == fila_completa:
                                            es_de_esta_tabla = True
                                            break
                                        # Verificar similitud
                                        if len(linea_stripped) > 10:
                                            palabras_linea = set(linea_stripped.split())
                                            palabras_tabla = set(fila_completa.split())
                                            if palabras_linea and palabras_tabla:
                                                coincidencia = len(palabras_linea & palabras_tabla) / len(palabras_linea | palabras_tabla)
                                                if coincidencia > 0.7:
                                                    es_de_esta_tabla = True
                                                    break

                                    # 2. Verificar celdas individuales
                                    if not es_de_esta_tabla:
                                        elementos_encontrados = []
                                        for texto_celda in tabla_info['textos_celdas']:
                                            if len(texto_celda) > 4 and texto_celda in linea_stripped:
                                                elementos_encontrados.append(texto_celda)

                                        # Si tiene 2+ elementos de esta tabla específica
                                        if len(elementos_encontrados) >= 2:
                                            es_de_esta_tabla = True
                                        # O si un elemento es >60% de la línea
                                        elif len(elementos_encontrados) == 1:
                                            if len(elementos_encontrados[0]) >= len(linea_stripped) * 0.6:
                                                es_de_esta_tabla = True

                                        # Verificación exacta
                                        if linea_stripped in tabla_info['textos_celdas']:
                                            es_de_esta_tabla = True

                                    # Si esta línea pertenece a esta tabla, actualizar posiciones
                                    if es_de_esta_tabla:
                                        if tabla_info['primera_linea'] is None:
                                            tabla_info['primera_linea'] = i
                                        tabla_info['ultima_linea'] = i

                        # Segunda pasada: reconstruir el contenido con las tablas en su posición
                        contenido_final_partes = []
                        i = 0

                        while i < len(lineas_originales):
                            # Verificar si alguna tabla comienza en esta línea
                            tabla_aqui = None
                            for tabla_info in tablas_info:
                                if tabla_info['primera_linea'] == i:
                                    tabla_aqui = tabla_info
                                    break

                            if tabla_aqui:
                                # Insertar el JSON de la tabla en lugar del texto original
                                contenido_final_partes.append(tabla_aqui['json'])
                                # Saltar todas las líneas de esta tabla
                                if tabla_aqui['ultima_linea'] is not None:
                                    i = tabla_aqui['ultima_linea'] + 1
                                else:
                                    i += 1
                            else:
                                # Verificar si esta línea NO pertenece a ninguna tabla
                                es_parte_de_alguna_tabla = False
                                for tabla_info in tablas_info:
                                    if (tabla_info['primera_linea'] is not None and
                                        tabla_info['ultima_linea'] is not None and
                                        tabla_info['primera_linea'] <= i <= tabla_info['ultima_linea']):
                                        es_parte_de_alguna_tabla = True
                                        break

                                if not es_parte_de_alguna_tabla:
                                    # Esta línea es texto normal, agregarla
                                    contenido_final_partes.append(lineas_originales[i])

                                i += 1

                        # Unir todo el contenido
                        contenido_pagina = '\n'.join(contenido_final_partes)

                        # Limpiar líneas vacías excesivas
                        contenido_pagina = re.sub(r'\n{3,}', '\n\n', contenido_pagina)

                        if contenido_pagina.strip():
                            contenido_pagina_partes.append(contenido_pagina.strip())

                    else:
                        # No hay tablas, extraer texto normalmente
                        texto = pagina.extract_text()
                        if texto:
                            contenido_pagina_partes.append(texto)

                    # Unir las partes de esta página
                    if contenido_pagina_partes:
                        contenido_pagina = ' '.join(contenido_pagina_partes)
                        contenido_completo.append(contenido_pagina)

        except Exception as e:
            print(f"  ⚠ Error procesando PDF digital: {str(e)}")
            # Intentar con OCR como respaldo
            if OCR_DISPONIBLE:
                print("  🔄 Intentando con OCR como respaldo...")
                texto_ocr = extraer_texto_con_ocr(ruta_pdf)
                if not texto_ocr.startswith("Error"):
                    contenido_completo.append(texto_ocr)
                    es_escaneado = True
                else:
                    return {
                        "Titulo": titulo,
                        "contenido": f"Error al procesar: {str(e)}"
                    }
            else:
                return {
                    "Titulo": titulo,
                    "contenido": f"Error al procesar: {str(e)}"
                }

    # Procesar el texto extraído
    if contenido_completo:
        # Detectar y ELIMINAR encabezados/pies de página
        encabezados, pies = detectar_encabezado_pie(contenido_completo)

        # Obtener márgenes laterales únicos
        margenes_unicos = list(set(todos_margenes_laterales)) if todos_margenes_laterales else []

        # Mostrar información de limpieza
        if encabezados:
            print(f"  🧹 Encabezados detectados: {len(set(encabezados))}")
        if pies:
            print(f"  🧹 Pies de página detectados: {len(set(pies))}")
        if margenes_unicos:
            print(f"  🧹 Márgenes laterales detectados: {len(margenes_unicos)}")

        # Eliminar encabezados, pies y márgenes laterales
        paginas_limpiadas = eliminar_encabezados_pies_contextual(contenido_completo, encabezados, pies, margenes_unicos)

        # Unir páginas con un solo salto de línea (no doble)
        contenido_final = '\n'.join(paginas_limpiadas)

        # PASO CRÍTICO: Eliminar texto fragmentado (cintas laterales letra por letra)
        print(f"  🔧 Eliminando texto fragmentado...")
        contenido_final = detectar_y_eliminar_texto_fragmentado(contenido_final)

        # Proteger las tablas JSON durante la corrección de saltos
        tablas_encontradas = []
        marcador_base = "TABLA_PLACEHOLDER"

        # Encontrar y reemplazar temporalmente todas las tablas
        patron_tabla = r'\{"tabla_\d+":.*?\}\}'
        for match in re.finditer(patron_tabla, contenido_final):
            tabla_json = match.group()
            marcador = f"{marcador_base}{len(tablas_encontradas)}_"
            tablas_encontradas.append(tabla_json)
            contenido_final = contenido_final.replace(tabla_json, marcador, 1)

        # Aplicar corrección de saltos de línea
        contenido_final = corregir_saltos_linea(contenido_final)

        # Restaurar las tablas JSON
        for i, tabla_json in enumerate(tablas_encontradas):
            marcador = f"{marcador_base}{i}_"
            contenido_final = contenido_final.replace(marcador, tabla_json)

        # Limpieza final de espacios
        contenido_final = re.sub(r'[ \t]+', ' ', contenido_final)
        contenido_final = re.sub(r' +$', '', contenido_final, flags=re.MULTILINE)

        return {
            "Titulo": titulo,
            "contenido": contenido_final
        }

    else:
        return {
            "Titulo": titulo,
            "contenido": "No se pudo extraer contenido del PDF"
        }

def procesar_carpeta_pdfs(ruta_carpeta: str, archivo_salida: str = "pdfs_extraidos.json"):
    """Procesa todos los PDFs en una carpeta y guarda el resultado en JSON"""

    # Convertir a Path para manejo más fácil
    carpeta = Path(ruta_carpeta)

    if not carpeta.exists():
        print(f"❌ La carpeta {ruta_carpeta} no existe")
        return

    # Buscar todos los archivos PDF
    archivos_pdf = list(carpeta.glob("*.pdf"))

    if not archivos_pdf:
        print(f"❌ No se encontraron archivos PDF en {ruta_carpeta}")
        return

    # ORDENAR ARCHIVOS: primero por número si tienen prefijo numérico, luego alfabéticamente
    def obtener_clave_orden(archivo_path):
        """Extrae clave de ordenamiento del nombre del archivo"""
        nombre = archivo_path.name

        # Buscar número al inicio del nombre
        match = re.match(r'^(\d+)', nombre)

        if match:
            # Si tiene número al inicio, usar el número para ordenar
            numero = int(match.group(1))
            return (0, numero, nombre.lower())
        else:
            # Si no tiene número, ordenar alfabéticamente después de los numerados
            return (1, 0, nombre.lower())

    # Ordenar los archivos usando la función de clave
    archivos_pdf = sorted(archivos_pdf, key=obtener_clave_orden)

    print(f"📁 Carpeta: {ruta_carpeta}")
    print(f"📊 Total de archivos PDF encontrados: {len(archivos_pdf)}")
    print(f"📋 Orden de procesamiento:")

    # Mostrar los primeros 10 archivos para confirmar el orden
    for i, pdf in enumerate(archivos_pdf[:10], 1):
        print(f"   {i}. {pdf.name}")
    if len(archivos_pdf) > 10:
        print(f"   ... y {len(archivos_pdf) - 10} archivos más")

    print("-" * 50)

    resultados = []

    for i, pdf_path in enumerate(archivos_pdf, 1):
        print(f"📄 [{i}/{len(archivos_pdf)}] Procesando: {pdf_path.name}")

        resultado = extraer_contenido_pdf(str(pdf_path))
        resultados.append(resultado)

        # Mostrar progreso
        progreso = (i / len(archivos_pdf)) * 100
        print(f"  ✅ Completado - Progreso total: {progreso:.2f}%")
        print()

    # Guardar resultados en JSON con contenido en una sola línea física
    archivo_json = Path(archivo_salida)
    with open(archivo_json, 'w', encoding='utf-8') as f:
        # Escribir el JSON manualmente para controlar el formato exacto
        f.write('[\n')
        for i, resultado in enumerate(resultados):
            f.write('  {\n')
            f.write(f'    "Titulo": {json.dumps(resultado["Titulo"], ensure_ascii=False)},\n')
            # El contenido se escribe en una sola línea con saltos de línea escapados
            # y ahora incluye las tablas embebidas como JSON strings
            f.write(f'    "contenido": {json.dumps(resultado["contenido"], ensure_ascii=False)}\n')
            if i < len(resultados) - 1:
                f.write('  },\n')
            else:
                f.write('  }\n')
        f.write(']')

    print("-" * 50)
    print(f"✅ Proceso completado")
    print(f"📝 Resultados guardados en: {archivo_json.absolute()}")
    print(f"📊 Total de PDFs procesados: {len(resultados)}")

def main():
    # Ruta de la carpeta con PDFs
    ruta_carpeta = r"C:\Users\julii\Documents\EDOMEX\LEYES Y CÓDIGOS"

    # Nombre del archivo JSON de salida
    archivo_salida = r"C:\Users\julii\Documents\Practicas\drive\EDOMEX\json\B1 CONTENIDO\LC-contenido.json"

    print("🚀 Iniciando extracción de PDFs con tablas estructuradas...")
    print("=" * 50)

    if OCR_DISPONIBLE:
        print("✅ OCR disponible - Los PDFs escaneados serán procesados")
    else:
        print("⚠ OCR no disponible - Solo se procesarán PDFs con texto digital")

    print("=" * 50)

    procesar_carpeta_pdfs(ruta_carpeta, archivo_salida)

if __name__ == "__main__":
    main()