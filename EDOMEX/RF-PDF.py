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

def corregir_saltos_linea(texto: str) -> str:
    """Une líneas que son continuación de la misma frase, mantiene saltos cuando termina el texto

    FILOSOFÍA:
    - Unir líneas cuando es obvio que continúa la misma frase (evita "con\\nfundamento")
    - Mantener saltos cuando realmente termina un bloque de texto
    - Detectar finales naturales: puntuación fuerte, artículos, fracciones, líneas vacías
    """
    if not texto:
        return texto

    lineas = texto.split('\n')
    resultado = []
    buffer = []

    for i, linea in enumerate(lineas):
        linea_limpia = linea.strip()

        # Línea vacía = fin de bloque, vaciar buffer
        if not linea_limpia:
            if buffer:
                resultado.append(' '.join(buffer))
                buffer = []
            resultado.append('')  # Mantener separador
            continue

        # Detectar si esta línea INICIA un nuevo bloque (Artículo, Capítulo, Fracción, etc.)
        es_inicio_bloque = re.match(
            r'^(Artículo\s+\d+|ARTÍCULO\s+\d+|CAPÍTULO|TÍTULO|SECCIÓN|'
            r'[IVX]+\.|[A-Z]\)|a\)|[0-9]+\.|[0-9]+\)|'
            r'Fracción|DISPOSICIONES|TRANSITORIOS)',
            linea_limpia
        )

        if es_inicio_bloque:
            # Vaciar buffer anterior y empezar nuevo bloque
            if buffer:
                resultado.append(' '.join(buffer))
                buffer = []
            buffer = [linea_limpia]
            continue

        # Unir palabra cortada con guión
        if buffer and buffer[-1].endswith('-'):
            buffer[-1] = buffer[-1][:-1] + linea_limpia
            continue

        # Detectar si la línea ANTERIOR termina de forma natural (fin de bloque)
        if buffer:
            ultima = buffer[-1]

            # Casos donde SÍ termina el bloque (crear salto de línea):
            # 1. Termina con punto, punto y coma, dos puntos
            termina_con_puntuacion_fuerte = re.search(r'[.;:]\s*$', ultima)

            # 2. Termina con coma + la siguiente empieza con mayúscula (posible lista)
            termina_coma_sig_mayuscula = (
                ultima.endswith(',') and
                re.match(r'^[A-ZÁÉÍÓÚÑ]', linea_limpia)
            )

            # 3. La línea actual empieza con minúscula = continuación
            empieza_minuscula = re.match(r'^[a-záéíóúñ]', linea_limpia)

            # 4. Termina con preposición/conjunción = continuación obvia
            termina_con_conector = re.search(
                r'\b(y|e|o|u|de|del|al|el|la|los|las|un|una|en|con|sin|por|para|como|sobre|entre|desde|hasta|hacia|que|se|me|te|le|les)\s*$',
                ultima,
                re.IGNORECASE
            )

            # DECISIÓN: ¿Unir o crear nuevo bloque?
            if empieza_minuscula or termina_con_conector:
                # Es continuación, agregar al buffer
                buffer.append(linea_limpia)
            elif termina_con_puntuacion_fuerte or termina_coma_sig_mayuscula:
                # Termina bloque, vaciar buffer y empezar nuevo
                resultado.append(' '.join(buffer))
                buffer = [linea_limpia]
            else:
                # Caso ambiguo: agregar al buffer (preferir continuidad)
                buffer.append(linea_limpia)
        else:
            # No hay buffer, empezar uno nuevo
            buffer = [linea_limpia]

    # Vaciar buffer final
    if buffer:
        resultado.append(' '.join(buffer))

    # Unir resultado
    texto_final = '\n'.join(resultado)

    # Limpiar espacios múltiples
    texto_final = re.sub(r'  +', ' ', texto_final)
    texto_final = re.sub(r' +([.,;:?!)\]}>])', r'\1', texto_final)

    # Limpiar múltiples saltos (máximo 2)
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

