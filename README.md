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

**`routes/noticias.py`** — CRUD completo de la tabla `Noticias`: listar con filtros (tema, fuente, búsqueda), obtener por ID, crear, editar y eliminar. Incluye el endpoint `GET /api/noticias/<id>/relacionadas` que devuelve hasta 4 noticias afines ordenadas por relevancia (ver sección *Noticias relacionadas*).

**`routes/glosario.py`** — CRUD completo de la tabla `Glosario`: listar términos, crear, editar y eliminar.

**`routes/fuentes.py`** — CRUD completo de la tabla `Fuentes`: listar fuentes RSS activas e inactivas, crear, editar y eliminar.

**`routes/favoritos.py`** — Gestión de noticias guardadas del usuario: listar IDs, listar objetos completos, guardar y eliminar. Todos los endpoints usan `@require_login`.

**`routes/scraper.py`** — Endpoints de solo lectura para el dashboard: estado en tiempo real del scraper, historial de ejecuciones y estadísticas globales. Todos usan `@require_admin`.

---

## Flujo del scraper

El scraper se ejecuta automáticamente cada 6 horas mediante **GitHub Actions**. Obtiene noticias de los feeds RSS, extrae el texto completo de cada artículo, lo enriquece con IA y lo guarda en Supabase.

```
GitHub Actions (cada dia)
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

**`guardar.py`** — Inserta las noticias enriquecidas en la tabla `Noticias` y añade al `Glosario` los términos nuevos detectados por la IA que aún no estuvieran registrados. Antes de cada `insert` aplica la función `limpiar_texto()` a todos los campos de texto, garantizando que no entre HTML residual en la base de datos.

**`limpiar.py`** — Script de mantenimiento puntual. Recorre las filas existentes en `Noticias` y `Glosario` y reescribe limpias las que tengan HTML residual, entidades sin decodificar o comillas tipográficas. Por defecto ejecuta un dry-run; con el flag `--aplicar` guarda los cambios. Permite limitar la limpieza a una tabla con `--solo noticias` o `--solo glosario`.

---

## Noticias relacionadas

Al abrir el panel de detalle de una noticia, el frontend solicita en paralelo el endpoint `GET /api/noticias/<id>/relacionadas`. El backend recupera los temas y términos de la noticia actual y lanza dos consultas a Supabase: una filtrando por solapamiento de `tema` y otra por solapamiento de `terminos`, ambas limitadas a 30 resultados. Los candidatos se fusionan en Python eliminando duplicados y se puntúan según el número de coincidencias compartidas, dando más peso a los temas (`temas × 2 + términos × 1`). Se devuelven las 4 noticias con mayor puntuación, que el frontend muestra como tarjetas clicables al pie del artículo. Al pulsar una tarjeta relacionada se abre esa noticia en el mismo panel, permitiendo navegar entre artículos afines sin volver al listado principal.

---

## Sistema de favoritos

Cualquier usuario autenticado puede marcar noticias con el icono de marcador de cada tarjeta y consultarlas después en `/guardados`. El icono alterna entre contorno vacío y relleno sólido según el estado. `guardados.html` carga primero el glosario y luego los favoritos; al quitar uno, la tarjeta desaparece con animación y el contador se actualiza en tiempo real. En `index.html` glosario y favoritos se cargan en paralelo con `Promise.all` para evitar la race condition que impedía que los tooltips funcionasen al abrir el detalle inmediatamente tras cargar la página.

---

## Dashboard de monitorización

El dashboard (`scraper.html`) está reservado exclusivamente para administradores: si el rol del usuario en sesión no es `admin`, el frontend redirige a `/inicio`. Toda la información se carga con una única petición a `GET /api/scraper/stats`, que devuelve en un solo JSON los totales globales, las distribuciones temáticas, el historial de los últimos 30 runs y el detalle de fuentes del último run completado.

Las cuatro visualizaciones de Chart.js 4 son:
- **Donut de temas** — distribución de los 14 temas geopolíticos en toda la base de datos.
- **Donut de categorías del glosario** — peso relativo de cada categoría de términos.
- **Barras horizontales** — número de noticias por idioma original.
- **Línea temporal** — noticias guardadas por ejecución en los últimos 30 runs.

El estado en tiempo real se obtiene de `GET /api/scraper/estado`, que consulta si existe algún run con `estado = 'en_curso'` en la tabla `ScraperRuns`. El dashboard sondea este endpoint cada 30 segundos y muestra un punto verde pulsante cuando el scraper está activo. Un selector desplegable permite cambiar el run mostrado en la tabla de fuentes y en el donut de aportación por fuente sin recargar el resto de la página.

---

## Seguridad

### Gestión de credenciales y secretos

Ninguna credencial real aparece en el código fuente. Todas las claves se leen exclusivamente de variables de entorno (`.env` en local, panel de variables de Render en producción). Si alguna variable crítica no está definida, el servidor rechaza arrancar con un error explícito en lugar de continuar con un valor inseguro por defecto. Los archivos `.env` están incluidos en `.gitignore` y nunca se suben al repositorio. La clave de la API de Gemini solo existe en GitHub Secrets y el propio archivo `.env.example` del scraper no contiene ningún valor real, solo los nombres de las variables.

### Autenticación y sesiones

Las contraseñas se almacenan en la base de datos siempre como hash bcrypt con salt aleatorio. Nunca se guarda ni se transmite la contraseña en texto plano. La autenticación usa sesiones de servidor firmadas criptográficamente con la `SECRET_KEY` de Flask. Las cookies de sesión tienen tres flags de protección activos en producción:

- `HttpOnly` — JavaScript no puede leer la cookie, lo que impide el robo de sesión mediante XSS.
- `SameSite=Lax` — la cookie no se envía en peticiones originadas desde otras webs, bloqueando ataques CSRF.
- `Secure=True` — la cookie solo viaja por HTTPS, nunca en claro.

### Control de acceso

Todas las rutas de escritura del backend (crear, editar, eliminar noticias, fuentes, términos y usuarios) están protegidas con el decorador `@require_admin`, que verifica tanto que haya sesión activa como que el rol sea `admin`. Las rutas que requieren sesión pero no admin usan `@require_login`. Los errores de autenticación devuelven `401` y los de autorización `403`, distinguiendo correctamente los dos casos. Los endpoints de lectura pública como `/api/noticias/` no exponen datos de usuarios ni información interna del sistema.

### Validación de entradas

El registro de usuarios valida el formato del email con un regex antes de consultar la base de datos, y exige una contraseña de al menos 8 caracteres. En el scraper, todos los campos de texto que llegan de feeds RSS o de la IA pasan por `limpiar_texto()` antes de insertarse en Supabase: decodifica entidades HTML (`&amp;`, `&lt;`…), elimina etiquetas completas y truncadas, normaliza comillas tipográficas y elimina espacios múltiples. Esto garantiza que no entre HTML residual ni marcado generado por el modelo en la base de datos, lo cual evitaría que el frontend renderizara contenido no controlado.

### Protección contra inyección

El acceso a la base de datos se hace exclusivamente a través del cliente oficial de Supabase, que usa la API de PostgREST. No se construyen queries SQL en texto plano ni se concatenan parámetros de usuario en ninguna consulta, eliminando el riesgo de inyección SQL. La búsqueda de texto libre en noticias y glosario sanitiza los caracteres especiales de PostgREST (comas, paréntesis) antes de incluirlos en el filtro `or_()`.

### Inyección desde la IA

El prompt enviado a Gemini prohíbe explícitamente que el modelo devuelva HTML, markdown o etiquetas de ningún tipo. Además, `limpiar_texto()` actúa como segundo filtro antes de cualquier `insert`, de forma que aunque el modelo ignore la instrucción, el HTML generado se elimina antes de llegar a la base de datos.

### CORS y superficie de ataque

El backend restringe CORS a los orígenes conocidos (`localhost:5000`, `localhost:5500`). En producción el frontend y el backend comparten el mismo origen en Render, por lo que CORS no interviene y la superficie de ataque es mínima. No existen endpoints de administración accesibles públicamente sin autenticación.

### Operaciones de escritura en Supabase

Las operaciones de eliminación y modificación en Supabase (que pueden estar protegidas por RLS) se realizan con la `SUPABASE_SERVICE_KEY` (clave de servicio), que tiene permisos completos y nunca se expone al frontend. El cliente del frontend usa únicamente la clave anon, cuyo alcance está limitado por las políticas RLS de la base de datos.

---


