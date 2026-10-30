# Cartografía y biblioteca

- Leaflet 1.9.4: https://leafletjs.com/ · licencia BSD-2-Clause en `vendor/leaflet/LICENSE`.
  Distribución: https://unpkg.com/leaflet@1.9.4/dist/ . La interfaz usa marcadores vectoriales;
  no necesita los iconos raster predeterminados.
- Natural Earth v5.1.2, Admin 0 Countries, escala 1:110m: dominio público.
  Fuente: https://github.com/nvkelso/natural-earth-vector/tree/v5.1.2/geojson .
  Condiciones: https://www.naturalearthdata.com/about/terms-of-use/ .
  `scripts/prepare_map.py` conserva la geometría redondeada a tres decimales y solo los
  atributos necesarios. Esta reducción de detalle no es apta para ubicar instalaciones.
  Los límites son orientativos, pueden omitir territorios pequeños o reflejar disputas;
  no representan una posición política de SENTINEL.

La cartografía y Leaflet se sirven localmente; no se consultan servidores de teselas.
