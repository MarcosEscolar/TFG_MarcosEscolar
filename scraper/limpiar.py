"""
limpiar.py — Mantenimiento puntual de la base de datos.

Recorre las tablas Noticias y Glosario detectando filas con HTML residual,
entidades sin decodificar o comillas tipográficas, y las reescribe limpias
usando la misma función `limpiar_texto` que utiliza el scraper en cada inserción.

Por defecto se ejecuta en modo dry-run: muestra los cambios sin tocar nada.
Para aplicar los cambios pásale el flag --aplicar.

Uso:
  python limpiar.py             # Dry-run, sólo informa
  python limpiar.py --aplicar   # Aplica los cambios en Supabase
  python limpiar.py --solo noticias --aplicar   # Limita a una tabla
  python limpiar.py --solo glosario
"""
import argparse
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Carga el .env del scraper
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Reusamos la misma sanitización que usa guardar.py para que el criterio sea
# el mismo en inserción y en limpieza retroactiva.
from guardar import limpiar_texto


def get_db():
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    if not url or not key:
        print('[ERROR] Faltan SUPABASE_URL o SUPABASE_SERVICE_KEY en scraper/.env')
        sys.exit(1)
    return create_client(url, key)


def _diff_breve(antes, despues, max_len=80):
    """Devuelve una versión recortada antes→después para imprimir en consola."""
    a = (antes or '').replace('\n', ' ')[:max_len]
    d = (despues or '').replace('\n', ' ')[:max_len]
    return f'    antes:    {a}{"…" if len(antes or "") > max_len else ""}\n    despues:  {d}{"…" if len(despues or "") > max_len else ""}'


def limpiar_tabla(db, tabla, campos, aplicar):
    """
    Limpia los `campos` de cada fila de `tabla`.
    Devuelve (filas_revisadas, filas_modificadas).
    """
    print(f'\n[{tabla}] Cargando filas…')
    select_str = ', '.join(['id'] + list(campos))
    try:
        result = db.table(tabla).select(select_str).execute()
    except Exception as e:
        print(f'[ERROR] No se pudo leer {tabla}: {e}')
        return 0, 0

    filas = result.data or []
    print(f'[{tabla}] {len(filas)} filas encontradas')

    modificadas = 0
    for fila in filas:
        cambios = {}
        for campo in campos:
            original = fila.get(campo) or ''
            limpio   = limpiar_texto(original)
            if limpio != original:
                cambios[campo] = limpio

        if not cambios:
            continue

        modificadas += 1
        print(f'\n  [{fila["id"]}] cambios en: {", ".join(cambios.keys())}')
        for campo, nuevo in cambios.items():
            print(f'  · {campo}')
            print(_diff_breve(fila.get(campo) or '', nuevo))

        if aplicar:
            try:
                db.table(tabla).update(cambios).eq('id', fila['id']).execute()
            except Exception as e:
                print(f'  [ERROR] No se pudo actualizar id={fila["id"]}: {e}')

    print(f'\n[{tabla}] {modificadas}/{len(filas)} filas con cambios'
          f'{"" if aplicar else "  (dry-run, no se ha guardado nada)"}')
    return len(filas), modificadas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aplicar', action='store_true',
                        help='Aplica los cambios. Sin este flag solo muestra qué cambiaría.')
    parser.add_argument('--solo', choices=['noticias', 'glosario'],
                        help='Limita la limpieza a una sola tabla.')
    args = parser.parse_args()

    print('=' * 60)
    print('  GEOSFERA — Limpieza retroactiva')
    print('  Modo:', 'APLICAR cambios' if args.aplicar else 'DRY-RUN (no toca nada)')
    print('=' * 60)

    db = get_db()
    print('[DB] Conectado a Supabase')

    if args.solo in (None, 'noticias'):
        limpiar_tabla(
            db, 'Noticias',
            campos=['titulo', 'resumen_es', 'contenido', 'tema'],
            aplicar=args.aplicar,
        )

    if args.solo in (None, 'glosario'):
        limpiar_tabla(
            db, 'Glosario',
            campos=['nombre', 'definicion', 'categoria'],
            aplicar=args.aplicar,
        )

    print('\nFin.')
    if not args.aplicar:
        print('Para aplicar los cambios reales:  python limpiar.py --aplicar')


if __name__ == '__main__':
    main()
