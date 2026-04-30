"""
guardar.py — Guarda noticias y términos de glosario en Supabase.
Evita duplicados comprobando la URL antes de insertar cada noticia.
Sanea todos los campos de texto antes de insertar para que NUNCA entre HTML
ni marcado en la base de datos (ver limpiar_texto).
"""
import html
import re

# ── Sanitizado de texto ────────────────────────────────────────────────────────
# Cualquier dato proveniente de la IA o de un feed RSS se pasa por aquí antes
# de meterlo en Supabase. Garantiza que el frontend reciba SIEMPRE texto plano,
# evitando el desalineamiento entre término visible y tooltip cuando el modelo
# decide fabricar etiquetas <span class="term-link" ...> por su cuenta.

_TAG_RE      = re.compile(r'<[^>]*>')         # cualquier <tag ...>
_TAG_RESTO   = re.compile(r'</?[A-Za-z][^\s>]*$')  # tag truncado al final
_WHITESPACE  = re.compile(r'\s+')

def limpiar_texto(texto):
    """Devuelve el texto sin etiquetas HTML, sin entidades y con espacios normalizados."""
    if not texto:
        return ''
    if not isinstance(texto, str):
        texto = str(texto)
    # 1) Decodificar entidades (&amp;, &lt;, &nbsp;…) para que las tags ocultas
    #    bajo entidades también caigan en el siguiente paso.
    texto = html.unescape(texto)
    # 2) Quitar etiquetas HTML completas
    texto = _TAG_RE.sub('', texto)
    # 3) Quitar restos de tags truncados al final ("<span class=" sin cierre)
    texto = _TAG_RESTO.sub('', texto)
    # 4) Normalizar comillas tipográficas y espacios múltiples
    texto = (texto
             .replace('“', '"').replace('”', '"')
             .replace('‘', "'").replace('’', "'")
             .replace('«', '"').replace('»', '"'))
    texto = _WHITESPACE.sub(' ', texto).strip()
    return texto


def obtener_urls_existentes(db):
    """Devuelve un set con todas las URLs ya guardadas en la tabla Noticias."""
    try:
        result = db.table('Noticias').select('url').execute()
        return {row['url'] for row in (result.data or [])}
    except Exception as e:
        print(f'  [ERROR] No se pudieron cargar URLs existentes: {e}')
        return set()


def obtener_nombres_glosario(db):
    """Devuelve una lista con los nombres de todos los términos del glosario (en minúsculas)."""
    try:
        result = db.table('Glosario').select('nombre').execute()
        return [row['nombre'].lower() for row in (result.data or [])]
    except Exception as e:
        print(f'  [ERROR] No se pudieron cargar términos del glosario: {e}')
        return []


def guardar_noticia(db, noticia):
    """
    Inserta una noticia en la tabla Noticias.
    Devuelve True si se guardó correctamente, False si hubo error.
    """
    try:
        # Saneamos cada campo de texto antes de insertarlo. Aunque el prompt
        # prohíbe HTML al modelo, esto es el último filtro que garantiza que
        # nunca entren tags ni residuos a la base de datos.
        nueva = {
            'titulo':      limpiar_texto(noticia['titulo_es']),
            'resumen_es':  limpiar_texto(noticia['resumen_es']),
            'contenido':   limpiar_texto(noticia.get('analisis_es', '')),
            'url':         noticia['url'],
            'fuente':      noticia['fuente'],
            'idioma':      noticia['idioma'],
            'tema':        limpiar_texto(noticia['tema']),
            'terminos':    [],
        }
        result = db.table('Noticias').insert(nueva).execute()
        return bool(result.data)
    except Exception as e:
        print(f'  [ERROR] Al guardar noticia "{noticia["titulo_es"][:50]}": {e}')
        return False


def guardar_termino_glosario(db, termino):
    """
    Inserta un nuevo término en la tabla Glosario.
    Devuelve True si se guardó correctamente.
    """
    try:
        nuevo = {
            'nombre':      limpiar_texto(termino['nombre']),
            'definicion':  limpiar_texto(termino['definicion']),
            'categoria':   limpiar_texto(termino.get('categoria', 'Geopolítica')),
            'relacionados': [],
            'emoji':       '',
        }
        # Si el sanitizador deja un nombre vacío, descartamos el término
        if not nuevo['nombre'] or not nuevo['definicion']:
            return False
        result = db.table('Glosario').insert(nuevo).execute()
        return bool(result.data)
    except Exception as e:
        print(f'  [ERROR] Al guardar término "{termino["nombre"]}": {e}')
        return False


def guardar_resultados(db, articulos_enriquecidos, urls_existentes, nombres_glosario):
    """
    Itera los artículos enriquecidos:
    - Inserta en Noticias los que no existan ya por URL
    - Inserta en Glosario los términos nuevos sugeridos por la IA
    Devuelve estadísticas del proceso.
    """
    noticias_guardadas  = 0
    noticias_duplicadas = 0
    terminos_guardados  = 0

    # Copia mutable para no repetir términos dentro de la misma ejecución
    nombres_vistos = set(nombres_glosario)

    for art in articulos_enriquecidos:
        # ── Noticia ──────────────────────────────────────────────────────
        if art['url'] in urls_existentes:
            noticias_duplicadas += 1
            continue

        ok = guardar_noticia(db, art)
        if ok:
            noticias_guardadas += 1
            urls_existentes.add(art['url'])

        # ── Términos del glosario ─────────────────────────────────────────
        for termino in art.get('terminos_nuevos', []):
            nombre_lower = termino['nombre'].lower()
            if nombre_lower in nombres_vistos:
                continue
            ok_t = guardar_termino_glosario(db, termino)
            if ok_t:
                terminos_guardados += 1
                nombres_vistos.add(nombre_lower)
                print(f'  [GLOSARIO] Término añadido: {termino["nombre"]}')

    return {
        'noticias_guardadas':  noticias_guardadas,
        'noticias_duplicadas': noticias_duplicadas,
        'terminos_guardados':  terminos_guardados,
    }
