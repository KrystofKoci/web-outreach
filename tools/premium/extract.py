import sys, re, json
sys.path.insert(0, '.')
from bs4 import BeautifulSoup, Comment
from pages import PAGES
from build import V2, rewrite_assets
from engine import process_doplnit
import build
CZ = re.compile(r'[A-Za-zÁ-ž]')
def strings(cfg):
    raw = (V2 / cfg['src']).read_text(encoding='utf-8')
    for a, b in cfg.get('pre', []): raw = raw.replace(a, b)
    for a, b in cfg.get('regex_pre', []): raw = re.sub(a, b, raw, flags=re.S)
    soup = BeautifulSoup(raw, 'html.parser')
    for sel in cfg.get('remove', []):
        for el in soup.select(sel): el.decompose()
    for c in soup.find_all(string=lambda x: isinstance(x, Comment)): c.extract()
    process_doplnit(soup, cfg, [])
    out = []
    for t in soup.find_all(string=True):
        if t.parent is None or t.parent.name in ('script', 'style', 'title'): continue
        n = re.sub(r'\s+', ' ', str(t)).strip()
        if n and CZ.search(n) and '@@' not in n.replace('@@V', ''): out.append(n)
        elif n and CZ.search(n): out.append(n)
    for el in soup.find_all(True):
        for k in ('alt', 'aria-label', 'title', 'placeholder', 'data-label'):
            v = el.get(k)
            if isinstance(v, str) and CZ.search(v): out.append(re.sub(r'\s+', ' ', v).strip())
    js = []
    for sc in soup.find_all('script'):
        code = sc.string or ''
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.S); code = re.sub(r'(?m)^\s*//.*$', '', code)
        for m in re.finditer(r"'([^'\n]*[ěščřžýáíéůúťďňĚŠČŘŽÝÁÍÉŮÚ][^'\n]*)'|\"([^\"\n]*[ěščřžýáíéůúťďňĚŠČŘŽÝÁÍÉŮÚ][^\"\n]*)\"|`([^`]*[ěščřžýáíéůúťďňĚŠČŘŽÝÁÍÉŮÚ][^`]*)`", code):
            js.append(m.group(1) or m.group(2) or m.group(3))
    seen = set(); o2 = []
    for x in out:
        if x not in seen: seen.add(x); o2.append(x)
    return o2, list(dict.fromkeys(js))
allt = {}
for cfg in PAGES:
    t, j = strings(cfg)
    allt[cfg['id']] = {'text': t, 'js': j}
json.dump(allt, open('/tmp/strings.json', 'w'), ensure_ascii=False, indent=0)
for k, v in allt.items(): print(k, len(v['text']), len(v['js']), sum(len(x) for x in v['text'] + v['js']))
