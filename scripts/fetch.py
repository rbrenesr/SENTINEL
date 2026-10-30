#!/usr/bin/env python3
"""Traceable RSS/Atom collection; bounded static history, standard library only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import email.utils
import hashlib
import html
import json
import math
import pathlib
import re
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc
MAX_FEED_BYTES = 8_000_000
SOURCES = [
    ('BBC World', 'Conflictos', 'https://feeds.bbci.co.uk/news/world/rss.xml'),
    ('Al Jazeera', 'Conflictos', 'https://www.aljazeera.com/xml/rss/all.xml'),
    ('The Guardian World', 'Conflictos', 'https://www.theguardian.com/world/rss'),
    ('CISA Alerts', 'Ciberseguridad', 'https://www.cisa.gov/cybersecurity-advisories/all.xml'),
    ('BleepingComputer', 'Ciberseguridad', 'https://www.bleepingcomputer.com/feed/'),
    ('Cloudflare Blog', 'Internet', 'https://blog.cloudflare.com/rss/'),
    ('Internet Society', 'Internet', 'https://www.internetsociety.org/feed/'),
    ('Google Research', 'IA', 'https://research.google/blog/rss/'),
    ('OpenAI News', 'IA', 'https://openai.com/news/rss.xml'),
    ('MIT Technology Review', 'IA', 'https://www.technologyreview.com/feed/'),
]
SOURCE_LANGUAGES = {name: 'en' for name, _, _ in SOURCES}
SPANISH_SOURCES = [
    ('BBC Mundo', 'Conflictos', 'https://feeds.bbci.co.uk/mundo/rss.xml'),
    ('DW Español', 'Conflictos', 'https://rss.dw.com/rdf/rss-sp-all'),
    ('INCIBE-CERT', 'Ciberseguridad', 'https://www.incibe.es/incibe-cert/alerta-temprana/avisos/feed'),
    ('Xataka IA', 'IA', 'https://www.xataka.com/tag/inteligencia-artificial/rss2.xml'),
    ('Xataka Internet', 'Internet', 'https://www.xataka.com/tag/internet/rss2.xml'),
]
SOURCES.extend(SPANISH_SOURCES)
SOURCE_LANGUAGES.update({name: 'es' for name, _, _ in SPANISH_SOURCES})
RULES = {
    'Ciberseguridad': r'\b(ransomware|malware|cyberattack|cybersecurity|cyber attack|data breach|vulnerability|vulnerabilities|cve-\d+|phishing|hacker|hackers|ciberataques?|ciberseguridad|vulnerabilidad(?:es)?|filtracion(?:es)? de datos)\b',
    'Internet': r'\b(internet|outage|outages|connectivity|telecom|telecommunications|submarine cable|subsea cable|bgp|dns|cdn|conectividad|apagon digital|cortes? de internet|telecomunicaciones|cables? submarinos?|fibra optica)\b',
    'IA': r'\b(artificial intelligence|generative ai|ai|ia|llm|llms|machine learning|neural network|language model|chatgpt|openai|deepmind|inteligencia artificial|modelos? de lenguaje|aprendizaje automatico|redes? neuronales?)\b',
    'Conflictos': r'\b(war|wars|military|missile|missiles|airstrike|airstrikes|ceasefire|troops|sanctions|diplomatic|diplomacy|armed conflict|invasion|guerras?|militar(?:es)?|misil(?:es)?|bombardeos?|sanciones|diplomacia|humanitarian|humanitari[oa]s?|occupation|hostage|hostages|fighting|clashes|armed forces|elections|political|government|geopolitical|ataques militares|alto el fuego|tropas|conflictos? armados?|rehenes|geopolitica|elecciones|gobierno)\b',
}
SCOPE_VERSION = 1
# Scope admission is independent of the older, broad category classifier.
# A country, publisher, government mention or the word "internet" is not enough.
SCOPE_RULES = {
    'Ciberseguridad': r'\b(?:ransomware|malware|ciberataques?|ciberseguridad|cyberattacks?|cybersecurity|cyber attacks?|phishing|data breaches?|filtracion(?:es)? de datos|exposicion de informacion|vulnerabilidad(?:es)?|vulnerabilities|vulnerability|cve-\d+|zero.day|dia cero|cross.site scripting|sql injection|inyeccion sql|escritura fuera de limites|out.of.bounds write|ejecucion (?:remota de codigo|de codigo)|remote code execution|denial.of.service|denegacion de servicio|botnets?|spyware|espionaje digital)\b',
    'Internet': r'\b(?:bgp|dns|cdn|telecomunicaciones|telecommunications|cables? submarinos?|submarine cables?|subsea cables?|fibra optica|fiber optic|internet (?:outages?|shutdowns?|blackouts?|access|infrastructure|connectivity)|(?:cortes?|apagones?|caidas?|bloqueos?|acceso|infraestructura) (?:de |a |del )?internet|(?:fallos?|fallas?|interrupciones?|caidas?|outages?|disruptions?)\b.{0,80}\b(?:internet|cloud|nube|conectividad|telecom|servicios? digitales?)|infraestructura digital|conectividad|connectivity|centros? de datos|data cent(?:er|re)s?)\b',
    'IA': r'\b(?:inteligencia artificial|artificial intelligence|ia|ai|llms?|modelos? de lenguaje|language models?|chatgpt|openai|deepmind|machine learning|aprendizaje automatico|redes? neuronales?|neural networks?|reinforcement learning|aprendizaje por refuerzo)\b',
    'Conflictos': r'\b(?:war|wars|armed conflict|military|missiles?|airstrikes?|ceasefire|troops|sanctions|diplomatic|diplomacy|invasion|guerras?|militar(?:es)?|misil(?:es)?|bombardeos?|sanciones|diplomaci[ao]|diplomatic[oa]s?|canciller|ministros? de exteriores|alto el fuego|tropas|conflictos? armados?|rehenes|hostages?|occupation|ocupacion|geopolitic[as]|geopolitical|otan|nato|g20|g7|nuclear weapons|armas nucleares|despliegue militar|ataques? (?:con drones?|con misiles?|militares?)|enfrentamientos? (?:armados?|fronterizos?)|border clashes|fighting|crisis humanitaria|humanitarian crisis|desplazados|refugees|refugiados|elecciones|elections|legislativas|midterms?|comision electoral|electoral commission|coalicion|coalition|partido comunista|communist party|injerencia|interferencia electoral|apoyo internacional|aliad[oa]s?|alianzas?|relaciones internacionales|socios estrategicos|censura|censorship|represion|repression|medio opositor|opposition newspaper|presos politicos|political prisoners|migracion|inmigracion|immigration|migration|politica exterior|foreign policy|intervencion extranjera)\b',
}
SPORTS = r'\b(?:rally|dakar|futbol|football|soccer|bayern|champions league|formula 1|formula one|balon de oro|ballon d.or|tenis|tennis|rugby|cricket|mundial de futbol|olympics|juegos olimpicos|futbolistas?|futbolista|goleador|goles)\b'
LIFESTYLE = r'\b(?:afeccion|genital|liquen|escleroso|piel|arrugas|adelgazar|skin care|skincare|recetas? de cocina|recipe|horoscopos?|zodiac|celebrity|famos[oa]s?|actriz|actor|actores|actrices|premios? emmy|globos? de oro|star trek|x.men|beauty|belleza|viajes? de lujo|crucero de lujo|test.{0,40}salud)\b'
TECH_CONTEXT = r'\b(?:software|servidores?|servers?|plataformas?|platforms?|supercl[au]ster|gpu|tarjetas graficas|chips?|modelos?|models?|infraestructura|infrastructure|nube|cloud|redes?|networks?|tecnologia|technology|algoritmos?|algorithms?|sistemas?|systems?)\b'
SCOPE_RULES['Conflictos'] += r'|\b(?:ataques? con dron(?:es)?|miembro asociado|asociacion sin adhesion|politica comercial|acuerdos? comerciales?|trade agreements?|trade deals?|aranceles?|tariffs?|presidencia|presidenta|presidential election)\b'
SCOPE_RULES['IA'] += r'|\b(?:grandes modelos|large models)\b'


def assess_relevance(item):
    title = normalized(clean(item.get('title', '')))
    summary = normalized(clean(item.get('summary', '')))
    title_matches = {category: sorted(set(re.findall(rule, title))) for category, rule in SCOPE_RULES.items()}
    summary_matches = {category: sorted(set(re.findall(rule, summary))) for category, rule in SCOPE_RULES.items()}
    if re.search(r'\b(?:petroleros?|buques?|tankers?|ships?)\b', title) and re.search(r'\b(?:minas|mines|explosivos|explosives|sabotaje|sabotage)\b', title + ' ' + summary):
        title_matches['Conflictos'].append('maritime_security_context')
    if re.search(r'\b(?:php|cloudflare|software|web|webs|servidores?|servers?)\b', title) and re.search(r'\b(?:fallos? (?:graves?|criticos?)|brechas?|critical flaws?|security flaws?)\b', title + ' ' + summary):
        title_matches['Ciberseguridad'].append('software_security_context')
    cyber_title = bool(title_matches['Ciberseguridad'])
    # Sports/celebrity/health reports are not admitted for incidental country or
    # political references. Direct cyber incidents and substantive AI risks remain.
    if re.search(SPORTS, title) and not (cyber_title or title_matches['Internet']):
        return {'included': False, 'reason': 'sports_focus'}
    if re.search(LIFESTYLE, title) and not (cyber_title or title_matches['IA']):
        return {'included': False, 'reason': 'lifestyle_focus'}
    candidates = {category: signals for category, signals in title_matches.items() if signals}
    reason = 'title_topic'
    if not candidates:
        # A generic technology headline needs explicit context in its summary;
        # otherwise require two distinct, topic-specific signals in that summary.
        candidates = {category: signals for category, signals in summary_matches.items()
                      if len(signals) >= 2 or (signals and re.search(TECH_CONTEXT, title))}
        reason = 'summary_context'
    if not candidates:
        return {'included': False, 'reason': 'no_scope_evidence'}
    category = max(candidates, key=lambda name: len(candidates[name]))
    return {'included': True, 'category': category, 'reason': reason,
            'signals': candidates[category], 'method': 'topic_rules', 'version': SCOPE_VERSION}


def scope_items(items):
    accepted = []
    for item in items:
        decision = assess_relevance(item)
        if decision['included']:
            accepted.append({**item, 'category': decision['category'], 'relevance': decision})
    return accepted


def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value or ''))).strip()[:650]


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.lower()) if not unicodedata.combining(c))


def parse_date(value):
    if not value:
        return None
    try:
        date = email.utils.parsedate_to_datetime(value)
    except (ValueError, TypeError, IndexError):
        try:
            date = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None
    return date.replace(tzinfo=date.tzinfo or UTC).astimezone(UTC).isoformat()


def canonical_url(value):
    try:
        url = urllib.parse.urlsplit(value)
        if url.scheme not in ('https', 'http') or not url.hostname or url.username or url.password:
            return None
        query = [(k, v) for k, v in urllib.parse.parse_qsl(url.query, keep_blank_values=True)
                 if not k.lower().startswith('utm_') and k.lower() not in
                 ('fbclid', 'gclid', 'traffic_source', 'mc_cid', 'mc_eid')]
        return urllib.parse.urlunsplit((url.scheme, url.netloc.lower(), url.path or '/',
                                       urllib.parse.urlencode(query), ''))
    except (ValueError, TypeError):
        return None


def stable_id(value):
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def classify(title, summary):
    text = normalized(title + ' ' + summary)
    scores = {category: len(set(re.findall(rule, text))) for category, rule in RULES.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else 'Sin clasificar'


def tag(element):
    return element.tag.split('}')[-1]


def txt(element, name):
    for child in element:
        if tag(child) == name:
            return ''.join(child.itertext()).strip()
    return ''


def normalize_language(value):
    language = re.split('[-_]', str(value or '').strip().lower())[0]
    return language if re.fullmatch(r'[a-z]{2,3}', language) else 'und'


def parse(content, source, category=None):
    root = ET.fromstring(content)
    channel = next((x for x in root if tag(x) == 'channel'), root)
    declared = normalize_language(root.get('{http://www.w3.org/XML/1998/namespace}lang') or txt(channel, 'language'))
    items = []
    for entry in root.iter():
        if tag(entry) not in ('item', 'entry'):
            continue
        title = clean(txt(entry, 'title'))
        links = [x for x in entry if tag(x) == 'link']
        link = next((x.attrib['href'] for x in links if x.attrib.get('href') and
                     x.attrib.get('rel', 'alternate') == 'alternate' and
                     x.attrib.get('type', 'text/html') in ('text/html', 'application/xhtml+xml')), '')
        link = link or next((''.join(x.itertext()).strip() for x in links if not x.attrib.get('href')), '')
        canonical = canonical_url(link)
        if not title or not canonical:
            continue
        summary = clean(txt(entry, 'description') or txt(entry, 'summary') or txt(entry, 'content'))
        item = dict(title=title, url=link, canonicalUrl=canonical, source=source,
                    category=classify(title, summary), published=parse_date(txt(entry, 'pubDate') or
                    txt(entry, 'published') or txt(entry, 'updated') or txt(entry, 'date')), summary=summary)
        entry_language = normalize_language(entry.get('{http://www.w3.org/XML/1998/namespace}lang') or txt(entry, 'language'))
        item['language'] = entry_language if entry_language != 'und' else declared if declared != 'und' else SOURCE_LANGUAGES.get(source, 'und')
        item['languageMethod'] = ('entry_declaration' if entry_language != 'und' else
                                  'feed_declaration' if declared != 'und' else
                                  'source_configuration' if source in SOURCE_LANGUAGES else 'unknown')
        # Publisher coordinates are approximate and not independently verified.
        point = entry.find('{http://www.georss.org/georss}point')
        if point is not None and point.text:
            try:
                lat, lon = map(float, point.text.split())
                if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
                    item['feedLocation'] = dict(label='Ubicación indicada por la fuente',
                        relation='occurrence', precision='approximate', countryCode=None,
                        geometry={'type': 'Point', 'coordinates': [lon, lat]},
                        evidence={'url': link, 'text': 'Coordenadas GeoRSS del editor', 'method': 'georss'},
                        verification='source_reported')
            except ValueError:
                pass
        items.append(item)
    return items[:35]


def load_countries():
    return json.loads((ROOT / 'assets/data/countries.json').read_text(encoding='utf8'))


def mentions(item, countries):
    text = normalized(item['title'] + ' ' + item.get('summary', ''))
    result, occupied, seen = [], [], set()
    candidates = []
    for country in countries:
        for alias in country['aliases']:
            for match in re.finditer(r'(?<!\w)' + re.escape(normalized(alias)) + r'(?!\w)', text):
                candidates.append((match.start(), match.end(), alias, country))
    # Longest place names win: Papua New Guinea must not also imply Guinea.
    for start, end, alias, country in sorted(candidates, key=lambda x: x[1] - x[0], reverse=True):
        if any(start < right and end > left for left, right in occupied):
            continue
        occupied.append((start, end))
        if country['code'] not in seen:
            seen.add(country['code'])
            result.append({'countryCode': country['code'], 'label': country['name'],
                           'relation': 'mentioned', 'matchedAlias': alias,
                           'method': 'dictionary', 'evidenceUrl': item['url']})
    return result


def validated_locations(annotation, item):
    locations = []
    for location in annotation.get('locations', []):
        if location.get('relation') not in ('occurrence', 'affected', 'related'):
            raise ValueError('Relación geográfica inválida en ' + item['url'])
        if location.get('precision') not in ('exact', 'approximate', 'country'):
            raise ValueError('Precisión geográfica inválida en ' + item['url'])
        evidence = location.get('evidence', {})
        if not canonical_url(evidence.get('url', '')) or not evidence.get('text') or not parse_date(evidence.get('reviewedAt')):
            raise ValueError('Falta evidencia revisada en ' + item['url'])
        if not location.get('label') or (location['precision'] == 'country' and not location.get('countryCode')):
            raise ValueError('Falta lugar/país en ' + item['url'])
        geometry = location.get('geometry')
        if location['precision'] != 'country':
            if not geometry or geometry.get('type') != 'Point':
                raise ValueError('Esta versión requiere un punto documentado en ' + item['url'])
            coordinates = geometry.get('coordinates', [])
            if len(coordinates) != 2 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or
                                          not math.isfinite(x) for x in coordinates):
                raise ValueError('Coordenadas inválidas en ' + item['url'])
            if not (-180 <= coordinates[0] <= 180 and -90 <= coordinates[1] <= 90):
                raise ValueError('Coordenadas fuera de rango en ' + item['url'])
        elif geometry:
            raise ValueError('No asignar un punto a una ubicación de país')
        locations.append({**location, 'verification': 'reviewed_location'})
    return locations


def enrich(item, countries, annotations):
    item = dict(item)
    canonical = canonical_url(item['url'])
    item.update(id=stable_id(canonical), canonicalUrl=canonical,
                category=classify(item['title'], item.get('summary', '')),
                categoryMethod='keyword_rules', verification='not_independently_verified')
    if item.get('relevance', {}).get('included'):
        item['category'] = item['relevance']['category']
        item['categoryMethod'] = 'scope_topic_rules'
    item['language'] = normalize_language(item.get('language'))
    if item['language'] == 'und':
        item['language'] = SOURCE_LANGUAGES.get(item['source'], 'und')
        item['languageMethod'] = 'source_configuration' if item['source'] in SOURCE_LANGUAGES else 'unknown'
    item['contentType'] = ('official_advisory' if item['source'] in ('CISA Alerts', 'INCIBE-CERT') else
                           'publisher_post' if item['source'] in ('Google Research', 'OpenAI News',
                           'Cloudflare Blog', 'Internet Society') else 'news')
    item['countries'] = mentions(item, countries)
    item['locations'] = validated_locations(annotations.get(canonical, {}), item)
    if item.get('feedLocation'):
        item['locations'].append(item['feedLocation'])
    return item


def merge_items(previous, incoming, now, countries, annotations):
    old_time = previous.get('updatedAt')
    merged = {}
    cutoff = dt.datetime.fromisoformat(now) - dt.timedelta(days=30)
    for item in previous.get('items', []):
        canonical = canonical_url(item.get('url', ''))
        if not canonical:
            continue
        last_seen = parse_date(item.get('lastSeenAt') or old_time)
        if not last_seen or dt.datetime.fromisoformat(last_seen) < cutoff:
            continue
        merged[canonical] = {**item, 'firstSeenAt': item.get('firstSeenAt') or old_time,
                             'lastSeenAt': last_seen}
    for item in incoming:
        canonical = canonical_url(item['url'])
        old = merged.get(canonical, {})
        merged[canonical] = {**item, 'firstSeenAt': old.get('firstSeenAt') or now, 'lastSeenAt': now}
    output = [enrich(item, countries, annotations) for item in scope_items(merged.values())]
    output.sort(key=lambda item: item.get('published') or item.get('firstSeenAt') or '', reverse=True)
    return output[:1000]


def related_groups(items):
    # Suggestions only: never merge records or transfer geographic evidence.
    buckets = {}
    for item in items:
        title = re.sub(r'\W+', ' ', normalized(item['title'])).strip()
        if len(title) >= 30 and item.get('published'):
            buckets.setdefault((item['category'], title), []).append(item)
    groups = []
    for candidates in buckets.values():
        candidates.sort(key=lambda x: x['published'])
        batch = []
        for item in candidates:
            if batch and (dt.datetime.fromisoformat(item['published']) -
                          dt.datetime.fromisoformat(batch[0]['published'])).total_seconds() > 72 * 3600:
                if len(batch) > 1:
                    groups.append({'status': 'suggested', 'method': 'same_title_72h', 'articleIds': [x['id'] for x in batch]})
                batch = []
            batch.append(item)
        if len(batch) > 1:
            groups.append({'status': 'suggested', 'method': 'same_title_72h', 'articleIds': [x['id'] for x in batch]})
    return groups


def collect(source):
    name, category, url = source
    try:
        request = urllib.request.Request(url, headers={
            'User-Agent': 'SENTINEL/1.1 (+https://github.com/rbrenesr/SENTINEL)',
            'Accept': 'application/rss+xml,application/atom+xml,application/xml,text/xml'})
        with urllib.request.urlopen(request, timeout=18) as response:
            content = response.read(MAX_FEED_BYTES + 1)
        if len(content) > MAX_FEED_BYTES:
            raise ValueError('El feed supera el límite de 8 MB')
        received = parse(content, name, category)
        items = scope_items(received)
        return items, {'name': name, 'category': category, 'url': url, 'language': SOURCE_LANGUAGES.get(name, 'und'),
                       'status': 'ok' if received else 'empty', 'count': len(items), 'receivedCount': len(received),
                       'excludedCount': len(received) - len(items), 'error': None}
    except Exception as error:
        print(f'{name}: {error}')
        return [], {'name': name, 'category': category, 'url': url, 'language': SOURCE_LANGUAGES.get(name, 'und'),
                    'status': 'error', 'count': 0, 'error': str(error)[:250]}


def write_output(path, output):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--offline', action='store_true', help='Enrich snapshot without claiming a new collection')
    args = parser.parse_args()
    path = ROOT / 'data/news.json'
    previous = json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
    countries = load_countries()
    annotations = json.loads((ROOT / 'data/annotations.json').read_text(encoding='utf8'))['articles']
    now = dt.datetime.now(UTC).isoformat()
    if args.offline:
        items = [enrich(item, countries, annotations) for item in scope_items(previous.get('items', []))]
        for item in items:
            item.setdefault('firstSeenAt', previous.get('updatedAt'))
            item.setdefault('lastSeenAt', previous.get('updatedAt'))
        output = {**previous, 'schemaVersion': 2, 'items': items,
                  'relatedGroups': related_groups(items), 'retentionDays': 30}
    else:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(collect, SOURCES))
        incoming = [item for items, _ in results for item in items]
        prior_status = {source['name']: source for source in previous.get('sources', [])}
        statuses = []
        for _, status in results:
            old = prior_status.get(status['name'], {})
            status.update(lastAttemptAt=now, lastSuccessAt=now if status['status'] == 'ok' else
                          old.get('lastSuccessAt') or (previous.get('updatedAt') if old.get('status') == 'ok' else None))
            statuses.append(status)
        items = merge_items(previous, incoming, now, countries, annotations)
        output = dict(schemaVersion=2, updatedAt=now if any(status['status'] == 'ok' for status in statuses) else previous.get('updatedAt'),
                      lastAttemptAt=now, items=items, sources=statuses,
                      relatedGroups=related_groups(items), retentionDays=30)
    output['scopeFilter'] = {'version': SCOPE_VERSION, 'method': 'topic_rules',
                            'topics': list(SCOPE_RULES), 'appliesTo': 'incoming_and_retained'}
    write_output(path, output)
    print(f'{len(output["items"])} retained articles; {sum(s["status"] == "ok" for s in output.get("sources", []))} sources OK')


if __name__ == '__main__':
    main()
