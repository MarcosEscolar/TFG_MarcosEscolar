"""
log_scraper.py — Registra el estado y resultados de cada ejecución del scraper
en las tablas ScraperRuns y ScraperFuentes de Supabase, y mantiene el fichero
estado.json para que el dashboard sepa si el scraper está corriendo ahora mismo.

API pública:
  run_id = iniciar_run(db)
  finalizar_run(db, run_id, stats, fuentes_stats)
  registrar_error(db, run_id, mensaje)
"""
import json
import os
from datetime import datetime, timezone

# estado.json vive junto a este módulo (scraper/)
ESTADO_PATH = os.path.join(os.path.dirname(__file__), 'estado.json')


def _ahora():
    """Devuelve el timestamp UTC actual en formato ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


# ── Inicio de ejecución ───────────────────────────────────────────────────────

def iniciar_run(db):
    """
    Crea una nueva fila en ScraperRuns con estado 'en_curso' y escribe estado.json.
    Devuelve el run_id (int) o None si Supabase falla (el scraper sigue funcionando).
    """
    inicio = _ahora()
    run_id = None

    try:
        result = db.table('ScraperRuns').insert({
            'fecha_inicio': inicio,
            'estado':       'en_curso',
        }).execute()
        if result.data:
            run_id = result.data[0]['id']
    except Exception as e:
        print(f'[LOG] Error al crear ScraperRun: {e}')

    # Escribir estado.json aunque Supabase haya fallado
    try:
        with open(ESTADO_PATH, 'w', encoding='utf-8') as f:
            json.dump({'corriendo': True, 'inicio': inicio, 'run_id': run_id}, f)
    except Exception as e:
        print(f'[LOG] Error al escribir estado.json: {e}')

    return run_id


# ── Fin de ejecución ─────────────────────────────────────────────────────────

def finalizar_run(db, run_id, stats, fuentes_stats):
    """
    Actualiza ScraperRuns con los resultados e inserta una fila en ScraperFuentes
    por cada fuente procesada. Elimina estado.json al terminar.

    stats (dict):
        noticias_guardadas, noticias_duplicadas, noticias_error, terminos_guardados

    fuentes_stats (list of dict):
        fuente_nombre, respondio (bool), articulos_recibidos (int),
        articulos_guardados (int), error_mensaje (str|None)
    """
    fin = _ahora()

    if run_id is not None:
        # Calcular duración real leyendo fecha_inicio de la BD
        duracion = None
        try:
            row = db.table('ScraperRuns').select('fecha_inicio').eq('id', run_id).execute()
            if row.data:
                inicio_str = row.data[0]['fecha_inicio']
                # Supabase devuelve algo como "2026-05-05T14:30:00+00:00" o con Z
                inicio_dt = datetime.fromisoformat(inicio_str.replace('Z', '+00:00'))
                fin_dt    = datetime.fromisoformat(fin)
                duracion  = round((fin_dt - inicio_dt).total_seconds(), 2)
        except Exception:
            pass

        try:
            db.table('ScraperRuns').update({
                'fecha_fin':           fin,
                'duracion_segundos':   duracion,
                'noticias_guardadas':  stats.get('noticias_guardadas',  0),
                'noticias_duplicadas': stats.get('noticias_duplicadas', 0),
                'noticias_error':      stats.get('noticias_error',      0),
                'terminos_guardados':  stats.get('terminos_guardados',  0),
                'estado':              'completado',
            }).eq('id', run_id).execute()
        except Exception as e:
            print(f'[LOG] Error al actualizar ScraperRun: {e}')

        # Insertar fila por cada fuente
        if fuentes_stats:
            try:
                filas = [
                    {
                        'run_id':              run_id,
                        'fuente_nombre':       f['fuente_nombre'],
                        'respondio':           f.get('respondio',           False),
                        'articulos_recibidos': f.get('articulos_recibidos', 0),
                        'articulos_guardados': f.get('articulos_guardados', 0),
                        'error_mensaje':       f.get('error_mensaje'),
                    }
                    for f in fuentes_stats
                ]
                db.table('ScraperFuentes').insert(filas).execute()
            except Exception as e:
                print(f'[LOG] Error al insertar ScraperFuentes: {e}')

    _borrar_estado()


# ── Error ─────────────────────────────────────────────────────────────────────

def registrar_error(db, run_id, error_mensaje):
    """Marca el run como 'error' en Supabase y elimina estado.json."""
    if run_id is not None:
        try:
            db.table('ScraperRuns').update({
                'fecha_fin':     _ahora(),
                'estado':        'error',
                'error_mensaje': str(error_mensaje)[:500],
            }).eq('id', run_id).execute()
        except Exception as e:
            print(f'[LOG] Error al registrar error en Supabase: {e}')
    _borrar_estado()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _borrar_estado():
    try:
        if os.path.exists(ESTADO_PATH):
            os.remove(ESTADO_PATH)
    except Exception as e:
        print(f'[LOG] Error al eliminar estado.json: {e}')
