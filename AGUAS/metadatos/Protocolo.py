#!/usr/bin/env python3
"""
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging
from datetime import datetime
import warnings
import unicodedata
from difflib import SequenceMatcher
warnings.filterwarnings('ignore')

# Librerías para procesamiento de PDF
import PyPDF2
import pdfplumber
import fitz  # PyMuPDF
from pdfminer.high_level import extract_text as pdfminer_extract
from pdfminer.layout import LAParams
import tabula
import easyocr
import numpy as np
from PIL import Image
import io

# Configuración de logging (solo consola)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ReglamentoProcessor:
    """Procesador especializado para Reglamentos y Leyes Federales Mexicanas"""
    
    def __init__(self, input_folder: str, output_folder: str):
        """
        Inicializa el procesador con las rutas especificadas

        Args:
            input_folder: Carpeta con los PDFs (ej: C:\\Users\\julii\\Documents\\Leyes y Reglamentos Federales\\REGLAMENTOS)
            output_folder: Carpeta donde se guardarán los JSON (ej: C:\\Users\\julii\\Documents\\Practicas\\Datos)
        """
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)

        # Crear la carpeta de salida si no existe
        self.output_folder.mkdir(parents=True, exist_ok=True)
        logger.info(f"Carpeta de salida: {self.output_folder}")
        
        # Inicializar EasyOCR (solo si se necesita)
        self.ocr_reader = None

        # Ruta del JSON con contenidos
        self.contenido_json_path = Path(r"C:\Users\julii\Documents\Practicas\drive\AGUAS\contenido\Protocolo\Protocolo-contenido.json")#contenidos de los PDFs
        self.contenido_data = None
        
        # Patrones regex para extraer información específica
        self.patterns = {
            'vigencia': r'(?:texto\s+vigente|vigente\s+a\s+partir|en\s+vigor)',
            'dof': r'(?:DOF|Diario\s+Oficial\s+de\s+la\s+Federación)',
            'articulos': r'(?:ARTÍCULO|Artículo|Art\.)\s+(\d+)',
            'capitulos': r'(?:CAPÍTULO|Capítulo|CAP\.)\s+([IVXLCDM]+|\d+)',
            'titulos': r'(?:TÍTULO|Título)\s+([IVXLCDM]+|\d+|\w+)',
            'texto_vigente': r'(?i)TEXTO\s+VIGENTE'  # MODIFICACIÓN: Agregado patrón para detectar "TEXTO VIGENTE"
        }
    
    def init_ocr(self):
        """Inicializa EasyOCR solo cuando es necesario"""
        if self.ocr_reader is None:
            logger.info("Inicializando EasyOCR...")
            self.ocr_reader = easyocr.Reader(['es'], gpu=False)
            logger.info("EasyOCR inicializado correctamente")

    def load_contenido_data(self):
        """Carga el JSON con los contenidos de los reglamentos"""
        try:
            if self.contenido_json_path.exists():
                with open(self.contenido_json_path, 'r', encoding='utf-8') as f:
                    self.contenido_data = json.load(f)
                logger.info(f"Cargados {len(self.contenido_data)} contenidos desde {self.contenido_json_path.name}")
                return True
            else:
                logger.warning(f"No se encontró el archivo de contenidos: {self.contenido_json_path}")
                return False
        except Exception as e:
            logger.error(f"Error cargando JSON de contenidos: {e}")
            return False
    
    def normalize_text(self, text: str) -> str:
        """
        Normaliza el texto para comparación: quita acentos, convierte a minúsculas,
        elimina caracteres especiales y espacios extras
        """
        if not text:
            return ""
        
        # Eliminar acentos y caracteres especiales
        text = unicodedata.normalize('NFKD', text)
        text = ''.join([c for c in text if not unicodedata.combining(c)])
        
        # Convertir a minúsculas
        text = text.lower()
        
        # Eliminar caracteres no alfanuméricos (excepto espacios)
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        
        # Eliminar espacios múltiples
        text = re.sub(r'\s+', ' ', text)
        
        # Eliminar espacios al inicio y final
        text = text.strip()
        
        return text

    def find_matching_contenido(self, titulo: str) -> Optional[str]:
        """
        Busca el contenido correspondiente al título del documento en juridico_docs.json
        Retorna el contenido si encuentra match, None si no
        """
        if not self.contenido_data or not titulo:
            return None

        titulo_normalizado = self.normalize_text(titulo)
        best_match = None
        best_ratio = 0
        best_contenido = None

        for item in self.contenido_data:
            # Obtener el título del JSON de contenidos - Buscar con "TITULO" (mayúsculas o minúsculas)
            titulo_json = item.get('TITULO') or item.get('titulo') or item.get('Titulo', '')
            if not titulo_json:
                continue

            titulo_json_normalizado = self.normalize_text(titulo_json)

            # Primero intentar match exacto
            if titulo_normalizado == titulo_json_normalizado:
                logger.info(f"Match exacto de contenido encontrado: {titulo[:50]}...")
                # Buscar el campo "contenido" (cualquier variación)
                return item.get('contenido') or item.get('Contenido') or item.get('CONTENIDO')

            # Calcular diferencia de longitud entre títulos
            len_diff = abs(len(titulo_normalizado) - len(titulo_json_normalizado))
            len_ratio = len_diff / max(len(titulo_normalizado), len(titulo_json_normalizado))

            # Rechazar si la diferencia de longitud es mayor al 25%
            if len_ratio > 0.25:
                continue

            # Calcular similaridad para encontrar el mejor match
            ratio = SequenceMatcher(None, titulo_normalizado, titulo_json_normalizado).ratio()

            # Aumentar umbral a 92% para mayor precisión
            if ratio > best_ratio and ratio > 0.92:
                # Verificar que no tenga palabras únicas problemáticas
                palabras_titulo = set(titulo_normalizado.split())
                palabras_json = set(titulo_json_normalizado.split())

                # Palabras que indican versiones/partes diferentes
                palabras_version = {'parte', 'tomo', 'volumen', 'seccion', 'libro', 'i', 'ii', 'iii', 'iv', 'v', '1', '2', '3', '4', '5'}

                # Verificar si hay palabras de versión en uno pero no en el otro
                tiene_version_titulo = bool(palabras_titulo & palabras_version)
                tiene_version_json = bool(palabras_json & palabras_version)

                # Si uno tiene palabras de versión y el otro no, rechazar el match
                if tiene_version_titulo != tiene_version_json:
                    continue

                best_ratio = ratio
                best_match = titulo_json
                # Buscar el campo "contenido" (cualquier variación)
                best_contenido = item.get('contenido') or item.get('Contenido') or item.get('CONTENIDO')

        if best_contenido:
            logger.info(f"Mejor match de contenido encontrado (similaridad {best_ratio:.2%}): {titulo[:50]}... -> {best_match[:50]}...")
            return best_contenido

        logger.warning(f"No se encontró contenido para: {titulo[:50]}...")
        return None
    
    def extract_title(self, text: str, pdf_path: Path) -> str:
        """
        Extrae el título del documento de forma más precisa
        """
        # Limpiar el texto para mejor procesamiento
        if not text or len(text.strip()) < 50:
            return self.clean_filename_to_title(pdf_path.stem)
        
        # Dividir en líneas y limpiar, ignorando líneas vacías
        lines = []
        for line in text.split('\n')[:200]:  # Buscar en más líneas
            cleaned = line.strip()
            # Ignorar líneas que son solo números de página o muy cortas
            if cleaned and len(cleaned) > 5 and not cleaned.isdigit():
                lines.append(cleaned)
        
        if not lines:
            return self.clean_filename_to_title(pdf_path.stem)
        
        # Buscar patrones específicos de títulos de documentos legales mexicanos
        title_patterns = [
            (r'^\s*(REGLAMENTO\s+(?:DE\s+)?(?:LA\s+)?(?:LEY\s+)?.*?)$', 'REGLAMENTO'),
            (r'^\s*(LEY\s+(?:FEDERAL\s+)?(?:GENERAL\s+)?(?:DE\s+)?.*?)$', 'LEY'),
            (r'^\s*(CÓDIGO\s+(?:FEDERAL\s+)?(?:DE\s+)?.*?)$', 'CÓDIGO'),
            (r'^\s*(DECRETO\s+(?:POR\s+EL\s+)?(?:QUE\s+)?.*?)$', 'DECRETO'),
            (r'^\s*(ACUERDO\s+(?:POR\s+EL\s+)?(?:QUE\s+)?.*?)$', 'ACUERDO'),
            (r'^\s*(NORMA\s+OFICIAL\s+MEXICANA.*?)$', 'NORMA'),
            (r'^\s*(ESTATUTO\s+(?:ORGÁNICO\s+)?(?:DE\s+)?.*?)$', 'ESTATUTO'),
            (r'^\s*(CONSTITUCIÓN\s+POLÍTICA.*?)$', 'CONSTITUCIÓN')
        ]
        
        # Buscar el título en las primeras líneas
        found_title = None
        title_line_index = -1
        
        for i, line in enumerate(lines[:100]):  # Buscar en las primeras 100 líneas
            # Ignorar líneas que contienen ARTÍCULO, CAPÍTULO, etc.
            if re.match(r'^\s*(ARTÍCULO|ART\.?|CAPÍTULO|CAP\.?|TÍTULO\s+[IVX]+|SECCIÓN)', line, re.IGNORECASE):
                continue
                
            for pattern, doc_type in title_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    found_title = match.group(1).strip()
                    title_line_index = i
                    
                    # Buscar continuación del título en las siguientes líneas
                    continuation_lines = []
                    for j in range(i + 1, min(i + 4, len(lines))):  # Revisar hasta 3 líneas más
                        next_line = lines[j].strip()
                        
                        # Detener si encontramos una sección o artículo
                        if re.match(r'^(ARTÍCULO|ART\.?|CAPÍTULO|CAP\.?|TÍTULO\s+[IVX]+|SECCIÓN|DISPOSICIONES|TRANSITORIOS)', next_line, re.IGNORECASE):
                            break
                        
                        # Detener si la línea es muy corta o es un número romano
                        if len(next_line) < 5 or re.match(r'^[IVX]+\.?\s*$', next_line):
                            break
                        
                        # Detener si parece ser una fecha o publicación
                        if re.search(r'(publicad[oa]|DOF|Diario\s+Oficial|vigente)', next_line, re.IGNORECASE):
                            break
                        
                        # Si parece ser continuación del título, agregarla
                        if len(next_line) > 10 and not next_line[0].islower():
                            continuation_lines.append(next_line)
                        else:
                            break
                    
                    # Unir las líneas de continuación
                    if continuation_lines:
                        found_title = f"{found_title} {' '.join(continuation_lines)}"
                    
                    # Limpiar y retornar el título
                    return self.clean_title(found_title)
        
        # Si no encontramos un título con los patrones, buscar líneas que parezcan títulos
        for i, line in enumerate(lines[:50]):
            # Buscar líneas en mayúsculas que contengan palabras clave de documentos legales
            if len(line) > 20:
                line_upper = line.upper()
                if any(word in line_upper for word in ['REGLAMENTO', 'LEY', 'CÓDIGO', 'DECRETO', 'NORMA']):
                    # Verificar que no sea un artículo o sección
                    if not re.match(r'^(ARTÍCULO|CAPÍTULO|TÍTULO\s+[IVX]+|SECCIÓN)', line, re.IGNORECASE):
                        return self.clean_title(line)
        
        # Si todo falla, usar el nombre del archivo
        return self.clean_filename_to_title(pdf_path.stem)
    
    def clean_title(self, title: str) -> str:
        """Limpia y formatea el título extraído"""
        # Eliminar caracteres extraños
        title = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', title)
        # Eliminar espacios múltiples
        title = re.sub(r'\s+', ' ', title)
        # Eliminar puntos al final
        title = title.rstrip('.')
        # Limitar longitud
        if len(title) > 300:
            title = title[:297] + "..."
        return title.strip()
    
    def clean_filename_to_title(self, filename: str) -> str:
        """Convierte el nombre del archivo en un título legible eliminando prefijos numéricos"""
        # Eliminar extensión si existe
        title = filename.replace('.pdf', '').replace('.PDF', '')
        
        # Eliminar prefijos numéricos comunes (1_, 2_, 01_, etc.)
        # Patrón mejorado para detectar varios formatos de numeración
        patterns_to_remove = [
            r'^\d+[_\-\s]+',        # 1_, 2-, 3 (número seguido de _, -, o espacio)
            r'^\d+\.\s*',           # 1. 2. (número seguido de punto)
            r'^\(\d+\)[_\-\s]*',    # (1)_ (2)- (número entre paréntesis)
            r'^[a-zA-Z]\d+[_\-\s]+', # A1_, B2- (letra y número)
            r'^\d{1,3}_',           # Cualquier número de 1-3 dígitos seguido de _
        ]
        
        for pattern in patterns_to_remove:
            title = re.sub(pattern, '', title, count=1)
        
        # Reemplazar guiones bajos y guiones por espacios
        title = title.replace('_', ' ').replace('-', ' ')
        
        # Eliminar espacios múltiples
        title = re.sub(r'\s+', ' ', title)
        
        # Capitalizar apropiadamente
        words = title.split()
        if not words:
            return f"Documento {filename[:20]}"
        
        # Lista de palabras que deben estar en minúsculas (excepto al inicio)
        lowercase_words = ['de', 'la', 'el', 'los', 'las', 'del', 'al', 'y', 'en', 'para', 'por', 'con']
        
        formatted_words = []
        for i, word in enumerate(words):
            word = word.strip()
            if not word:
                continue
                
            # Primera palabra siempre capitalizada
            if i == 0:
                formatted_words.append(word.capitalize())
            # Palabras en mayúsculas completas (siglas) se mantienen
            elif word.isupper() and len(word) > 1:
                formatted_words.append(word)
            # Palabras de conexión en minúsculas
            elif word.lower() in lowercase_words:
                formatted_words.append(word.lower())
            # Resto de palabras capitalizadas
            else:
                formatted_words.append(word.capitalize())
        
        title = ' '.join(formatted_words)
        
        # Si el título queda vacío o muy corto
        if len(title.strip()) < 5:
            # Intentar usar el nombre original sin el prefijo numérico
            title = re.sub(r'^\d+[_\-]', '', filename.replace('.pdf', ''))
            if len(title.strip()) < 5:
                title = f"Documento Legal"
        
        return title.strip()
    
    def extract_keywords(self, text: str) -> List[str]:
        """
        Extrae palabras clave del documento
        Busca secciones específicas o analiza frecuencia de términos importantes
        """
        keywords = set()
        
        # Buscar sección de palabras clave si existe
        keywords_match = re.search(r'(?:palabras\s+clave|conceptos\s+clave)[:\s]+([^\n]+)', text, re.IGNORECASE)
        if keywords_match:
            kw_text = keywords_match.group(1)
            keywords.update([kw.strip() for kw in re.split(r'[,;]', kw_text)])
        
        # Buscar términos legales importantes
        legal_terms = [
            'reglamento', 'ley', 'decreto', 'acuerdo', 'norma',
            'artículo', 'fracción', 'párrafo', 'inciso',
            'obligación', 'derecho', 'sanción', 'multa',
            'autoridad', 'competencia', 'jurisdicción',
            'procedimiento', 'recurso', 'impugnación'
        ]
        
        text_lower = text.lower()
        for term in legal_terms:
            if term in text_lower:
                keywords.add(term)
        
        # Buscar materias específicas mencionadas
        materias = re.findall(r'(?:materia\s+de\s+)(\w+(?:\s+\w+)?)', text, re.IGNORECASE)
        keywords.update(materias)
        
        return list(keywords)[:20]  # Limitar a 20 palabras clave
    
    def extract_vigencia(self, text: str) -> Optional[str]:
        """Extrae información sobre la vigencia del documento"""
        vigencia_match = re.search(self.patterns['vigencia'], text, re.IGNORECASE)
        if vigencia_match:
            # Buscar contexto alrededor del match
            start = max(0, vigencia_match.start() - 50)
            end = min(len(text), vigencia_match.end() + 100)
            context = text[start:end]
            return context.strip()
        return None

    def extract_fecha_publicacion(self, text: str) -> Optional[str]:
        """
        Extrae la fecha de publicación del PDF
        Busca específicamente el formato del Periódico Oficial del Estado de Aguascalientes:
        "Periódico Oficial del Estado de Aguascalientes, el [día] [día] de [mes] de [año]"
        Ejemplo: "Periódico Oficial del Estado de Aguascalientes, el lunes 14 de agosto de 2017"

        También busca otros patrones comunes como fallback.
        """
        if not text:
            return None

        # Buscar en los primeros 15000 caracteres para cubrir la segunda página
        text_inicio = text[:15000] if len(text) > 15000 else text

        # Patrones ordenados por prioridad (del más específico al más general)
        patrones = [
            # Patrón 1: ESPECÍFICO para Periódico Oficial de Aguascalientes
            # Formato: "Periódico Oficial del Estado de Aguascalientes, el [día_semana] [número] de [mes] de [año]"
            r'Peri[oó]dico\s+Oficial\s+del\s+Estado\s+de\s+Aguascalientes,?\s+el\s+(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})',

            # Patrón 2: Versión sin día de la semana
            r'Peri[oó]dico\s+Oficial\s+del\s+Estado\s+de\s+Aguascalientes,?\s+el\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})',

            # Patrón 3: Versión más flexible con saltos de línea
            r'Peri[oó]dico\s+Oficial\s+del\s+Estado\s+de\s*[\r\n\s]*Aguascalientes,?\s+el\s+(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})',

            # Patrón 4: "desde su publicación" - MUY FLEXIBLE
            r'desde\s+su\s+publicaci[oó]n[^\d]{0,20}(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})',

            # Patrón 5: "desde la publicación" - MUY FLEXIBLE
            r'desde\s+la\s+publicaci[oó]n[^\d]{0,50}(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})',

            # Patrón 6: Solo "publicación" seguido de fecha
            r'publicaci[oó]n[^\d]{0,30}(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})',

            # Patrón 7: "publicada" o "publicado"
            r'publicad[oa][^\d]{0,20}(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})',

            # Patrón 8: "vigente desde"
            r'vigente[^\d]{0,20}(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})',

            # Patrón 9: "en vigor"
            r'en\s+vigor[^\d]{0,20}(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})',

            # Patrón 10: Simplemente capturar cualquier fecha en formato largo en las primeras líneas
            r'(\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+\d{4})',
        ]

        for i, patron in enumerate(patrones, 1):
            match = re.search(patron, text_inicio, re.IGNORECASE)
            if match:
                fecha = match.group(1).strip()
                logger.info(f"Fecha de publicación extraída con patrón #{i}: {fecha}")
                return fecha

        logger.warning("No se encontró fecha de publicación en el PDF")
        return None

    def extract_ultima_reforma(self, text: str) -> Optional[str]:
        """
        Extrae la última reforma/actualización del PDF
        Busca patrones AGRESIVOS para capturar variantes como:
        - "Ultima Reforma decreto No. 02 del 11 de octubre de 2021"
        - "ULTIMA ACTUALIZACIÓN 5/ABRIL/2021"
        - "Última reforma 03 de septiembre de 2021"
        """
        if not text:
            return None

        # Buscar en los primeros 10000 caracteres (primera hoja completa y algo más)
        text_inicio = text[:10000] if len(text) > 10000 else text

        # Patrones MUY AGRESIVOS - simplificados para capturar más casos
        # Soporta: DD de mes de YYYY, DD/MM/YYYY, DD-MM-YYYY, DD/MES/YYYY
        patrones = [
            # Patrón 1: "Última reforma" - MUY FLEXIBLE - formato largo
            r'[UÚ]ltima\s+[Rr]eforma[^\d]{0,50}(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})',

            # Patrón 2: "Última actualización" - formato DD/MES/YYYY
            r'[UÚ]ltima\s+[Aa]ctualizaci[oó]n[^\d]{0,30}(\d{1,2}/\w+/\d{4})',

            # Patrón 3: "Última actualización" - formato DD/MM/YYYY
            r'[UÚ]ltima\s+[Aa]ctualizaci[oó]n[^\d]{0,30}(\d{1,2}/\d{1,2}/\d{4})',

            # Patrón 4: "Última reforma" - formato corto DD-MM-YYYY
            r'[UÚ]ltima\s+[Rr]eforma[^\d]{0,30}(\d{1,2}-\d{1,2}-\d{4})',

            # Patrón 5: "Última modificación"
            r'[UÚ]ltima\s+[Mm]odificaci[oó]n[^\d]{0,30}(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
            r'[UÚ]ltima\s+[Mm]odificaci[oó]n[^\d]{0,30}(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})',

            # Patrón 6: Solo "reforma" seguido de fecha
            r'[Rr]eforma[^\d]{0,50}(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})',
            r'[Rr]eforma[^\d]{0,30}(\d{1,2}[-/]\d{1,2}[-/]\d{4})',

            # Patrón 7: Solo "actualización" seguido de fecha
            r'[Aa]ctualizaci[oó]n[^\d]{0,30}(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
            r'[Aa]ctualizaci[oó]n[^\d]{0,30}(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})',

            # Patrón 8: "modificación" genérica
            r'[Mm]odificaci[oó]n[^\d]{0,30}(\d{1,2}[-/]\d{1,2}[-/]\d{4})',
            r'[Mm]odificaci[oó]n[^\d]{0,30}(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})',

            # Patrón 9: Captura genérica - cualquier fecha en formato DD/MES/YYYY (como 5/ABRIL/2021)
            r'(\d{1,2}/(?:ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)/\d{4})',
        ]

        for patron in patrones:
            match = re.search(patron, text_inicio, re.IGNORECASE)
            if match:
                fecha = match.group(1).strip()
                logger.info(f"Última reforma/actualización extraída con patrón: {fecha}")
                return fecha

        logger.warning("No se encontró última reforma/actualización en el PDF")
        return None
    
    # MODIFICACIÓN: Nuevo método para detectar si el documento tiene status "TEXTO VIGENTE"
    def detect_texto_vigente(self, text: str) -> bool:
        """
        Detecta si el documento contiene "TEXTO VIGENTE" en las primeras páginas
        
        Args:
            text: Texto extraído del PDF
        
        Returns:
            True si encuentra "TEXTO VIGENTE", False en caso contrario
        """
        if not text:
            return False
        
        # Buscar en los primeros 5000 caracteres (aproximadamente primera hoja)
        text_inicio = text[:5000] if len(text) > 5000 else text
        
        # Buscar el patrón "TEXTO VIGENTE" (case insensitive)
        if re.search(self.patterns['texto_vigente'], text_inicio):
            logger.info("Status 'TEXTO VIGENTE' encontrado")
            return True
        
        # También buscar variaciones comunes
        variaciones = [
            r'(?i)texto\s+vigente',
            r'(?i)vigente',
            r'(?i)texto\s+en\s+vigor'
        ]
        
        for patron in variaciones:
            if re.search(patron, text_inicio):
                logger.info(f"Status vigente encontrado con patrón: {patron}")
                return True
        
        logger.info("No se encontró indicación de 'TEXTO VIGENTE'")
        return False
    
    def detect_if_scanned(self, pdf_path: Path) -> bool:
        """
        Detecta si un PDF es escaneado con múltiples criterios mejorados
        """
        try:
            # Criterios para determinar si es escaneado
            text_threshold = 200  # Mínimo de caracteres para considerar que tiene texto
            words_threshold = 30   # Mínimo de palabras para considerar que tiene texto
            
            # Método 1: Verificar con PyPDF2
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Revisar las primeras 5 páginas (más páginas = más precisión)
                pages_to_check = min(5, len(pdf_reader.pages))
                total_text = ""
                readable_pages = 0
                
                for i in range(pages_to_check):
                    page = pdf_reader.pages[i]
                    page_text = page.extract_text()
                    if page_text:
                        total_text += page_text
                        # Contar palabras reales (no solo caracteres)
                        words = len(page_text.split())
                        if words > 20:  # Si una página tiene más de 20 palabras
                            readable_pages += 1
                
                # Análisis del texto extraído
                total_chars = len(total_text.strip())
                total_words = len(total_text.split())
                
                # Es escaneado si:
                # 1. Tiene muy pocos caracteres
                # 2. Tiene muy pocas palabras
                # 3. Menos del 40% de las páginas tienen texto legible
                if total_chars < text_threshold or total_words < words_threshold:
                    logger.info(f"PDF escaneado detectado: {total_chars} caracteres, {total_words} palabras")
                    return True
                
                if pages_to_check > 0 and (readable_pages / pages_to_check) < 0.4:
                    logger.info(f"PDF escaneado detectado: solo {readable_pages}/{pages_to_check} páginas legibles")
                    return True
            
            # Método 2: Verificar calidad del texto con pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                if pdf.pages:
                    # Revisar primeras 2 páginas con pdfplumber
                    check_pages = min(2, len(pdf.pages))
                    text_quality_score = 0
                    
                    for i in range(check_pages):
                        page_text = pdf.pages[i].extract_text()
                        if page_text:
                            # Verificar si el texto tiene estructura coherente
                            # (no solo símbolos o caracteres aleatorios)
                            lines = page_text.split('\n')
                            coherent_lines = 0
                            for line in lines:
                                # Una línea coherente tiene al menos 3 palabras
                                if len(line.split()) >= 3:
                                    coherent_lines += 1
                            
                            if coherent_lines > 5:
                                text_quality_score += 1
                    
                    # Si ninguna página tiene texto coherente, es escaneado
                    if text_quality_score == 0:
                        logger.info("PDF escaneado detectado: texto sin estructura coherente")
                        return True
            
            # Método 3: Verificar con PyMuPDF para más precisión
            pdf_document = fitz.open(str(pdf_path))
            
            # Verificar si las páginas contienen imágenes principalmente
            image_pages = 0
            text_pages = 0
            
            for page_num in range(min(3, pdf_document.page_count)):
                page = pdf_document[page_num]
                
                # Contar imágenes vs texto
                image_list = page.get_images()
                text = page.get_text()
                
                # Si hay imágenes grandes y poco texto, probablemente es escaneado
                if len(image_list) > 0 and len(text.strip()) < 100:
                    image_pages += 1
                elif len(text.strip()) > 100:
                    text_pages += 1
            
            pdf_document.close()
            
            # Si hay más páginas con imágenes que con texto, es escaneado
            if image_pages > text_pages:
                logger.info(f"PDF escaneado detectado: {image_pages} páginas con imágenes vs {text_pages} con texto")
                return True
            
            logger.info(f"PDF digital detectado: texto extraíble encontrado")
            return False
            
        except Exception as e:
            logger.warning(f"Error detectando si PDF es escaneado: {e}")
            # En caso de error, asumir que no es escaneado
            return False
    
    def detect_tables(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Detecta si el PDF contiene tablas usando múltiples métodos
        """
        tables_info = {
            'has_tables': False,
            'table_count': 0,
            'pages_with_tables': [],
            'table_extraction_method': None
        }
        
        try:
            # Método 1: pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    tables = page.extract_tables()
                    if tables:
                        tables_info['has_tables'] = True
                        tables_info['table_count'] += len(tables)
                        tables_info['pages_with_tables'].append(i + 1)
                        tables_info['table_extraction_method'] = 'pdfplumber'
            
            # Método 2: tabula-py (si no se encontraron con pdfplumber)
            if not tables_info['has_tables']:
                try:
                    dfs = tabula.read_pdf(pdf_path, pages='all', silent=True)
                    if dfs:
                        tables_info['has_tables'] = True
                        tables_info['table_count'] = len(dfs)
                        tables_info['table_extraction_method'] = 'tabula'
                except:
                    pass
            
        except Exception as e:
            logger.warning(f"Error detectando tablas: {e}")
        
        return tables_info
    
    def extract_text_with_ocr(self, pdf_path: Path) -> str:
        """
        Extrae texto usando OCR (EasyOCR) para PDFs escaneados
        """
        text = ""
        try:
            self.init_ocr()  # Inicializar OCR solo cuando se necesita
            
            pdf_document = fitz.open(str(pdf_path))
            
            # Limitar páginas para OCR (es lento)
            max_pages = min(pdf_document.page_count, 50)
            
            for page_num in range(max_pages):
                try:
                    logger.info(f"Procesando página {page_num + 1}/{max_pages} con OCR...")
                    page = pdf_document[page_num]
                    
                    # Convertir página a imagen con buena resolución
                    mat = fitz.Matrix(2, 2)  # Factor de zoom para mejor calidad
                    pix = page.get_pixmap(matrix=mat)
                    img_data = pix.tobytes("png")
                    
                    # Convertir a array numpy para EasyOCR
                    img = Image.open(io.BytesIO(img_data))
                    img_array = np.array(img)
                    
                    # Aplicar OCR
                    results = self.ocr_reader.readtext(img_array, paragraph=True)
                    
                    # Extraer texto de los resultados
                    if results:
                        page_text = '\n'.join([result[1] for result in results])
                        text += f"\n--- Página {page_num + 1} ---\n{page_text}"
                
                except Exception as page_error:
                    logger.warning(f"Error procesando página {page_num + 1}: {page_error}")
                    continue
            
            pdf_document.close()
            
        except Exception as e:
            logger.error(f"Error crítico en OCR: {e}")
            logger.info("Intentando método alternativo sin OCR...")
        
        return text
    
    def extract_text_combined(self, pdf_path: Path) -> Tuple[str, str]:
        """
        Extrae texto usando múltiples métodos y combina los resultados
        Retorna: (texto_extraido, metodo_usado)
        """
        text = ""
        method = "combined"
        
        try:
            # Método 1: PyMuPDF (fitz) - Generalmente el más rápido
            pdf_document = fitz.open(str(pdf_path))
            fitz_text = ""
            for page in pdf_document:
                fitz_text += page.get_text()
            pdf_document.close()
            
            if len(fitz_text.strip()) > 100:
                text = fitz_text
                method = "PyMuPDF"
            
            # Método 2: PDFMiner - Mejor conservación de layout
            if not text or len(text.strip()) < 100:
                try:
                    laparams = LAParams(line_overlap=0.5, char_margin=2.0, line_margin=0.5)
                    miner_text = pdfminer_extract(str(pdf_path), laparams=laparams)
                    if len(miner_text.strip()) > len(text.strip()):
                        text = miner_text
                        method = "PDFMiner"
                except:
                    pass
            
            # Método 3: pdfplumber - Bueno para estructura
            if not text or len(text.strip()) < 100:
                try:
                    with pdfplumber.open(pdf_path) as pdf:
                        plumber_text = ""
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                plumber_text += page_text + "\n"
                        
                        if len(plumber_text.strip()) > len(text.strip()):
                            text = plumber_text
                            method = "pdfplumber"
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Error extrayendo texto: {e}")
        
        return text, method
    
    def get_pdf_metadata(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Obtiene metadatos completos del PDF
        """
        metadata = {
            'num_pages': 0,
            'file_size_mb': 0,
            'creation_date': None,
            'modification_date': None,
            'author': None,
            'subject': None,
            'producer': None
        }
        
        try:
            # Tamaño del archivo
            file_size = os.path.getsize(pdf_path)
            metadata['file_size_mb'] = round(file_size / (1024 * 1024), 2)
            
            # Metadatos con PyMuPDF
            pdf_document = fitz.open(str(pdf_path))
            metadata['num_pages'] = pdf_document.page_count
            
            pdf_metadata = pdf_document.metadata
            if pdf_metadata:
                metadata['creation_date'] = pdf_metadata.get('creationDate')
                metadata['modification_date'] = pdf_metadata.get('modDate')
                metadata['author'] = pdf_metadata.get('author')
                metadata['subject'] = pdf_metadata.get('subject')
                metadata['producer'] = pdf_metadata.get('producer')
            
            pdf_document.close()
            
        except Exception as e:
            logger.error(f"Error obteniendo metadatos: {e}")
            # Intentar con PyPDF2 como respaldo
            try:
                with open(pdf_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    metadata['num_pages'] = len(pdf_reader.pages)
            except:
                pass
        
        return metadata
    
    def process_single_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Procesa un único archivo PDF y extrae solo la información más importante
        """
        logger.info(f"{'='*60}")
        logger.info(f"Procesando: {pdf_path.name}")
        
        # IMPORTANTE: Usar el nombre del archivo limpio como título principal
        titulo_base = self.clean_filename_to_title(pdf_path.stem)
        
        # Estructura del JSON de salida
        result = {
            'titulo': titulo_base,  # Usar nombre del archivo limpio como título
            'ordenamiento': 'PROTOCOLO',  # Tipo de ordenamiento
            'jurisdiccion': 'AGUAS CALIENTES',  # Jurisdicción
            'fuente_oficial': 'DIARIO OFICIAL DE LA FEDERACION',  # Fuente oficial
            'es_escaneado': False,
            'tiene_tablas': False
        }
        
        try:
            # 1. Obtener metadatos básicos
            try:
                metadata = self.get_pdf_metadata(pdf_path)
                result['numero_paginas'] = metadata['num_pages']
            except Exception as e:
                logger.warning(f"Error obteniendo metadatos de {pdf_path.name}: {e}")
                result['numero_paginas'] = 0
            
            # 2. Detectar si es escaneado
            try:
                result['es_escaneado'] = self.detect_if_scanned(pdf_path)
                logger.info(f"Es escaneado: {result['es_escaneado']}")
            except Exception as e:
                logger.warning(f"Error detectando si es escaneado: {e}")
                result['es_escaneado'] = False
            
            # 3. Detectar tablas
            try:
                tables_info = self.detect_tables(pdf_path)
                result['tiene_tablas'] = tables_info['has_tables']
                logger.info(f"Tiene tablas: {result['tiene_tablas']}")
            except Exception as e:
                logger.warning(f"Error detectando tablas: {e}")
                result['tiene_tablas'] = False
            
            # 4. Extraer texto con manejo robusto de errores
            text = ""
            try:
                if result['es_escaneado']:
                    logger.info("PDF escaneado detectado, usando OCR...")
                    text = self.extract_text_with_ocr(pdf_path)
                    # Si OCR falla o devuelve poco texto, intentar método estándar
                    if len(text.strip()) < 100:
                        logger.info("OCR devolvió poco texto, intentando método estándar...")
                        text_alt, method = self.extract_text_combined(pdf_path)
                        if len(text_alt) > len(text):
                            text = text_alt
                else:
                    logger.info("Extrayendo texto con métodos estándar...")
                    text, method = self.extract_text_combined(pdf_path)
            except Exception as e:
                logger.error(f"Error extrayendo texto: {e}")
                text = ""
            
            logger.info(f"Texto extraído: {len(text)} caracteres")

            # El título ya está establecido desde el nombre del archivo
            logger.info(f"Título (del archivo): {result['titulo'][:50] if result['titulo'] else 'No encontrado'}...")

            return result
            
        except Exception as e:
            logger.error(f"Error crítico procesando {pdf_path.name}: {e}")
            # Devolver resultado mínimo con información del error
            return {
                'titulo': self.clean_filename_to_title(pdf_path.stem),
                'ordenamiento': 'PROTOCOLO',
                'jurisdiccion': 'AGUAS CALIENTES',
                'fuente_oficial': 'DIARIO OFICIAL DE LA FEDERACION',
                'es_escaneado': False,
                'tiene_tablas': False,
                'error': str(e)
            }
    
    def sanitize_filename(self, titulo: str) -> str:
        """
        Convierte el título en un nombre de archivo válido
        Limita la longitud para evitar errores en Windows (límite de 260 caracteres en ruta completa)
        """
        # Eliminar caracteres no permitidos en nombres de archivo
        filename = re.sub(r'[<>:"/\\|?*]', '', titulo)
        # Reemplazar espacios múltiples por uno solo
        filename = re.sub(r'\s+', ' ', filename)
        # Eliminar espacios al inicio y final
        filename = filename.strip()

        # Limitar longitud a 150 caracteres para el nombre (sin extensión)
        # Esto previene exceder el límite de 260 caracteres de ruta completa en Windows
        max_length = 150
        if len(filename) > max_length:
            # Truncar y agregar indicador de truncamiento
            filename = filename[:max_length].strip()
            # Asegurar que no termine con un carácter de puntuación que pueda causar problemas
            filename = filename.rstrip('.,;:-_')

        return filename

    def process_all_pdfs(self) -> List[Dict[str, Any]]:
        """
        Procesa todos los PDFs en orden alfabético/numérico y guarda cada documento como un JSON individual
        """
        # Cargar el JSON con los contenidos
        logger.info("\n" + "="*60)
        logger.info("Cargando archivo de contenidos...")
        self.load_contenido_data()
        logger.info("="*60 + "\n")
        
        pdf_files = list(self.input_folder.glob("*.pdf"))
        
        # ORDENAR ARCHIVOS: primero por número si tienen prefijo numérico, luego alfabéticamente
        def sort_key(file_path):
            filename = file_path.name
            # Intentar extraer número del inicio del nombre
            match = re.match(r'^(\d+)', filename)
            if match:
                # Si tiene número, usar el número para ordenar
                return (0, int(match.group(1)), filename.lower())
            else:
                # Si no tiene número, ordenar alfabéticamente después de los numerados
                return (1, 0, filename.lower())
        
        # Ordenar los archivos
        pdf_files = sorted(pdf_files, key=sort_key)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Encontrados {len(pdf_files)} archivos PDF en {self.input_folder}")
        logger.info(f"Orden de procesamiento:")
        for idx, pdf in enumerate(pdf_files[:10], 1):  # Mostrar primeros 10
            logger.info(f"  {idx}. {pdf.name}")
        if len(pdf_files) > 10:
            logger.info(f"  ... y {len(pdf_files) - 10} archivos más")
        logger.info(f"{'='*60}\n")
        
        # Lista para almacenar todos los documentos procesados
        documentos = []
        
        for i, pdf_file in enumerate(pdf_files, 1):
            logger.info(f"Procesando archivo {i}/{len(pdf_files)}: {pdf_file.name}")
            try:
                result = self.process_single_pdf(pdf_file)

                # Buscar Contenido correspondiente
                contenido = self.find_matching_contenido(result['titulo'])

                # Reorganizar el diccionario con el orden deseado incluyendo 'Contenido'
                ordered_result = {
                    'titulo': result['titulo'],
                    'Contenido': contenido if contenido else None,  # Campo Contenido debajo del título
                    'ordenamiento': result['ordenamiento'],
                    'jurisdiccion': result['jurisdiccion'],
                    'fuente_oficial': result['fuente_oficial'],
                    'es_escaneado': result['es_escaneado'],
                    'tiene_tablas': result['tiene_tablas']
                }

                # Guardar JSON individual para este documento
                try:
                    json_filename = self.sanitize_filename(result['titulo']) + '.json'
                    json_filepath = self.output_folder / json_filename

                    # Verificar longitud de la ruta completa
                    if len(str(json_filepath)) > 255:
                        logger.warning(f"Ruta muy larga ({len(str(json_filepath))} caracteres), truncando más...")
                        # Truncar aún más el nombre si la ruta completa es demasiado larga
                        max_name_length = 100
                        json_filename = self.sanitize_filename(result['titulo'][:max_name_length]) + '.json'
                        json_filepath = self.output_folder / json_filename

                    with open(json_filepath, 'w', encoding='utf-8') as f:
                        json.dump(ordered_result, f, ensure_ascii=False, indent=2)
                    logger.info(f"✓ JSON guardado: {json_filename}")
                except Exception as save_error:
                    logger.error(f"Error guardando JSON para '{result['titulo'][:50]}...': {save_error}")
                    # Intentar con un nombre simplificado
                    try:
                        simple_filename = f"doc_{i:04d}.json"
                        simple_filepath = self.output_folder / simple_filename
                        with open(simple_filepath, 'w', encoding='utf-8') as f:
                            json.dump(ordered_result, f, ensure_ascii=False, indent=2)
                        logger.info(f"✓ JSON guardado con nombre alternativo: {simple_filename}")
                    except Exception as fallback_error:
                        logger.error(f"Error crítico guardando JSON incluso con nombre simplificado: {fallback_error}")

                documentos.append(ordered_result)
            except Exception as e:
                logger.error(f"Error crítico con {pdf_file.name}: {e}")
                # Intentar buscar Contenido incluso en caso de error
                titulo_temp = self.clean_filename_to_title(pdf_file.stem)
                contenido = self.find_matching_contenido(titulo_temp)

                # Manejo de errores
                error_result = {
                    'titulo': titulo_temp,
                    'Contenido': contenido if contenido else None,  # Campo Contenido debajo del título
                    'ordenamiento': 'PROTOCOLO',
                    'jurisdiccion': 'AGUAS CALIENTES',
                    'fuente_oficial': 'DIARIO OFICIAL DE LA FEDERACION',
                    'es_escaneado': False,
                    'tiene_tablas': False,
                    'error': str(e)
                }

                # Guardar JSON individual incluso en caso de error
                try:
                    json_filename = self.sanitize_filename(titulo_temp) + '.json'
                    json_filepath = self.output_folder / json_filename

                    # Verificar longitud de la ruta completa
                    if len(str(json_filepath)) > 255:
                        logger.warning(f"Ruta muy larga, truncando...")
                        max_name_length = 100
                        json_filename = self.sanitize_filename(titulo_temp[:max_name_length]) + '.json'
                        json_filepath = self.output_folder / json_filename

                    with open(json_filepath, 'w', encoding='utf-8') as f:
                        json.dump(error_result, f, ensure_ascii=False, indent=2)
                    logger.info(f"✓ JSON guardado (con error): {json_filename}")
                except Exception as save_error:
                    logger.error(f"Error guardando JSON de error: {save_error}")
                    # Intentar con nombre simplificado
                    try:
                        simple_filename = f"doc_{i:04d}_error.json"
                        simple_filepath = self.output_folder / simple_filename
                        with open(simple_filepath, 'w', encoding='utf-8') as f:
                            json.dump(error_result, f, ensure_ascii=False, indent=2)
                        logger.info(f"✓ JSON guardado con nombre alternativo: {simple_filename}")
                    except Exception as fallback_error:
                        logger.error(f"Error crítico guardando: {fallback_error}")

                documentos.append(error_result)
        
        # Mostrar estadísticas
        total_procesados = len([d for d in documentos if 'error' not in d])
        total_errores = len([d for d in documentos if 'error' in d])
        total_escaneados = sum(1 for d in documentos if d.get('es_escaneado', False))
        total_con_tablas = sum(1 for d in documentos if d.get('tiene_tablas', False))
        total_con_contenido = sum(1 for d in documentos if d.get('Contenido') is not None)
        total_sin_contenido = len(documentos) - total_con_contenido

        logger.info(f"\n{'='*60}")
        logger.info(f"PROCESAMIENTO COMPLETADO")
        logger.info(f"{'='*60}")
        logger.info(f"✓ Total procesados exitosamente: {total_procesados}/{len(pdf_files)}")
        logger.info(f"✓ Archivos JSON individuales generados: {len(documentos)}")
        logger.info(f"✓ Errores: {total_errores}")
        logger.info(f"✓ Archivos escaneados: {total_escaneados}")
        logger.info(f"✓ Archivos con tablas: {total_con_tablas}")
        logger.info(f"✓ Contenidos encontrados: {total_con_contenido}/{len(documentos)}")
        if total_sin_contenido > 0:
            logger.info(f"⚠ Sin Contenido: {total_sin_contenido} documentos")
        
        return documentos


def main():
    """Función principal para ejecutar el procesamiento"""
    
    # Rutas configuradas según lo especificado
    INPUT_FOLDER = r"C:\Users\julii\Documents\AGUASCALIENTES DOF\Protocolo" # Carpeta con los PDFs
    OUTPUT_FOLDER = r"C:\Users\julii\Documents\Practicas\drive\AGUAS\json\Protocolo"  # Misma carpeta que el script
    
    print("="*60)
    print("PROCESADOR DE REGLAMENTOS Y LEYES FEDERALES")
    print("="*60)
    print(f"Carpeta de entrada: {INPUT_FOLDER}")
    print(f"Carpeta de salida: {OUTPUT_FOLDER}")
    print()
    
    # Verificar que existe la carpeta de entrada
    if not os.path.exists(INPUT_FOLDER):
        print(f"ERROR: La carpeta {INPUT_FOLDER} no existe")
        print("Por favor verifica la ruta e intenta de nuevo")
        return
    
    # Crear instancia del procesador
    processor = ReglamentoProcessor(INPUT_FOLDER, OUTPUT_FOLDER)
    
    # Opción para procesar un solo archivo o todos
    import sys
    if len(sys.argv) > 1:
        # Procesar un archivo específico
        pdf_name = sys.argv[1]
        pdf_path = Path(INPUT_FOLDER) / pdf_name
        if pdf_path.exists():
            print(f"Procesando archivo único: {pdf_name}")

            # Cargar Contenidos si están disponibles
            processor.load_contenido_data()

            result = processor.process_single_pdf(pdf_path)

            # Buscar Contenido correspondiente
            contenido = processor.find_matching_contenido(result['titulo'])

            # Reorganizar el diccionario con el orden deseado incluyendo 'Contenido'
            ordered_result = {
                'titulo': result['titulo'],
                'Contenido': contenido if contenido else None,  # Campo Contenido debajo del título
                'ordenamiento': result['ordenamiento'],
                'jurisdiccion': result['jurisdiccion'],
                'fuente_oficial': result['fuente_oficial'],
                'es_escaneado': result['es_escaneado'],
                'tiene_tablas': result['tiene_tablas']
            }
            
            # Guardar en un JSON individual sin campo orden
            output_file = Path(OUTPUT_FOLDER) / "reglamento_individual.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump([ordered_result], f, ensure_ascii=False, indent=2)
            
            print("\nResultado guardado en:", output_file)
            print(json.dumps(ordered_result, ensure_ascii=False, indent=2))
        else:
            print(f"ERROR: El archivo {pdf_path} no existe")
    else:

        documentos = processor.process_all_pdfs()
        
        print("\n" + "="*60)
        print("PROCESO COMPLETADO EXITOSAMENTE")
        print("="*60)
        print(f"Total de documentos procesados: {len(documentos)}")
        print(f"Archivos JSON individuales guardados en: {OUTPUT_FOLDER}")


if __name__ == "__main__":
    main()