from flask import Blueprint, request, jsonify
from database import get_db
from auth import require_admin

noticias_bp = Blueprint('noticias', __name__)


def _str_a_array(valor):
    """Convierte 'term1, term2' → ['term1', 'term2']. Vacío → []."""
    if not valor:
        return []
    if isinstance(valor, list):
        return valor
    return [v.strip() for v in str(valor).split(',') if v.strip()]


def _tabla_noticias(db):
    """Devuelve el nombre real de la tabla probando mayúscula y minúscula."""
    for nombre in ('Noticias', 'noticias'):
        try:
            r = db.table(nombre).select('id').limit(1).execute()
            # Si no lanza excepción, la tabla existe
            return nombre
        except Exception:
            continue
    return 'Noticias'  # fallback


# GET / — listar noticias
@noticias_bp.route('/', methods=['GET'])
def get_noticias():
    try:
        db = get_db()

        tema   = request.args.get('tema')
        idioma = request.args.get('idioma')
        fuente = request.args.get('fuente')
        q      = request.args.get('q')
        limite = min(int(request.args.get('limite', 50)), 500)
        offset = int(request.args.get('offset', 0))

        tabla = _tabla_noticias(db)
        query = db.table(tabla).select('*')
        if tema:   query = query.eq('tema', tema)
        if idioma: query = query.eq('idioma', idioma)
        if fuente: query = query.eq('fuente', fuente)
        if q:      query = query.ilike('titulo', f'%{q}%')

        try:
            result = query.order('id', desc=True).range(offset, offset + limite - 1).execute()
        except Exception:
            result = query.execute()  # fallback sin orden ni paginación

        return jsonify({'noticias': result.data or [], 'total': len(result.data or []), 'tabla': tabla})

    except Exception as e:
        return jsonify({'error': str(e), 'noticias': []}), 500


# GET /<id> — obtener una noticia
@noticias_bp.route('/<noticia_id>', methods=['GET'])
def get_noticia(noticia_id):
    try:
        db = get_db()
        tabla = _tabla_noticias(db)
        result = db.table(tabla).select('*').eq('id', noticia_id).execute()
        if not result.data:
            return jsonify({'error': 'Noticia no encontrada.'}), 404
        return jsonify(result.data[0])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# POST / — crear noticia
@noticias_bp.route('/', methods=['POST'])
@require_admin
def create_noticia():
    try:
        data = request.get_json()

        if not data or not data.get('titulo'):
            return jsonify({'error': "El campo 'titulo' es obligatorio."}), 400
        if not data.get('url'):
            return jsonify({'error': "El campo 'url' es obligatorio."}), 400
        if not data.get('fuente'):
            return jsonify({'error': "El campo 'fuente' es obligatorio."}), 400

        db = get_db()
        tabla = _tabla_noticias(db)
        nueva = {
            'titulo':     data['titulo'],
            'resumen_es': data.get('resumen_es', ''),
            'contenido':  data.get('contenido', ''),
            'url':        data['url'],
            'fuente':     data['fuente'],
            'idioma':     data.get('idioma', 'ES'),
            'tema':       data.get('tema', ''),
            'terminos':   _str_a_array(data.get('terminos', '')),
        }

        result = db.table(tabla).insert(nueva).execute()
        if not result.data:
            return jsonify({'error': 'Error al crear la noticia.'}), 500

        return jsonify({'mensaje': 'Noticia creada.', 'noticia': result.data[0]}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# PUT /<id> — editar noticia
@noticias_bp.route('/<noticia_id>', methods=['PUT'])
@require_admin
def update_noticia(noticia_id):
    try:
        data = request.get_json()
        db = get_db()
        tabla = _tabla_noticias(db)

        if not db.table(tabla).select('id').eq('id', noticia_id).execute().data:
            return jsonify({'error': 'Noticia no encontrada.'}), 404

        campos = ('titulo', 'resumen_es', 'contenido', 'url', 'fuente', 'idioma', 'tema', 'terminos')
        update_data = {k: v for k, v in (data or {}).items() if k in campos}
        # Convertir terminos a array si viene como string
        if 'terminos' in update_data:
            update_data['terminos'] = _str_a_array(update_data['terminos'])

        if not update_data:
            return jsonify({'error': 'No hay datos para actualizar.'}), 400

        result = db.table(tabla).update(update_data).eq('id', noticia_id).execute()
        noticia = result.data[0] if result.data else {}
        return jsonify({'mensaje': 'Noticia actualizada.', 'noticia': noticia})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# DELETE /<id> — eliminar noticia
@noticias_bp.route('/<noticia_id>', methods=['DELETE'])
@require_admin
def delete_noticia(noticia_id):
    try:
        db = get_db()
        tabla = _tabla_noticias(db)
        if not db.table(tabla).select('id').eq('id', noticia_id).execute().data:
            return jsonify({'error': 'Noticia no encontrada.'}), 404
        result = db.table(tabla).delete().eq('id', noticia_id).execute()
        if result.data is not None and len(result.data) == 0:
            return jsonify({'error': 'Supabase no eliminó el registro. Posiblemente RLS activo. Añade SUPABASE_SERVICE_KEY al .env'}), 403
        return jsonify({'mensaje': 'Noticia eliminada.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# GET /temas — listar temas únicos
@noticias_bp.route('/temas', methods=['GET'])
def get_temas():
    try:
        db = get_db()
        result = db.table('Noticias').select('tema').execute()
        temas = sorted(set(n['tema'] for n in (result.data or []) if n.get('tema')))
        return jsonify(temas)
    except Exception as e:
        return jsonify([])
