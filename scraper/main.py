"""
main.py — Orquestador del scraper de GEOSFERA.

Flujo:
  1. Conectar a Supabase
  2. Obtener artículos de todos los feeds RSS activos
  3. Filtrar los que ya existen (por URL)
  4. Enriquecer cada artículo nuevo con DeepSeek (resumen, tema, términos)
  5. Guardar noticias y términos nuevos en Supabase

Uso:
  python main.py
"""
import os
import sys
import time
from dotenv import load_dotenv
from supabase import create_client

# Cargar variables de entorno desde scraper/.env
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from feeds   import obtener_articulos
from guardar import obtener_urls_existentes, obtener_nombres_glosario, guardar_resultados
from ia      import enriquecer_articulo


def get_db():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    if not url or not key:
        print('[ERROR] Faltan SUPABASE_URL o SUPABASE_SERVICE_KEY en scraper/.env')
        sys.exit(1)
    return create_client(url, key)


def main():
    print('=' * 55)
    print('  GEOSFERA Scraper')
    print('=' * 55)

    usar_ia = bool(os.getenv('GEMINI_API_KEY'))
    if not usar_ia:
        print('[WARN] GEMINI_API_KEY no encontrada → se guardan noticias sin enriquecer')

    # ── 1. Conexión a Supabase ────────────────────────────────────────────
    db = get_db()
    print('[DB] Conectado a Supabase')

    # ── 2. Obtener artículos de los feeds ────────────────────────────────
    articulos = obtener_articulos(db)
    if not articulos:
        print('[INFO] No se encontraron artículos. Fin.')
        return

    # ── 3. Filtrar duplicados y cargar glosario ──────────────────────────
    print('[DB] Cargando URLs existentes y términos del glosario…')
    urls_existentes  = obtener_urls_existentes(db)
    nombres_glosario = obtener_nombres_glosario(db)

    nuevos = [a for a in articulos if a['url'] not in urls_existentes]
    print(f'[INFO] {len(nuevos)} artículos nuevos / {len(articulos) - len(nuevos)} duplicados descartados')

    if not nuevos:
        print('[INFO] Nada nuevo que guardar. Fin.')
        return

    # ── 4. Enriquecer con IA ─────────────────────────────────────────────
    enriquecidos = []
    total = len(nuevos)

    for i, art in enumerate(nuevos, 1):
        print(f'  [{i}/{total}] {art["titulo"][:70]}')

        if usar_ia:
            resultado = enriquecer_articulo(art, nombres_glosario)
            time.sleep(0.5)  # pausa para no saturar la API
        else:
            resultado = {
                'titulo_es':       art['titulo'],
                'resumen_es':      art.get('resumen_raw', '')[:300],
                'tema':            '',
                'terminos_nuevos': [],
            }

        enriquecidos.append({**art, **resultado})

    # ── 5. Guardar en Supabase ────────────────────────────────────────────
    print('[DB] Guardando en Supabase…')
    stats = guardar_resultados(db, enriquecidos, urls_existentes, nombres_glosario)

    print('=' * 55)
    print(f'  ✓ Noticias guardadas:  {stats["noticias_guardadas"]}')
    print(f'  ✓ Términos añadidos:   {stats["terminos_guardados"]}')
    print(f'  ○ Duplicados omitidos: {stats["noticias_duplicadas"]}')
    print('=' * 55)


if __name__ == '__main__':
    main()
