from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from config import Config
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY

CORS(app, origins=['http://localhost:5000', 'http://127.0.0.1:5000',
                    'http://localhost:5500', 'http://127.0.0.1:5500'],
    supports_credentials=True)

# Carpetas del proyecto
BASE_DIR      = os.path.join(os.path.dirname(__file__), '..')
PAGES_DIR     = os.path.join(BASE_DIR, 'frontend', 'pages')
CSS_DIR       = os.path.join(BASE_DIR, 'frontend', 'css')
IMAGENES_DIR  = os.path.join(BASE_DIR, 'frontend', 'imagenes')

# ─── Blueprints ────────────────────────────────────────────────────────────────
from routes.auth     import auth_bp
from routes.noticias import noticias_bp
from routes.fuentes  import fuentes_bp
from routes.glosario import glosario_bp

app.register_blueprint(auth_bp,     url_prefix='/api/auth')
app.register_blueprint(noticias_bp, url_prefix='/api/noticias')
app.register_blueprint(fuentes_bp,  url_prefix='/api/fuentes')
app.register_blueprint(glosario_bp, url_prefix='/api/glosario')

# ─── Páginas HTML ──────────────────────────────────────────────────────────────
# La home pública es la presentación. El dashboard real (index.html) vive en /inicio
# y exige sesión iniciada (la propia página redirige a /login si no la tiene).
@app.route('/')
@app.route('/presentacion')
def home():
    return send_from_directory(PAGES_DIR, 'Presentacion.html')

@app.route('/inicio')
def inicio_page():
    return send_from_directory(PAGES_DIR, 'index.html')

@app.route('/fuentes')
def fuentes_page():
    return send_from_directory(PAGES_DIR, 'fuentes.html')

@app.route('/glosario')
def glosario_page():
    return send_from_directory(PAGES_DIR, 'glosario.html')

@app.route('/login')
def login_page():
    return send_from_directory(PAGES_DIR, 'login.html')

# ─── Estáticos ─────────────────────────────────────────────────────────────────
@app.route('/css/<path:filename>')
def css(filename):
    return send_from_directory(CSS_DIR, filename)

@app.route('/imagenes/<path:filename>')
def imagenes(filename):
    return send_from_directory(IMAGENES_DIR, filename)

@app.route('/api')
def api_info():
    return jsonify({'api': 'GEOSFERA', 'version': '1.0', 'estado': 'activo'})

@app.route('/api/health')
def health():
    return jsonify({'estado': 'ok'})

# ─── Errores ───────────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Ruta no encontrada.'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Error interno del servidor.'}), 500


if __name__ == '__main__':
    app.run(debug=Config.DEBUG, port=Config.PORT)
