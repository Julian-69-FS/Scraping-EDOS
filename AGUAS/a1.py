import os
import win32com.client

# Ruta de la carpeta que contiene los archivos .doc
ruta_origen = r"C:\Users\julii\Documents\AGUASCALIENTES DOF\Reglamento"

# Abre la aplicación de Word
word = win32com.client.Dispatch("Word.Application")
word.Visible = False  # No mostrar Word mientras convierte

# Recorre todos los archivos en la carpeta
for archivo in os.listdir(ruta_origen):
    if archivo.lower().endswith(".doc"):
        ruta_doc = os.path.join(ruta_origen, archivo)
        nombre_pdf = os.path.splitext(archivo)[0] + ".pdf"
        ruta_pdf = os.path.join(ruta_origen, nombre_pdf)

        # Abre el documento y guárdalo como PDF
        try:
            doc = word.Documents.Open(ruta_doc)
            doc.SaveAs(ruta_pdf, FileFormat=17)  # 17 = formato PDF
            doc.Close()
            print(f"✅ Convertido: {archivo} → {nombre_pdf}")
        except Exception as e:
            print(f"⚠️ Error al convertir {archivo}: {e}")

# Cierra Word
word.Quit()

print("\n🎉 ¡Conversión completa! Todos los archivos .doc fueron pasados a .pdf.")
