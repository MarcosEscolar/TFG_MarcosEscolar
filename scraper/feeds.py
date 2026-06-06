"""
feeds.py — Lee las fuentes activas de Supabase y parsea sus feeds RSS.
Intenta extraer el artículo completo con trafilatura; si falla usa el resumen del RSS.
"""
import re
import calendar
import requests
import feedparser
import trafilatura
from datetime import datetime, timezone



def obtener_fuentes(db):
    """Devuelve la lista de fuentes activas desde la tabla Fuentes."""
    try:
        result = db.table('Fuentes').select('*').eq('activa', True).execute()
        return result.data or []
    except Exception as e:
        print(f'  [ERROR] No se pudieron cargar las fuentes: {e}')
        return []


def parsear_feed(fuente, urls_existentes=None):
    """
    Parsea el feed RSS de una fuente y devuelve una lista de artículos normalizados.
    Cada artículo tiene: titulo, url, resumen_raw, fuente, idioma.

    urls_existentes: set de URLs ya guardadas en Supabase. Si se proporciona,
    se salta el costoso paso de trafilatura para los artículos duplicados.

    IMPORTANTE: los errores de conexión y parseo del feed se dejan propagar al
    caller (_parsear_feed_con_stat) para que pueda registrarlos en error_mensaje.
    Solo los errores al procesar entradas individuales se capturan internamente.
    """
    articulos = []
    urls_existentes = urls_existentes or set()

    # Conexión y parseo inicial: si falla, la excepción sube al caller.
    resp = requests.get(fuente['url_rss'], timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
    feed = feedparser.parse(resp.content)
    if feed.bozo and not feed.entries:
        raise ConnectionError(f'Feed inaccesible o malformado: {fuente["nombre"]}')

    for entry in feed.entries:
        try:
            titulo = entry.get('title', '').strip()
            url    = entry.get('link', '').strip()

            if not titulo or not url:
                continue

            # Fecha de publicación del XML (<pubDate> / <dc:date> / <updated>)
            tp = entry.get('published_parsed') or entry.get('updated_parsed')
            fecha = None
            if tp:
                try:
                    fecha = datetime.fromtimestamp(
                        calendar.timegm(tp), tz=timezone.utc
                    ).isoformat()
                except Exception:
                    fecha = None

            # Si la URL ya existe en Supabase, la marcamos sin trafilatura ni Gemini
            if url in urls_existentes:
                articulos.append({
                    'titulo':      titulo,
                    'url':         url,
                    'resumen_raw': '',
                    'contenido':   '',
                    'fuente':      fuente['nombre'],
                    'idioma':      fuente.get('idioma', 'ES'),
                    'fecha':       fecha,
                    '_duplicado':  True,
                })
                continue

            # Resumen raw (puede venir en varios campos según el feed)
            resumen_raw = (
                entry.get('summary') or
                entry.get('description') or
                (entry.get('content') or [{}])[0].get('value', '')
            )

            # Limpiar etiquetas HTML y espacios del resumen
            resumen_raw = re.sub(r'<[^>]+>', ' ', resumen_raw or '').strip()
            resumen_raw = re.sub(r'\s+', ' ', resumen_raw)[:800]

            # Intentar extraer el artículo completo con trafilatura
            contenido = extraer_contenido(url)

            articulos.append({
                'titulo':      titulo,
                'url':         url,
                'resumen_raw': resumen_raw,
                'contenido':   contenido,
                'fuente':      fuente['nombre'],
                'idioma':      fuente.get('idioma', 'ES'),
                'fecha':       fecha,
                '_duplicado':  False,
            })

        except Exception as e:
            # Error en una entrada concreta: se registra pero no detiene el resto
            print(f'  [WARN] Error procesando entrada de {fuente["nombre"]}: {e}')
            continue

    return articulos


def extraer_contenido(url):
    """
    Descarga la página y extrae el cuerpo del artículo con trafilatura.
    Devuelve el texto limpio o '' si el sitio lo bloquea o falla.
    Timeout de 5s: si no responde en 5s no va a dar mejor contenido esperando más.
    """
    try:
        resp = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
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


def obtener_articulos(db, urls_existentes=None):
    """
    Función principal: obtiene todas las fuentes activas y devuelve
    todos los artículos de sus feeds RSS combinados, junto con las
    estadísticas por fuente para el log del scraper.

    urls_existentes: set de URLs ya en Supabase. Si se proporciona,
    se evita llamar a trafilatura en duplicados y se limitan los
    artículos nuevos a MAX_POR_FUENTE por fuente.

    Devuelve: (articulos, fuentes_stats)
      articulos    — lista de dicts con los artículos
      fuentes_stats — lista de dicts con {fuente_nombre, respondio,
                      articulos_recibidos, error_mensaje}
    """
    fuentes       = obtener_fuentes(db)
    total         = len(fuentes)
    articulos     = []
    fuentes_stats = []

    print(f'[feeds] {total} fuentes activas encontradas')

    for i, fuente in enumerate(fuentes, 1):
        print(f'  [{i}/{total}] Parseando: {fuente["nombre"]}')
        nuevos, stat = _parsear_feed_con_stat(fuente, urls_existentes)
        articulos.extend(nuevos)
        fuentes_stats.append(stat)
        nuevos_count = sum(1 for a in nuevos if not a.get('_duplicado'))
        print(f'         -> {stat["articulos_recibidos"]} recibidos, {nuevos_count} nuevos a procesar')

    nuevos_total = sum(1 for a in articulos if not a.get('_duplicado'))
    print(f'[feeds] Total: {len(articulos)} artículos ({nuevos_total} nuevos, {len(articulos)-nuevos_total} duplicados)')
    return articulos, fuentes_stats


def _parsear_feed_con_stat(fuente, urls_existentes=None):
    """
    Wrapper sobre parsear_feed que devuelve también el dict de estadísticas
    para ScraperFuentes. No reemplaza parsear_feed para no romper usos futuros.
    """
    stat = {
        'fuente_nombre':       fuente['nombre'],
        'respondio':           False,
        'articulos_recibidos': 0,
        'error_mensaje':       None,
    }
    try:
        articulos = parsear_feed(fuente, urls_existentes)
        stat['respondio']           = True
        # Solo contamos los nuevos en "recibidos" (los duplicados ya estaban)
        stat['articulos_recibidos'] = sum(1 for a in articulos if not a.get('_duplicado'))
    except Exception as e:
        stat['error_mensaje'] = str(e)[:300]
        articulos = []
    return articulos, stat