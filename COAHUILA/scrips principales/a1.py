# -*- coding: utf-8 -*-
import os
import shutil
from pathlib import Path

def mover_archivos_y_eliminar_carpetas(ruta_principal):
    """
    Recorre subcarpetas del tipo: Acuerdo/00-00-0000/archivos.pdf
    Mueve los archivos UN nivel arriba y elimina la carpeta fecha.

    Args:
        ruta_principal: Ruta de la carpeta principal a procesar
    """
    ruta_principal = Path(ruta_principal)

    if not ruta_principal.exists():
        print(f"Error: La ruta {ruta_principal} no existe")
        return

    # Contador de archivos movidos y carpetas eliminadas
    archivos_movidos = 0
    carpetas_eliminadas = 0

    # Buscar todas las subcarpetas que contienen archivos
    # Ejemplo: "Acuerdo" es una subcarpeta de la principal
    for subcarpeta in ruta_principal.iterdir():
        if not subcarpeta.is_dir():
            continue

        print(f"\n--- Procesando subcarpeta: {subcarpeta.name} ---")

        # Dentro de cada subcarpeta (ej: "Acuerdo"), buscar carpetas con fechas
        for carpeta_fecha in subcarpeta.iterdir():
            if not carpeta_fecha.is_dir():
                continue

            # Listar archivos dentro de la carpeta fecha (ej: "00-00-0000")
            archivos = [f for f in carpeta_fecha.iterdir() if f.is_file()]

            if archivos:
                print(f"\n  Carpeta: {carpeta_fecha.name}")
                print(f"  Encontrados {len(archivos)} archivo(s)")

                # Mover cada archivo UN nivel arriba (a la carpeta padre, ej: "Acuerdo")
                for archivo in archivos:
                    destino = subcarpeta / archivo.name

                    # Si ya existe un archivo con el mismo nombre, agregar sufijo
                    contador = 1
                    while destino.exists():
                        nombre_base = archivo.stem
                        extension = archivo.suffix
                        destino = subcarpeta / f"{nombre_base}_{contador}{extension}"
                        contador += 1

                    try:
                        shutil.move(str(archivo), str(destino))
                        print(f"    -> Movido: {archivo.name}")
                        archivos_movidos += 1
                    except Exception as e:
                        print(f"    X Error moviendo {archivo.name}: {e}")

                # Eliminar la carpeta fecha si esta vacia
                try:
                    if not any(carpeta_fecha.iterdir()):
                        carpeta_fecha.rmdir()
                        print(f"    -> Carpeta eliminada: {carpeta_fecha.name}")
                        carpetas_eliminadas += 1
                except Exception as e:
                    print(f"    X Error eliminando {carpeta_fecha.name}: {e}")

    print(f"\n{'='*60}")
    print(f"Proceso completado:")
    print(f"  - Archivos movidos: {archivos_movidos}")
    print(f"  - Carpetas eliminadas: {carpetas_eliminadas}")
    print(f"{'='*60}")


if __name__ == "__main__":
    # Ruta principal a procesar
    ruta = r"C:\Users\julii\Documents\COAHUILA DOF"

    print(f"Iniciando proceso en: {ruta}")
    print("="*60)

    # Confirmar antes de ejecutar
    respuesta = input("\n¿Deseas continuar? Esta operacion movera archivos. (s/n): ")

    if respuesta.lower() == 's':
        mover_archivos_y_eliminar_carpetas(ruta)
    else:
        print("Operacion cancelada.")
