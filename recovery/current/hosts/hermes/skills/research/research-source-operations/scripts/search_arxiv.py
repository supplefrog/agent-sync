#!/usr/bin/env python3
"""Search arXiv and display results in a clean format."""
import sys
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
NS = {'a': 'http://www.w3.org/2005/Atom'}
def search(query=None, author=None, category=None, ids=None, max_results=5, sort='relevance'):
    params = {}
    if ids:
        params['id_list'] = ids
    else:
        parts = []
        if query: parts.append(f'all:{urllib.parse.quote(query)}')
        if author: parts.append(f'au:{urllib.parse.quote(author)}')
        if category: parts.append(f'cat:{category}')
        if not parts: raise SystemExit('provide a query, --author, --category, or --id')
        params['search_query'] = '+AND+'.join(parts)
    params['max_results'] = str(max_results)
    params['sortBy'] = {'relevance':'relevance','date':'submittedDate','updated':'lastUpdatedDate'}.get(sort, sort)
    params['sortOrder'] = 'descending'
    url = 'https://export.arxiv.org/api/query?' + '&'.join(f'{k}={v}' for k,v in params.items())
    req = urllib.request.Request(url, headers={'User-Agent':'HermesAgent/1.0'})
    with urllib.request.urlopen(req, timeout=15) as resp: data = resp.read()
    root = ET.fromstring(data); entries = root.findall('a:entry', NS)
    if not entries: print('No results found.'); return
    total = root.find('{http://a9.com/-/spec/opensearch/1.1/}totalResults')
    if total is not None: print(f'Found {total.text} results (showing {len(entries)})\n')
    for i, entry in enumerate(entries):
        title = entry.find('a:title', NS).text.strip().replace('\n',' ')
        full_id = entry.find('a:id', NS).text.strip().split('/abs/')[-1]
        published = entry.find('a:published', NS).text[:10]; updated = entry.find('a:updated', NS).text[:10]
        authors = ', '.join(a.find('a:name', NS).text for a in entry.findall('a:author', NS))
        summary = entry.find('a:summary', NS).text.strip().replace('\n',' ')
        cats = ', '.join(c.get('term') for c in entry.findall('a:category', NS))
        print(f'{i+1}. {title}\n   ID: {full_id} | Published: {published} | Updated: {updated}\n   Authors: {authors}\n   Categories: {cats}\n   Abstract: {summary[:300]}{"..." if len(summary)>300 else ""}\n   Links: https://arxiv.org/abs/{full_id} | https://arxiv.org/pdf/{full_id}\n')
if __name__ == '__main__':
    args=sys.argv[1:]
    if not args or args[0] in {'-h','--help'}: print(__doc__); raise SystemExit()
    query=author=category=ids=None; max_results=5; sort='relevance'; positional=[]; i=0
    while i<len(args):
        if args[i]=='--max' and i+1<len(args): max_results=int(args[i+1]); i+=2
        elif args[i]=='--sort' and i+1<len(args): sort=args[i+1]; i+=2
        elif args[i]=='--author' and i+1<len(args): author=args[i+1]; i+=2
        elif args[i]=='--category' and i+1<len(args): category=args[i+1]; i+=2
        elif args[i]=='--id' and i+1<len(args): ids=args[i+1]; i+=2
        else: positional.append(args[i]); i+=1
    if positional: query=' '.join(positional)
    search(query,author,category,ids,max_results,sort)
