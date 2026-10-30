# SENTINEL Lite

Monitor web estático de noticias globales. Sin servidor propio, base de datos ni claves API.

## Publicar en GitHub Pages

1. Crear un repositorio **público** nuevo en GitHub (por ejemplo, `sentinel-lite`).
2. Subir **el contenido de esta carpeta** a la raíz del repositorio, incluida `.github/workflows/update-news.yml`.
3. En **Settings → Pages**, seleccionar **Deploy from a branch**, rama `main` y carpeta `/ (root)`; guardar.
4. En **Actions**, habilitar workflows si GitHub lo solicita. Abrir **Update public news feeds** y elegir **Run workflow** para la primera recopilación.
5. Esperar la ejecución y la publicación de Pages. La URL normalmente será `https://USUARIO.github.io/sentinel-lite/`.
6. En **Settings → Actions → General → Workflow permissions**, verificar que los workflows tengan permiso de lectura/escritura del repositorio. En repositorios nuevos puede ser necesario habilitarlo para que el JSON se actualice.

## Funcionamiento

- `index.html` es la aplicación, sin dependencias externas.
- `scripts/fetch.py` consulta fuentes RSS públicas con Python estándar.
- `.github/workflows/update-news.yml` intenta ejecutar la recopilación cada 30 minutos y confirma `data/news.json` en el repositorio.
- El navegador consulta ese JSON cada minuto y guarda favoritos en LocalStorage.
- Si un proveedor cambia su RSS o bloquea consultas, aparecerá como `Error` o `Vacía` en el panel de fuentes.

## Privacidad y límites

GitHub Pages **no protege** esta página mediante autenticación, aunque el repositorio sea privado. No agregar secretos. La aplicación es de uso personal, pero su URL puede ser accesible por terceros. Las noticias dependen de la disponibilidad de los RSS. No se promete cobertura exhaustiva, ni actualización instantánea, ni verificación automática. Las acciones programadas de GitHub pueden retrasarse o suspenderse por inactividad.

## Prueba local (opcional)

`python scripts/fetch.py` para actualizar las noticias. Luego abrir `index.html` mediante un servidor estático local; abrirlo directamente con `file://` puede impedir la lectura del JSON.
