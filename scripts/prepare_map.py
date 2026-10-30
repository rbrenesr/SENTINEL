"""Rebuild local world geometry from the pinned Natural Earth release."""
import argparse
import json
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_110m_admin_0_countries.geojson'
ALIASES = {
    'US': ['United States', 'United States of America', 'Estados Unidos', 'USA', 'U.S.'],
    'GB': ['United Kingdom', 'Reino Unido', 'Britain', 'Great Britain', 'UK'],
    'RU': ['Russia', 'Rusia', 'Russian Federation'],
    'KR': ['South Korea', 'Corea del Sur'], 'KP': ['North Korea', 'Corea del Norte'],
    'AE': ['United Arab Emirates', 'Emiratos Árabes Unidos', 'UAE'],
    'PS': ['Palestine', 'Palestina'], 'TW': ['Taiwan', 'Taiwán'],
    'TR': ['Türkiye', 'Turquía'], 'CD': ['Democratic Republic of the Congo', 'República Democrática del Congo', 'DR Congo'],
    'CG': ['Republic of the Congo', 'República del Congo'],
    'CI': ["Côte d’Ivoire", "Côte d'Ivoire", 'Ivory Coast', 'Costa de Marfil'],
}
AMBIGUOUS = {'Georgia', 'Jordan', 'Chad', 'Turkey', 'Congo'}


def rounded(value):
    if isinstance(value, list):
        return [rounded(x) for x in value]
    return round(value, 3) if isinstance(value, float) else value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=pathlib.Path)
    args = parser.parse_args()
    if args.source:
        original = json.loads(args.source.read_text(encoding='utf8'))
    else:
        with urllib.request.urlopen(SOURCE, timeout=30) as response:
            original = json.load(response)
    features, countries = [], []
    for feature in original['features']:
        p = feature['properties']
        code = p['ISO_A2_EH']
        if code == '-99':
            code = p['ADM0_A3']  # Stable cartographic identifier, not an invented ISO code.
        name = p.get('NAME_ES') or p['NAME_EN']
        aliases = set(ALIASES.get(code, []))
        aliases.update(x for x in (p.get('NAME_EN'), p.get('NAME_ES'), p.get('NAME_LONG'))
                       if x and len(x) > 3 and x not in AMBIGUOUS)
        countries.append(dict(code=code, name=name, region=p['REGION_UN'], aliases=sorted(aliases)))
        features.append(dict(type='Feature', properties=dict(code=code, name=name, region=p['REGION_UN']),
                             geometry=dict(type=feature['geometry']['type'], coordinates=rounded(feature['geometry']['coordinates']))))
    target = ROOT / 'assets/data'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'world.geojson').write_text(json.dumps(dict(type='FeatureCollection', features=features),
                                                   ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf8')
    (target / 'countries.json').write_text(json.dumps(countries, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(f'{len(countries)} cartographic units prepared from Natural Earth v5.1.2')


if __name__ == '__main__':
    main()
