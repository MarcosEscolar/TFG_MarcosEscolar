"""
recuperar_fechas.py — Rellena fecha en noticias que no la tienen.

Para cada noticia con fecha NULL, descarga su URL y busca
la fecha en los metadatos HTML (article:published_time, og, JSON-LD…).
Si no la encuentra en el HTML, puede usar created_at como fallback.

Uso:
    python recuperar_fechas.py            # solo HTML, sin fallback
    python recuperar_fechas.py --fallback # si no hay fecha en HTML, usa created_at
    python recuperar_fechas.py --dry-run  # muestra qué haría sin tocar la BD
"""
import os
import re
import sys
import json
import time
import argparse
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# ── Configuración 
TIMEOUT       = 8       # segundos por petición HTTP
PAUSA         = 0.3     # segundos entre peticiones para no saturar los servidores
LOTE          = 1000    # cuántas noticias pedir a Supabase por vez


# ── Conectar a Supabase 
def get_db():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    if not url or not key:
        print('[ERROR] Faltan SUPABASE_URL o SUPABASE_SERVICE_KEY en scraper/.env')
        sys.exit(1)
    return create_client(url, key)


# ── Extracción de fecha del HTML 

# Metaetiquetas que suelen llevar la fecha de publicación, en orden de fiabilidad
_META_PROPS = [
    'article:published_time',
    'og:article:published_time',
    'article:published',
    'datePublished',
    'pubdate',
    'date',
    'DC.date',
    'DC.date.issued',
    'sailthru.date',
    'parsely-pub-date',
    'cXenseParse:recs:publishtime',
]

