import re, sys, glob, json
from bs4 import BeautifulSoup, Comment
CZ = re.compile(r'[ěščřžýáíéůúťďňĚŠČŘŽÝÁÍÉŮÚŤĎŇ]')
CZW = re.compile(r'\b(je|se|pro|nebo|jak|kdy|vám|nás|podle|jen|při|bez|aby|také|ale|který|která|které|jsou|není|vás|si)\b')
out = {}
only = sys.argv[1:] 
for f in sorted(glob.glob(str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'pipeline/templates/premium/*.en.html.j2'))):
    pid = f.split('/')[-1].split('.')[0]
    if only and pid not in only: continue
    s = open(f, encoding='utf-8').read()
    soup = BeautifulSoup(s, 'html.parser')
    left = []
    for t in soup.find_all(string=True):
        if isinstance(t, Comment) or t.parent.name in ('style',): continue
        if t.parent.name == 'script':
            code = re.sub(r'/\*.*?\*/', '', str(t), flags=re.S); code = re.sub(r'(?m)//.*$', '', code)
            for m in re.finditer(r"'([^'\n]*)'|\"([^\"\n]*)\"|`([^`]*)`", code):
                x = m.group(1) or m.group(2) or m.group(3) or ''
                if CZ.search(x) and len(x) < 400: left.append('JS::' + x)
            continue
        n = re.sub(r'\s+', ' ', str(t).replace(' ', ' ')).strip()
        if n and (CZ.search(n) or (len(n) > 25 and len(CZW.findall(n)) >= 2)): left.append(n)
    for el in soup.find_all(True):
        for k in ('alt', 'aria-label', 'title', 'placeholder', 'content'):
            v = el.get(k)
            if isinstance(v, str) and CZ.search(v): left.append('ATTR::' + v)
    out[pid] = list(dict.fromkeys(left))
json.dump(out, open('/tmp/left.json', 'w'), ensure_ascii=False, indent=0)
for k, v in out.items(): print(k, len(v))
