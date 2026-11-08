"""EN překlady: slovníky en/*.json (sloučené) – text uzly a atributy přes BeautifulSoup,
řetězce v JS: klíče "__js__" (přesná náhrada uvnitř <script>) + citované texty ze slovníku."""
import json, re
from pathlib import Path
from bs4 import NavigableString, Comment

D = Path(__file__).parent / 'en'
_T, _J, _R = {}, {}, {}


def _norm(s):
    return re.sub(r'\s+', ' ', s.replace(' ', ' ')).strip()


def _load():
    if _T:
        return
    for f in sorted(D.glob('*.json')):
        d = json.loads(f.read_text(encoding='utf-8'))
        _J.update(d.pop('__js__', {}))
        _R.update(d.pop('__raw__', {}))
        _T.update({_norm(k): v for k, v in d.items()})


def apply_raw(pid, raw):
    _load()
    for a, b in sorted(_R.items(), key=lambda x: -len(x[0])):
        raw = raw.replace(a, b)
    return raw


def apply_soup(pid, soup):
    _load()
    for t in list(soup.find_all(string=True)):
        if t.parent is None or t.parent.name in ('script', 'style') or isinstance(t, Comment):
            continue
        s = str(t)
        n = _norm(s)
        if n in _T:
            lead = ' ' if s[:1].isspace() else ''
            trail = ' ' if s[-1:].isspace() else ''
            t.replace_with(NavigableString(lead + _T[n] + trail))
    for el in soup.find_all(True):
        for k in ('alt', 'aria-label', 'title', 'content', 'placeholder', 'data-label', 'data-ok', 'data-err'):
            v = el.get(k)
            if isinstance(v, str) and _norm(v) in _T:
                el[k] = _T[_norm(v)]


MISSING = {}


def apply_post(pid, html):
    _load()
    def fix(m):
        code = m.group(2)
        for a, b in sorted(_J.items(), key=lambda x: -len(x[0])):
            code = code.replace(a, b)
        for a, b in _T.items():
            if len(a) < 4:
                continue
            for q in ("'", '"', '`'):
                if q + a + q in code:
                    bb = b.replace(q, "\\" + q) if q != '`' else b
                    code = code.replace(q + a + q, q + bb + q)
        return m.group(1) + code + m.group(3)
    html = re.sub(r'(<script\b[^>]*>)(.*?)(</script>)', fix, html, flags=re.S)
    return html
