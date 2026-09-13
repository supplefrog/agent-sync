#!/usr/bin/env python3
"""Read RSS, Atom, or JSON Feed URLs and discover feeds behind pages."""
from __future__ import annotations
import argparse,html,json,re,sys,urllib.error,urllib.parse,urllib.request,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
UA='hermes-agent/1.0'; TIMEOUT=20
NS={'atom':'http://www.w3.org/2005/Atom','dc':'http://purl.org/dc/elements/1.1/','content':'http://purl.org/rss/1.0/modules/content/'}
TYPES=('application/rss+xml','application/atom+xml','application/feed+json','application/json')
PATHS=('/feed','/feed.xml','/rss','/rss.xml','/atom.xml','/index.xml','/feed.json','/blog/feed','/blog/rss.xml')
def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'*/*'})
 with urllib.request.urlopen(req,timeout=TIMEOUT) as r:return r.read(),r.headers.get('Content-Type','')
def clean(x):return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',x or ''))).strip()
def date(x):
 if not x:return None
 try:d=parsedate_to_datetime(x.strip())
 except (TypeError,ValueError):
  try:d=datetime.fromisoformat(x.strip().replace('Z','+00:00'))
  except ValueError:return x.strip()
 if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
 return d.astimezone(timezone.utc).isoformat()
def text(el,*paths):
 for p in paths:
  n=el.find(p,NS)
  if n is not None and (n.text or '').strip():return n.text
 return None
def parse(data,ctype=''):
 if data.lstrip()[:1]==b'{' or 'json' in ctype:
  doc=json.loads(data); out=[]
  for x in doc.get('items',[]):
   authors=x.get('authors') or ([x['author']] if x.get('author') else [])
   out.append({'title':clean(x.get('title')),'link':x.get('url') or x.get('external_url'),'published':date(x.get('date_published') or x.get('date_modified')),'author':', '.join(a.get('name','') for a in authors if isinstance(a,dict)) or None,'summary':clean(x.get('summary') or x.get('content_text') or x.get('content_html'))[:2000]})
  return {'format':'jsonfeed','title':clean(doc.get('title')),'entries':out}
 root=ET.fromstring(data); tag=root.tag.rsplit('}',1)[-1].lower(); out=[]
 if tag=='feed':
  for e in root.findall('atom:entry',NS):
   links=[x.get('href') for x in e.findall('atom:link',NS) if x.get('href') and x.get('rel','alternate')=='alternate']
   out.append({'title':clean(text(e,'atom:title')),'link':links[0] if links else None,'published':date(text(e,'atom:published','atom:updated')),'author':clean(text(e,'atom:author/atom:name','dc:creator')) or None,'summary':clean(text(e,'atom:summary','atom:content'))[:2000]})
  return {'format':'atom','title':clean(text(root,'atom:title')),'entries':out}
 channel=root.find('channel') if tag=='rss' else root
 if channel is None:raise ValueError('unrecognised feed')
 items=channel.iter('item') if tag=='rss' else root.iter('{http://purl.org/rss/1.0/}item')
 for e in items:out.append({'title':clean(text(e,'title','{http://purl.org/rss/1.0/}title')),'link':(text(e,'link','{http://purl.org/rss/1.0/}link') or '').strip() or None,'published':date(text(e,'pubDate','dc:date')),'author':clean(text(e,'dc:creator','author')) or None,'summary':clean(text(e,'content:encoded','description','{http://purl.org/rss/1.0/}description'))[:2000]})
 return {'format':'rss','title':clean(text(channel,'title','{http://purl.org/rss/1.0/}title')),'entries':out}
def looks(data,ctype):
 h=data.lstrip()[:300].lower();return (h.startswith(b'{') and b'items' in data[:2000]) or b'<rss' in h or b'<feed' in h or b'<rdf' in h
def discover(url,body=None):
 if body is None:body,_=fetch(url)
 s=body.decode('utf-8','replace'); found=[]
 for m in re.finditer(r'<link\b[^>]*>',s,re.I):
  t=m.group(0); typ=re.search(r'''type\s*=\s*["']([^"']+)''',t,re.I); href=re.search(r'''href\s*=\s*["']([^"']+)''',t,re.I); rel=re.search(r'''rel\s*=\s*["']([^"']+)''',t,re.I)
  if href and typ and typ.group(1).lower() in TYPES and (not rel or 'alternate' in rel.group(1).lower()):
   u=urllib.parse.urljoin(url,html.unescape(href.group(1)))
   if u not in found:found.append(u)
 if found:return found
 p=urllib.parse.urlsplit(url);base=f'{p.scheme}://{p.netloc}';return [base+x for x in PATHS]
def read(url):
 data,ctype=fetch(url)
 if looks(data,ctype):f=parse(data,ctype);f['url']=url;return f
 for candidate in discover(url,data):
  try:d,c=fetch(candidate)
  except (urllib.error.URLError,OSError):continue
  if looks(d,c):f=parse(d,c);f['url']=candidate;f['discovered_from']=url;return f
 raise SystemExit(f'no feed found at {url}')
def main():
 ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='cmd',required=True);r=sub.add_parser('read');r.add_argument('url');r.add_argument('--limit',type=int,default=20);r.add_argument('--since');r.add_argument('--json',action='store_true');d=sub.add_parser('discover');d.add_argument('url');d.add_argument('--json',action='store_true');a=ap.parse_args()
 if a.cmd=='discover':
  x=discover(a.url);print(json.dumps(x,indent=2) if a.json else '\n'.join(x));return
 f=read(a.url);entries=f['entries']
 if a.since:
  cutoff=datetime.fromisoformat(a.since.replace('Z','+00:00'))
  if cutoff.tzinfo is None:cutoff=cutoff.replace(tzinfo=timezone.utc)
  entries=[e for e in entries if e['published'] and datetime.fromisoformat(e['published'])>=cutoff]
 entries.sort(key=lambda e:e['published'] or '',reverse=True);f['entries']=entries[:a.limit]
 if a.json:print(json.dumps(f,indent=2,ensure_ascii=False))
 else:
  print(f"{f.get('title') or '(untitled feed)'} [{f['format']}] {f['url']}")
  for e in f['entries']:print(f"- {(e['published'] or '')[:10]} {e['title'] or '(no title)'}\n  {e['link'] or ''}")
if __name__=='__main__':main()