_RE_META = re.compile(
    r'<meta\s[^>]*(property|name|itemprop)\s*=\s*["\']([^"\']+)["\'][^>]*'
    r'content\s*=\s*["\']([^"\']+)["\']|'
    r'<meta\s[^>]*content\s*=\s*["\']([^"\']+)["\'][^>]*'
    r'(property|name|itemprop)\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)

_RE_JSONLD = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def _parse_iso(valor):
    """Intenta convertir una cadena de fecha a datetime UTC. Devuelve None si falla."""
    if not valor:
        return None
    valor = valor.strip()
    for fmt in (
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S.%f%z',
        '%Y-%m-%dT%H:%M%z',
        '%Y-%m-%d %H:%M:%S%z',
        '%Y-%m-%d',
        '%d/%m/%Y',
        '%B %d, %Y',
    ):
        try:
            dt = datetime.strptime(valor[:25], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def extraer_fecha_html(html):
    """
    Busca la fecha de publicación en el HTML de un artículo.
    Devuelve un datetime en UTC o None si no encuentra nada.
    """
    props_lower = {p.lower() for p in _META_PROPS}

    # 1) Metaetiquetas <meta property/name/itemprop … content …>
    for m in _RE_META.finditer(html):
        nombre  = (m.group(2) or m.group(6) or '').lower().strip()
        contenido = (m.group(3) or m.group(4) or '').strip()
        if nombre in props_lower and contenido:
            dt = _parse_iso(contenido)
            if dt:
                return dt

    # 2) JSON-LD (Schema.org NewsArticle / Article)
    for m in _RE_JSONLD.finditer(html):
        try:
            datos = json.loads(m.group(1))
            # Puede ser un dict o una lista de dicts
            if isinstance(datos, list):
                candidatos = datos
            else:
                candidatos = [datos]
            for obj in candidatos:
                for clave in ('datePublished', 'dateCreated', 'dateModified'):
                    val = obj.get(clave)
                    if val:
                        dt = _parse_iso(str(val))
                        if dt:
                            return dt
        except Exception:
            continue

    # 3) time[datetime] — fallback para formatos como <time datetime="…">
    m = re.search(r'<time[^>]+datetime=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if m:
        dt = _parse_iso(m.group(1))
        if dt:
            return dt

    return None


def fecha_desde_patron_url(url):
    """
    Extrae la fecha directamente del patrón de la URL, sin petición HTTP.
    Funciona con medios que incluyen la fecha en su estructura de URL, como:
        - El País:  /internacional/2026-05-01/titulo
        - El Mundo: /2026/05/01/titulo
        - Reuters:  /world/2026-05-01/titulo
    Devuelve datetime UTC (a medianoche) o None si no hay patrón reconocible.
    """
    # Patrón YYYY-MM-DD en cualquier parte de la URL
    m = re.search(r'[/\-_](\d{4})[/\-_](\d{2})[/\-_](\d{2})(?:[/\-_T]|$)', url)
    if m:
        try:
            anio, mes, dia = int(m.group(1)), int(m.group(2)), int(m.group(3))
            # Sanidad básica
            if 2000 <= anio <= 2100 and 1 <= mes <= 12 and 1 <= dia <= 31:
                return datetime(anio, mes, dia, 12, 0, 0, tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def fecha_desde_url(url):
    """
    Intenta obtener la fecha de publicación en dos pasos:
    1. Del patrón de la propia URL (sin petición HTTP, instantáneo)
    2. Descargando la página y buscando metadatos HTML
    """
    # Paso 1: patrón en la URL (gratis, sin red)
    dt = fecha_desde_patron_url(url)
    if dt:
        return dt

    # Paso 2: descargar y buscar metadatos
    try:
        resp = requests.get(
            url, timeout=TIMEOUT,
            headers={'User-Agent': 'Mozilla/5.0'},
            allow_redirects=True,
        )
        if not resp.ok:
            return None
        return extraer_fecha_html(resp.text)
    except Exception:
        return None


# ── Noticias sin fecha ─────────────────────────────────────────────────────────

def obtener_todas(db):
    """Devuelve todas las noticias para intentar recuperar su fecha real del HTML."""
    todas = []
    offset = 0
    while True:
        result = (
            db.table('Noticias')
            .select('id, url, fecha')
            .range(offset, offset + LOTE - 1)
            .execute()
        )
        batch = result.data or []
        todas.extend(batch)
        if len(batch) < LOTE:
            break
        offset += LOTE
    return todas


def actualizar_fecha(db, noticia_id, fecha_iso):
    """Actualiza fecha de una noticia en Supabase."""
    db.table('Noticias').update({'fecha': fecha_iso}).eq('id', noticia_id).execute()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Recuperar fechas de publicación desde HTML')
    parser.add_argument('--fallback', action='store_true',
                        help='Si no se encuentra fecha en el HTML, usar created_at')
    parser.add_argument('--dry-run', action='store_true',
                        help='Solo mostrar qué se haría, sin modificar la BD')
    args = parser.parse_args()

    db = get_db()
    print('[DB] Conectado a Supabase')

    noticias = obtener_todas(db)
    total = len(noticias)
    print(f'[INFO] {total} noticias a procesar\n')

    if total == 0:
        print('[OK] No hay noticias en la BD.')
        return

    encontradas = 0
    fallbacks   = 0
    sin_fecha   = 0

    for i, n in enumerate(noticias, 1):
        url        = n['url']
        prefijo    = f'[{i}/{total}]'

        dt = fecha_desde_url(url)

        if dt:
            iso = dt.isoformat()
            print(f'{prefijo} ✓ {iso}  {url[:70]}')
            if not args.dry_run:
                actualizar_fecha(db, n['id'], iso)
            encontradas += 1

        elif args.fallback and n.get('fecha'):
            # Mantener la fecha de scraping que ya tiene (no se sobreescribe)
            iso = n['fecha']
            print(f'{prefijo} ~ fallback created_at  {url[:70]}')
            if not args.dry_run:
                actualizar_fecha(db, n['id'], iso)
            fallbacks += 1

        else:
            print(f'{prefijo} ✗ sin fecha  {url[:70]}')
            sin_fecha += 1

        time.sleep(PAUSA)

    print()
    print('=' * 55)
    if args.dry_run:
        print('  [DRY-RUN] No se ha modificado nada en la BD')
    print(f'  ✓ Fechas recuperadas del HTML:  {encontradas}')
    if args.fallback:
        print(f'  ~ Fallback a created_at:        {fallbacks}')
    print(f'  ✗ Sin fecha (no actualizadas):  {sin_fecha}')
    print('=' * 55)


if __name__ == '__main__':
    main()
