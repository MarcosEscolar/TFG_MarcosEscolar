from flask import Blueprint, request, jsonify
from database import get_db
from auth import require_admin

glosario_bp = Blueprint('glosario', __name__)


def _str_a_array(valor):
    """Convierte 'term1, term2' → ['term1', 'term2']. Vacío → []."""
    if not valor:
        return []
    return [v.strip() for v in str(valor).split(',') if v.strip()]


# GET / — listar términos
@glosario_bp.route('/', methods=['GET'])
def get_terminos():
    try:
        db = get_db()

        categoria = request.args.get('categoria')
        q         = request.args.get('q')
        limite    = min(int(request.args.get('limite', 0)), 500)
        offset    = int(request.args.get('offset', 0))

        # Sin límite explícito → devolver todo (compatibilidad con el cache del glosario
        # que usa index.html para los tooltips de términos)
        if limite == 0:
            query = db.table('Glosario').select('*')
            if categoria: query = query.eq('categoria', categoria)
            if q:
                q_safe = q.replace(',', ' ').replace('(', ' ').replace(')', ' ')
                query = query.or_(f'nombre.ilike.%{q_safe}%,definicion.ilike.%{q_safe}%')
            result = query.order('nombre').execute()
            return jsonify(result.data or [])

        # Con límite → paginación server-side
        query = db.table('Glosario').select('*', count='exact')
        if categoria: query = query.eq('categoria', categoria)
        if q:
            q_safe = q.replace(',', ' ').replace('(', ' ').replace(')', ' ')
            query = query.or_(f'nombre.ilike.%{q_safe}%,definicion.ilike.%{q_safe}%')

        result = query.order('nombre').range(offset, offset + limite - 1).execute()

        total         = result.count if getattr(result, 'count', None) is not None else len(result.data or [])
        total_paginas = (total + limite - 1) // limite if limite > 0 else 1
        pagina_actual = (offset // limite) + 1 if limite > 0 else 1

        return jsonify({
            'terminos':      result.data or [],
            'total':         total,
            'pagina':        pagina_actual,
            'por_pagina':    limite,
            'total_paginas': total_paginas,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# GET /<id> — obtener término
@glosario_bp.route('/<termino_id>', methods=['GET'])
def get_termino(termino_id):
    try:
        db = get_db()
        result = db.table('Glosario').select('*').eq('id', termino_id).execute()
        if not result.data:
            return jsonify({'error': 'Término no encontrado.'}), 404
        return jsonify(result.data[0])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# POST / — crear término
@glosario_bp.route('/', methods=['POST'])
@require_admin
def create_termino():
    try:
        data = request.get_json()

        for campo in ('nombre', 'definicion'):
            if not data or not data.get(campo):
                return jsonify({'error': f"El campo '{campo}' es obligatorio."}), 400

        db = get_db()
        nuevo = {
            'nombre':      data['nombre'],
            'definicion':  data['definicion'],
            'categoria':   data.get('categoria', 'General'),
            'relacionados': _str_a_array(data.get('relacionados', '')),
            'emoji':       data.get('emoji', ''),
        }

        result = db.table('Glosario').insert(nuevo).execute()
        if not result.data:
            return jsonify({'error': 'Error al crear el término.'}), 500

        return jsonify({'mensaje': 'Término creado.', 'termino': result.data[0]}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# PUT /<id> — editar término
@glosario_bp.route('/<termino_id>', methods=['PUT'])
@require_admin
def update_termino(termino_id):
    try:
        data = request.get_json()
        db = get_db()

        if not db.table('Glosario').select('id').eq('id', termino_id).execute().data:
            return jsonify({'error': 'Término no encontrado.'}), 404

        campos = ('nombre', 'definicion', 'categoria', 'relacionados', 'emoji')
        update_data = {k: v for k, v in (data or {}).items() if k in campos}
        # Convertir relacionados a array si viene como string
        if 'relacionados' in update_data:
            update_data['relacionados'] = _str_a_array(update_data['relacionados'])

        if not update_data:
            return jsonify({'error': 'No hay datos para actualizar.'}), 400

        result = db.table('Glosario').update(update_data).eq('id', termino_id).execute()
        termino = result.data[0] if result.data else {}
        return jsonify({'mensaje': 'Término actualizado.', 'termino': termino})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# DELETE /<id> — eliminar término
@glosario_bp.route('/<termino_id>', methods=['DELETE'])
@require_admin
def delete_termino(termino_id):
    try:
        db = get_db()
        if not db.table('Glosario').select('id').eq('id', termino_id).execute().data:
            return jsonify({'error': 'Término no encontrado.'}), 404
        result = db.table('Glosario').delete().eq('id', termino_id).execute()
        if result.data is not None and len(result.data) == 0:
            return jsonify({'error': 'Supabase no eliminó el registro. Posiblemente RLS activo. Añade SUPABASE_SERVICE_KEY al .env'}), 403
        return jsonify({'mensaje': 'Término eliminado.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# GET /categorias — categorías únicas
@glosario_bp.route('/categorias', methods=['GET'])
def get_categorias():
    try:
        db = get_db()
        result = db.table('Glosario').select('categoria').execute()
        categorias = sorted(set(t['categoria'] for t in (result.data or []) if t.get('categoria')))
        return jsonify(categorias)
    except Exception:
        return jsonify([])
