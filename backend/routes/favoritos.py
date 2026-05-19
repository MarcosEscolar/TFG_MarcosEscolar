from flask import Blueprint, request, jsonify, session
from database import get_db
from auth import require_login

favoritos_bp = Blueprint('favoritos', __name__)


# GET / — devuelve la lista de IDs de noticias guardadas por el usuario
@favoritos_bp.route('/', methods=['GET'])
@require_login
def get_favoritos():
    try:
        db         = get_db()
        usuario_id = session.get('user_id')
        res        = db.table('Favoritos').select('noticia_id').eq('usuario_id', usuario_id).execute()
        ids        = [r['noticia_id'] for r in res.data]
        return jsonify(ids)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# GET /noticias — devuelve las noticias completas guardadas por el usuario
@favoritos_bp.route('/noticias', methods=['GET'])
@require_login
def get_favoritos_noticias():
    try:
        db         = get_db()
        usuario_id = session.get('user_id')

        # Obtener IDs guardados ordenados por fecha más reciente 
        res_fav = db.table('Favoritos') \
            .select('noticia_id, created_at') \
            .eq('usuario_id', usuario_id) \
            .order('created_at', desc=True) \
            .execute()

        if not res_fav.data:
            return jsonify([])

        ids = [r['noticia_id'] for r in res_fav.data]

        # Obtener las noticias completas
        res_noticias = db.table('Noticias').select('*').in_('id', ids).execute()

        # Ordenar igual que los favoritos, más reciente guardado primero
        orden = {nid: i for i, nid in enumerate(ids)}
        noticias = sorted(res_noticias.data, key=lambda n: orden.get(n['id'], 999))

        return jsonify(noticias)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# POST / — guardar una noticia
@favoritos_bp.route('/', methods=['POST'])
@require_login
def add_favorito():
    try:
        db         = get_db()
        usuario_id = session.get('user_id')
        data       = request.get_json()
        noticia_id = data.get('noticia_id')

        if not noticia_id:
            return jsonify({'error': 'Falta noticia_id'}), 400

        db.table('Favoritos').insert({
            'usuario_id': usuario_id,
            'noticia_id': noticia_id
        }).execute()

        return jsonify({'ok': True}), 201
    except Exception as e:
        # Si ya existe (UNIQUE constraint) devolvemos 200 igualmente
        if 'duplicate' in str(e).lower() or 'unique' in str(e).lower():
            return jsonify({'ok': True}), 200
        return jsonify({'error': str(e)}), 500


# DELETE — quitar una noticia de favoritos
@favoritos_bp.route('/<int:noticia_id>', methods=['DELETE'])
@require_login
def remove_favorito(noticia_id):
    try:
        db         = get_db()
        usuario_id = session.get('user_id')
        db.table('Favoritos') \
            .delete() \
            .eq('usuario_id', usuario_id) \
            .eq('noticia_id', noticia_id) \
            .execute()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
