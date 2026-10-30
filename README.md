# SENTINEL v1.1

Monitor personal de fuentes abiertas para geopolítica, ciberseguridad, Internet e IA.
Sitio estático en https://rbrenesr.github.io/SENTINEL/ . Sin backend propio, base de datos,
claves API ni instalación para los visitantes.

## Funcionalidad

- Mapa mundial interactivo, oscuro y responsive, con Leaflet y cartografía local de Natural Earth.
- Vistas separadas de ubicaciones reportadas y países mencionados. Una mención no crea un marcador.
- Filtros compartidos por búsqueda, categoría, fuente, país, región y fecha; capas por categoría.
- Español como vista inicial y selector «Español / Todos los idiomas», aplicado a lista,
  mapa y cronología. Los totales de publicaciones y últimas 24 horas siguen el idioma;
  el estado de fuentes y los favoritos conservan sus totales globales.
- Cronología de publicaciones de los últimos 14 días y selección de un intervalo de fechas.
- Enlaces originales, favoritos locales compatibles con Lite y detalles de trazabilidad.
- Historial de hasta 1.000 registros vistos durante los últimos 30 días, con conservación ante fallos parciales.
- Estado y diagnóstico de cada fuente; indicador de antigüedad después de 90 minutos sin resultados nuevos.
- Sugerencias de relación por título normalizado coincidente dentro de 72 horas; nunca fusionan evidencia.

## Publicación y actualización automática

En **Settings → Pages → Build and deployment → Source**, seleccionar **GitHub Actions**.
El flujo `.github/workflows/update-news.yml` recopila, valida, conserva los datos en el
repositorio y despliega explícitamente un artefacto a Pages. No depende de que una
confirmación realizada por `GITHUB_TOKEN` dispare una segunda publicación.

- Cada 30 minutos, a los minutos 7 y 37, sujeto a disponibilidad de GitHub Actions.
- Manualmente con **Actions → Update public news feeds → Run workflow**.
- Al subir cambios de código a `main`; recopila noticias antes de desplegar.
  Cambios únicamente en documentación o en `news.json`
  no disparan el flujo de push.
- Los fallos de las pruebas impiden publicar. Las ejecuciones se serializan.
- Se publican únicamente `index.html`, `assets/` y `data/news.json`.

El flujo necesita `contents: write`, `pages: write`, `id-token: write` y el entorno
`github-pages` habilitado para `main`. Las restricciones de ramas o entornos de la cuenta
pueden exigir configuración adicional. Los retrasos y la suspensión por inactividad de
GitHub Actions impiden prometer actualización continua.

El navegador vuelve a consultar el JSON cada minuto mientras la página está visible.
**Revisar datos** consulta el contenido ya publicado; no ejecuta GitHub Actions.

## Recopilación

Python 3.12 o posterior, solo biblioteca estándar:

```sh
python scripts/fetch.py
python scripts/fetch.py --offline
python scripts/preview.py
```

La vista previa abre la misma ruta base que producción:
http://127.0.0.1:8765/SENTINEL/ . No abrir `index.html` con `file://`.
`--offline` recalcula clasificación y geografía sin consultar proveedores ni cambiar
las fechas de observación. No sustituye una recopilación exitosa.

Se consultan quince fuentes RSS/Atom con un máximo de cuatro conexiones simultáneas,
timeout de 18 segundos, límite de 8 MB por respuesta y hasta 35 registros por fuente.
El feed de CISA supera el antiguo límite de 2 MB; se conserva su endpoint oficial.
Las categorías se proponen por reglas de palabras clave sobre título y resumen;
son heurísticas auditables y pueden ser incompletas.

### Filtro de relevancia temática

Antes de publicar se aplica una admisión independiente de la clasificación antigua.
Requiere señales explícitas de geopolítica/conflictos, ciberseguridad, infraestructura
de Internet o IA en el título, o contexto temático suficiente en el resumen. Una fuente,
un país, una mención al gobierno o la palabra «internet» por sí solos no bastan.
Las noticias de deportes, celebridades, salud y estilo de vida se descartan cuando
constituyen el tema principal; incidentes cibernéticos y riesgos de IA relacionados
con esos ámbitos pueden seguir siendo relevantes.

El filtro también revisa el historial conservado, incluido `--offline`, para que las
noticias ajenas al alcance no reaparezcan tras un fallo de fuentes. Cada registro
admitido contiene `relevance`: versión de política, método, categoría, motivo y señales.
`scopeFilter` identifica la política aplicada al conjunto. No se usa la categoría
de la fuente como permiso de publicación ni se admite «Sin clasificar» automáticamente.
El diagnóstico de las consultas distingue publicaciones recibidas, admitidas y
descartadas (`receivedCount`, `count`, `excludedCount`). Un feed accesible con cero
publicaciones relevantes sigue siendo operativo.

Estas reglas no equivalen a una revisión editorial ni a verificación de hechos: pueden
omitir contenido pertinente y aceptar coincidencias imprecisas. Se mantienen pruebas
con ejemplos fuera de alcance y casos relevantes en español e inglés.

### Publicaciones originales en español

Se conservan las diez fuentes internacionales anteriores y se incorporan:

