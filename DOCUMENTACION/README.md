# Documentación de Prácticas - Procesamiento de Documentos Legales

> **Autor:** Julian
> **Período:** 2025
> **Propósito:** Automatización de descarga, extracción y clasificación de documentos legales mexicanos

---

## Resumen Ejecutivo

Este proyecto consiste en un **sistema automatizado de procesamiento de documentos legales** de estados mexicanos. El pipeline completo transforma documentos desde portales web gubernamentales hasta archivos JSON estructurados y clasificados, listos para su uso en sistemas de búsqueda, análisis o bases de datos.

### Resultado final

```
Portales Web Gubernamentales
            │
            ▼
    ┌───────────────┐
    │  130+ PDFs    │  ──►  23+ MB de texto extraído  ──►  130+ JSON estructurados
    │  descargados  │                                      con metadatos y clasificación
    └───────────────┘
```

---

## Documentación Disponible

| # | Documento | Descripción |
|---|-----------|-------------|
| 1 | [SCRAPING_BAJA_CALIFORNIA.md](./SCRAPING_BAJA_CALIFORNIA.md) | Scripts de web scraping para descarga automática de PDFs |
| 2 | [EXTRACCION_PDF_BAJA_CALIFORNIA.md](./EXTRACCION_PDF_BAJA_CALIFORNIA.md) | Scripts de extracción de texto de PDFs (incluye OCR) |
| 3 | [METADATOS_BAJA_CALIFORNIA.md](./METADATOS_BAJA_CALIFORNIA.md) | Scripts de consolidación de datos en JSON final |
| 4 | [CLASIFICACION_MATERIAS.md](./CLASIFICACION_MATERIAS.md) | Sistema de clasificación por rama del derecho |
| 5 | [FLUJO_DATOS_BAJA_CALIFORNIA.md](./FLUJO_DATOS_BAJA_CALIFORNIA.md) | Mapa completo del flujo de datos y carpetas |

---

## Pipeline de Procesamiento

