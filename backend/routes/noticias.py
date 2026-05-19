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



# GET — listar noticias
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

        tabla = 'Noticias'
        # count='exact' pide a Supabase el total real de filas que cumplen los filtros,
        # independientemente de la página devuelta. Queda en result.count.
        query = db.table(tabla).select('*', count='exact')
        if tema:   query = query.contains('tema', [tema])
        if idioma: query = query.eq('idioma', idioma)
        if fuente: query = query.eq('fuente', fuente)
        if q:
            # Buscar el texto tanto en el título como en el resumen.
            # Sanitizamos los caracteres que romperían el operador or_ de PostgREST.
            q_safe = q.replace(',', ' ').replace('(', ' ').replace(')', ' ')
            query = query.or_(f'titulo.ilike.%{q_safe}%,resumen_es.ilike.%{q_safe}%')

        try:
            result = (
                query
                .order('fecha', desc=True, nullsfirst=False)
                .order('id', desc=True)
                .range(offset, offset + limite - 1)
                .execute()
            )
        except Exception:
            result = query.execute()  # fallback sin orden ni paginación

        total = result.count if getattr(result, 'count', None) is not None else len(result.data or [])
        total_paginas = (total + limite - 1) // limite if limite > 0 else 1
        pagina_actual = (offset // limite) + 1 if limite > 0 else 1

        return jsonify({
            'noticias':      result.data or [],
            'total':         total,
            'pagina':        pagina_actual,
            'por_pagina':    limite,
            'total_paginas': total_paginas,
            'tabla':         tabla,
        })

    except Exception as e:
        return jsonify({'error': str(e), 'noticias': []}), 500


# GET  — obtener una noticia
@noticias_bp.route('/<noticia_id>', methods=['GET'])
def get_noticia(noticia_id):
    try:
        db = get_db()
        tabla = 'Noticias'
        result = db.table(tabla).select('*').eq('id', noticia_id).execute()
        if not result.data:
            return jsonify({'error': 'Noticia no encontrada.'}), 404
        return jsonify(result.data[0])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# POST — crear noticia
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
        tabla = 'Noticias'
        nueva = {
            'titulo':            data['titulo'],
            'resumen_es':        data.get('resumen_es', ''),
            'contenido':         data.get('contenido', ''),
            'url':               data['url'],
            'fuente':            data['fuente'],
            'idioma':            data.get('idioma', 'ES'),
            'tema':              _str_a_array(data.get('tema', '')),
            'terminos':          _str_a_array(data.get('terminos', '')),
            'fecha': data.get('fecha') or None,
        }

        result = db.table(tabla).insert(nueva).execute()
        if not result.data:
            return jsonify({'error': 'Error al crear la noticia.'}), 500

        return jsonify({'mensaje': 'Noticia creada.', 'noticia': result.data[0]}), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# PUT — editar noticia
@noticias_bp.route('/<noticia_id>', methods=['PUT'])
@require_admin
def update_noticia(noticia_id):
    try:
        data = request.get_json()
        db = get_db()
        tabla = 'Noticias'

        if not db.table(tabla).select('id').eq('id', noticia_id).execute().data:
            return jsonify({'error': 'Noticia no encontrada.'}), 404

        campos = ('titulo', 'resumen_es', 'contenido', 'url', 'fuente', 'idioma', 'tema', 'terminos', 'fecha')
        update_data = {k: v for k, v in (data or {}).items() if k in campos}
        # Convertir terminos y tema a array si vienen como string
        if 'terminos' in update_data:
            update_data['terminos'] = _str_a_array(update_data['terminos'])
        if 'tema' in update_data:
            update_data['tema'] = _str_a_array(update_data['tema'])

        if not update_data:
            return jsonify({'error': 'No hay datos para actualizar.'}), 400

        result = db.table(tabla).update(update_data).eq('id', noticia_id).execute()
        noticia = result.data[0] if result.data else {}
        return jsonify({'mensaje': 'Noticia actualizada.', 'noticia': noticia})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# DELETE — eliminar noticia
@noticias_bp.route('/<noticia_id>', methods=['DELETE'])
@require_admin
def delete_noticia(noticia_id):
    try:
        db = get_db()
        tabla = 'Noticias'
        if not db.table(tabla).select('id').eq('id', noticia_id).execute().data:
            return jsonify({'error': 'Noticia no encontrada.'}), 404
        result = db.table(tabla).delete().eq('id', noticia_id).execute()
        if result.data is not None and len(result.data) == 0:
            return jsonify({'error': 'Supabase no eliminó el registro. Posiblemente RLS activo. Añade SUPABASE_SERVICE_KEY al .env'}), 403
        return jsonify({'mensaje': 'Noticia eliminada.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# GET — noticias puntuadas por temas y términos en común
@noticias_bp.route('/<noticia_id>/relacionadas', methods=['GET'])
def get_relacionadas(noticia_id):
    try:
        db = get_db()

        ref = db.table('Noticias').select('tema, terminos').eq('id', noticia_id).execute()
        if not ref.data:
            return jsonify([])

        temas     = ref.data[0].get('tema')     or []
        terminos  = ref.data[0].get('terminos') or []

        if not temas and not terminos:
            return jsonify([])

        campos = 'id, titulo, resumen_es, fuente, fecha, tema, terminos'
        candidatos = {}

        if temas:
            r = (db.table('Noticias').select(campos)
                .overlaps('tema', temas)
                .neq('id', noticia_id)
                .order('fecha', desc=True, nullsfirst=False)
                .limit(30)
                .execute())
            for n in (r.data or []):
                candidatos[n['id']] = n

        if terminos:
            r = (db.table('Noticias').select(campos)
                .overlaps('terminos', terminos)
                .neq('id', noticia_id)
                .order('fecha', desc=True, nullsfirst=False)
                .limit(30)
                .execute())
            for n in (r.data or []):
                candidatos[n['id']] = n

        def puntuar(n):
            temas_comunes    = len(set(n.get('tema')    or []) & set(temas))
            terminos_comunes = len(set(n.get('terminos') or []) & set(terminos))
            return temas_comunes * 2 + terminos_comunes

        ordenados = sorted(candidatos.values(), key=puntuar, reverse=True)
        return jsonify(ordenados[:4])

    except Exception as e:
        return jsonify([])


# GET — listar temas únicos
@noticias_bp.route('/temas', methods=['GET'])
def get_temas():
    try:
        db = get_db()
        result = db.table('Noticias').select('tema').execute()
        temas_set = set()
        for n in (result.data or []):
            val = n.get('tema')
            if not val:
                continue
            if isinstance(val, list):
                temas_set.update(t for t in val if t)
            else:
                temas_set.add(val)
        temas = sorted(temas_set)
        return jsonify(temas)
    except Exception as e:
        return jsonify([])
