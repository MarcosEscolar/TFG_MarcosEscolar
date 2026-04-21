from flask import Blueprint, request, jsonify, session
from database import get_db
from auth import hash_password, check_password, require_login, require_admin

auth_bp = Blueprint('auth', __name__)


# ─── Registro ──────────────────────────────────────────────────────────────────
@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()

        if not data or not data.get('email') or not data.get('password') or not data.get('nombre'):
            return jsonify({'error': 'Nombre, email y contraseña son obligatorios.'}), 400

        email    = data['email'].lower().strip()
        password = data['password']
        nombre   = data['nombre'].strip()

        if len(password) < 8:
            return jsonify({'error': 'La contraseña debe tener al menos 8 caracteres.'}), 400

        db = get_db()

        # Comprobar si el email ya existe
        existing = db.table('usuarios').select('id').eq('email', email).execute()
        if existing.data:
            return jsonify({'error': 'Ya existe una cuenta con ese email.'}), 409

        # El primer usuario que se registra recibe rol 'admin', el resto 'lector'
        count = db.table('usuarios').select('id', count='exact').execute()
        rol = 'admin' if (count.count or 0) == 0 else 'lector'

        # Guardar con contraseña hasheada
        resultado = db.table('usuarios').insert({
            'email':         email,
            'password_hash': hash_password(password),
            'nombre':        nombre,
            'rol':           rol,
        }).execute()

        if not resultado.data:
            return jsonify({'error': 'Error al crear el usuario.'}), 500

        user = resultado.data[0]

        # Iniciar sesión automáticamente tras el registro
        session['user_id'] = user['id']
        session['nombre']  = user['nombre']
        session['email']   = user['email']
        session['rol']     = user['rol']

        return jsonify({
            'mensaje': 'Cuenta creada correctamente.',
            'usuario': {
                'id':     user['id'],
                'nombre': user['nombre'],
                'email':  user['email'],
                'rol':    user['rol'],
            }
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Login ─────────────────────────────────────────────────────────────────────
@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()

        if not data or not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email y contraseña son obligatorios.'}), 400

        email    = data['email'].lower().strip()
        password = data['password']

        db = get_db()
        resultado = db.table('usuarios').select('*').eq('email', email).execute()

        if not resultado.data:
            return jsonify({'error': 'Email o contraseña incorrectos.'}), 401

        user = resultado.data[0]

        if not check_password(password, user['password_hash']):
            return jsonify({'error': 'Email o contraseña incorrectos.'}), 401

        # Guardar datos en la sesión
        session['user_id'] = user['id']
        session['nombre']  = user['nombre']
        session['email']   = user['email']
        session['rol']     = user['rol']

        return jsonify({
            'mensaje': 'Sesión iniciada correctamente.',
            'usuario': {
                'id':     user['id'],
                'nombre': user['nombre'],
                'email':  user['email'],
                'rol':    user['rol'],
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Logout ────────────────────────────────────────────────────────────────────
@auth_bp.route('/logout', methods=['POST'])
@require_login
def logout():
    session.clear()
    return jsonify({'mensaje': 'Sesión cerrada.'})


# ─── Usuario actual ────────────────────────────────────────────────────────────
@auth_bp.route('/me', methods=['GET'])
@require_login
def me():
    return jsonify({
        'id':     session.get('user_id'),
        'nombre': session.get('nombre'),
        'email':  session.get('email'),
        'rol':    session.get('rol'),
    })


# ─── Listar usuarios (solo admin) ─────────────────────────────────────────────
@auth_bp.route('/usuarios', methods=['GET'])
@require_admin
def get_usuarios():
    db = get_db()
    resultado = db.table('usuarios').select('id, email, nombre, rol, created_at').order('created_at').execute()
    return jsonify(resultado.data)


# ─── Cambiar rol (solo admin) ──────────────────────────────────────────────────
@auth_bp.route('/usuarios/<int:user_id>/rol', methods=['PUT'])
@require_admin
def update_rol(user_id):
    data    = request.get_json()
    nuevo_rol = data.get('rol') if data else None

    if nuevo_rol not in ('admin', 'lector'):
        return jsonify({'error': "El rol debe ser 'admin' o 'lector'."}), 400

    if user_id == session.get('user_id') and nuevo_rol != 'admin':
        return jsonify({'error': 'No puedes quitarte el rol de admin a ti mismo.'}), 400

    db = get_db()
    if not db.table('usuarios').select('id').eq('id', user_id).execute().data:
        return jsonify({'error': 'Usuario no encontrado.'}), 404

    resultado = db.table('usuarios').update({'rol': nuevo_rol}).eq('id', user_id).execute()
    return jsonify({'mensaje': 'Rol actualizado.', 'usuario': resultado.data[0]})


# ─── Eliminar usuario (solo admin) ────────────────────────────────────────────
@auth_bp.route('/usuarios/<int:user_id>', methods=['DELETE'])
@require_admin
def delete_usuario(user_id):
    if user_id == session.get('user_id'):
        return jsonify({'error': 'No puedes eliminar tu propia cuenta.'}), 400

    db = get_db()
    if not db.table('usuarios').select('id').eq('id', user_id).execute().data:
        return jsonify({'error': 'Usuario no encontrado.'}), 404

    db.table('usuarios').delete().eq('id', user_id).execute()
    return jsonify({'mensaje': 'Usuario eliminado.'})