### Las 3 Etapas + Clasificación

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   ETAPA 1: SCRAPING                                                          │
│   ├── Scripts: scraping/Leyes.py, codigos.py, reglamentos.py                │
│   ├── Entrada: URLs de portales gubernamentales                              │
│   ├── Salida: PDFs descargados + json_metadatos/*.json                      │
│   └── Tecnología: Selenium, requests                                         │
│                                                                              │
│   ETAPA 2: EXTRACCIÓN                                                        │
│   ├── Scripts: scrips/leyes-PDF.py, codigo-PDF.py, reglamentos-PDF.py       │
│   ├── Entrada: PDFs descargados                                              │
│   ├── Salida: contenido/*-contenido.json                                     │
│   └── Tecnología: pdfplumber, PyMuPDF, pytesseract (OCR)                    │
│                                                                              │
│   ETAPA 3: CONSOLIDACIÓN                                                     │
│   ├── Scripts: metadatos/leyes.py, codigos.py, reglamentos.py               │
│   ├── Entrada: PDFs + contenido.json + metadatos.json                        │
│   ├── Salida: json/[Tipo]/*.json (archivos individuales)                    │
│   └── Tecnología: PyMuPDF, EasyOCR, SequenceMatcher                         │
│                                                                              │
│   ETAPA 4: CLASIFICACIÓN                                                     │
│   ├── Scripts: agregar_materias_[ESTADO].py                                  │
│   ├── Entrada: JSON finales                                                  │
│   ├── Salida: JSON con campo "materia" agregado                              │
│   └── Tecnología: Clasificación por palabras clave (37 categorías)          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Estructura de Carpetas

```
C:\Users\julii\Documents\
│
├── BAJA CALIFORNIA\                    # PDFs descargados
│   ├── Codigos\
│   ├── Leyes\
│   └── Reglamentos\
│
└── Practicas\
    ├── drive\
    │   └── BAJA CALIFORNIA\
    │       ├── scraping\               # Scripts Etapa 1
    │       ├── scrips\                 # Scripts Etapa 2
    │       ├── metadatos\              # Scripts Etapa 3
    │       ├── json_metadatos\         # Salida Etapa 1
    │       ├── contenido\              # Salida Etapa 2
    │       └── json\                   # Salida Etapa 3 (FINAL)
    │           ├── Códigos\
    │           ├── Leyes\
    │           └── Reglamentos\
    │
    ├── DOCUMENTACION\                  # Esta documentación
    │
    └── resumen_clasificacion_materias.txt
```

---

## Tecnologías Utilizadas

### Lenguaje
- **Python 3.8+**

### Librerías principales

| Categoría | Librerías |
|-----------|-----------|
| **Web Scraping** | Selenium, webdriver-manager, requests |
| **Procesamiento PDF** | PyPDF2, pdfplumber, PyMuPDF (fitz), pdfminer.six, tabula-py |
| **OCR** | pytesseract, pdf2image, EasyOCR |
| **Imágenes** | Pillow, numpy |
| **Datos** | json (estándar), difflib (SequenceMatcher) |

### Software requerido
- Google Chrome (para Selenium)
- Java JRE (para tabula-py)
- Tesseract OCR (opcional, para pytesseract)

---

## Estructura del JSON Final

```json
{
  "titulo": "Código Civil del Estado de Baja California",
  "materia": ["civil"],
  "Contenido": "ARTICULO 1.- Las disposiciones de este Código...",
  "ordenamiento": "CODIGO",
  "jurisdiccion": "ESTATAL",
  "fuente_oficial": "BAJA CALIFORNIA",
  "Fecha de última modificación": "2025/04/11",
  "Fecha de publicación": "31/01/1974",
  "url": "https://transparencia.pjbc.gob.mx/.../CodigoCivil.pdf",
  "es_escaneado": false,
  "tiene_tablas": true
}
```

---

## Categorías de Clasificación (37 Materias)

| Categoría | Ejemplos de documentos |
|-----------|------------------------|
| `constitucional` | Constituciones estatales |
| `civil` | Códigos civiles, derecho familiar |
| `penal` | Códigos penales, leyes de delitos |
| `administrativo` | Organización gubernamental |
| `fiscal` | Impuestos, hacienda |
| `laboral` | Leyes del trabajo |
| `electoral` | Procesos electorales |
| `transparencia` | Acceso a información |
| `derechos humanos` | Protección de derechos |
| `género` | Igualdad, violencia de género |
| `salud` | Sistema de salud |
| `educación` | Sistema educativo |
| `ambiental` | Medio ambiente |
| `municipal` | Gobierno local |
| ... | (37 categorías en total) |

---

## Estados Procesados

| Estado | Archivos | Materias principales |
|--------|----------|---------------------|
| **Baja California** | 130+ | civil, penal, administrativo |
| **Aguascalientes** | 384 | general, municipal, educación |
| **Campeche** | 441 | municipal, general, fiscal |
| **Guerrero** | 589 | (procesado) |

**Total:** 1,500+ documentos procesados

---

## Orden de Ejecución

### Para procesar un nuevo estado:

```bash
# 1. SCRAPING - Descargar PDFs y metadatos
python scraping/Leyes.py
python scraping/codigos.py
python scraping/reglamentos.py

# 2. EXTRACCIÓN - Convertir PDFs a texto
python scrips/leyes-PDF.py
python scrips/codigo-PDF.py
python scrips/reglamentos-PDF.py

# 3. CONSOLIDACIÓN - Generar JSON finales
python metadatos/leyes.py
python metadatos/codigos.py
python metadatos/reglamentos.py

# 4. CLASIFICACIÓN - Agregar campo materia
python agregar_materias_[ESTADO].py
```

---

## Consideraciones Importantes

### Antes de ejecutar

1. **Modificar rutas** - Las rutas están hardcodeadas para el usuario `julii`
2. **Instalar dependencias** - Ver sección de librerías
3. **Verificar Chrome** - Necesario para Selenium
4. **Conexión a internet** - Requerida para scraping

### Limitaciones

- El scraping puede fallar si los sitios web cambian su estructura
- OCR puede ser lento en documentos escaneados
- La clasificación por palabras clave tiene precisión limitada

### Mantenimiento

- Revisar periódicamente que las URLs sigan funcionando
- Actualizar selectores HTML si cambian los portales
- Agregar nuevas palabras clave si aparecen nuevas materias

---

## Casos de Uso

1. **Búsqueda legal** - Filtrar documentos por materia, estado, tipo
2. **Análisis de legislación** - Estadísticas por rama del derecho
3. **Bases de datos legales** - Importar JSON a sistemas de gestión
4. **Machine Learning** - Entrenar modelos de clasificación legal
5. **APIs REST** - Exponer documentos mediante servicios web

---

## Contacto y Mantenimiento

- **Autor:** Julian
- **Período:** Prácticas 2025
- **Ubicación scripts:** `/home/julian69/` y `C:\Users\julii\Documents\Practicas\`
- **Documentación:** `C:\Users\julii\Documents\Practicas\DOCUMENTACION\`

---

## Resumen Visual

```
     ┌──────────────────────────────────────────────────────────────┐
     │                    PROYECTO COMPLETO                         │
     ├──────────────────────────────────────────────────────────────┤
     │                                                              │
     │   ENTRADA                                                    │
     │   ════════                                                   │
     │   • Portales web gubernamentales (Congreso, Poder Judicial)  │
     │   • URLs de leyes, códigos, reglamentos                      │
     │                                                              │
     │   PROCESO                                                    │
     │   ════════                                                   │
     │   • 12 scripts Python organizados en 4 etapas                │
     │   • Web scraping + Extracción PDF + OCR + Clasificación      │
     │   • ~10 librerías especializadas                             │
     │                                                              │
     │   SALIDA                                                     │
     │   ══════                                                     │
     │   • 1,500+ documentos procesados                             │
     │   • JSON estructurados con metadatos completos               │
     │   • Clasificación en 37 materias legales                     │
     │   • Listos para búsqueda, análisis o importación             │
     │                                                              │
     └──────────────────────────────────────────────────────────────┘
```

---

> **Documentación generada:** Noviembre 2025

