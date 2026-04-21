"""
feeds.py — Lee las fuentes activas de Supabase y parsea sus feeds RSS.
Intenta extraer el artículo completo con trafilatura; si falla usa el resumen del RSS.
"""
import re
import requests
import feedparser
import trafilatura


def obtener_fuentes(db):
    """Devuelve la lista de fuentes activas desde la tabla Fuentes."""
    try:
        result = db.table('Fuentes').select('*').eq('activa', True).execute()
        return result.data or []
    except Exception as e:
        print(f'  [ERROR] No se pudieron cargar las fuentes: {e}')
        return []


def parsear_feed(fuente):
    """
    Parsea el feed RSS de una fuente y devuelve una lista de artículos normalizados.
    Cada artículo tiene: titulo, url, resumen_raw, fuente, idioma.
    """
    articulos = []
    try:
        # Timeout de 10s para no quedarse colgado en fuentes lentas o caídas
        resp = requests.get(fuente['url_rss'], timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        feed = feedparser.parse(resp.content)
        if feed.bozo and not feed.entries:
            print(f'  [WARN] Feed inaccesible: {fuente["nombre"]}')
            return []

        for entry in feed.entries:
            titulo = entry.get('title', '').strip()
            url    = entry.get('link', '').strip()

            if not titulo or not url:
                continue

            # Resumen raw (puede venir en varios campos según el feed)
            resumen_raw = (
                entry.get('summary') or
                entry.get('description') or
                (entry.get('content') or [{}])[0].get('value', '')
            )

            # Limpiar etiquetas HTML y espacios del resumen
            resumen_raw = re.sub(r'<[^>]+>', ' ', resumen_raw or '').strip()
            resumen_raw = re.sub(r'\s+', ' ', resumen_raw)[:800]  # máx 800 chars

            # Intentar extraer el artículo completo con trafilatura
            contenido = extraer_contenido(url)

            articulos.append({
                'titulo':      titulo,
                'url':         url,
                'resumen_raw': resumen_raw,
                'contenido':   contenido,   # texto completo o '' si no se pudo
                'fuente':      fuente['nombre'],
                'idioma':      fuente.get('idioma', 'ES'),
            })

    except Exception as e:
        print(f'  [ERROR] Fallo al parsear {fuente["nombre"]}: {e}')

    return articulos


def extraer_contenido(url):
    """
    Descarga la página y extrae el cuerpo del artículo con trafilatura.
    Devuelve el texto limpio o '' si el sitio lo bloquea o falla.
    Timeout de 15s para no bloquear el scraper con fuentes lentas.
    """
    try:
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        if not resp.ok:
            return ''
        texto = trafilatura.extract(
            resp.text,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
        return texto or ''
    except Exception:
        return ''


def obtener_articulos(db):
    """
    Función principal: obtiene todas las fuentes activas y devuelve
    todos los artículos de sus feeds RSS combinados.
    """
    fuentes   = obtener_fuentes(db)
    total     = len(fuentes)
    articulos = []

    print(f'[feeds] {total} fuentes activas encontradas')

    for i, fuente in enumerate(fuentes, 1):
        print(f'  [{i}/{total}] Parseando: {fuente["nombre"]}')
        nuevos = parsear_feed(fuente)
        articulos.extend(nuevos)
        print(f'         → {len(nuevos)} artículos')

    print(f'[feeds] Total artículos: {len(articulos)}')
    return articulos
