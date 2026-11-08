"""Převod schválených HTML návrhů (vzory2) na Jinja2 šablony pipeline (premium).

Tokeny v mezivýstupu:  @@V x@@ -> {{ x }},  @@IF c@@ -> {% if c %},  @@ENDIF@@ -> {% endif %},
@@RAW x@@ -> {{ x|safe }}.  Vše ostatní ve stylu {{ / {% / {# je escapováno.
"""
from __future__ import annotations
import re, os, shutil, json
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Comment, Tag

DOPL = '[doplnit]'
ROW_STOP = {'section', 'body', 'main', 'header', 'footer', 'nav', 'ul', 'ol', 'dl', 'form', 'article', 'html'}
DAYS = {
    'pondělí': 0, 'úterý': 1, 'středa': 2, 'čtvrtek': 3, 'pátek': 4, 'sobota': 5, 'neděle': 6,
    'po': 0, 'út': 1, 'st': 2, 'čt': 3, 'pá': 4, 'so': 5, 'ne': 6,
}


def txt(el) -> str:
    return re.sub(r'\s+', ' ', el.get_text(' ', strip=True) if isinstance(el, Tag) else str(el)).strip()


def label_of(el) -> str:
    return txt(el).replace(DOPL, '').strip(' :·–-')


def row_of(node):
    """Nejbližší malý „řádek“ obsahující doplnit (li, dd, p, a, span...)."""
    cur = node
    while cur.parent is not None and cur.parent.name not in ROW_STOP:
        par = cur.parent
        if len(label_of(par)) > 34 or par.get_text().count(DOPL) > 1 \
                or par.find(['button', 'input', 'select', 'textarea', 'nav']) is not None:
            break
        cur = par
    return cur


def wrap_if(el, cond: str, start=None):
    (start if start is not None else el).insert_before(NavigableString(f'@@IF {cond}@@'))
    el.insert_after(NavigableString('@@ENDIF@@'))


def remove_row(row):
    if row.name == 'dd':
        dt = row.find_previous_sibling()
        if dt is not None and dt.name == 'dt':
            dt.decompose()
    par = row.parent
    row.decompose()
    # prázdný obal (div s dt/dd) pryč
    while par is not None and par.name in ('div', 'li', 'p', 'span') and not txt(par) and not par.find(['img', 'svg', 'input', 'select', 'textarea', 'button']):
        nxt = par.parent
        par.decompose()
        par = nxt


def classify(label: str, el) -> str:
    l = label.lower()
    a = el if el.name == 'a' else el.find_parent('a')
    if a is not None and (a.get('href') or '').startswith('tel:'):
        return 'phone'
    if a is not None and (a.get('href') or '').startswith('mailto:'):
        return 'email'
    if el.get('data-doplnit') == 'mesto':
        return 'city'
    cls = ' '.join(el.get('class') or [])
    if 'cena' in cls or el.get('data-cena') is not None or el.find_parent(attrs={'data-cena': True}) is not None:
        return 'price'
    first = l.split(' ')[0] if l else ''
    if first in DAYS and len(l) <= 12:
        return 'day'
    if re.search(r'z\s*5\b', l) or 'hodnocení' in l:
        return 'rating'
    if 'recenz' in l:
        return 'rcount'
    if re.search(r'\b(tel\.?|telefon|zavolat|phone)\b', l):
        return 'phone'
    if 'e-mail' in l or l == 'email':
        return 'email'
    if re.search(r'^(okolí|město|působíme)\b', l):
        return 'city'
    if re.search(r'^(mapa|map)\b', l):
        return 'maps'
    if re.search(r'^(adresa|sídlo)\b', l):
        return 'address'
    if re.search(r'(otevřeno|otevírací doba|dnes otevřeno)$', l) or l in ('otevřeno', 'otevírací doba'):
        return 'today'
    return 'remove'


def _wrap_bare(soup):
    for t in list(soup.find_all(string=re.compile(r'\[doplnit\]'))):
        if t.parent is None or t.parent.name in ('script', 'style') or isinstance(t, Comment):
            continue
        p = t.parent
        if 'doplnit' in (p.get('class') or []) and p.get_text().strip() == DOPL:
            continue
        parts = str(t).split(DOPL)
        for i, part in enumerate(parts):
            if part:
                t.insert_before(NavigableString(part))
            if i < len(parts) - 1:
                sp = soup.new_tag('span'); sp['class'] = ['doplnit']; sp.string = DOPL; t.insert_before(sp)
        t.extract()


def _price(sp, row):
    sp.replace_with(NavigableString('@@PRICE@@'))
    anc = None
    for cand in [row] + list(row.parents)[:4]:
        if cand is None or cand.name in ('body', 'html', '[document]'):
            break
        if '@@PRICE@@' in cand.decode_contents():
            anc = cand
            if re.search(r'(\bod\b|Kč|Cena)', cand.get_text(' ')):
                break
    if anc is None:
        return
    raw = anc.decode_contents()
    raw2 = re.sub(r'(?:\b[oO]d|Cena)?(?:\s|&nbsp;|\u00a0)*((?:<[^>]+>)*)@@PRICE@@((?:</[^>]+>)*)(?:\s|&nbsp;|\u00a0)*(?:Kč)?',
                  r'\1@@V price_text@@\2', raw)
    anc.clear()
    for n in list(BeautifulSoup(raw2, 'html.parser').contents):
        anc.append(n)


