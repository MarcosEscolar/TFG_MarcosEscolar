"""
main.py — Orquestador del scraper de GEOSFERA.

Flujo:
  1. Conectar a Supabase y registrar inicio de ejecución
  2. Obtener artículos de todos los feeds RSS activos
  3. Filtrar los que ya existen (por URL)
  4. Enriquecer cada artículo nuevo con Gemini (resumen, tema, términos)
  5. Guardar noticias y términos nuevos en Supabase
  6. Registrar fin de ejecución con estadísticas por fuente

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

from feeds       import obtener_articulos
from guardar     import obtener_urls_existentes, obtener_nombres_glosario, guardar_resultados
from ia          import enriquecer_articulo
from log_scraper import iniciar_run, finalizar_run, registrar_error


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

    # ── 1. Conexión a Supabase + inicio de log ───────────────────────────
    db = get_db()
    print('[DB] Conectado a Supabase')
    run_id = iniciar_run(db)
    print(f'[LOG] Ejecución iniciada (run_id={run_id})')

    try:
        # ── 2. Cargar URLs y glosario ANTES de parsear feeds ────────────
        # Así feeds.py puede saltarse trafilatura en artículos ya existentes,
        # reduciendo el tiempo de ejecución de ~40 min a ~5-10 min.
        print('[DB] Cargando URLs existentes y términos del glosario…')
        urls_existentes  = obtener_urls_existentes(db)
        nombres_glosario = obtener_nombres_glosario(db)
        print(f'[DB] {len(urls_existentes)} URLs en BD, {len(nombres_glosario)} términos en glosario')

        # ── 3. Obtener artículos de los feeds (solo trafilatura en nuevos) ──
        articulos, fuentes_stats = obtener_articulos(db, urls_existentes)
        if not articulos:
            print('[INFO] No se encontraron artículos. Fin.')
            finalizar_run(db, run_id, {
                'noticias_guardadas':  0,
                'noticias_duplicadas': 0,
                'noticias_error':      0,
                'terminos_guardados':  0,
            }, fuentes_stats)
            return

        nuevos = [a for a in articulos if not a.get('_duplicado')]
        duplicados = len(articulos) - len(nuevos)
        print(f'[INFO] {len(nuevos)} artículos a procesar / {duplicados} duplicados omitidos')

        if not nuevos:
            print('[INFO] Nada nuevo que guardar. Fin.')
            finalizar_run(db, run_id, {
                'noticias_guardadas':  0,
                'noticias_duplicadas': len(articulos),
                'noticias_error':      0,
                'terminos_guardados':  0,
            }, fuentes_stats)
            return

        # ── 4. Enriquecer con IA ─────────────────────────────────────────
        enriquecidos = []
        total = len(nuevos)

        for i, art in enumerate(nuevos, 1):
            print(f'  [{i}/{total}] {art["titulo"][:70]}')

            if usar_ia:
                resultado = enriquecer_articulo(art, nombres_glosario)
                time.sleep(4)  # Gemini Flash free: 15 req/min → mín. 4 s entre llamadas
            else:
                resultado = {
                    'titulo_es':       art['titulo'],
                    'resumen_es':      art.get('resumen_raw', '')[:300],
                    'analisis_es':     '',
                    'tema':            [],
                    'terminos_nuevos': [],
                }

            enriquecidos.append({**art, **resultado})

        # ── 5. Guardar en Supabase ────────────────────────────────────────
        print('[DB] Guardando en Supabase…')
        stats = guardar_resultados(db, enriquecidos, urls_existentes, nombres_glosario)
        # Sumar los duplicados filtrados antes del enriquecimiento (los que ya
        # estaban en la BD por URL y nunca llegaron a guardar_resultados)
        stats['noticias_duplicadas'] += duplicados

        # ── 6. Combinar stats de fuentes (recibidos + guardados) ──────────
        guardadas_por_fuente = stats.pop('guardadas_por_fuente', {})
        for fs in fuentes_stats:
            fs['articulos_guardados'] = guardadas_por_fuente.get(fs['fuente_nombre'], 0)

        finalizar_run(db, run_id, stats, fuentes_stats)

        print('=' * 55)
        print(f'  ✓ Noticias guardadas:  {stats["noticias_guardadas"]}')
        print(f'  ✓ Términos añadidos:   {stats["terminos_guardados"]}')
        print(f'  ○ Duplicados omitidos: {stats["noticias_duplicadas"]}')
        if stats['noticias_error']:
            print(f'  ✗ Errores al guardar:  {stats["noticias_error"]}')
        print('=' * 55)

    except Exception as e:
        print(f'[ERROR] Fallo inesperado: {e}')
        registrar_error(db, run_id, e)
        raise


if __name__ == '__main__':
    main()
