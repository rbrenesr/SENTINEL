'use strict';
(() => {
  const C = window.SentinelCore;
  const $ = id => document.getElementById(id);
  const make = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const fmt = value => value && Number.isFinite(new Date(value).getTime()) ?
    new Intl.DateTimeFormat('es-CR', {dateStyle: 'medium', timeStyle: 'short'}).format(new Date(value)) : 'No disponible';
  const link = (text, url) => {
    const node = make('a', '', text);
    node.href = C.safeURL(url) || '#';
    node.target = '_blank'; node.rel = 'noopener noreferrer';
    return node;
  };
  let data = null, countries = [], world = null, map = null, countryLayer = null, markerLayer = null;
  let limit = 25, favoritesOnly = false, loading = false, loadError = false, mapFitted = false;
  const enabledLayers = new Set(C.categories);
  let saved = new Set();
  function storageWarning(text) { $('storageWarning').textContent = text; $('storageWarning').hidden = false; }
  try {
    const stored = JSON.parse(localStorage.getItem('sentinel-favorites') || '[]');
    if (!Array.isArray(stored)) throw Error('Favoritos inválidos');
    saved = new Set(stored.filter(value => typeof value === 'string' && C.safeURL(value)).map(C.canonicalURL));
  } catch { storageWarning('No se pudieron recuperar los favoritos locales. Podés seguir usando SENTINEL y guardar nuevos favoritos.'); }

  function filters(extra = {}) {
    const region = $('region').value;
    return {query: $('search').value, language: $('language').value, category: $('category').value, source: $('source').value,
      country: $('country').value, geoMode: $('geoMode').value, hours: Number($('period').value) || null,
      start: $('startDate').value, end: $('endDate').value, locatedOnly: $('locatedOnly').checked,
      favoritesOnly, saved, regionCodes: region ? new Set(countries.filter(x => x.region === region).map(x => x.code)) : null, ...extra};
  }
  function filtered(extra = {}) { return C.filterArticles(data?.items || [], filters(extra)).filter(item => enabledLayers.has(item.category)); }
  function save(item) {
    if (C.isSaved(item, saved)) {
      for (const url of [...saved]) if (C.canonicalURL(url) === C.canonicalURL(item.url)) saved.delete(url);
    } else saved.add(item.canonicalUrl || C.canonicalURL(item.url));
    try { localStorage.setItem('sentinel-favorites', JSON.stringify([...saved])); }
    catch { storageWarning('El navegador no permite guardar favoritos. Los cambios durarán solo durante esta sesión.'); }
    render();
  }
  function populateOptions() {
    const selectedSource = $('source').value, selectedCountry = $('country').value;
    $('source').replaceChildren(new Option('Todas las fuentes', ''));
    const languageItems = C.filterArticles(data.items, {language: $('language').value});
    for (const source of [...new Set(languageItems.map(item => item.source))].sort()) $('source').add(new Option(source, source));
    if ([...$('source').options].some(x => x.value === selectedSource)) $('source').value = selectedSource;
    $('country').replaceChildren(new Option('Todos los países', ''));
    for (const country of [...countries].sort((a, b) => a.name.localeCompare(b.name, 'es'))) $('country').add(new Option(country.name, country.code));
    if ([...$('country').options].some(x => x.value === selectedCountry)) $('country').value = selectedCountry;
  }
  function updateConnection() {
    if (!data) return;
    const success = new Date(data.updatedAt).getTime();
    const stale = !Number.isFinite(success) || Date.now() - success > 90 * 60000;
    const degraded = data.sources.some(source => source.status !== 'ok');
    const text = loadError ? 'Error al revisar · mostrando datos anteriores' : stale ? 'Datos antiguos · revisá la recopilación' :
      degraded ? 'Datos disponibles · cobertura parcial' : 'Datos disponibles';
    $('connection').textContent = text;
    $('connection').classList.toggle('warning', stale || degraded || loadError);
  }
  function sourcePanels() {
    $('sources').replaceChildren();
    for (const source of data.sources) {
      const row = make('div', 'source'), title = make('div', 'source-title');
      title.append(make('span', '', source.name), make('span', source.status === 'ok' ? 'ok' : 'bad',
        source.status === 'ok' ? `${source.count} notas` : source.status === 'empty' ? 'Vacía' : 'Error'));
      row.append(title);
      const details = make('details'), summary = make('summary', '', 'Detalle de la consulta');
      details.append(summary, make('p', '', `Último éxito: ${fmt(source.lastSuccessAt || (source.status === 'ok' ? data.updatedAt : null))}`));
      details.append(make('p', '', `Idioma: ${languageLabel(source.language)}.`));
      if (Number.isInteger(source.receivedCount)) details.append(make('p', '', `${source.receivedCount} publicaciones recibidas; ${source.excludedCount || 0} descartadas por relevancia temática.`));
      if (source.lastAttemptAt) details.append(make('p', '', `Intento: ${fmt(source.lastAttemptAt)}`));
      if (source.error) details.append(make('p', '', source.error));
      if (source.url) details.append(link('Consultar feed ↗', source.url));
      row.append(details); $('sources').append(row);
    }
    $('updated').textContent = `Última recopilación con resultados: ${fmt(data.updatedAt)}`;
    $('lastAttempt').textContent = data.lastAttemptAt ? `Último intento: ${fmt(data.lastAttemptAt)}` : '';
  }
  function card(item) {
    const node = make('article', 'article');
    node.style.setProperty('--item-color', C.colors[item.category] || C.colors['Sin clasificar']);
    const meta = make('div', 'meta');
    meta.append(make('span', 'pill', item.category), make('span', '', item.source), make('span', '', languageLabel(item.language)), make('span', '', fmt(item.published)));
    const title = make('h3'); title.append(link(item.title, item.url));
    if (/^[a-z]{2,3}$/.test(item.language || '') && item.language !== 'und') { title.lang = item.language; }
    node.append(meta, title);
    if (item.summary) { const summary = make('p', '', item.summary); summary.lang = title.lang; node.append(summary); }
    const locs = C.locations(item);
    if (!locs.length) node.append(make('span', 'geo-tag', 'Sin ubicación de acontecimiento'));
    for (const loc of locs) node.append(make('span', 'geo-tag', `${loc.label} · ${precisionLabel(loc.precision)}`));
    for (const country of item.countries || []) node.append(make('span', 'geo-tag', `${country.label} · mención`));
    const footer = make('footer'), button = make('button', 'save', C.isSaved(item, saved) ? '★' : '☆');
    button.type = 'button'; button.setAttribute('aria-label', C.isSaved(item, saved) ? 'Quitar favorito' : 'Guardar favorito');
    button.setAttribute('aria-pressed', String(C.isSaved(item, saved))); button.onclick = () => save(item);
    footer.append(link('Ver fuente original ↗', item.url), button); node.append(footer);
    const details = make('details'), summary = make('summary', '', 'Trazabilidad y evidencia');
    details.append(summary, make('p', '', `Publicación: ${fmt(item.published)} · Primera observación: ${fmt(item.firstSeenAt)} · Última observación: ${fmt(item.lastSeenAt)}`));
    const type = {official_advisory: 'Comunicado oficial', publisher_post: 'Publicación del editor', news: 'Noticia'}[item.contentType] || 'Publicación';
    details.append(make('p', '', `${type} · Categoría sugerida por palabras clave · Afirmaciones sin verificación independiente.`));
    if (item.relevance?.included) details.append(make('p', '', `Relevancia temática: ${item.relevance.category}. Señales encontradas en ${item.relevance.reason === 'title_topic' ? 'el título' : 'el contexto del resumen'}. Este filtro es orientativo y no verifica la noticia.`));
    details.append(make('p', '', `Idioma original: ${languageLabel(item.language)}. ${['entry_declaration', 'feed_declaration'].includes(item.languageMethod) ? 'Declarado por el editor en el feed.' : item.languageMethod === 'source_configuration' ? 'Identificado por la edición o canal de la fuente.' : 'Sin identificación de idioma.'} El contenido se conserva sin traducción automática.`));
    for (const loc of item.locations || []) {
      details.append(make('p', '', `${loc.label}: ${loc.evidence?.text || 'Sin descripción'} · ${loc.verification === 'reviewed_location' ? 'Ubicación revisada; no implica verificar la noticia' : 'Ubicación indicada por la fuente'}`));
      if (loc.evidence?.url) details.append(link('Ver evidencia geográfica ↗', loc.evidence.url));
    }
    if ((item.countries || []).length) details.append(make('p', '', 'Menciones detectadas por nombres de países en el título o resumen. Pueden ser ambiguas y no acreditan ubicación ni afectación.'));
    const group = (data.relatedGroups || []).find(group => group.articleIds.includes(item.id));
    if (group) {
      details.append(make('p', '', 'Posible relación por título coincidente dentro de 72 horas; no confirma un mismo acontecimiento.'));
      for (const related of C.filterArticles(data.items, {language: $('language').value}).filter(x => group.articleIds.includes(x.id) && x.id !== item.id)) {
        const p = make('p'); p.append(link(`${related.source}: ${related.title}`, related.url)); details.append(p);
      }
    }
    node.append(details); return node;
  }
  function precisionLabel(value) { return {exact: 'exacta documentada', approximate: 'aproximada', country: 'a nivel de país'}[value] || 'sin precisión'; }
  function languageLabel(value) { return {es: 'Español', en: 'Inglés', und: 'Idioma no determinado'}[value] || (value ? 'Otro idioma' : 'Idioma no determinado'); }
  function fitWorld() {
    if (!map || !map.getSize().x) return;
    map.fitBounds([[-55, -180], [78, 180]], {padding: [8, 8], maxZoom: 2});
    mapFitted = true;
  }
  function renderTimeline() {
    const context = filtered({start: '', end: '', hours: null});
    const bins = [];
    for (let i = 13; i >= 0; i--) { const day = new Date(); day.setHours(12, 0, 0, 0); day.setDate(day.getDate() - i); bins.push({key: C.dayKey(day), count: 0}); }
    for (const item of context) {
      if (!item.published || new Date(item.published).getTime() > Date.now()) continue;
      const bin = bins.find(bin => bin.key === C.dayKey(item.published)); if (bin) bin.count++;
    }
    const maximum = Math.max(1, ...bins.map(bin => bin.count));
    $('timeline').replaceChildren();
    for (const bin of bins) {
      const button = make('button', 'timeline-bar'), bar = make('span');
      button.title = `${bin.key}: ${bin.count} publicaciones`;
      button.setAttribute('aria-label', `Filtrar ${bin.key}: ${bin.count} publicaciones`);
      button.setAttribute('aria-pressed', String($('startDate').value === bin.key && $('endDate').value === bin.key));
      bar.style.height = `${Math.max(4, bin.count / maximum * 100)}%`;
      button.append(bar); button.onclick = () => { $('startDate').value = $('endDate').value = bin.key; $('period').value = ''; limit = 25; render(); };
      $('timeline').append(button);
    }
    $('timelineStart').textContent = bins[0].key.slice(5); $('timelineEnd').textContent = bins.at(-1).key.slice(5);
  }
  function render() {
    if (!data) return;
    const items = filtered();
    const invalidRange = $('startDate').value && $('endDate').value && $('startDate').value > $('endDate').value;
    $('filterNote').textContent = invalidRange ? 'El inicio del período debe ser anterior o igual al final.' :
      $('geoMode').value === 'mentions' ? 'Vista de contexto: el filtro por país incluye menciones; no confirma ubicación ni afectación.' :
      'El filtro por país usa ubicaciones reportadas. Para buscar menciones, cambiá a la vista de contexto.';
    const language = $('language').value, languageItems = C.filterArticles(data.items, {language});
    $('total').textContent = languageItems.length;
    $('last24').textContent = C.filterArticles(languageItems, {hours: 24}).length;
    $('totalLabel').textContent = language ? 'Publicaciones en español' : 'Publicaciones conservadas';
    $('last24Label').textContent = language ? 'En español · últimas 24 horas' : 'Publicadas en 24 horas';
    $('languageNote').textContent = language ? 'Mostrando publicaciones originales en español. Elegí «Todos los idiomas» para ampliar la cobertura internacional.' : 'Mostrando publicaciones en su idioma original, sin traducción automática.';
    $('savedCount').textContent = saved.size;
    $('feeds').textContent = `${data.sources.filter(x => x.status === 'ok').length}/${data.sources.length}`;
    $('favorites').setAttribute('aria-pressed', String(favoritesOnly));
    $('shown').textContent = `${items.length} resultados · ${items.filter(item => C.locations(item).length).length} con ubicación`;
    $('feed').replaceChildren();
    if (!items.length) {
      const empty = make('div', 'empty', invalidRange ? 'Revisá el intervalo de fechas seleccionado.' :
        language ? 'No hay publicaciones en español para estos filtros. Podés limpiar los filtros o ampliar la cobertura a todos los idiomas.' :
        'No hay publicaciones para estos filtros. Probá otra búsqueda o consultá los datos sin ubicación.');
      if (language) { const button = make('button', '', 'Ver todos los idiomas'); button.onclick = () => { $('language').value = ''; populateOptions(); render(); }; empty.append(make('p'), button); }
      $('feed').append(empty);
    }
    for (const item of items.slice(0, limit)) $('feed').append(card(item));
    $('more').hidden = items.length <= limit;
    const located = languageItems.filter(item => C.locations(item).length).length;
    $('coverage').textContent = `${located} de ${languageItems.length} publicaciones${language ? ' en español' : ''} tienen ubicación reportada. ${languageItems.length - located} permanecen en la lista sin asignar un lugar.`;
    updateConnection(); renderMap(items); renderTimeline();
  }
  function selectCountry(code) {
    $('country').value = code; limit = 25; render();
    const feature = world?.features.find(feature => feature.properties.code === code);
    if (feature && map) map.fitBounds(L.geoJSON(feature).getBounds(), {maxZoom: 5, padding: [25, 25]});
  }
  function countryPopup(feature, items) {
    const node = make('div'); node.append(make('h3', '', feature.properties.name));
    const mode = $('geoMode').value;
    const matching = items.filter(item => C.countryCodes(item, mode).includes(feature.properties.code));
    node.append(make('p', '', mode === 'mentions' ? `${matching.length} publicaciones con mención o ubicación reportada. Las menciones no son incidentes.` : `${matching.length} publicaciones con ubicación o afectación reportada en este país.`));
    for (const item of matching.slice(0, 4)) { const p = make('p'); p.append(link(item.title, item.url)); node.append(p); }
    const button = make('button', '', 'Filtrar publicaciones de este país'); button.onclick = () => selectCountry(feature.properties.code); node.append(button);
    return node;
  }
  function renderMap(items) {
    const mode = $('geoMode').value;
    const mapped = items.filter(item => C.locations(item).length).length;
    $('mapSummary').textContent = `${mapped} con ubicación · ${items.length - mapped} sin ubicación · ${mode === 'mentions' ? 'contexto de menciones' : 'ubicaciones reportadas'}`;
    $('mapMessage').replaceChildren(make('span', '', mode === 'mentions' ?
      'Los países resaltados tienen menciones o ubicaciones reportadas en las publicaciones filtradas. El color no mide riesgo.' :
      mapped ? 'Los puntos y países muestran ubicaciones reportadas; consultá su precisión y evidencia en cada publicación.' :
      'Estas publicaciones no aportan ubicaciones de acontecimientos. No se han creado marcadores a partir de menciones.'));
    if (!mapped && mode !== 'mentions') {
      const contextButton = make('button', '', 'Explorar países mencionados');
      contextButton.onclick = () => { $('geoMode').value = 'mentions'; render(); }; $('mapMessage').append(contextButton);
    }
    if (!map || !world) return;
    if (countryLayer) countryLayer.remove();
    markerLayer.clearLayers();
    const counts = new Map();
    for (const item of items) for (const code of C.countryCodes(item, mode)) counts.set(code, (counts.get(code) || 0) + 1);
    countryLayer = L.geoJSON(world, {
      style: feature => {
        const count = counts.get(feature.properties.code) || 0, selected = $('country').value === feature.properties.code;
        return {color: selected ? '#f0d89c' : '#365164', weight: selected ? 2 : .7,
          fillColor: count ? (mode === 'mentions' ? '#6789ac' : '#65bda0') : '#172c3c',
          fillOpacity: count ? Math.min(.8, .32 + Math.log2(count + 1) * .1) : .8};
      },
      onEachFeature: (feature, layer) => {
        layer.bindTooltip(() => {
          const label = make('span', '', `${feature.properties.name} · ${counts.get(feature.properties.code) || 0} publicaciones`); return label;
        }, {sticky: true});
        layer.bindPopup(() => countryPopup(feature, items));
      }
    }).addTo(map);
    // Aggregate only close screen points; the first documented coordinate anchors each group.
    const clusters = new Map();
    for (const item of items) for (const loc of C.locations(item)) {
      if (loc.geometry?.type !== 'Point') continue;
      const [lon, lat] = loc.geometry.coordinates || [];
      if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) continue;
      const projected = map.project([lat, lon], map.getZoom());
      const key = `${Math.floor(projected.x / 32)},${Math.floor(projected.y / 32)}`;
      if (!clusters.has(key)) clusters.set(key, []);
      clusters.get(key).push({item, loc, lat, lon});
    }
    for (const group of clusters.values()) {
      const first = group[0], count = new Set(group.map(x => x.item.id || x.item.url)).size;
      const color = C.colors[first.item.category] || '#a3b3c2';
      const marker = L.circleMarker([first.lat, first.lon], {radius: count > 1 ? 11 : 7, color, fillColor: color, fillOpacity: .75, weight: 2});
      const popup = make('div'); popup.append(make('h3', '', count > 1 ? `${count} publicaciones cercanas` : first.loc.label));
      if (count > 1) popup.append(make('p', '', 'Agrupación visual anclada en una coordenada reportada; no indica un mismo acontecimiento.'));
      for (const {item, loc} of group.slice(0, 15)) {
        const p = make('p'); p.append(link(item.title, item.url), make('span', '', ` · ${precisionLabel(loc.precision)}`)); popup.append(p);
        if (loc.evidence?.url) popup.append(link('Evidencia geográfica ↗', loc.evidence.url));
      }
      marker.bindPopup(popup).bindTooltip(`${count} publicación${count > 1 ? 'es' : ''} · ${first.loc.label}`).addTo(markerLayer);
    }
    markerLayer.bringToFront();
  }
  async function initMap() {
    try {
      if (!window.L) throw Error('Biblioteca no disponible');
      const response = await fetch('./assets/data/world.geojson');
      if (!response.ok) throw Error('Cartografía no disponible');
      world = await response.json();
      map = L.map('map', {minZoom: 0, maxZoom: 9, zoomSnap: .25, worldCopyJump: false, maxBounds: [[-85, -200], [85, 200]],
        maxBoundsViscosity: .8, zoomAnimation: !matchMedia('(prefers-reduced-motion: reduce)').matches}).setView([18, 0], 2);
      map.attributionControl.addAttribution('Cartografía: <a href="https://www.naturalearthdata.com/">Natural Earth</a> · límites orientativos');
      markerLayer = L.featureGroup().addTo(map);
      map.on('zoomend', () => { if (data) renderMap(filtered()); });
      fitWorld();
      if (data) renderMap(filtered());
    } catch (error) {
      $('map').replaceChildren(make('div', 'map-unavailable', 'No se pudo cargar el mapa. La lista, los filtros y las fuentes siguen disponibles.'));
      $('mapSummary').textContent = 'Mapa no disponible'; console.error(error);
    }
  }
  async function load() {
    if (loading) return;
    loading = true; $('refresh').disabled = true;
    try {
      const response = await fetch('./data/news.json', {cache: 'no-store'});
      if (!response.ok) throw Error(`HTTP ${response.status}`);
      const snapshot = await response.json();
      if (!C.validSnapshot(snapshot)) throw Error('Formato de noticias inválido');
      data = snapshot; loadError = false; populateOptions(); sourcePanels(); render();
    } catch (error) {
      loadError = true;
      if (data) updateConnection();
      else {
        $('connection').textContent = 'No se pudieron cargar las noticias'; $('connection').classList.add('warning');
        $('feed').replaceChildren(make('div', 'empty', 'No se pudo consultar el archivo de noticias. Probá «Revisar datos» o revisá la recopilación en GitHub Actions.'));
      }
      console.error(error);
    } finally { loading = false; $('refresh').disabled = false; }
  }
  function setView(view) {
    $('main').classList.toggle('mobile-list', view === 'list'); $('main').classList.toggle('mobile-map', view === 'map');
    $('showMap').setAttribute('aria-pressed', String(view === 'map')); $('showList').setAttribute('aria-pressed', String(view === 'list'));
    if (map) requestAnimationFrame(() => { map.invalidateSize(); if (!mapFitted) fitWorld(); });
  }
  for (const category of C.categories) {
    const label = make('label', 'category-option'), checkbox = make('input');
    checkbox.type = 'checkbox'; checkbox.checked = true; checkbox.setAttribute('aria-label', `Capa ${category}`);
    label.style.setProperty('--category', C.colors[category]); label.append(checkbox, document.createTextNode(category));
    checkbox.onchange = () => { checkbox.checked ? enabledLayers.add(category) : enabledLayers.delete(category); limit = 25; render(); };
    $('layers').append(label);
  }
  for (const id of ['category', 'source', 'country', 'region', 'period', 'startDate', 'endDate', 'geoMode', 'locatedOnly']) {
    $(id).onchange = () => { limit = 25; render(); };
  }
  $('language').onchange = () => { limit = 25; if (data) populateOptions(); render(); };
  let searchTimer;
  $('search').oninput = () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { limit = 25; render(); }, 120); };
  $('favorites').onclick = () => { favoritesOnly = !favoritesOnly; limit = 25; render(); };
  $('costaRica').onclick = () => { $('country').value = 'CR'; $('region').value = ''; $('geoMode').value = 'mentions'; $('locatedOnly').checked = false; selectCountry('CR'); };
  $('reset').onclick = () => {
    for (const id of ['search', 'category', 'source', 'country', 'region', 'period', 'startDate', 'endDate']) $(id).value = '';
    $('language').value = 'es'; if (data) populateOptions();
    $('locatedOnly').checked = false; $('geoMode').value = 'occurrences'; favoritesOnly = false; limit = 25;
    enabledLayers.clear(); for (const category of C.categories) enabledLayers.add(category);
    for (const checkbox of $('layers').querySelectorAll('input')) checkbox.checked = true;
    render();
  };
  $('clearTimeline').onclick = () => { $('startDate').value = $('endDate').value = $('period').value = ''; render(); };
  $('refresh').onclick = load;
  $('more').onclick = () => { limit += 25; render(); };
  $('showMap').onclick = () => setView('map'); $('showList').onclick = () => setView('list');
  $('worldView').onclick = fitWorld;
  // Default to the list on small screens so reports without coordinates remain visible.
  setView(matchMedia('(max-width: 820px)').matches ? 'list' : 'map');
  (async () => {
    try {
      const response = await fetch('./assets/data/countries.json');
      if (!response.ok) throw Error('Catálogo de países no disponible');
      countries = await response.json();
    } catch (error) { console.error(error); }
    await Promise.all([load(), initMap()]);
  })();
  setInterval(() => { if (!document.hidden) load(); }, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
})();
