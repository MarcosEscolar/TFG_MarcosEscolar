from flask import Blueprint, request, jsonify
from database import get_db
from auth import require_admin

fuentes_bp = Blueprint('fuentes', __name__)


# GET / — listar fuentes
@fuentes_bp.route('/', methods=['GET'])
def get_fuentes():
    try:
        db = get_db()

        region = request.args.get('region')
        idioma = request.args.get('idioma')
        activa = request.args.get('activa')

        query = db.table('Fuentes').select('*')
        if region: query = query.eq('region', region)
        if idioma: query = query.eq('idioma', idioma)
        if activa is not None:
            query = query.eq('activa', activa.lower() == 'true')

        result = query.order('nombre').execute()
        return jsonify(result.data or [])

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# GET /<id> — obtener fuente
@fuentes_bp.route('/<fuente_id>', methods=['GET'])
def get_fuente(fuente_id):
    try:
        db = get_db()
        result = db.table('Fuentes').select('*').eq('id', fuente_id).execute()
        if not result.data:
            return jsonify({'error': 'Fuente no encontrada.'}), 404
        return jsonify(result.data[0])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# POST / — crear fuente
@fuentes_bp.route('/', methods=['POST'])
@require_admin
def create_fuente():
    try:
        data = request.get_json()

        for campo in ('nombre', 'url_rss'):
            if not data or not data.get(campo):
                return jsonify({'error': f"El campo '{campo}' es obligatorio."}), 400

        db = get_db()
        nueva = {
            'nombre':  data['nombre'],
            'url_rss': data['url_rss'],
            'idioma':  data.get('idioma', 'ES'),
            'region':  data.get('region', ''),
            'activa':  data.get('activa', True),
        }

        result = db.table('Fuentes').insert(nueva).execute()
        if not result.data:
            return jsonify({'error': 'Error al crear la fuente.'}), 500

        return jsonify({'mensaje': 'Fuente creada.', 'fuente': result.data[0]}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# PUT /<id> — editar fuente
@fuentes_bp.route('/<fuente_id>', methods=['PUT'])
@require_admin
def update_fuente(fuente_id):
    try:
        data = request.get_json()
        db = get_db()

        if not db.table('Fuentes').select('id').eq('id', fuente_id).execute().data:
            return jsonify({'error': 'Fuente no encontrada.'}), 404

        campos = ('nombre', 'url_rss', 'idioma', 'region', 'activa')
        update_data = {k: v for k, v in (data or {}).items() if k in campos}

        if not update_data:
            return jsonify({'error': 'No hay datos para actualizar.'}), 400

        result = db.table('Fuentes').update(update_data).eq('id', fuente_id).execute()
        fuente = result.data[0] if result.data else {}
        return jsonify({'mensaje': 'Fuente actualizada.', 'fuente': fuente})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# DELETE /<id> — eliminar fuente
@fuentes_bp.route('/<fuente_id>', methods=['DELETE'])
@require_admin
def delete_fuente(fuente_id):
    try:
        db = get_db()
        if not db.table('Fuentes').select('id').eq('id', fuente_id).execute().data:
            return jsonify({'error': 'Fuente no encontrada.'}), 404
        result = db.table('Fuentes').delete().eq('id', fuente_id).execute()
        if result.data is not None and len(result.data) == 0:
            return jsonify({'error': 'Supabase no eliminó el registro. Posiblemente RLS activo. Añade SUPABASE_SERVICE_KEY al .env'}), 403
        return jsonify({'mensaje': 'Fuente eliminada.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
