const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const C = require('../assets/core.js');
const now = Date.parse('2026-10-30T05:00:00Z');
const news = {id: '1', title: 'Internet en Costa Rica', summary: '', source: 'Example', category: 'Internet',
  url: 'https://example.org/article?id=1&utm_source=rss', published: '2026-10-30T03:00:00Z',
  countries: [{countryCode: 'CR', label: 'Costa Rica'}], locations: []};
test('script syntax is valid', () => {
  new vm.Script(fs.readFileSync('assets/app.js', 'utf8'));
  new vm.Script(fs.readFileSync('assets/core.js', 'utf8'));
});
test('future and missing dates are excluded from rolling time filters', () => {
  const items = [news, {...news, published: '2026-10-31T03:00:00Z'}, {...news, published: null}];
  assert.equal(C.filterArticles(items, {hours: 24}, now).length, 1);
});
test('country mention does not become a reported occurrence', () => {
  assert.equal(C.filterArticles([news], {country: 'CR', geoMode: 'occurrences'}, now).length, 0);
  assert.equal(C.filterArticles([news], {country: 'CR', geoMode: 'mentions'}, now).length, 1);
  assert.equal(C.filterArticles([news], {locatedOnly: true}, now).length, 0);
});
test('reviewed affected country is included and related country is excluded', () => {
  const item = {...news, locations: [{countryCode: 'CR', relation: 'affected'}, {countryCode: 'US', relation: 'related'}]};
  assert.deepEqual(C.countryCodes(item, 'occurrences'), ['CR']);
});
test('search, category, source, region and dates combine', () => {
  const result = C.filterArticles([news], {query: 'costa ríca', category: 'Internet', source: 'Example',
    geoMode: 'mentions', regionCodes: new Set(['CR']), start: '2026-10-01', end: '2026-10-31'}, now);
  assert.equal(result.length, 1);
  assert.equal(C.filterArticles([news], {source: 'Other'}, now).length, 0);
  assert.equal(C.filterArticles([news], {start: '2026-11-01', end: '2026-10-01'}, now).length, 0);
});
test('favorites survive tracking URL changes and ID parameters remain distinct', () => {
  assert.ok(C.isSaved(news, new Set([news.url])));
  assert.ok(C.isSaved(news, new Set(['https://example.org/article?id=1'])));
  assert.notEqual(C.canonicalURL(news.url), C.canonicalURL('https://example.org/article?id=2'));
});
test('unsafe URLs and malformed snapshots are rejected', () => {
  assert.equal(C.safeURL('javascript:alert(1)'), null);
  assert.equal(C.safeURL('https://user:secret@example.org'), null);
  assert.equal(C.validSnapshot({items: [news], sources: []}), true);
  assert.equal(C.validSnapshot({items: [{...news, url: 'data:text/html,hello'}], sources: []}), false);
  assert.equal(C.validSnapshot({items: [{...news, published: 'not a date'}], sources: []}), false);
});
test('Spanish view excludes English and unknown language without dropping them from all languages', () => {
  const items = [{...news, language: 'es'}, {...news, id: '2', language: 'en'}, {...news, id: '3'}, {...news, id: '4', language: 'und'}];
  assert.deepEqual(C.filterArticles(items, {language: 'es'}, now).map(x => x.id), ['1']);
  assert.equal(C.filterArticles(items, {language: ''}, now).length, 4);
});
test('language combines with favorites, source, country and rolling period', () => {
  const item = {...news, language: 'es'};
  const filters = {language: 'es', favoritesOnly: true, saved: new Set([news.url]), source: 'Example',
    country: 'CR', geoMode: 'mentions', hours: 24};
  assert.equal(C.filterArticles([item, {...item, language: 'en'}], filters, now).length, 1);
});