def _put(sp, token):
    if sp.name == 'span' and (sp.get('class') or []) == ['doplnit'] and len(sp.attrs) == 1:
        n = NavigableString(token)
        sp.replace_with(n)
        return n
    else:
        sp['class'] = [c for c in (sp.get('class') or []) if c != 'doplnit']
        if not sp['class']:
            del sp['class']
        sp.clear(); sp.append(NavigableString(token))
        return sp


def _apply(sp, row, lab, kind, hours_parents, rating_secs, prices_off, start=None):
    if kind == 'phone':
        a = sp if sp.name == 'a' else sp.find_parent('a')
        _n = _put(sp, '@@V phone@@')
        row = _n if row is sp else row
        if a is not None:
            a['href'] = 'tel:@@V phone_href@@'
        wrap_if(row, 'phone', start)
    elif kind == 'email':
        a = sp.find_parent('a')
        _n = _put(sp, '@@V email@@')
        row = _n if row is sp else row
        if a is not None:
            a['href'] = 'mailto:@@V email@@'
        wrap_if(row, 'email', start)
    elif kind == 'address':
        _n = _put(sp, '@@V address@@')
        row = _n if row is sp else row
        wrap_if(row, 'address', start)
    elif kind == 'city':
        _n = _put(sp, '@@V city@@')
        row = _n if row is sp else row
        if row is not sp:
            wrap_if(row, 'city', start)
    elif kind == 'maps':
        a = sp.find_parent('a')
        _n = _put(sp, '@@V t_map@@')
        row = _n if row is sp else row
        if a is not None:
            a['href'] = '@@V maps_url@@'; a['target'] = '_blank'; a['rel'] = 'noopener'
        wrap_if(row, 'maps_url', start)
    elif kind == 'today':
        _n = _put(sp, '@@V hours_today@@')
        row = _n if row is sp else row
        wrap_if(row, 'hours_today', start)
    elif kind == 'day':
        d = DAYS[lab.lower().split(' ')[0]]
        _n = _put(sp, f'@@V hday[{d}]@@')
        row = _n if row is sp else row
        if row.parent not in hours_parents:
            hours_parents.append(row.parent)
    elif kind == 'rating':
        _n = _put(sp, '@@V rating_txt@@')
        row = _n if row is sp else row
        sec = row.find_parent('section') or row.parent
        if sec is not None and sec not in rating_secs:
            rating_secs.append(sec)
    elif kind == 'rcount':
        _n = _put(sp, '@@V rating_count@@')
        row = _n if row is sp else row
        wrap_if(row, 'show_count', start)
    elif kind == 'price':
        if prices_off:
            sp.decompose()
        else:
            _price(sp, row)
    else:
        if start is not None:
            start.decompose()
        remove_row(row)


def process_doplnit(soup, cfg, log):
    hours_parents, rating_secs = [], []
    prices_off = cfg.get('prices') == 'hide'
    _wrap_bare(soup)
    for _ in range(800):
        zbyva = [x for x in soup.select('.doplnit') if x.get_text().strip().startswith('[doplnit') and x.parent is not None]
        if not zbyva:
            break
        sp = zbyva[0]
        row = row_of(sp)
        lab = label_of(row)
        if not lab and row.name in ('dd', 'td'):
            pr = row.find_previous_sibling(['dt', 'th'])
            lab = label_of(pr) if pr is not None else ''
        start = None
        if row is sp and not lab:
            pe = sp.previous_sibling
            while isinstance(pe, NavigableString) and not str(pe).strip():
                pe = pe.previous_sibling
            if isinstance(pe, Tag) and pe.name in ('b', 'strong', 'dt', 'label', 'em', 'span', 'small') and 0 < len(txt(pe)) <= 30:
                lab = txt(pe); start = pe
        kind = classify(lab, sp)
        if kind == 'remove' and row is sp and start is None:
            prev = sp.previous_sibling
            ptxt = str(prev)[-30:] if isinstance(prev, NavigableString) else ''
            kind = classify(ptxt.strip(), sp) if ptxt.strip() else 'remove'
            if kind == 'remove':
                log.append(('VETA', txt(sp.parent)[:140]))
        _apply(sp, row, lab, kind, hours_parents, rating_secs, prices_off, start)
    for hp in hours_parents:
        wrap_if(hp, 'hours')
    for rs in rating_secs:
        wrap_if(rs, 'rating')
    for el in list(soup.find_all(True)):
        for k, v in list(el.attrs.items()):
            if isinstance(v, str) and 'doplnit' in v:
                lv = v.lower()
                if k == 'href' and 'wa.me' in lv:
                    el['href'] = 'https://wa.me/@@V wa_digits@@'
                    wrap_if(el, 'wa_digits')
                elif re.search(r'(tel|zavolat|phone)', lv):
                    el[k] = re.sub(r'\[?doplnit\]?', '@@V phone@@', v)
                else:
                    el[k] = re.sub(r'\s*[:–-]?\s*\[?doplnit\]?', '', v).strip()
    return log

ESC_RE = re.compile(r'\{[{%#]')


def finalize(html: str) -> str:
    html = ESC_RE.sub(lambda m: '{{ "%s" }}' % m.group(0), html)
    html = re.sub(r'@@V ([^@]+)@@', r'{{ \1 }}', html)
    html = re.sub(r'@@RAW ([^@]+)@@', r'{{ \1|safe }}', html)
    html = re.sub(r'@@IF ([^@]+)@@', r'{% if \1 %}', html)
    html = html.replace('@@ENDIF@@', '{% endif %}')
    html = html.replace('@@ELSE@@', '{% else %}')
    return html