def detectar_encabezado_pie(paginas_texto: List[str]) -> Tuple[List[str], List[str]]:
    """Detecta patrones comunes de encabezados y pies de página

    Retorna listas de patrones que aparecen consistentemente en las primeras/últimas líneas
    de múltiples páginas, indicando que son encabezados/pies de página.
    """
    encabezados = []
    pies = []

    if len(paginas_texto) < 3:  # Necesitamos al menos 3 páginas para detectar patrones
        return [], []

    # Analizar las primeras y últimas líneas de cada página
    for pagina in paginas_texto:
        lineas = [l.strip() for l in pagina.split('\n') if l.strip()]
        if len(lineas) >= 5:  # Solo analizar páginas con contenido suficiente
            # Primeras 2 líneas (posible encabezado) - reducido de 3 a 2
            encabezados.extend(lineas[:2])
            # Últimas 2 líneas (posible pie) - reducido de 3 a 2
            pies.extend(lineas[-2:])

    # Encontrar líneas repetitivas (aparecen en más del 40% de las páginas)
    from collections import Counter

    encabezado_counter = Counter(encabezados)
    pie_counter = Counter(pies)

    # Aumentar el umbral al 40% para ser más conservadores
    umbral = len(paginas_texto) * 0.4

    # Filtrar candidatos que sean realmente repetitivos y no muy largos
    encabezados_comunes = [
        texto for texto, count in encabezado_counter.items()
        if count > umbral
        and len(texto.strip()) > 3  # Ignorar líneas muy cortas
        and len(texto.strip()) < 150  # Ignorar líneas muy largas (probablemente contenido)
        and not re.search(r'^(TÍTULO|CAPÍTULO|Capítulo|SECCIÓN|Sección|Artículo)\s+', texto)  # No eliminar títulos estructurales
    ]

    pies_comunes = [
        texto for texto, count in pie_counter.items()
        if count > umbral
        and len(texto.strip()) > 3
        and len(texto.strip()) < 150
        and not re.search(r'^(TÍTULO|CAPÍTULO|Capítulo|SECCIÓN|Sección|Artículo)\s+', texto)
    ]

    return encabezados_comunes, pies_comunes


def eliminar_encabezados_pies_contextual(paginas_texto: List[str], encabezados: List[str], pies: List[str]) -> List[str]:
    """Elimina encabezados y pies de página de forma agresiva

    Elimina:
    - Encabezados detectados automáticamente
    - Patrones comunes: DIARIO OFICIAL, fechas, números de página, etc.
    """
    paginas_limpiadas = []

    # Patrones agresivos de encabezados/pies a eliminar
    patrones_eliminar = [
        r'DIARIO OFICIAL',
        r'Diario Oficial',
        r'(Primera|Segunda|Tercera|Cuarta) Sección',
        r'(Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)\s+\d+\s+de\s+\w+\s+de\s+\d{4}',
        r'^\d+\s*$',  # Solo números
        r'^Página\s+\d+',
        r'^Page\s+\d+',
        r'^\d+\s+\(\w+\s+Sección\)',
    ]

    for pagina in paginas_texto:
        lineas = pagina.split('\n')
        lineas_mantener = []

        for i, linea in enumerate(lineas):
            linea_stripped = linea.strip()
            es_encabezado = False
            es_pie = False

            # Verificar patrones agresivos en las primeras 5 líneas
            if i < 5:
                for patron in patrones_eliminar:
                    if re.search(patron, linea_stripped, re.IGNORECASE):
                        es_encabezado = True
                        break

            # Verificar patrones agresivos en las últimas 5 líneas
            if i >= len(lineas) - 5:
                for patron in patrones_eliminar:
                    if re.search(patron, linea_stripped, re.IGNORECASE):
                        es_pie = True
                        break

            # Verificar encabezados detectados automáticamente
            if i < 5:
                for encabezado in encabezados:
                    if linea_stripped == encabezado:
                        es_encabezado = True
                        break

            # Verificar pies detectados automáticamente
            if i >= len(lineas) - 5:
                for pie in pies:
                    if linea_stripped == pie:
                        es_pie = True
                        break

            # Mantener la línea solo si NO es encabezado ni pie
            if not es_encabezado and not es_pie:
                lineas_mantener.append(linea)

        # Reconstruir la página sin encabezados/pies
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
        paginas_limpiadas = eliminar_encabezados_pies_contextual(contenido_completo, encabezados, pies)

        # Unir páginas con un solo salto de línea (no doble)
        contenido_final = '\n'.join(paginas_limpiadas)

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
    ruta_carpeta = r"C:\Users\julii\Documents\EDOMEX\REGLAMENTOS FEDERALES"

    # Nombre del archivo JSON de salida
    archivo_salida = r"C:\Users\julii\Documents\Practicas\drive\EDOMEX\json\B1 CONTENIDO\RF-contenido.json"

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