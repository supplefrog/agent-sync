"""Repair PptxGenJS Node SVG fallbacks in freshly authored decks only.

Keeps the native SVG part; replaces SVG bytes mislabeled as PNG with real PNG.
No LibreOffice, remote service, or lasting rollback copy is used.
"""
from pathlib import Path
import os
import sys
import tempfile
import zipfile
import pymupdf


def normalize(path):
    path = Path(path)
    fixed = []
    fd, temporary = tempfile.mkstemp(suffix='.pptx', dir=path.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(temporary, 'w') as target:
            for info in source.infolist():
                data = source.read(info)
                if info.filename.startswith('ppt/media/') and info.filename.endswith('.png') and data.lstrip().startswith(b'<svg'):
                    with pymupdf.open(stream=data, filetype='svg') as svg:
                        data = svg[0].get_pixmap(alpha=True).tobytes('png')
                    fixed.append(info.filename)
                target.writestr(info, data)
        if fixed:
            os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return fixed


if __name__ == '__main__':
    import json
    print(json.dumps({'repaired_fallbacks': normalize(sys.argv[1])}))
