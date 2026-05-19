"""
scraper.py — Endpoints para el dashboard de monitorización del scraper.

GET /api/scraper/estado        → estado actual (corriendo o no, desde estado.json)
GET /api/scraper/runs          → lista de las últimas N ejecuciones
GET /api/scraper/runs/<run_id> → detalle completo de una ejecución (con fuentes)
GET /api/scraper/stats         → estadísticas globales para el dashboard
"""
from flask import Blueprint, jsonify, request
from database import get_db

scraper_bp = Blueprint('scraper', __name__)


# Estado del Scraper  

@scraper_bp.route('/estado', methods=['GET'])
def get_estado():
    """
    Devuelve si el scraper está corriendo ahora mismo.
    Fuente de verdad: tabla ScraperRuns — si hay algún run con estado='en_curso'
    el scraper está activo. Así funciona tanto en local como en producción (Render),
    independientemente de dónde se ejecute el scraper (GitHub Actions, local…).
    """
    try:
        db = get_db()
        result = (
            db.table('ScraperRuns')
            .select('id, fecha_inicio')
            .eq('estado', 'en_curso')
            .order('fecha_inicio', desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            run = result.data[0]
            return jsonify({'corriendo': True, 'inicio': run['fecha_inicio'], 'run_id': run['id']})
        return jsonify({'corriendo': False})
    except Exception as e:
        return jsonify({'corriendo': False, 'error': str(e)})


# Lista de ejecuciones 

@scraper_bp.route('/runs', methods=['GET'])
def get_runs():
    """Devuelve las últimas N ejecuciones (por defecto 30)."""
    try:
        limite = min(int(request.args.get('limite', 30)), 100)
        db = get_db()
        result = (
            db.table('ScraperRuns')
            .select('*')
            .order('fecha_inicio', desc=True)
            .limit(limite)
            .execute()
        )
        return jsonify(result.data or [])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Detalle de una ejecución 

@scraper_bp.route('/runs/<int:run_id>', methods=['GET'])
def get_run(run_id):
    """Devuelve el detalle de un run concreto, incluyendo sus fuentes."""
    try:
        db = get_db()
        run = db.table('ScraperRuns').select('*').eq('id', run_id).execute()
        if not run.data:
            return jsonify({'error': 'Ejecución no encontrada.'}), 404

        fuentes = (
            db.table('ScraperFuentes')
            .select('*')
            .eq('run_id', run_id)
            .order('articulos_guardados', desc=True)
            .execute()
        )
        return jsonify({
            **run.data[0],
            'fuentes': fuentes.data or [],
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Estadísticas globales para el dashboard 

@scraper_bp.route('/stats', methods=['GET'])
def get_stats():
    """
    Devuelve en una sola llamada todo lo que necesita el dashboard:
    - Último run completado con sus fuentes
    - Totales históricos (últimos 30 días)
    - Distribución de temas de noticias y glosario
    - Noticias por idioma
    - Historial de runs (para la gráfica de líneas)
    """
    try:
        db = get_db()

        # Último run completado 
        ultimo_run_res = (
            db.table('ScraperRuns')
            .select('*')
            .eq('estado', 'completado')
            .order('fecha_inicio', desc=True)
            .limit(1)
            .execute()
        )
        ultimo_run = ultimo_run_res.data[0] if ultimo_run_res.data else None

        fuentes_ultimo = []
        if ultimo_run:
            fuentes_res = (
                db.table('ScraperFuentes')
                .select('*')
                .eq('run_id', ultimo_run['id'])
                .order('articulos_guardados', desc=True)
                .execute()
            )
            fuentes_ultimo = fuentes_res.data or []

        # Historial de los últimos 30 runs 
        historial_res = (
            db.table('ScraperRuns')
            .select('id, fecha_inicio, noticias_guardadas, estado, duracion_segundos')
            .order('fecha_inicio', desc=True)
            .limit(30)
            .execute()
        )
        historial = list(reversed(historial_res.data or []))

        # Temas de noticias 
        temas_res = db.table('Noticias').select('tema').execute()
        temas_count = {}
        for row in (temas_res.data or []):
            val = row.get('tema')
            if not val:
                continue
            items = val if isinstance(val, list) else [val]
            for t in items:
                if t:
                    temas_count[t] = temas_count.get(t, 0) + 1

        # Categorías de glosario
        cat_res = db.table('Glosario').select('categoria').execute()
        cat_count = {}
        for row in (cat_res.data or []):
            c = row.get('categoria')
            if c:
                cat_count[c] = cat_count.get(c, 0) + 1

        # Noticias por idioma
        idioma_res = db.table('Noticias').select('idioma').execute()
        idioma_count = {}
        for row in (idioma_res.data or []):
            lang = row.get('idioma') or 'Desconocido'
            idioma_count[lang] = idioma_count.get(lang, 0) + 1

        # Datos globales 
        total_noticias = (db.table('Noticias')
                            .select('id', count='exact')
                            .limit(1).execute().count or 0)
        total_glosario = (db.table('Glosario')
                            .select('id', count='exact')
                            .limit(1).execute().count or 0)
        total_runs     = (db.table('ScraperRuns')
                            .select('id', count='exact')
                            .limit(1).execute().count or 0)

        return jsonify({
            'ultimo_run':    ultimo_run,
            'fuentes_ultimo': fuentes_ultimo,
            'historial':     historial,
            'temas_noticias': temas_count,
            'categorias_glosario': cat_count,
            'idiomas':       idioma_count,
            'totales': {
                'noticias': total_noticias,
                'glosario': total_glosario,
                'runs':     total_runs,
            },
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
