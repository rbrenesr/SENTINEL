import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('collector', ROOT / 'scripts/fetch.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)
NOW = '2026-10-30T05:00:00+00:00'


def article(url='https://example.org/story?id=1', **values):
    return dict(title='A reported cybersecurity incident', url=url, source='Example', category='Ciberseguridad',
                published='2026-10-29T12:00:00+00:00', summary='', **values)


class CollectorTests(unittest.TestCase):
    def test_distinct_identifiers_survive_and_tracking_is_removed(self):
        self.assertNotEqual(collector.canonical_url('https://example.org/?id=1'), collector.canonical_url('https://example.org/?id=2'))
        self.assertEqual(collector.canonical_url('https://example.org/?id=1&utm_source=feed#top'), 'https://example.org/?id=1')
        self.assertIsNone(collector.canonical_url('javascript:alert(1)'))
        self.assertIsNone(collector.canonical_url('https://user:secret@example.org/'))

    def test_atom_prefers_article_over_self(self):
        xml = '''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Report</title>
          <link rel="self" href="https://example.org/api/1"/>
          <link rel="alternate" type="text/html" href="https://example.org/story"/>
          <updated>2026-10-29T12:00:00Z</updated></entry></feed>'''
        self.assertEqual(collector.parse(xml, 'Example')[0]['url'], 'https://example.org/story')

    def test_dates_are_utc_and_invalid_dates_are_missing(self):
        self.assertEqual(collector.parse_date('2026-10-29T12:00:00'), '2026-10-29T12:00:00+00:00')
        self.assertEqual(collector.parse_date('2026-10-29T12:00:00-06:00'), '2026-10-29T18:00:00+00:00')
        self.assertIsNone(collector.parse_date('not a date'))

    def test_partial_failure_keeps_history_and_observation_time(self):
        old = article()
        previous = {'updatedAt': '2026-10-29T13:00:00+00:00', 'items': [old]}
        merged = collector.merge_items(previous, [article('https://other.org/new')], NOW, [], {})
        self.assertEqual(len(merged), 2)
        retained = next(x for x in merged if x['url'] == old['url'])
        self.assertEqual(retained['lastSeenAt'], previous['updatedAt'])
        self.assertEqual(retained['firstSeenAt'], previous['updatedAt'])

    def test_total_failure_does_not_refresh_observation(self):
        previous = {'updatedAt': '2026-10-29T13:00:00+00:00', 'items': [article()]}
        retained = collector.merge_items(previous, [], NOW, [], {})
        self.assertEqual(retained[0]['lastSeenAt'], previous['updatedAt'])

    def test_retention_and_stable_identity(self):
        old = article(lastSeenAt='2026-08-01T00:00:00+00:00')
        self.assertEqual(collector.merge_items({'items': [old]}, [], NOW, [], {}), [])
        first = collector.enrich(article(), [], {})
        second = collector.enrich(article('https://example.org/story?id=1&utm_source=rss'), [], {})
        self.assertEqual(first['id'], second['id'])

    def test_mentions_never_become_occurrence_coordinates(self):
        item = article()
        item['title'] = 'New AI model from a company in Costa Rica'
        enriched = collector.enrich(item, [{'code': 'CR', 'name': 'Costa Rica', 'aliases': ['Costa Rica']}], {})
        self.assertEqual(enriched['countries'][0]['relation'], 'mentioned')
        self.assertEqual(enriched['locations'], [])
        self.assertEqual(enriched['category'], 'IA')

    def test_source_category_does_not_classify_unrelated_news(self):
        self.assertEqual(collector.classify('Feral deer spread across Australia', ''), 'Sin clasificar')

    def test_spanish_categories(self):
        for title, category in [
            ('Múltiples vulnerabilidades en un producto', 'Ciberseguridad'),
            ('Una red neuronal impulsa nuevos modelos de IA', 'IA'),
            ('Nuevos cables submarinos y fibra óptica', 'Internet'),
            ('Las tropas alcanzan un alto el fuego', 'Conflictos')]:
            with self.subTest(title=title):
                self.assertEqual(collector.classify(title, ''), category)

    def test_language_declaration_has_priority_over_source_defaults(self):
        xml = '''<rss><channel><language>es-CR</language><item><title>Noticia</title>
          <link>https://example.org/es</link></item><item><title>English item</title>
          <link>https://example.org/en</link><language>en-US</language></item></channel></rss>'''
        items = collector.parse(xml, 'BBC World')
        self.assertEqual([(x['language'], x['languageMethod']) for x in items],
                         [('es', 'feed_declaration'), ('en', 'entry_declaration')])

    def test_atom_xml_language_and_source_fallback(self):
        xml = '''<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="es"><entry><title>Informe</title>
          <link href="https://example.org/es"/></entry></feed>'''
        self.assertEqual(collector.parse(xml, 'Example')[0]['language'], 'es')
        rss = '<rss><channel><item><title>Informe</title><link>https://example.org/es</link></item></channel></rss>'
        self.assertEqual(collector.parse(rss, 'Xataka IA')[0]['language'], 'es')
        self.assertEqual(collector.parse(rss, 'Example')[0]['language'], 'und')

    def test_legacy_articles_get_known_source_language_without_guessing(self):
        item = article()
        self.assertEqual(collector.enrich(item, [], {})['language'], 'und')
        item['source'] = 'BBC World'
        self.assertEqual(collector.enrich(item, [], {})['language'], 'en')
        item['source'] = 'BBC Mundo'
        enriched = collector.enrich(item, [], {})
        self.assertEqual(enriched['language'], 'es')
        self.assertEqual(enriched['languageMethod'], 'source_configuration')
        item['language'] = 'en-US'
        self.assertEqual(collector.enrich(item, [], {})['language'], 'en')

    def test_language_survives_partial_failure_history(self):
        old = article(language='es', languageMethod='feed_declaration')
        previous = {'updatedAt': NOW, 'items': [old]}
        retained = collector.merge_items(previous, [], NOW, [], {})
        self.assertEqual(retained[0]['language'], 'es')
        self.assertEqual(retained[0]['languageMethod'], 'feed_declaration')

    def test_longer_country_names_do_not_create_nested_mentions(self):
        item = article()
        item['title'] = 'Internet in Papua New Guinea'
        countries = [{'code': 'PG', 'name': 'Papúa Nueva Guinea', 'aliases': ['Papua New Guinea']},
                     {'code': 'GN', 'name': 'Guinea', 'aliases': ['Guinea']}]
        self.assertEqual([x['countryCode'] for x in collector.mentions(item, countries)], ['PG'])

    def test_georss_is_source_reported_and_invalid_coordinates_are_ignored(self):
        xml = '''<rss xmlns:georss="http://www.georss.org/georss"><channel><item><title>Incident</title>
           <link>https://example.org/story</link><georss:point>{}</georss:point></item></channel></rss>'''
        parsed = collector.parse(xml.format('9.9 -84.1'), 'Example')[0]
        self.assertEqual(parsed['feedLocation']['geometry']['coordinates'], [-84.1, 9.9])
        self.assertEqual(parsed['feedLocation']['verification'], 'source_reported')
        for value in ['nan 0', '91 0', '10 181', 'bad value']:
            self.assertNotIn('feedLocation', collector.parse(xml.format(value), 'Example')[0])

    def test_manual_location_requires_reviewed_evidence(self):
        item = article()
        location = {'label': 'Lugar documentado', 'relation': 'occurrence', 'precision': 'country', 'countryCode': 'CR',
                    'evidence': {'url': item['url'], 'text': 'La fuente sitúa el acontecimiento en Costa Rica.', 'reviewedAt': NOW}}
        self.assertEqual(len(collector.validated_locations({'locations': [location]}, item)), 1)
        broken = copy.deepcopy(location)
        broken['evidence'].pop('reviewedAt')
        with self.assertRaises(ValueError):
            collector.validated_locations({'locations': [broken]}, item)
        broken = copy.deepcopy(location)
        broken['geometry'] = {'type': 'Point', 'coordinates': [0, 0]}
        with self.assertRaises(ValueError):
            collector.validated_locations({'locations': [broken]}, item)

    def test_suggestions_do_not_merge_publications_or_geography(self):
        records = [collector.enrich(article('https://example.org/a'), [], {}), collector.enrich(article('https://example.org/b'), [], {})]
        groups = collector.related_groups(records)
        self.assertEqual(groups[0]['status'], 'suggested')
        self.assertEqual(len(records), 2)
        self.assertTrue(all(not item['locations'] for item in records))

    def test_valid_feed_above_old_two_mb_limit(self):
        content = ('<rss><channel><!--' + ('x' * 2_100_000) + '--><item><title>Report</title><link>https://example.org/story</link></item></channel></rss>').encode()
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return content[:size]
        with patch.object(collector.urllib.request, 'urlopen', return_value=Response()):
            items, status = collector.collect(('Example', 'IA', 'https://example.org/feed'))
        self.assertEqual(status['status'], 'ok')
        self.assertEqual(len(items), 1)

    def test_atomic_write_and_snapshot_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            target = pathlib.Path(directory) / 'news.json'
            collector.write_output(target, {'items': []})
            self.assertEqual(json.loads(target.read_text()), {'items': []})
            self.assertFalse(target.with_suffix('.tmp').exists())
        snapshot = json.loads((ROOT / 'data/news.json').read_text(encoding='utf8'))
        self.assertEqual(snapshot['schemaVersion'], 2)
        self.assertEqual(len({item['id'] for item in snapshot['items']}), len(snapshot['items']))
        for item in snapshot['items']:
            self.assertTrue(collector.canonical_url(item['url']))
            self.assertTrue(item['firstSeenAt'])
            self.assertTrue(item['lastSeenAt'])
            self.assertEqual(item['verification'], 'not_independently_verified')


if __name__ == '__main__':
    unittest.main()
