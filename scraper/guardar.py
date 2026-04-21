"""
guardar.py — Guarda noticias y términos de glosario en Supabase.
Evita duplicados comprobando la URL antes de insertar cada noticia.
"""


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
        nueva = {
            'titulo':      noticia['titulo_es'],
            'resumen_es':  noticia['resumen_es'],
            'contenido':   noticia.get('analisis_es', ''),
            'url':         noticia['url'],
            'fuente':      noticia['fuente'],
            'idioma':      noticia['idioma'],
            'tema':        noticia['tema'],
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
            'nombre':      termino['nombre'],
            'definicion':  termino['definicion'],
            'categoria':   termino.get('categoria', 'Geopolítica'),
            'relacionados': [],
            'emoji':       '',
        }
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
