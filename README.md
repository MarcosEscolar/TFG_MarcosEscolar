# GEOSFERA — Portal de noticias geopolíticas

Aplicación web de análisis geopolítico con scraper automático de noticias, enriquecimiento por IA y glosario interactivo.

---

## Flujo del backend

El backend es una API REST construida con **Flask** que gestiona la autenticación, los datos y sirve el frontend estático.

```
Petición HTTP
     │
     ▼
  app.py  ──→  routes/  ──→  database.py  ──→  Supabase
               (CRUD)         (conexión)
     │
     ▼
  auth.py
  (sesiones)
```

### Archivos

**`app.py`** — Punto de entrada. Arranca el servidor Flask, registra todos los blueprints de rutas y sirve los archivos estáticos del frontend.

**`config.py`** — Carga las variables de entorno del `.env` (URL de Supabase, claves, puerto, modo debug).

**`database.py`** — Gestiona la conexión singleton con Supabase. Cualquier ruta que necesite acceder a la base de datos llama a `get_db()` desde aquí.

**`auth.py`** — Maneja el registro, login y logout de usuarios mediante sesiones de Flask. Expone también el decorador `@require_admin` que protege los endpoints de administración.

**`routes/noticias.py`** — CRUD completo de la tabla `Noticias`: listar con filtros (tema, fuente, búsqueda), obtener por ID, crear, editar y eliminar.

**`routes/glosario.py`** — CRUD completo de la tabla `Glosario`: listar términos, crear, editar y eliminar.

**`routes/fuentes.py`** — CRUD completo de la tabla `Fuentes`: listar fuentes RSS activas e inactivas, crear, editar y eliminar.

---

## Flujo del scraper

El scraper se ejecuta automáticamente cada 6 horas mediante **GitHub Actions**. Obtiene noticias de los feeds RSS, extrae el texto completo de cada artículo, lo enriquece con IA y lo guarda en Supabase.

```
GitHub Actions (cada 6h)
        │
        ▼
     main.py
        │
        ├──→ feeds.py ──→ RSS feeds ──→ trafilatura (texto completo)
        │
        ├──→ ia.py ──→ Gemini API
        │         (traducción, resumen, análisis, tema, términos)
        │
        └──→ guardar.py ──→ Supabase
                        (Noticias + Glosario)
```

### Archivos

**`main.py`** — Orquestador principal. Conecta con Supabase, llama a los feeds, filtra duplicados por URL, envía cada artículo nuevo a la IA y guarda los resultados.

**`feeds.py`** — Lee las fuentes activas de la tabla `Fuentes`, parsea cada feed RSS con `feedparser` e intenta extraer el texto completo del artículo con `trafilatura`. Si el sitio bloquea el scraping, usa el resumen del RSS como fallback.

**`ia.py`** — Llama a la API de Gemini para enriquecer cada artículo. Por cada noticia genera: título traducido al español, resumen breve, análisis geopolítico, tema principal (de una lista fija) y términos nuevos para el glosario.

**`guardar.py`** — Inserta las noticias enriquecidas en la tabla `Noticias` y añade al `Glosario` los términos nuevos detectados por la IA que aún no estuvieran registrados.
