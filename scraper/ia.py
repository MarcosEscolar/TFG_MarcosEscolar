"""
ia.py — Llamadas a Gemini (Google) para enriquecer cada noticia.
Por cada artículo genera:
  - titulo_es:       título traducido al español (si ya está en ES, lo deja igual)
  - resumen_es:      resumen en español de 2-3 frases
  - analisis_es:     análisis geopolítico en español
  - tema:            tema geopolítico principal (una o dos palabras)
  - terminos_nuevos: lista de términos que deberían estar en el glosario y aún no están,
                     cada uno con nombre y definición
"""
import json
import os
import time
import google.generativeai as genai

_model = None

def get_model():
    global _model
    if _model is None:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise RuntimeError('Falta GEMINI_API_KEY en el .env del scraper')
        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel('gemini-2.5-flash')
    return _model


def enriquecer_articulo(articulo, terminos_existentes):
    titulo      = articulo['titulo']
    resumen_raw = articulo.get('resumen_raw', '')
    contenido   = articulo.get('contenido', '')
    idioma      = articulo.get('idioma', 'ES')
    existentes_str = ', '.join(terminos_existentes) if terminos_existentes else 'ninguno'

    tiene_contenido = bool(contenido and len(contenido) > 200)
    texto_fuente = contenido[:3000] if tiene_contenido else resumen_raw

    instruccion_analisis = (
        'análisis geopolítico en español de 4-6 párrafos basado en el artículo completo. '
        'Explica el contexto, los actores implicados y las implicaciones geopolíticas.'
        if tiene_contenido else
        'resumen en español de 3-4 frases explicando la noticia y su relevancia geopolítica.'
    )

    prompt = f"""Eres un analista especializado en geopolítica. Analiza la siguiente noticia y responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional.

NOTICIA:
Título: {titulo}
Contenido: {texto_fuente}
Idioma original: {idioma}

TÉRMINOS YA EN EL GLOSARIO (no los repitas): {existentes_str}

Responde con este JSON exacto:
{{
    "titulo_es": "título traducido al español (si ya está en español, cópialo igual)",
    "resumen_es": "resumen en español de 2-3 frases, para la tarjeta de la noticia",
    "analisis_es": "{instruccion_analisis}",
    "tema": ["tema_principal"] o ["tema_principal", "tema_secundario"] — array con 1 o 2 valores de esta lista exacta: Oriente Medio, Europa, Rusia-Ucrania, Estados Unidos, China, Asia-Pacífico, América Latina, África, Diplomacia, Seguridad, Economía Global, Energía, Derechos Humanos, Tecnología, Medio Ambiente, Política,
    "terminos_nuevos": [
    {{
        "nombre": "Nombre del término",
        "definicion": "Definición clara en español de 1-2 frases",
        "categoria": "una de estas categorías exactas: Geopolítica, Seguridad, Economía, Derecho Internacional, Diplomacia, Organizaciones Internacionales, Política, Tecnología, Medio Ambiente, Cultura y Sociedad"
    }}
    ]
}}

REGLAS:
- El campo "tema" DEBE ser un array JSON con 1 valor, o excepcionalmente 2 si la noticia cubre dos ámbitos claramente distintos. Nunca más de 2. Usa solo valores de la lista, sin variaciones
- El campo "categoria" de cada término DEBE ser exactamente uno de los valores de la lista
- terminos_nuevos solo debe incluir términos geopolíticos relevantes que NO estén ya en el glosario
- Si no hay términos nuevos relevantes, pon terminos_nuevos como array vacío []
- Los terminos nuevos deben de ser prioritariamente sobre siglas, nombres propios o demas palabras tecnicas; se pueden añadir al glosario breves descripciones de personas si es poco conocido para el publico general y relevante en la noticia, pero no deben ser el foco principal de los terminos nuevos
- Máximo 3 términos nuevos por noticia
- El JSON debe ser válido y no contener nada fuera de las llaves

REGLAS DE FORMATO DE TEXTO (MUY IMPORTANTE):
- TODOS los campos de texto (titulo_es, resumen_es, analisis_es, definicion) deben ser TEXTO PLANO en español natural.
- PROHIBIDO incluir: etiquetas HTML (<span>, <a>, <p>, <br>, etc.), atributos (class, data-*, href, style), markdown (**, *, _, #, [, ], `), comillas tipográficas («», "", ''), emojis o caracteres < y > de cualquier tipo.
- PROHIBIDO inventar tooltips, enlaces o resaltados — el frontend ya enlaza los términos del glosario automáticamente; tú solo escribe prosa limpia.
- Usa concordancia de género correcta en español (ej. "la soberanía", no "el soberanía"; "el derecho internacional", no "la derecho internacional").
- Si necesitas citar literalmente algo, usa comillas dobles rectas: " ... "."""

    REINTENTOS   = 3
    ESPERA_BASE  = 10   # segundos entre reintentos (rate limit o error transitorio)

    for intento in range(1, REINTENTOS + 1):
        try:
            model    = get_model()
            response = model.generate_content(prompt)
            texto    = response.text.strip()

            # Limpiar bloque ```json ... ``` si Gemini lo incluye
            if texto.startswith('```'):
                texto = texto.split('```')[1]
                if texto.startswith('json'):
                    texto = texto[4:]
                texto = texto.strip()

            # A veces Gemini añade texto antes o después del JSON; extraer solo {}
            inicio = texto.find('{')
            fin    = texto.rfind('}')
            if inicio != -1 and fin != -1:
                texto = texto[inicio:fin + 1]

            resultado = json.loads(texto)

            analisis = resultado.get('analisis_es', '')
            if not analisis:
                analisis = contenido if tiene_contenido else ''

            # tema puede llegar como array ["x"] o ["x","y"], o como string legacy "x"
            tema_raw = resultado.get('tema', [])
            if isinstance(tema_raw, str):
                tema_raw = [tema_raw] if tema_raw else []
            tema_raw = [t.strip() for t in tema_raw if isinstance(t, str) and t.strip()][:2]

            return {
                'titulo_es':       resultado.get('titulo_es', titulo),
                'resumen_es':      resultado.get('resumen_es', ''),
                'analisis_es':     analisis,
                'tema':            tema_raw,
                'terminos_nuevos': resultado.get('terminos_nuevos', []),
            }

        except json.JSONDecodeError as e:
            print(f'  [IA] Intento {intento}/{REINTENTOS} — JSON inválido para "{titulo[:50]}": {e}')
            if intento < REINTENTOS:
                time.sleep(ESPERA_BASE)

        except Exception as e:
            msg = str(e).lower()
            # Rate limit o error de cuota: esperar más antes de reintentar
            espera = ESPERA_BASE * 2 if ('quota' in msg or 'rate' in msg or '429' in msg) else ESPERA_BASE
            print(f'  [IA] Intento {intento}/{REINTENTOS} — Error para "{titulo[:50]}": {e}')
            if intento < REINTENTOS:
                print(f'  [IA] Esperando {espera}s antes de reintentar…')
                time.sleep(espera)

    # Fallback: los 3 intentos fallaron
    print(f'  [IA] Fallback sin traducción para "{titulo[:50]}"')
    return {
        'titulo_es':       titulo,
        'resumen_es':      resumen_raw[:300] if resumen_raw else '',
        'analisis_es':     contenido if tiene_contenido else '',
        'tema':            [],
        'terminos_nuevos': [],
    }
