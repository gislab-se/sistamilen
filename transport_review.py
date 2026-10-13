"""Package the local transport review map for the main app without a second server."""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
MAP_ROOT = ROOT / 'prototypes' / 'fredriksberg_resor'
LINK = re.compile(r'<link rel="stylesheet" href="([^"]+)">')
SCRIPT = re.compile(r'<script defer src="([^"]+)"></script>')


def local_asset(relative):
    path = (MAP_ROOT / relative).resolve()
    if not path.is_relative_to(MAP_ROOT.resolve()):
        raise ValueError('Map assets must stay inside the review directory')
    return path


def asset_signature():
    """Invalidate cached HTML when a map asset, download or method changes."""
    html = (MAP_ROOT / 'index.html').read_text(encoding='utf-8')
    names = ['index.html', 'README.md', 'data/adressmatchning.csv'] + LINK.findall(html) + SCRIPT.findall(html)
    names += [p.relative_to(MAP_ROOT).as_posix() for p in (MAP_ROOT / 'vendor/images').glob('*') if p.is_file()]
    return tuple((name, local_asset(name).stat().st_mtime_ns, local_asset(name).stat().st_size) for name in names)


def data_url(path):
    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    return 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode('ascii')


def embedded_map_html():
    """Inline trusted local assets, keeping script execution after DOM creation."""
    html = (MAP_ROOT / 'index.html').read_text(encoding='utf-8')

    def stylesheet(match):
        path = local_asset(match[1])
        css = path.read_text(encoding='utf-8')
        css = re.sub(r'url\(images/([^\)]+)\)', lambda image: 'url(' + data_url(path.parent / 'images' / image[1]) + ')', css)
        return '<style>\n' + css + '\n</style>'

    scripts = []

    def script(match):
        js = local_asset(match[1]).read_text(encoding='utf-8')
        js = re.sub('</script', r'<\\/script', js, flags=re.IGNORECASE)
        scripts.append('<script>\n' + js + '\n</script>')
        return ''

    html = LINK.sub(stylesheet, html)
    html = SCRIPT.sub(script, html)
    html = html.replace('href="./index.html"', 'href="#map"')
    html = html.replace('href="README.md"', 'download="Metod-transportanalys.md" href="' + data_url(MAP_ROOT / 'README.md') + '"')
    html = html.replace('href="data/adressmatchning.csv"', 'href="' + data_url(MAP_ROOT / 'data/adressmatchning.csv') + '"')
    return html.replace('</body>', '\n'.join(scripts) + '\n</body>')
