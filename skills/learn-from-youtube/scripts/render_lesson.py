"""Optional offline Markdown reader. No course-specific inputs or synthesis.

Requires markdown, beautifulsoup4 and Pillow. Local images stay byte-identical;
remote images, escaping asset paths and active source HTML are not accepted.
"""
import argparse
import base64
import html
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import markdown
from bs4 import BeautifulSoup
from PIL import Image

ASSETS = Path(__file__).resolve().parent.parent / 'assets'
ALLOWED = set('h1 h2 h3 h4 h5 h6 p a strong em b i s del ul ol li blockquote pre code hr br table thead tbody tr th td img details summary div span sup sub dl dt dd'.split())


def image_info(path):
    data = path.read_bytes()
    if path.suffix.lower() == '.svg':
        text = data.decode('utf-8')
        if re.search(r'<!DOCTYPE|<!ENTITY|<\?(?!xml\s)', text, re.I):
            raise ValueError('SVG declarations are not supported')
        # Declarations/entities are rejected above, before the bounded XML parse.
        root = ET.fromstring(text)
        for element in root.iter():
            if element.tag.split('}')[-1].lower() not in {
                    'svg', 'g', 'defs', 'title', 'desc', 'path', 'rect', 'circle', 'ellipse',
                    'line', 'polyline', 'polygon', 'text', 'tspan', 'textpath', 'use',
                    'clippath', 'mask', 'marker', 'lineargradient', 'radialgradient', 'stop', 'pattern'}:
                raise ValueError('Active SVG is not supported')
            for key, value in element.attrib.items():
                key = key.split('}')[-1].lower()
                if key.startswith('on') or (key == 'href' and not value.startswith('#')) or re.search(r'url\(\s*[\"\x27]?(?!#)', value, re.I):
                    raise ValueError('SVG links/events are not supported')
        view = root.get('viewBox', '').replace(',', ' ').split()
        if len(view) != 4 or float(view[2]) <= 0 or float(view[3]) <= 0:
            raise ValueError('SVG requires a positive viewBox')
        return data, 'image/svg+xml', float(view[2]), float(view[3])
    with Image.open(path) as image:
        dimensions = image.size
        mime = Image.MIME[image.format]
        image.verify()
    return data, mime, *dimensions


def render(manuscript, target):
    manuscript, target = Path(manuscript).resolve(), Path(target).resolve()
    if manuscript == target or target.exists():
        raise ValueError('Choose a new output file; source and existing outputs are protected')
    text = manuscript.read_text(encoding='utf-8')
    if len(text.encode('utf-8')) > 2_000_000:
        raise ValueError('Manuscript exceeds 2 MB')
    soup = BeautifulSoup(markdown.markdown(text, extensions=['tables', 'toc', 'md_in_html', 'footnotes']), 'html.parser')
    # Source-derived HTML is data, not executable UI code.
    for tag in list(soup.find_all(['script', 'style', 'iframe', 'object', 'embed', 'base', 'link', 'meta', 'form'])):
        tag.decompose()
    for tag in list(soup.find_all(True)):
        if tag.name not in ALLOWED:
            tag.unwrap()
            continue
        for key in list(tag.attrs):
            if key not in {'id', 'href', 'src', 'alt', 'title', 'colspan', 'rowspan', 'start'}:
                del tag[key]
        if tag.name == 'a':
            href = tag.get('href', '').strip()
            if urlsplit(href).scheme.lower() not in {'', 'https', 'http'}:
                del tag['href']
    titles = soup.find_all('h1')
    if len(titles) != 1:
        raise ValueError('Use exactly one top-level title')
    ids = [tag['id'] for tag in soup.select('[id]')]
    if len(ids) != len(set(ids)) or set(ids) & {'reading', 'figure-dialog', 'figure-title', 'figure-size', 'figure-close'}:
        raise ValueError('Duplicate or reserved ID')
    for anchor in soup.select('a[href^="#"]'):
        if anchor['href'][1:] not in ids:
            raise ValueError('Broken in-document reference: ' + anchor['href'])
    total = 0
    for image in list(soup.find_all('img')):
        src = image.get('src', '')
        path = (manuscript.parent / src).resolve()
        if re.match(r'^[a-zA-Z][\w+.-]*:', src) or not path.is_relative_to(manuscript.parent):
            raise ValueError('Images must be local to the manuscript workspace')
        total += path.stat().st_size
        if total > 20_000_000:
            raise ValueError('Image input budget exceeds 20 MB')
        data, mime, width, height = image_info(path)
        if not image.get('alt', '').strip():
            raise ValueError('Every teaching image needs alternative text')
        image['src'] = f'data:{mime};base64,' + base64.b64encode(data).decode('ascii')
        image['width'], image['height'] = str(width), str(height)
        image['loading'] = 'lazy'
        figure = soup.new_tag('figure')
        parent = image.parent
        if parent.name == 'p' and not parent.get_text(strip=True) and len(parent.find_all('img')) == 1:
            parent.replace_with(figure)
        else:
            image.replace_with(figure)
        button = soup.new_tag('button', attrs={'type':'button','class':'zoom','aria-haspopup':'dialog','aria-controls':'figure-dialog','aria-label':'Enlarge: '+image['alt']})
        button.append(image.extract())
        hint = soup.new_tag('span', attrs={'class':'zoom-hint','aria-hidden':'true'})
        hint.string = 'Enlarge figure ↗'
        button.append(hint)
        figure.append(button)
        following = figure.find_next_sibling()
        if following and following.name == 'p' and following.find('em') and following.get_text(strip=True) == following.find('em').get_text(strip=True):
            caption = soup.new_tag('figcaption')
            for node in list(following.find('em').contents):
                caption.append(node.extract())
            figure.append(caption)
            following.decompose()
    for table in soup.find_all('table'):
        for header in table.find_all('th'):
            header['scope'] = 'col'
        table.wrap(soup.new_tag('div', attrs={'class':'table-scroll','tabindex':'0','aria-label':'Comparison table; scroll if needed'}))
    headings = soup.find_all(['h2', 'h3'])
    for heading in headings:
        heading['tabindex'] = '-1'
    if headings:
        links = ''.join(f'<li><a href="#{html.escape(h["id"], quote=True)}">{html.escape(h.get_text())}</a></li>' for h in headings if h.get('id'))
        headings[0].insert_before(BeautifulSoup('<div class="reading-tools"><details class="contents"><summary>Explore the sections</summary><nav aria-label="Lesson contents"><ul>'+links+'</ul></nav></details></div>', 'html.parser'))
    title = html.escape(titles[0].get_text())
    style, script = ((ASSETS / name).read_text(encoding='utf-8') for name in ['reader.css', 'reader.js'])
    dialog = '<dialog id="figure-dialog" aria-labelledby="figure-title"><div class="dialog-head"><span id="figure-title">Figure detail</span><div class="zoom-actions"><button id="figure-size" type="button" aria-pressed="false">Actual size</button><button id="figure-close" type="button" autofocus>Close</button></div></div><div class="image-view"></div></dialog>'
    page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>'+style+'</style></head><body><a class="skip" href="#reading">Skip to lesson</a><main id="reading" tabindex="-1">'+str(soup)+'</main>'+dialog+'<script>'+script+'</script></body></html>'
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8') as output:
        output.write(page)
    return {'output':str(target),'image_count':len(soup.find_all('img')),'bytes':target.stat().st_size,'semantic_review':False}


def main():
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manuscript', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(render(args.manuscript, args.output), indent=2))
    except (OSError, ValueError, ET.ParseError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
