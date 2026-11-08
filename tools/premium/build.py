#!/usr/bin/env python3
"""Sestaví pipeline/templates/premium/<id>.<lang>.html.j2 a pipeline/premium_assets/<id>/ ze schválených návrhů.

python3 build.py  [--only id]
"""
from __future__ import annotations
import os, re, sys, json, shutil, glob
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Comment
sys.path.insert(0, str(Path(__file__).parent))
from engine import process_doplnit, finalize, txt, wrap_if
from common import common_blocks, EXT_CSS, extension_html
from pages import PAGES
import translate

V2 = Path(os.environ.get('VZORY_DIR', '/home/claude/ref/vzory2'))  # ruční návrhy (HTML + obrázky), nejsou v repu
OUT = Path(__file__).resolve().parents[2] / 'pipeline'
TPL = OUT / 'templates' / 'premium'
AST = OUT / 'premium_assets'


def rewrite_assets(raw: str, prefixes) -> str:
    for p in prefixes:
        raw = re.sub(r'(?<=["\'(`\s,=])' + re.escape(p), '@@V A@@' + p, raw)
    return raw


def collect_assets(cfg, html: str):
    base = (V2 / cfg['src']).parent
    dst = AST / cfg['id']
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    refs = set(re.findall(r'@@V A@@([\w./\-]+)', html))
    for d in cfg.get('asset_dirs', []):
        shutil.copytree(base / d, dst / d)
    missing = []
    for r in sorted(refs):
        r = r.rstrip('.')
        src = base / r
        if any(r.startswith(d.rstrip('/') + '/') for d in cfg.get('asset_dirs', [])):
            continue
        if src.is_file():
            (dst / r).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst / r)
        elif not src.exists():
            missing.append(r)
    return missing


def brandify(soup, names):
    pats = [(re.compile(r'(?<![\wÀ-ž])' + re.escape(n) + r'(?![\wÀ-ž])'), n) for n in names]
    def sub(s):
        for rx, n in pats:
            s = rx.sub('@@V brand_up@@' if n.isupper() and len(n) > 1 else '@@V brand@@', s)
        return s
    for t in list(soup.find_all(string=True)):
        if t.parent is None or t.parent.name in ('script', 'style') or isinstance(t, Comment):
            continue
        n = sub(str(t))
        if n != str(t):
            t.replace_with(NavigableString(n))
    for el in soup.find_all(True):
        for k in ('alt', 'aria-label', 'title', 'content', 'placeholder', 'value'):
            v = el.get(k)
            if isinstance(v, str):
                nv = sub(v)
                if nv != v:
                    el[k] = nv


def build_page(cfg, lang):
    raw = (V2 / cfg['src']).read_text(encoding='utf-8')
    for a, b in cfg.get('pre', []):
        if a not in raw:
            print('  !! pre nenalezeno:', cfg['id'], a[:60])
        raw = raw.replace(a, b)
    for a, b in cfg.get('post', []):
        raw = raw.replace(a, b)
    for a, b in cfg.get('regex_pre', []):
        raw, n = re.subn(a, b, raw, flags=re.S)
        if not n:
            print('  !! regex_pre nenalezeno:', cfg['id'], a)
    MESTO = r'<span class="doplnit" data-doplnit="mesto">\[doplnit[^\]]*\]</span>'
    raw = re.sub(r'\bv(?:\s|&nbsp;)+' + MESTO + r'(?:\s|&nbsp;)+a(?:\s|&nbsp;)+okolí', '@@V city_in@@', raw)
    raw = re.sub(r'Pro řidiče ' + MESTO + r' to vychází', 'Většinou to vychází', raw)
    raw = re.sub(r'řidiči ' + MESTO + r' ptají', 'řidiči @@V city_in@@ ptají', raw)
    raw = rewrite_assets(raw, cfg['assets'])
    if lang == 'en':
        raw = translate.apply_raw(cfg['id'], raw)
    soup = BeautifulSoup(raw, 'html.parser')
    # hlava
    if soup.html is not None:
        soup.html['lang'] = 'cs' if lang == 'cs' else 'en'
    if soup.title is not None:
        soup.title.string = '@@V page_title@@'
    md = soup.find('meta', attrs={'name': 'description'})
    if md is not None:
        md['content'] = '@@V meta_description@@'
    for sel in cfg.get('remove', []):
        for el in soup.select(sel):
            el.decompose()
    log = []
    process_doplnit(soup, cfg, log)
    brandify(soup, cfg['brand'])
    for sel, val in cfg.get('set_html', []):
        for el in soup.select(sel):
            el.clear(); el.append(BeautifulSoup(val, 'html.parser'))
    for sel, attr, val in cfg.get('set_attr', []):
        for el in soup.select(sel):
            el[attr] = val
    if lang == 'en':
        translate.apply_soup(cfg['id'], soup)
    for c in soup.find_all(string=lambda x: isinstance(x, Comment)):
        c.extract()
    # dostavba (dávka 1)
    if cfg.get('extension') or cfg.get('extension_after'):
        ext = BeautifulSoup(extension_html(cfg, lang), 'html.parser')
        if cfg.get('extension'):
            soup.select_one(cfg['extension']).insert_before(ext)
        else:
            soup.select_one(cfg['extension_after']).insert_after(ext)
    blocks = common_blocks(cfg, lang)
    # hodnocení + případná patička: před poslední <footer>, jinak na konec body
    foot = soup.find_all('footer')
    target = foot[-1] if foot else None
    rating_html = '' if cfg.get('own_rating') else blocks['rating']
    b = BeautifulSoup(rating_html + (blocks['footer'] if not foot or cfg.get('add_footer') else ''), 'html.parser')
    if target is not None and not cfg.get('add_footer'):
        target.insert_before(b)
    else:
        scripts = soup.body.find_all('script', recursive=False)
        (scripts[0].insert_before(b) if scripts else soup.body.append(b))
    soup.head.append(BeautifulSoup(blocks['css'] + (EXT_CSS if (cfg.get('extension') or cfg.get('extension_after')) else '')
                                   + ('<style>' + cfg['extra_css'] + '</style>' if cfg.get('extra_css') else ''), 'html.parser'))
    soup.body.append(BeautifulSoup(blocks['tail'], 'html.parser'))
    if soup.html is not None and cfg.get('html_attrs'):
        for k, v in cfg['html_attrs'].items():
            soup.html[k] = v
    html = str(soup)
    for a, b in cfg.get('post_html', []):
        if a not in html:
            print('  !! post_html nenalezeno', cfg['id'], a)
        html = html.replace(a, b)
    if lang == 'en':
        html = translate.apply_post(cfg['id'], html)
    if '[doplnit' in html:
        for m in re.finditer(r'\[doplnit', html):
            log.append(('ZBYTEK', html[max(0, m.start() - 90):m.start() + 30].replace('\n', ' ')))
    return finalize(html), log, html


def main():
    only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
    TPL.mkdir(parents=True, exist_ok=True)
    for cfg in PAGES:
        if only and cfg['id'] != only:
            continue
        for lang in ('cs', 'en'):
            j2, log, mid = build_page(cfg, lang)
            (TPL / f"{cfg['id']}.{lang}.html.j2").write_text(j2, encoding='utf-8')
            if lang == 'cs':
                miss = collect_assets(cfg, mid)
                if miss:
                    log.append(('CHYBI_ASSET', ', '.join(miss)))
            for k, v in log:
                print(f"  [{cfg['id']}/{lang}] {k}: {v}")
        print('OK', cfg['id'])


if __name__ == '__main__':
    main()
