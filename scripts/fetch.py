#!/usr/bin/env python3
"""Fetch public RSS/Atom feeds into static JSON. Standard library only."""
import datetime as dt, email.utils, json, pathlib, re, urllib.request, xml.etree.ElementTree as ET, html
ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCES = [
 ('BBC World','Conflictos','https://feeds.bbci.co.uk/news/world/rss.xml'),
 ('Al Jazeera','Conflictos','https://www.aljazeera.com/xml/rss/all.xml'),
 ('The Guardian World','Conflictos','https://www.theguardian.com/world/rss'),
 ('CISA Alerts','Ciberseguridad','https://www.cisa.gov/cybersecurity-advisories/all.xml'),
 ('BleepingComputer','Ciberseguridad','https://www.bleepingcomputer.com/feed/'),
 ('Cloudflare Blog','Internet','https://blog.cloudflare.com/rss/'),
 ('Internet Society','Internet','https://www.internetsociety.org/feed/'),
 ('Google Research','IA','https://research.google/blog/rss/'),
 ('OpenAI News','IA','https://openai.com/news/rss.xml'),
 ('MIT Technology Review','IA','https://www.technologyreview.com/feed/'),
]
def clean(s):
 return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',s or ''))).strip()[:650]
def parse_date(s):
 try: return email.utils.parsedate_to_datetime(s).astimezone(dt.timezone.utc).isoformat()
 except Exception:
  try: return dt.datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(dt.timezone.utc).isoformat()
  except Exception: return None
def tag(el): return el.tag.split('}')[-1]
def child(el, name):
 for x in el:
  if tag(x)==name: return x
 return None
def txt(el,name):
 x=child(el,name)
 return ''.join(x.itertext()).strip() if x is not None else ''
def parse(content,source,category):
 root=ET.fromstring(content)
 items=[]
 for item in root.iter():
  if tag(item) not in ('item','entry'): continue
  title=clean(txt(item,'title'))
  link=txt(item,'link')
  if not link:
   x=child(item,'link')
   if x is not None: link=x.attrib.get('href','')
  if not link.startswith('https://') and not link.startswith('http://'): continue
  date=parse_date(txt(item,'pubDate') or txt(item,'published') or txt(item,'updated') or txt(item,'date'))
  summary=clean(txt(item,'description') or txt(item,'summary') or txt(item,'content'))
  if title: items.append(dict(title=title,url=link,source=source,category=category,published=date,summary=summary))
 return items[:35]
def main():
 items=[]; statuses=[]
 for source,category,url in SOURCES:
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'SentinelLite/1.0 (+personal RSS monitor)','Accept':'application/rss+xml,application/atom+xml,application/xml,text/xml,*/*'})
   with urllib.request.urlopen(req,timeout=18) as res: data=res.read(2_000_000)
   result=parse(data,source,category)
   items.extend(result)
   statuses.append({'name':source,'category':category,'status':'ok' if result else 'empty','count':len(result)})
  except Exception as exc:
   print(f'{source}: {exc}')
   statuses.append({'name':source,'category':category,'status':'error','count':0})
 seen=set(); unique=[]
 for item in sorted(items,key=lambda x:x['published'] or '',reverse=True):
  key=item['url'].split('?')[0].rstrip('/')
  if key not in seen: seen.add(key);unique.append(item)
 output={'updatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'items':unique[:300],'sources':statuses}
 dest=ROOT/'data'/'news.json'
 # Keep previous articles if all feeds temporarily fail.
 if not unique and dest.exists():
  previous=json.loads(dest.read_text(encoding='utf8'))
  output['items']=previous.get('items',[])
 dest.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf8')
 print(f'{len(unique)} articles, {sum(s["status"]=="ok" for s in statuses)} sources OK')
if __name__=='__main__':main()
