"""Embed the independent public DVA map without loading transport records."""
from pathlib import Path
import re

from transport_review import LINK, SCRIPT, data_url

MAP_ROOT=Path(__file__).resolve().parent/'prototypes/dva_transportnarvaro'


def asset_signature():
    html=(MAP_ROOT/'index.html').read_text(encoding='utf-8')
    names=['index.html','README.md']+LINK.findall(html)+SCRIPT.findall(html)
    names += [p.relative_to(MAP_ROOT).as_posix() for p in (MAP_ROOT/'vendor/images').glob('*') if p.is_file()]
    return tuple((name,(MAP_ROOT/name).stat().st_mtime_ns,(MAP_ROOT/name).stat().st_size) for name in names)


def embedded_map_html():
    html=(MAP_ROOT/'index.html').read_text(encoding='utf-8')
    scripts=[]

    def stylesheet(match):
        path=MAP_ROOT/match[1]
        css=path.read_text(encoding='utf-8')
        css=re.sub(r'url\(images/([^\)]+)\)',lambda image:'url('+data_url(path.parent/'images'/image[1])+')',css)
        return '<style>\n'+css+'\n</style>'

    def script(match):
        js=(MAP_ROOT/match[1]).read_text(encoding='utf-8')
        js=re.sub('</script',r'<\\/script',js,flags=re.IGNORECASE)
        scripts.append('<script>\n'+js+'\n</script>')
        return ''

    html=LINK.sub(stylesheet,html)
    html=SCRIPT.sub(script,html)
    html=html.replace('href="README.md"','download="Metod-sophamtningskarta.md" href="'+data_url(MAP_ROOT/'README.md')+'"')
    return html.replace('</body>','\n'.join(scripts)+'\n</body>')
