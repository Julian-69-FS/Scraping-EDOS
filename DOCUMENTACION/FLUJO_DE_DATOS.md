# Documentación: Flujo de Datos y Estructura de Carpetas - Baja California

> **Estado:** Baja California
> **Fecha de documentación:** Noviembre 2025
> **Autor original:** Julian
> **Propósito:** Documentar el flujo completo de datos desde la descarga hasta el JSON final

---

## Índice

1. [Visión General del Pipeline](#1-visión-general-del-pipeline)
2. [Mapa de Carpetas](#2-mapa-de-carpetas)
3. [Etapa 1: Scraping - Descarga de PDFs y Metadatos](#3-etapa-1-scraping---descarga-de-pdfs-y-metadatos)
4. [Etapa 2: Extracción - Contenido de PDFs](#4-etapa-2-extracción---contenido-de-pdfs)
5. [Etapa 3: Consolidación - JSON Final](#5-etapa-3-consolidación---json-final)
6. [Estructura de Archivos por Carpeta](#6-estructura-de-archivos-por-carpeta)
7. [Relación entre Archivos](#7-relación-entre-archivos)
8. [Estadísticas del Estado](#8-estadísticas-del-estado)

---

## 1. Visión General del Pipeline

El procesamiento de documentos legales de Baja California sigue un pipeline de **3 etapas**:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           PIPELINE DE PROCESAMIENTO                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ETAPA 1: SCRAPING                                                               │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐            │
│  │   Portales Web  │────►│  Scripts de     │────►│  PDFs + JSON    │            │
│  │   Gobierno BC   │     │  Scraping       │     │  Metadatos      │            │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘            │
│                                                         │                        │
│                                                         ▼                        │
│  ETAPA 2: EXTRACCIÓN                                                             │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐            │
│  │   PDFs          │────►│  Scripts de     │────►│  JSON           │            │
│  │   Descargados   │     │  Extracción     │     │  Contenido      │            │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘            │
│                                                         │                        │
│                                                         ▼                        │
│  ETAPA 3: CONSOLIDACIÓN                                                          │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐            │
│  │  Contenido +    │────►│  Scripts de     │────►│  JSON Final     │            │
│  │  Metadatos +PDF │     │  Metadatos      │     │  Individual     │            │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘            │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Mapa de Carpetas

### Estructura completa

```
C:\Users\julii\Documents\
│
├── BAJA CALIFORNIA\                          # PDFs DESCARGADOS (fuera de Practicas)
│   ├── Codigos\                              # 10+ PDFs de códigos
│   ├── Leyes\                                # 100+ PDFs de leyes
│   └── Reglamentos\                          # 20+ PDFs de reglamentos
│
└── Practicas\
    └── drive\
        └── BAJA CALIFORNIA\
            │
            ├── scraping\                     # SCRIPTS ETAPA 1
            │   ├── Leyes.py
            │   ├── codigos.py
            │   ├── reglamentos.py
            │   └── periodico.py (vacío)
            │
            ├── scrips\                       # SCRIPTS ETAPA 2
            │   ├── codigo-PDF.py
            │   ├── leyes-PDF.py
            │   └── reglamentos-PDF.py
            │
            ├── metadatos\                    # SCRIPTS ETAPA 3
            │   ├── codigos.py
            │   ├── leyes.py
            │   └── reglamentos.py
            │
            ├── json_metadatos\               # SALIDA ETAPA 1
            │   ├── metadatos_codigos.json    (2.6 KB)
            │   ├── metadatos_leyes.json      (51.8 KB)
            │   ├── metadatos_reglamentos.json (8.4 KB)
            │   └── metadatos_periodico.json  (0 bytes - vacío)
            │
            ├── contenido\                    # SALIDA ETAPA 2
            │   ├── codigo-contenido.json     (6.4 MB)
            │   ├── leyes-contenido.json      (16.2 MB)
            │   └── reglamentos-contenido.json (863 KB)
            │
            └── json\                         # SALIDA ETAPA 3 (FINAL)
                ├── Códigos\                  # JSONs individuales
                ├── Leyes\                    # JSONs individuales
                └── Reglamentos\              # JSONs individuales
```

### Tabla resumen de rutas

| Tipo | Ruta |
|------|------|
| **PDFs descargados** | `C:\Users\julii\Documents\BAJA CALIFORNIA\` |
| **Scripts scraping** | `...\Practicas\drive\BAJA CALIFORNIA\scraping\` |
| **Scripts extracción** | `...\Practicas\drive\BAJA CALIFORNIA\scrips\` |
| **Scripts consolidación** | `...\Practicas\drive\BAJA CALIFORNIA\metadatos\` |
| **JSON metadatos (scraping)** | `...\Practicas\drive\BAJA CALIFORNIA\json_metadatos\` |
| **JSON contenido** | `...\Practicas\drive\BAJA CALIFORNIA\contenido\` |
| **JSON final** | `...\Practicas\drive\BAJA CALIFORNIA\json\` |

---

## 3. Etapa 1: Scraping - Descarga de PDFs y Metadatos

### Objetivo
Descargar automáticamente los PDFs de los portales oficiales y extraer los metadatos básicos de las páginas web.

### Scripts involucrados

| Script | Fuente | URL |
|--------|--------|-----|
| `Leyes.py` | Congreso de BC | https://www.congresobc.gob.mx/TrabajoLegislativo/Leyes |
| `codigos.py` | Poder Judicial | https://transparencia.pjbc.gob.mx/paginas/MarcoJuridico.aspx?opc=1 |
| `reglamentos.py` | Poder Judicial | https://transparencia.pjbc.gob.mx/paginas/MarcoJuridico.aspx?opc=2 |

### Entrada
- URLs de portales web gubernamentales

### Salida

#### PDFs descargados:
```
C:\Users\julii\Documents\BAJA CALIFORNIA\
├── Codigos\
│   ├── Código Civil del Estado de Baja California.pdf
│   ├── Código Civil Federal.pdf
│   └── ...
├── Leyes\
│   ├── Ley de Acceso de las Mujeres.pdf
│   └── ...
└── Reglamentos\
    ├── Reglamento Interior de los Juzgados.pdf
    └── ...
```

#### JSON de metadatos (json_metadatos):

**metadatos_codigos.json** (estructura del Poder Judicial):
```json
[
  {
    "titulo": "Código Civil del Estado de Baja California",
    "Fecha de Última modificación": "2025/04/11",
    "Fecha de publicación": "31/01/1974",
    "url": "https://transparencia.pjbc.gob.mx/documentos/pdfs/Codigos/CodigoCivil.pdf"
  }
]
```

**metadatos_leyes.json** (estructura del Congreso):
```json
[
  {
    "NOMBRE": "Ley de Acceso de las Mujeres a una Vida Libre de Violencia",
    "FECHA PER OFIC": "2008-07-25",
    "ESTATUS": "Vigente",
    "TOMO": "CXIV",
    "URL": "https://www.congresobc.gob.mx/..."
  }
]
```

---

## 4. Etapa 2: Extracción - Contenido de PDFs

### Objetivo
Extraer el texto completo de cada PDF descargado, incluyendo OCR para documentos escaneados.

### Scripts involucrados

| Script | Procesa |
|--------|---------|
| `codigo-PDF.py` | PDFs en `...\BAJA CALIFORNIA\Codigos\` |
| `leyes-PDF.py` | PDFs en `...\BAJA CALIFORNIA\Leyes\` |
| `reglamentos-PDF.py` | PDFs en `...\BAJA CALIFORNIA\Reglamentos\` |

### Entrada
- PDFs descargados en la Etapa 1

### Salida (contenido/)

**codigo-contenido.json** (~6.4 MB):
```json
[
  {
    "Titulo": "Código Civil del Estado de Baja California",
    "contenido": "Sección I, Tomo LXXXI\nDISPOSICIONES PRELIMINARES\nARTICULO 1.- Las disposiciones de este Código regirán en el Estado de Baja California en asuntos de orden común.\nARTICULO 2.- La capacidad jurídica es igual para el hombre y la mujer..."
  }
]
```

### Características del contenido
- Texto completo extraído del PDF
- Tablas convertidas a texto
- OCR aplicado si el documento está escaneado
- Limpieza de encabezados/pies de página

---

## 5. Etapa 3: Consolidación - JSON Final

### Objetivo
Combinar toda la información (PDF procesado + contenido + metadatos) en un único JSON por documento.

### Scripts involucrados

| Script | Genera JSONs en |
|--------|-----------------|
| `codigos.py` | `json\Códigos\` |
| `leyes.py` | `json\Leyes\` |
| `reglamentos.py` | `json\Reglamentos\` |

### Entradas
1. **PDFs** - Para extracción adicional y verificación
2. **contenido.json** - Texto ya extraído
3. **metadatos.json** - Información del scraping

### Proceso de matching
Los scripts usan `SequenceMatcher` para encontrar correspondencias entre:
- Nombre del archivo PDF
- Título en contenido.json
- Título/NOMBRE en metadatos.json

### Salida (json/)

**Ejemplo: `json\Códigos\Código Civil del Estado de Baja California.json`**
```json
{
  "titulo": "Código Civil del Estado de Baja California",
  "Contenido": "Sección I, Tomo LXXXI\nDISPOSICIONES PRELIMINARES\nARTICULO 1.- Las disposiciones de este Código regirán...",
  "ordenamiento": "CODIGO",
  "jurisdiccion": "ESTATAL",
  "fuente_oficial": "BAJA CALIFORNIA",
  "Fecha de última modificación": "2025/04/11",
  "Fecha de publicación": "31/01/1974",
  "url": "https://transparencia.pjbc.gob.mx/documentos/pdfs/Codigos/CodigoCivil.pdf",
  "es_escaneado": false,
  "tiene_tablas": true
}
```

---

## 6. Estructura de Archivos por Carpeta

### json_metadatos/ (Etapa 1 - Salida del scraping)

| Archivo | Tamaño | Registros | Fuente |
|---------|--------|-----------|--------|
| `metadatos_codigos.json` | 2.6 KB | ~10 | Poder Judicial |
| `metadatos_leyes.json` | 51.8 KB | ~100+ | Congreso BC |
| `metadatos_reglamentos.json` | 8.4 KB | ~20 | Poder Judicial |
| `metadatos_periodico.json` | 0 bytes | 0 | No implementado |

### contenido/ (Etapa 2 - Salida de extracción)

| Archivo | Tamaño | Contenido |
|---------|--------|-----------|
| `codigo-contenido.json` | 6.4 MB | Texto completo de códigos |
| `leyes-contenido.json` | 16.2 MB | Texto completo de leyes |
| `reglamentos-contenido.json` | 863 KB | Texto completo de reglamentos |

### json/ (Etapa 3 - Salida final)

```
json/
├── Códigos/
│   ├── Código Civil del Estado de Baja California.json
│   ├── Código Civil Federal.json
│   ├── Código de Comercio.json
│   ├── Código de Procedimientos Civiles del Estado.json
│   ├── Código de Ética del Poder Judicial.json
│   ├── Código Fiscal del Estado de Baja California.json
│   ├── Código Nacional de Procedimientos Civiles y Familiares.json
│   ├── Código Nacional de Procedimientos Penales.json
│   └── ...
│
├── Leyes/
│   ├── Ley DE ACCESO DE LAS MUJERES A UNA VIDA LIBRE DE VIOLENCIA.json
│   ├── Ley DE ADOPCIONES DEL ESTADO DE BAJA CALIFORNIA.json
│   ├── Ley DE ADQUISICIONES, ARRENDAMIENTOS y SERVICIOS.json
│   └── ... (100+ archivos)
│
└── Reglamentos/
    ├── Reglamento Interior de los Juzgados de Baja California.json
    ├── Reglamento Interior del Consejo de Administración.json
    ├── Reglamento Interior del Consejo de la Judicatura.json
    ├── Reglamento Interior del Instituto de la Judicatura.json
    ├── Reglamento Interior del Tribunal Superior de Justicia.json
    └── ...
```

---

## 7. Relación entre Archivos

### Diagrama de flujo de datos

```
                              ETAPA 1                    ETAPA 2                    ETAPA 3
                             SCRAPING                  EXTRACCIÓN               CONSOLIDACIÓN
                                │                          │                          │
                                ▼                          ▼                          ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Portal Web     │    │  metadatos_      │    │  codigo-         │    │  Código Civil    │
│   Poder Judicial │───►│  codigos.json    │───►│  contenido.json  │───►│  del Estado.json │
│                  │    │                  │    │                  │    │                  │
│   (scraping)     │    │  • titulo        │    │  • Titulo        │    │  • titulo        │
│                  │    │  • fecha mod     │    │  • contenido     │    │  • Contenido     │
│                  │    │  • fecha pub     │    │                  │    │  • ordenamiento  │
│                  │    │  • url           │    │                  │    │  • jurisdiccion  │
│                  │    │                  │    │                  │    │  • fecha mod     │
│                  │    │                  │    │                  │    │  • fecha pub     │
│                  │    │                  │    │                  │    │  • url           │
│                  │    │                  │    │                  │    │  • es_escaneado  │
└──────────────────┘    └──────────────────┘    └──────────────────┘    └──────────────────┘
         │                                               │
         │                                               │
         ▼                                               │
┌──────────────────┐                                     │
│   PDFs           │─────────────────────────────────────┘
│   Descargados    │
│   (Codigos/)     │
└──────────────────┘
```

### Campos y su origen

| Campo en JSON Final | Origen | Etapa |
|---------------------|--------|-------|
| `titulo` | Nombre del PDF / matching | 3 |
| `Contenido` | `contenido.json` | 2 |
| `ordenamiento` | Generado (LEY/CODIGO/REGLAMENTO) | 3 |
| `jurisdiccion` | Generado (ESTATAL) | 3 |
| `fuente_oficial` | Generado (BAJA CALIFORNIA) | 3 |
| `Fecha de última modificación` | `metadatos.json` | 1 |
| `Fecha de publicación` | `metadatos.json` | 1 |
| `url` | `metadatos.json` | 1 |
| `es_escaneado` | Detección automática | 3 |
| `tiene_tablas` | Detección automática | 3 |

### Diferencias por tipo de documento

| Campo | Leyes (Congreso) | Códigos/Reglamentos (P. Judicial) |
|-------|------------------|-----------------------------------|
| Título origen | `NOMBRE` | `titulo` |
| Fecha 1 | `FECHA PER OFIC` | `Fecha de última modificación` |
| Fecha 2 | - | `Fecha de publicación` |
| Estado | `ESTATUS` | - |
| Tomo | `TOMO` | - |
| URL | `URL` | `url` |

---

## 8. Estadísticas del Estado

### Resumen de archivos

| Categoría | Cantidad aprox. | Tamaño total |
|-----------|-----------------|--------------|
| **PDFs Códigos** | 10+ | Variable |
| **PDFs Leyes** | 100+ | Variable |
| **PDFs Reglamentos** | 20+ | Variable |
| **JSON Contenido** | 3 archivos | ~23.5 MB |
| **JSON Metadatos** | 4 archivos | ~63 KB |
| **JSON Final** | 130+ archivos | Variable |

### Flujo de volumen de datos

```
Portales Web
     │
     ▼ (Scraping)
130+ PDFs descargados + 4 JSON metadatos (~63 KB)
     │
     ▼ (Extracción)
3 JSON contenido (~23.5 MB de texto)
     │
     ▼ (Consolidación)
130+ JSON individuales (completos y estructurados)
```

---

## Comandos de Verificación

### Contar archivos por carpeta

```bash
# PDFs
ls "C:\Users\julii\Documents\BAJA CALIFORNIA\Codigos" | wc -l
ls "C:\Users\julii\Documents\BAJA CALIFORNIA\Leyes" | wc -l
ls "C:\Users\julii\Documents\BAJA CALIFORNIA\Reglamentos" | wc -l

# JSON finales
ls "...\BAJA CALIFORNIA\json\Códigos" | wc -l
ls "...\BAJA CALIFORNIA\json\Leyes" | wc -l
ls "...\BAJA CALIFORNIA\json\Reglamentos" | wc -l
```

### Ver tamaños de archivos

```bash
# Contenido
ls -lh "...\BAJA CALIFORNIA\contenido\"

# Metadatos
ls -lh "...\BAJA CALIFORNIA\json_metadatos\"
```

### Verificar estructura de un JSON final

```bash
head -50 "...\json\Códigos\Código Civil del Estado de Baja California.json"
```

---

## Notas Importantes

### Dependencias entre etapas

1. **Etapa 2 depende de Etapa 1:** Los PDFs deben estar descargados
2. **Etapa 3 depende de Etapa 1 y 2:** Necesita tanto los metadatos como el contenido

### Orden de ejecución recomendado

```bash
# 1. Scraping (descargar PDFs y extraer metadatos de la web)
python scraping/Leyes.py
python scraping/codigos.py
python scraping/reglamentos.py

# 2. Extracción (procesar PDFs a texto)
python scrips/leyes-PDF.py
python scrips/codigo-PDF.py
python scrips/reglamentos-PDF.py

# 3. Consolidación (generar JSON finales)
python metadatos/leyes.py
python metadatos/codigos.py
python metadatos/reglamentos.py
```

### Archivos críticos

| Archivo | Criticidad | Razón |
|---------|------------|-------|
| `metadatos_*.json` | Alta | Contiene URLs y fechas oficiales |
| `*-contenido.json` | Alta | Contiene todo el texto procesado |
| `json/` | Producto final | Datos consolidados listos para uso |

---

> **Última actualización de documentación:** Noviembre 2025

