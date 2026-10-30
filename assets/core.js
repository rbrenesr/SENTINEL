(function (root) {
  'use strict';
  const categories = ['Conflictos', 'Ciberseguridad', 'Internet', 'IA', 'Sin clasificar'];
  const colors = {Conflictos: '#ffa890', Ciberseguridad: '#c6a1ff', Internet: '#7bc9f5', IA: '#7be1ba', 'Sin clasificar': '#a3b3c2'};
  const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  function safeURL(value) {
    try { const u = new URL(value); return ['http:', 'https:'].includes(u.protocol) && !u.username && !u.password ? u.href : null; }
    catch { return null; }
  }
  function canonicalURL(value) {
    const safe = safeURL(value);
    if (!safe) return null;
    const url = new URL(safe);
    url.hash = '';
    for (const key of [...url.searchParams.keys()]) {
      if (key.toLowerCase().startsWith('utm_') || ['fbclid', 'gclid', 'traffic_source', 'mc_cid', 'mc_eid'].includes(key.toLowerCase())) url.searchParams.delete(key);
    }
    return url.href;
  }
  function dayKey(value) {
    const d = new Date(value);
    if (!Number.isFinite(d.getTime())) return '';
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
  const occurrence = location => ['occurrence', 'affected'].includes(location.relation);
  const locations = item => (item.locations || []).filter(occurrence);
  function countryCodes(item, mode) {
    const codes = locations(item).map(x => x.countryCode).filter(Boolean);
    if (mode === 'mentions') codes.push(...(item.countries || []).map(x => x.countryCode));
    return [...new Set(codes)];
  }
  function isSaved(item, saved) {
    return saved.has(item.url) || saved.has(item.canonicalUrl) || saved.has(canonicalURL(item.url));
  }
  function filterArticles(items, filters = {}, now = Date.now()) {
    const q = normalize(filters.query).trim();
    return items.filter(item => {
      const timestamp = item.published ? new Date(item.published).getTime() : NaN;
      const codes = countryCodes(item, filters.geoMode);
      const text = normalize([item.title, item.summary, item.source, ...(item.countries || []).map(x => x.label), ...(item.locations || []).map(x => x.label)].join(' '));
      return (!q || text.includes(q)) && (!filters.language || item.language === filters.language) &&
        (!filters.category || item.category === filters.category) &&
        (!filters.source || item.source === filters.source) && (!filters.country || codes.includes(filters.country)) &&
        (!filters.regionCodes || codes.some(code => filters.regionCodes.has(code))) &&
        (!filters.favoritesOnly || isSaved(item, filters.saved || new Set())) &&
        (!filters.locatedOnly || locations(item).length > 0) &&
        (!filters.hours || (Number.isFinite(timestamp) && timestamp <= now && now - timestamp <= filters.hours * 3600000)) &&
        (!filters.start || (Number.isFinite(timestamp) && dayKey(item.published) >= filters.start)) &&
        (!filters.end || (Number.isFinite(timestamp) && dayKey(item.published) <= filters.end));
    });
  }
  function validSnapshot(value) {
    return value && Array.isArray(value.items) && Array.isArray(value.sources) &&
      value.items.every(item => typeof item.title === 'string' && safeURL(item.url) &&
        (!item.published || Number.isFinite(new Date(item.published).getTime())) &&
        (!item.locations || Array.isArray(item.locations)) && (!item.countries || Array.isArray(item.countries)));
  }
  const api = {categories, colors, normalize, safeURL, canonicalURL, dayKey, locations, countryCodes, isSaved, filterArticles, validSnapshot};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.SentinelCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
