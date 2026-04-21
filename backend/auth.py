"""
Utilidades de autenticación:
- Hash y verificación de contraseñas con bcrypt
- Decoradores para proteger rutas según sesión y rol
"""
import bcrypt
from functools import wraps
from flask import session, jsonify


# ─── Contraseñas ───────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Devuelve el hash bcrypt de una contraseña."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def check_password(password: str, hashed: str) -> bool:
    """Devuelve True si la contraseña coincide con el hash."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


# ─── Decoradores ───────────────────────────────────────────────────────────────

def require_login(fn):
    """Protege una ruta: el usuario debe haber iniciado sesión."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'Debes iniciar sesión para acceder.'}), 401
        return fn(*args, **kwargs)
    return wrapper


def require_admin(fn):
    """Protege una ruta: el usuario debe ser administrador."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({'error': 'Debes iniciar sesión para acceder.'}), 401
        if session.get('rol') != 'admin':
            return jsonify({'error': 'Acceso denegado. Se requiere rol de administrador.'}), 403
        return fn(*args, **kwargs)
    return wrapper