| Fuente | Feed público |
| --- | --- |
| BBC Mundo | https://feeds.bbci.co.uk/mundo/rss.xml |
| DW Español | https://rss.dw.com/rdf/rss-sp-all |
| INCIBE-CERT | https://www.incibe.es/incibe-cert/alerta-temprana/avisos/feed |
| Xataka IA | https://www.xataka.com/tag/inteligencia-artificial/rss2.xml |
| Xataka Internet | https://www.xataka.com/tag/internet/rss2.xml |

Cada publicación registra `language` y `languageMethod`. Se da prioridad al idioma
declarado por la entrada, después al del feed y finalmente a la configuración de la
edición o canal conocido. Los códigos regionales se normalizan (`es-CR` → `es`).
No se deduce el idioma por la ubicación geográfica de la noticia. Los registros sin
idioma identificado (`und`) solo aparecen al seleccionar todos los idiomas.
El catálogo de fuentes de los filtros corresponde al idioma elegido; «Limpiar» vuelve
a español. El contenido y los enlaces originales se mantienen, sin traducción automática.
La identificación por edición/canal es orientativa: una declaración de idioma específica
de la entrada prevalece sobre la del canal.

## Modelo y reglas geográficas

`data/news.json`, esquema 2:

- `updatedAt`: último intento que obtuvo publicaciones válidas; no se renueva si fallan todas las fuentes.
- `lastAttemptAt`: última consulta del conjunto de fuentes.
- `sources`: estado, error, URL, cantidad, último intento y último éxito por fuente.
- `items`: ID estable, URL original y normalizada, fuente, título, resumen, categoría,
  fecha de publicación, primera y última observación, tipo de contenido, verificación y geografía.
- `relatedGroups`: sugerencias de publicaciones relacionadas, sin considerarlas acontecimientos verificados.

La retención se mide desde `lastSeenAt`, no desde la publicación. Una noticia antigua que
el proveedor siga incluyendo puede permanecer. El límite total puede recortar registros
antes de los 30 días. Las fechas de publicación ausentes permanecen desconocidas.
El filtro de últimas horas excluye fechas futuras. Las fechas se almacenan en UTC y la
interfaz las muestra en la zona horaria del navegador.

`countries` solo contiene menciones detectadas por diccionario en el título/resumen,
sin inferir que un incidente ocurrió allí. Se prioriza el nombre más largo para evitar
menciones anidadas y se excluyen algunos nombres ambiguos. El diccionario no identifica
todos los países ni todas las expresiones; las menciones no demuestran afectación.

`locations` identifica relación (`occurrence`, `affected`, `related`) y precisión
(`exact`, `approximate`, `country`) por separado. Solo las dos primeras relaciones
entran en la vista de ubicaciones reportadas.

- Los puntos GeoRSS proceden del editor, se indican como aproximados y sin verificación independiente.
- Las anotaciones revisadas viven en `data/annotations.json`, por URL normalizada.
  Requieren lugar, relación, precisión y evidencia con URL, descripción y `reviewedAt`.
  Esta versión admite puntos documentados y ubicaciones a nivel de país.
- Una ubicación de país carece de coordenadas; se resalta su polígono. No se usa su capital ni un centroide como incidente.
- Las agrupaciones de puntos cercanos son visuales y se anclan en una coordenada reportada.
- La revisión de una ubicación no verifica las afirmaciones de la noticia.

Se incluyen tres publicaciones revisadas a nivel de país a partir de sus títulos y
resúmenes RSS, con cuatro relaciones geográficas. No se inventan posiciones exactas.
La incorporación de nuevas anotaciones debe revisar de nuevo el contenido y su procedencia.
Las noticias sin evidencia permanecen disponibles en la lista.

El acceso rápido **Costa Rica** filtra menciones y ubicaciones documentadas. No calcula
riesgo, predicciones ni impactos económicos o políticos automáticos.

## Cartografía y licencias

Leaflet 1.9.4 se distribuye localmente con su licencia BSD-2-Clause. Natural Earth v5.1.2
es de dominio público. `assets/THIRD_PARTY.md` documenta procedencia y transformaciones.
Para regenerar la geometría y el catálogo de países desde la versión fijada:

```sh
python scripts/prepare_map.py
```

La escala 1:110m es orientativa: puede omitir islas, mostrar límites disputados y no
sirve como evidencia de la ubicación de una instalación. No hay servidores de teselas,
CDN, geocodificación externa, servicios pagos ni claves en el navegador.

## Validación

```sh
python -m unittest discover -s tests -v
node --test tests/frontend.test.cjs
```

Cubren Atom/RSS, fechas, canonicalización, retención ante fallos, límite del feed de CISA,
IDs, evidencia geográfica, menciones anidadas, filtros, favoritos, fechas futuras y URLs inseguras.
La revisión visual debe comprobar mapa, filtros sincronizados, vistas móviles y navegación por teclado.

## Límites

SENTINEL conserva noticias de terceros y no verifica independientemente cada afirmación.
La frecuencia de publicaciones no equivale a riesgo o intensidad de un conflicto.
El sitio publicado es público. No agregar secretos o información privada.
Los favoritos solo existen en el navegador; el almacenamiento puede estar restringido.
Un fallo de red conserva los datos cargados durante la sesión, pero no hay modo sin conexión persistente.

No se scrapean artículos completos. La consulta pública de un RSS no concede derechos
de redistribución ilimitados; deben respetarse las condiciones del proveedor y los
enlaces originales. Fuentes OSINT adicionales, polígonos de acontecimientos, rutas,
deduplicación semántica y análisis documentado de implicaciones quedan para etapas posteriores.
