#!/usr/bin/env python3
"""Recover blocked pages from archives or keyed Jina rendering."""
from __future__ import annotations
import argparse,json,os,re,sys,time,urllib.error,urllib.parse,urllib.request
UA='Mozilla/5.0'; HOSTS=['archive.ph','archive.md','archive.li','archive.is']; BAD=('just a moment','redirecting','google search','attention required','access denied','are you a robot','one more step')
def fetch(url,timeout,headers=None,follow=False):
 req=urllib.request.Request(url,headers={'User-Agent':UA,**(headers or {})})
 for attempt in range(3):
  try:
   with urllib.request.urlopen(req,timeout=timeout) as r:return r.status,r.read(),r.geturl()
  except urllib.error.HTTPError as e:
   if e.code==429 and attempt<2:time.sleep(5*(attempt+1));continue
   return e.code,e.read() if e.fp else b'',e.geturl() or url
  except (urllib.error.URLError,OSError,ValueError):return 0,b'',url
def valid(body,route,target):
 floor=512 if route=='jina' else 3072
 if len(body)<floor:return False
 m=re.search(r'<title[^>]*>(.*?)</title>',body[:65536].decode('utf-8','replace'),re.I|re.S); title=re.sub(r'\s+',' ',m.group(1)).lower() if m else ''
 if any(x in title for x in BAD):return False
 if len(body)<8192 and re.search(r'http-equiv=["\']?refresh|window\.location|location\.replace',body.decode('utf-8','replace'),re.I):
  host=urllib.parse.urlsplit(target).hostname or ''
  if host.encode() in body:return False
 return True
def recover(url,timeout=25):
 api='https://archive.org/wayback/available?url='+urllib.parse.quote(url,safe='');status,raw,_=fetch(api,timeout);snap=None;stamp=None
 if status==200:
  try:c=json.loads(raw).get('archived_snapshots',{}).get('closest',{});snap=c.get('url') if c.get('available') else None;stamp=c.get('timestamp')
  except Exception:pass
 snap=(snap or 'https://web.archive.org/web/2/'+url).replace('http://web.archive.org','https://web.archive.org');status,body,final=fetch(snap,timeout,follow=True)
 if status==200 and valid(body,'archive',url):return {'route':'wayback','provenance':'snapshot','snapshot_timestamp':stamp,'source_url':final,'body':body}
 for host in HOSTS:
  u=f'https://{host}/newest/{url}';status,body,_=fetch(u,timeout)
  if status==200 and valid(body,'archive',url):return {'route':f'archive_today:{host}','provenance':'snapshot','snapshot_timestamp':None,'source_url':u,'body':body}
 key=os.environ.get('JINA_API_KEY')
 if key:
  u='https://r.jina.ai/'+url;status,body,_=fetch(u,timeout,{'Authorization':f'Bearer {key}'})
  if status==200 and valid(body,'jina',url):return {'route':'jina_reader','provenance':'live','snapshot_timestamp':None,'source_url':u,'body':body}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('url');ap.add_argument('--json',action='store_true');ap.add_argument('--out');ap.add_argument('--timeout',type=int,default=25);a=ap.parse_args()
 if not a.url.startswith(('http://','https://')):raise SystemExit('URL must start with http:// or https://')
 r=recover(a.url,a.timeout)
 if not r:print('No archive copy found; try an API/feed pivot or browser.',file=sys.stderr);raise SystemExit(1)
 body=r.pop('body');r.update({'recovered':True,'url':a.url,'body_bytes':len(body)})
 if a.out:open(a.out,'wb').write(body);r['saved_to']=a.out
 print(json.dumps(r,indent=2) if a.json else '\n'.join(f'{k}: {v}' for k,v in r.items()))
 if r['provenance']=='snapshot':print('NOTE: archived snapshot, not the live page; cite its timestamp.',file=sys.stderr)
if __name__=='__main__':main()
