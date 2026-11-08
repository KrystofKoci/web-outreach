"""Website audit: is the site missing, parked, outdated or fine?

Two entry points:

* :func:`audit_html` - pure function over HTML text (+ optional response
  headers), fully unit-testable without network.
* :func:`audit_website` - fetches the URL (15 s, mobile UA, follows redirects,
  tries ``https://`` first when given plain ``http://``), optionally fetches a
  contact sub-page for e-mails and PageSpeed mobile performance, then calls
  :func:`audit_html`.

Scoring: each finding is an :class:`AuditReason` with a weight; the sum is
clipped to 0-100.  Branches:

``no_website``  no site at all / unreachable / parked or placeholder page -> score 100
``redesign``    score >= REDESIGN_THRESHOLD (45)
``skip``        the site is good enough - do not contact
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .config import Settings, get_settings
from .models import AuditReason, AuditResult, SocialLinks

log = logging.getLogger("pipeline.audit")

REDESIGN_THRESHOLD = 45
CONTACT_PATHS = ("/kontakt", "/kontakty", "/contact", "/contact-us", "/kontakt/", "/contact/")

PARKED_PATTERNS = [
    # domain for sale / parking
    r"domain (?:is )?for sale", r"buy this domain", r"this domain (?:is|has been) (?:parked|registered)",
    r"dom[ée]na (?:je )?na prodej", r"dom[ée]na je zaparkov", r"tato dom[ée]na (?:je|byla) (?:registrov|zaparkov)",
    r"parked (?:free|domain)", r"sedo(?:parking)?\.com", r"hugedomains", r"afternic", r"dan\.com", r"godaddy.*parked",
    r"namecheap.*parking", r"domain parking", r"zaparkovan[áa] dom", r"webglobe.*dom[ée]na", r"wedos.*dom[ée]na",
    r"forpsi.*dom[ée]na", r"active 24.*dom[ée]na", r"dom[ée]na (?:byla )?(?:úspěšně )?zaregistrov",
    # construction / placeholders
    r"under construction", r"coming soon", r"site (?:is )?coming soon", r"str[áa]nky se p[řr]ipravuj",
    r"web se p[řr]ipravuje", r"str[áa]nka se p[řr]ipravuje", r"pracujeme na nov[ýy]ch str[áa]nk",
    r"welcome to nginx", r"apache2? (?:ubuntu |debian )?default page", r"it works!", r"iis windows server",
    r"index of /", r"default web site page", r"plesk.*default page", r"website is temporarily unavailable",
    r"account suspended", r"str[áa]nka nebyla nalezena", r"tato str[áa]nka (?:zat[íi]m )?nen[íi] k dispozici",
    r"web (?:je|byl) pozastaven", r"hosting (?:expired|vypr[šs]el)", r"webnode.*vytvo[řr]te si",
    r"wix\.com.*create your website", r"squarespace.*domain", r"this site can.t be reached",
]
_PARKED_RE = re.compile("|".join(PARKED_PATTERNS), re.IGNORECASE)

GENERATOR_PATTERNS: List[Tuple[str, str]] = [
    (r"wordpress\s*([\d.]+)?", "WordPress"), (r"joomla!?\s*([\d.]+)?", "Joomla"), (r"drupal\s*([\d.]+)?", "Drupal"),
    (r"webnode", "Webnode"), (r"wix\.com", "Wix"), (r"estranky", "Estranky"), (r"weebly", "Weebly"),
    (r"squarespace", "Squarespace"), (r"godaddy website builder|starfield technologies", "GoDaddy Builder"),
    (r"shoptet", "Shoptet"), (r"typo3\s*(?:cms)?\s*([\d.]+)?", "TYPO3"), (r"prestashop", "PrestaShop"),
    (r"mobirise", "Mobirise"), (r"microsoft frontpage\s*([\d.]+)?", "FrontPage"),
    (r"adobe dreamweaver|dreamweaver", "Dreamweaver"), (r"microsoft word", "MS Word"), (r"jimdo", "Jimdo"),
    (r"webflow", "Webflow"), (r"solidpixels", "Solidpixels"), (r"saywebpage", "SayWebPage"),
    (r"eshop-rychle|eshoprychle", "Eshop-rychle"), (r"webareal", "Webareal"), (r"nicepage", "Nicepage"),
]
# CMS fingerprints in HTML when no generator meta is present
CMS_HTML_HINTS: List[Tuple[str, str]] = [
    (r"/wp-content/|/wp-includes/", "WordPress"), (r"/media/jui/|/media/system/js/|joomla", "Joomla"),
    (r"webnode\.(?:cz|com|page)|wnd\.", "Webnode"), (r"static\.parastorage\.com|wixstatic\.com|wix-code", "Wix"),
    (r"estranky\.cz|estranky\.sk", "Estranky"), (r"weebly\.com|editmysite\.com", "Weebly"),
    (r"squarespace\.com|sqsp\.net|static1\.squarespace", "Squarespace"),
    (r"img1\.wsimg\.com|godaddy", "GoDaddy Builder"), (r"sites/default/files|drupal\.js|data-drupal", "Drupal"),
    (r"cdn\.shoptet\.cz|shoptet", "Shoptet"), (r"typo3temp|typo3conf", "TYPO3"), (r"webflow\.com|w-nav", "Webflow"),
    (r"jimdo", "Jimdo"), (r"mobirise", "Mobirise"), (r"solidpixels", "Solidpixels"),
]
_WP_VERSION_HINTS = re.compile(r"(?:ver=|wp-emoji-release\.min\.js\?ver=)(\d+\.\d+(?:\.\d+)?)")
_JQUERY_RE = re.compile(r"jquery[-.]?(\d+\.\d+(?:\.\d+)?)(?:\.min)?\.js|jQuery (?:v|JavaScript Library v)(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE)
_COPYRIGHT_RE = re.compile(r"(?:©|&copy;|\(c\)|copyright)\s*(?:\d{4}\s*[-–]\s*)?((?:19|20)\d{2})", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)\d{3}[\s.-]?\d{3,4}(?:[\s.-]?\d{2,3})?")
_MEDIA_QUERY_RE = re.compile(r"@media[^{]*\((?:max|min)-width", re.IGNORECASE)
_FIXED_WIDTH_RE = re.compile(r"width\s*:\s*(9[5-9]\d|1[0-2]\d{2})px", re.IGNORECASE)
_IMG_EXT_RE = re.compile(r"\.(?:png|jpe?g|gif|svg|webp|css|js)$", re.IGNORECASE)

EMAIL_RANK = ["info", "kontakt", "office", "hello", "contact", "mail", "posta", "objednavky", "rezervace",
              "recepce", "ordinace", "servis", "salon", "obchod", "sales", "ahoj", "booking", "bookings"]
EMAIL_NOISE = ("example.com", "sentry", "wixpress", "w3.org", "schema.org", "your-domain", "domain.com",
               "email.com", "googlemail.example", "yoursite", "jquery", "@2x", "@3x", "noreply", "no-reply",
               "donotreply", "@mailchimp", "cookiebot", "wordpress.org", "@sentry")

_CS_WORDS = {"a", "je", "na", "se", "pro", "jsme", "nás", "naše", "kontakt", "služby", "více", "nebo", "firma"}
_EN_WORDS = {"the", "and", "we", "our", "services", "contact", "about", "more", "you", "with", "for", "your"}
_DE_WORDS = {"und", "wir", "der", "die", "das", "kontakt", "unsere", "mit", "für", "sie", "ihre", "leistungen"}


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _reason(key: str, weight: int, cs: str, en: str) -> AuditReason:
    return AuditReason(key=key, weight=weight, text_cs=cs, text_en=en)


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def _version_tuple(v: str) -> Tuple[int, ...]:
    out = []
    for part in (v or "").split("."):
        if part.isdigit():
            out.append(int(part))
        else:
            break
    return tuple(out) or (0,)


def rank_emails(emails: List[str], site_domain: str = "") -> List[str]:
    """De-duplicate and sort e-mails: generic business boxes on the site's own domain first."""
    cleaned = []
    seen = set()
    for e in emails:
        e = e.strip().strip(".,;:()<>[]\"'").lower()
        if not e or "@" not in e or e in seen or _IMG_EXT_RE.search(e):
            continue
        if any(n in e for n in EMAIL_NOISE):
            continue
        local, _, dom = e.partition("@")
        if len(local) > 40 or len(dom) > 60 or dom.count(".") > 4:
            continue
        seen.add(e)
        cleaned.append(e)

    def key(e: str):
        local, _, dom = e.partition("@")
        try:
            r = EMAIL_RANK.index(local)
        except ValueError:
            r = len(EMAIL_RANK) + (0 if "." not in local else 1)   # personal first.last@ last
        same_domain = 0 if site_domain and dom.endswith(site_domain) else 1
        return (same_domain, r, e)

    return sorted(cleaned, key=key)


def guess_language(text: str, html_lang: str = "") -> str:
    if html_lang:
        return html_lang.split("-")[0].lower()[:2]
    words = re.findall(r"[a-záčďéěíňóřšťúůýž]+", (text or "").lower())
    sample = words[:800]
    scores = {
        "cs": sum(1 for w in sample if w in _CS_WORDS) + 2 * sum(1 for w in sample if re.search(r"[ěščřžůň]", w)),
        "en": sum(1 for w in sample if w in _EN_WORDS),
        "de": sum(1 for w in sample if w in _DE_WORDS),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 2 else ""


def detect_parked(soup: BeautifulSoup, html: str, text: str) -> bool:
    """Parked / placeholder / registrar default page heuristics."""
    title = (soup.title.string if soup.title and soup.title.string else "") or ""
    head = (title + " " + text[:1500]).lower()
    if _PARKED_RE.search(head):
        return True
    body_text = text.strip()
    # practically empty page (no content, no links) -> placeholder
    links = soup.find_all("a", href=True)
    if len(body_text) < 120 and len(links) <= 2 and len(html) < 20000:
        return True
    return False


# ---------------------------------------------------------------------------
# pure analysis
# ---------------------------------------------------------------------------
def audit_html(html: str, url: str, headers: Optional[Dict[str, str]] = None, *,
               final_url: str = "", status_code: Optional[int] = None, cert_error: bool = False,
               https_redirect: bool = False, extra_emails: Optional[List[str]] = None,
               pagespeed_mobile: Optional[int] = None, now: Optional[datetime] = None) -> AuditResult:
    """Analyse HTML and return a scored :class:`AuditResult` (no network)."""
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    now = now or datetime.now(timezone.utc)
    final_url = final_url or url
    res = AuditResult(url=url, final_url=final_url, reachable=True, status_code=status_code or 200,
                      cert_error=cert_error, https_redirect=https_redirect, pagespeed_mobile=pagespeed_mobile)
    res.https_ok = final_url.lower().startswith("https://") and not cert_error
    res.last_modified = headers.get("last-modified", "")
    res.page_weight_kb = max(1, len(html.encode("utf-8", "ignore")) // 1024) if html else 0

    soup = BeautifulSoup(html or "", "lxml")
    text = soup.get_text(" ", strip=True)
    low_html = (html or "").lower()
    reasons: List[AuditReason] = []

    # --- parked / placeholder --------------------------------------------
    res.parked = detect_parked(soup, html or "", text)
    if res.parked:
        res.screenshot_able = True
        res.score = 100
        res.branch = "no_website"
        res.reasons = [_reason("parked", 100,
                               "Doména je zaparkovaná / web je jen zástupná stránka",
                               "Domain is parked / the site is only a placeholder page")]
        res.title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
        return res

    # --- basic meta --------------------------------------------------------
    res.title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    md = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    res.meta_description = (md.get("content") or "").strip() if md else ""
    h1 = soup.find("h1")
    res.h1 = h1.get_text(" ", strip=True)[:200] if h1 else ""
    html_tag = soup.find("html")
    res.lang = guess_language(text, (html_tag.get("lang") or "") if html_tag else "")

    # --- generator / CMS ---------------------------------------------------
    gen = soup.find("meta", attrs={"name": re.compile("^generator$", re.I)})
    res.generator = (gen.get("content") or "").strip() if gen else ""
    for pat, name in GENERATOR_PATTERNS:
        m = re.search(pat, res.generator, re.IGNORECASE)
        if m:
            res.cms = name
            res.cms_version = (m.group(1) or "") if m.groups() else ""
            break
    if not res.cms:
        for pat, name in CMS_HTML_HINTS:
            if re.search(pat, low_html):
                res.cms = name
                break
    if res.cms == "WordPress" and not res.cms_version:
        m = _WP_VERSION_HINTS.search(html or "")
        if m:
            res.cms_version = m.group(1)
    if res.cms:
        res.tech.append(res.cms + (f" {res.cms_version}" if res.cms_version else ""))

    jq = _JQUERY_RE.search(html or "")
    if jq:
        res.jquery_version = jq.group(1) or jq.group(2) or ""
        res.tech.append(f"jQuery {res.jquery_version}")
    if "bootstrap" in low_html:
        res.tech.append("Bootstrap")
    if "tailwind" in low_html:
        res.tech.append("Tailwind")
    if re.search(r"react|__next|_next/static", low_html):
        res.tech.append("React/Next")

    # --- responsiveness ----------------------------------------------------
    vp = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})
    res.viewport = bool(vp and "width" in (vp.get("content") or "").lower())
    if _MEDIA_QUERY_RE.search(html or ""):
        res.responsive_signals.append("media-queries")
    if re.search(r"display\s*:\s*(flex|grid)", low_html):
        res.responsive_signals.append("flex/grid")
    if re.search(r"class=\"[^\"]*(?:col-(?:xs|sm|md|lg)|container|row|grid|flex|md:|lg:)", low_html):
        res.responsive_signals.append("framework-classes")
    if soup.find("picture") or soup.find("img", attrs={"srcset": True}):
        res.responsive_signals.append("srcset")
    fixed_width = bool(_FIXED_WIDTH_RE.search(html or ""))

    # --- legacy markup -----------------------------------------------------
    res.has_flash = bool(soup.find("object", attrs={"type": re.compile("shockwave|flash", re.I)})
                         or soup.find("embed", attrs={"src": re.compile(r"\.swf", re.I)})
                         or ".swf" in low_html)
    tables = soup.find_all("table")
    body = soup.body
    res.table_layout = False
    if tables and body:
        # layout tables: large tables with width attr or nested tables directly under body
        for t in tables:
            if t.get("width") in ("100%", "960", "1000", "980", "800", "900") or t.find("table"):
                res.table_layout = True
                break
        if not res.table_layout and len(tables) >= 3 and len(soup.find_all("div")) < 10:
            res.table_layout = True
    for tag in ("font", "center", "marquee", "blink", "frameset", "frame"):
        if soup.find(tag):
            res.legacy_tags.append(tag)

    m = _COPYRIGHT_RE.findall(html or "")
    if m:
        years = [int(y) for y in m if 1995 <= int(y) <= now.year + 1]
        if years:
            res.copyright_year = max(years)

    # --- contact & links ---------------------------------------------------
    res.has_contact_form = bool(soup.find("form") and (
        soup.find("textarea") or soup.find("input", attrs={"type": re.compile("email", re.I)})
        or soup.find("input", attrs={"name": re.compile("mail|zprava|message|jmeno|name", re.I)})))
    site_dom = _domain(final_url)
    social = SocialLinks()
    for a in soup.find_all("a", href=True):
        href = (a["href"] or "").strip()
        hl = href.lower()
        if hl.startswith("tel:"):
            res.tel_links.append(href[4:].strip())
        elif hl.startswith("mailto:"):
            res.mailto_links.append(href[7:].split("?")[0].strip())
        elif "facebook.com/" in hl and "sharer" not in hl and "share.php" not in hl and not social.facebook:
            social.facebook = href
        elif "instagram.com/" in hl and not social.instagram:
            social.instagram = href
        elif "linkedin.com/" in hl and "share" not in hl and not social.linkedin:
            social.linkedin = href
        elif ("youtube.com/" in hl or "youtu.be/" in hl) and not social.youtube:
            social.youtube = href
        elif "tiktok.com/" in hl and not social.tiktok:
            social.tiktok = href
    res.social = social
    found_emails = _EMAIL_RE.findall(html or "") + res.mailto_links + list(extra_emails or [])
    res.emails = rank_emails(found_emails, site_dom)
    phones = list(res.tel_links)
    for cand in _PHONE_RE.findall(text):
        digits = re.sub(r"\D", "", cand)
        if 9 <= len(digits) <= 13:
            phones.append(cand.strip())
    seen = set()
    res.phones = []
    for p in phones:
        k = re.sub(r"\D", "", p)
        if k and k not in seen:
            seen.add(k)
            res.phones.append(p)
    res.phones = res.phones[:5]

    # --- images ------------------------------------------------------------
    imgs = soup.find_all("img")
    res.images_total = len(imgs)
    res.images_without_alt = sum(1 for i in imgs if not (i.get("alt") or "").strip())

    # --- scoring -----------------------------------------------------------
    if not res.viewport:
        reasons.append(_reason("no_viewport", 25, "Web není přizpůsoben mobilům (chybí viewport)",
                               "Site is not mobile-friendly (no viewport meta)"))
    elif not res.responsive_signals or fixed_width:
        reasons.append(_reason("weak_responsive", 10, "Slabé známky responzivity (pevná šířka / bez media queries)",
                               "Weak responsive signals (fixed width / no media queries)"))
    if res.copyright_year and res.copyright_year < now.year - 2:
        age = now.year - res.copyright_year
        reasons.append(_reason("old_copyright", 20 if age >= 5 else 15,
                               f"Copyright v patičce je z roku {res.copyright_year}",
                               f"Footer copyright says {res.copyright_year}"))
    if res.cms == "WordPress" and res.cms_version and _version_tuple(res.cms_version) < (5,):
        reasons.append(_reason("old_cms", 12, f"Zastaralý WordPress {res.cms_version}",
                               f"Outdated WordPress {res.cms_version}"))
    elif res.cms == "Joomla" and (not res.cms_version or _version_tuple(res.cms_version) < (4,)):
        reasons.append(_reason("old_cms", 12, f"Starý Joomla {res.cms_version}".strip(),
                               f"Old Joomla {res.cms_version}".strip()))
    elif res.cms in ("Estranky", "Webnode", "Weebly", "GoDaddy Builder", "Mobirise", "Webareal",
                     "Eshop-rychle", "SayWebPage", "Jimdo"):
        reasons.append(_reason("builder_dated", 10, f"Web postavený na šablonovém builderu ({res.cms})",
                               f"Site built on a dated template builder ({res.cms})"))
    elif res.cms in ("FrontPage", "Dreamweaver", "MS Word"):
        reasons.append(_reason("ancient_tool", 20, f"Web vytvořený v {res.cms} (velmi zastaralé)",
                               f"Site made with {res.cms} (very outdated)"))
    elif res.cms in ("Wix", "Squarespace"):
        reasons.append(_reason("builder_generic", 4, f"Šablonový builder ({res.cms})",
                               f"Template builder ({res.cms})"))
    if res.jquery_version and _version_tuple(res.jquery_version) < (2,):
        reasons.append(_reason("old_jquery", 10, f"Stará knihovna jQuery {res.jquery_version}",
                               f"Old jQuery {res.jquery_version}"))
    if res.has_flash:
        reasons.append(_reason("flash", 20, "Používá Flash (nefunguje v žádném moderním prohlížeči)",
                               "Uses Flash (does not work in any modern browser)"))
    if res.table_layout:
        reasons.append(_reason("table_layout", 15, "Rozložení stránky pomocí tabulek",
                               "Table-based page layout"))
    if res.legacy_tags:
        reasons.append(_reason("legacy_tags", 10, f"Zastaralé HTML značky ({', '.join(res.legacy_tags)})",
                               f"Obsolete HTML tags ({', '.join(res.legacy_tags)})"))
    if not res.title:
        reasons.append(_reason("no_title", 5, "Chybí titulek stránky", "Missing page title"))
    if not res.meta_description:
        reasons.append(_reason("no_meta_desc", 5, "Chybí meta popis pro vyhledávače",
                               "Missing meta description"))
    if not res.h1:
        reasons.append(_reason("no_h1", 5, "Chybí hlavní nadpis (H1)", "Missing main heading (H1)"))
    if not res.has_contact_form:
        reasons.append(_reason("no_contact_form", 5, "Bez kontaktního formuláře", "No contact form"))
    if not res.tel_links:
        reasons.append(_reason("no_tel_link", 5, "Telefon není klikací (tel: odkaz)",
                               "Phone number is not tap-to-call"))
    if not res.https_ok:
        if cert_error:
            reasons.append(_reason("cert_error", 15, "Neplatný certifikát HTTPS (prohlížeč varuje)",
                                   "Invalid HTTPS certificate (browser warning)"))
        else:
            reasons.append(_reason("no_https", 15, "Web neběží na HTTPS (prohlížeč hlásí „Nezabezpečeno“)",
                                   "Site is not served over HTTPS (browser shows 'Not secure')"))
    elif url.lower().startswith("http://") and not https_redirect:
        reasons.append(_reason("no_https_redirect", 5, "HTTP nepřesměrovává automaticky na HTTPS",
                               "HTTP does not redirect to HTTPS"))
    if res.page_weight_kb > 6000:
        reasons.append(_reason("heavy_page", 10, "Velmi těžká stránka (>6 MB)", "Very heavy page (>6 MB)"))
    elif res.page_weight_kb > 3000:
        reasons.append(_reason("heavy_page", 5, "Těžká stránka (>3 MB)", "Heavy page (>3 MB)"))
    if res.images_total >= 4 and res.images_without_alt / max(1, res.images_total) > 0.5:
        reasons.append(_reason("img_alt", 5, "Většina obrázků bez popisku (přístupnost, SEO)",
                               "Most images lack alt text (accessibility, SEO)"))
    if pagespeed_mobile is not None:
        if pagespeed_mobile < 50:
            reasons.append(_reason("slow_mobile", 15, f"Pomalý na mobilu (PageSpeed {pagespeed_mobile}/100)",
                                   f"Slow on mobile (PageSpeed {pagespeed_mobile}/100)"))
        elif pagespeed_mobile < 70:
            reasons.append(_reason("slow_mobile", 8, f"Průměrná rychlost na mobilu (PageSpeed {pagespeed_mobile}/100)",
                                   f"Average mobile speed (PageSpeed {pagespeed_mobile}/100)"))
    if res.last_modified:
        try:
            lm = datetime.strptime(res.last_modified[:25].strip(), "%a, %d %b %Y %H:%M:%S")
            if (now.replace(tzinfo=None) - lm).days > 730:
                reasons.append(_reason("stale_last_modified", 5,
                                       f"Server hlásí poslední změnu {lm:%Y-%m}",
                                       f"Server reports last change {lm:%Y-%m}"))
        except ValueError:
            pass

    reasons.sort(key=lambda r: (-r.weight, r.key))
    res.reasons = reasons
    res.score = min(100, sum(r.weight for r in reasons))
    res.branch = "redesign" if res.score >= REDESIGN_THRESHOLD else "skip"
    res.screenshot_able = True
    return res


def unreachable_result(url: str, error: str, *, cert_error: bool = False,
                       status_code: Optional[int] = None) -> AuditResult:
    """Result for a site that could not be loaded - treated as ``no_website``."""
    return AuditResult(
        url=url, final_url=url, reachable=False, error=error, cert_error=cert_error, status_code=status_code,
        score=100, branch="no_website",
        reasons=[_reason("unreachable", 100,
                         f"Web se nepodařilo načíst ({error})", f"Website could not be loaded ({error})")],
    )


SOCIAL_ONLY_DOMAINS = ("facebook.com", "fb.com", "fb.me", "instagram.com", "linkedin.com", "linktr.ee", "tiktok.com",
                       "youtube.com", "twitter.com", "x.com")
DIRECTORY_DOMAINS = ("firmy.cz", "zlatestranky.cz", "najisto.cz", "zivefirmy.cz", "business.site", "yelp.com",
                     "yellowpages.com", "yell.com", "goldenpages.ie", "truelocal.com.au", "yellow.co.nz", "sites.google.com")


def social_only_result(url: str) -> Optional[AuditResult]:
    """``no_website`` when the "website" is only a social profile or a directory listing."""
    host = _domain(url)
    if not host:
        return None
    if any(host == d or host.endswith("." + d) for d in SOCIAL_ONLY_DOMAINS):
        return AuditResult(url=url, final_url=url, reachable=False, score=100, branch="no_website",
                           reasons=[_reason("social_only", 100, "Firma má místo webu jen profil na sociální síti",
                                            "Business only has a social media profile instead of a website")])
    if any(host == d or host.endswith("." + d) for d in DIRECTORY_DOMAINS):
        return AuditResult(url=url, final_url=url, reachable=False, score=100, branch="no_website",
                           reasons=[_reason("directory_only", 100, "Místo webu jen zápis v katalogu firem",
                                            "Only a business-directory listing instead of a website")])
    return None


def no_website_result() -> AuditResult:
    return AuditResult(
        url="", final_url="", reachable=False, score=100, branch="no_website",
        reasons=[_reason("no_website", 100, "Firma nemá žádný web", "Business has no website")],
    )


# ---------------------------------------------------------------------------
# network
# ---------------------------------------------------------------------------
def normalise_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "http://" + url
    return url


def _fetch(url: str, s: Settings, timeout: Optional[int] = None) -> requests.Response:
    headers = {"User-Agent": s.user_agent, "Accept-Language": "cs,en;q=0.8",
               "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"}
    return requests.get(url, headers=headers, timeout=timeout or s.http_timeout, allow_redirects=True)


def fetch_pagespeed_mobile(url: str, s: Settings) -> Optional[int]:
    """PageSpeed Insights v5 mobile performance score (0-100) or ``None``.

    Free quota is 25 000 requests/day (requires a key); one call takes 10-40 s,
    so it is only used when ``PAGESPEED_API_KEY`` is set.
    """
    if not s.pagespeed_api_key:
        return None
    try:
        resp = requests.get(
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
            params={"url": url, "strategy": "mobile", "category": "performance", "key": s.pagespeed_api_key},
            timeout=60,
        )
        if resp.status_code != 200:
            log.warning("PageSpeed HTTP %s for %s", resp.status_code, url)
            return None
        score = resp.json()["lighthouseResult"]["categories"]["performance"]["score"]
        return int(round(float(score) * 100))
    except Exception as exc:       # noqa: BLE001 - optional signal, never fatal
        log.warning("PageSpeed failed for %s: %s", url, exc)
        return None


def audit_website(url: str, settings: Optional[Settings] = None, *, with_pagespeed: bool = True,
                  follow_contact_page: bool = True) -> AuditResult:
    """Fetch ``url`` and audit it. Never raises; failures become ``no_website``."""
    s = settings or get_settings()
    url = normalise_url(url)
    if not url:
        return no_website_result()
    social = social_only_result(url)
    if social is not None:
        return social

    candidates = [url]
    if url.lower().startswith("http://"):
        candidates.insert(0, "https://" + url[7:])      # try https first
    resp = None
    cert_error = False
    last_err = ""
    started = time.time()
    for cand in candidates:
        try:
            resp = _fetch(cand, s)
            if resp.status_code >= 400 and cand != candidates[-1]:
                last_err = f"HTTP {resp.status_code}"
                resp = None
                continue
            break
        except requests.exceptions.SSLError as exc:
            cert_error = True
            last_err = "neplatný certifikát"
            log.info("SSL error for %s: %s", cand, exc)
            continue
        except requests.exceptions.Timeout:
            last_err = "timeout"
            continue
        except requests.exceptions.ConnectionError:
            last_err = "spojení odmítnuto / DNS"
            continue
        except requests.RequestException as exc:
            last_err = str(exc)[:80]
            continue
    if resp is None:
        res = unreachable_result(url, last_err or "neznámá chyba", cert_error=cert_error)
        res.fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        return res
    if resp.status_code >= 400:
        return unreachable_result(url, f"HTTP {resp.status_code}", status_code=resp.status_code)

    final_url = resp.url
    https_redirect = url.lower().startswith("http://") and final_url.lower().startswith("https://")
    ctype = resp.headers.get("Content-Type", "")
    if ctype and "html" not in ctype and "xml" not in ctype and "text" not in ctype:
        return unreachable_result(url, f"neočekávaný typ obsahu ({ctype.split(';')[0]})", status_code=resp.status_code)
    html = resp.text or ""

    extra_emails: List[str] = []
    if follow_contact_page and not _EMAIL_RE.search(html):
        soup = BeautifulSoup(html, "lxml")
        links = []
        for a in soup.find_all("a", href=True):
            h = a["href"].lower()
            if any(p.strip("/") in h for p in ("kontakt", "contact")):
                links.append(urljoin(final_url, a["href"]))
        for p in CONTACT_PATHS:
            links.append(urljoin(final_url, p))
        tried = 0
        for link in dict.fromkeys(links):
            if tried >= 2 or time.time() - started > 25:
                break
            tried += 1
            try:
                r2 = _fetch(link, s, timeout=8)
                if r2.status_code == 200 and "html" in r2.headers.get("Content-Type", ""):
                    extra_emails.extend(_EMAIL_RE.findall(r2.text or ""))
                    if extra_emails:
                        break
            except requests.RequestException:
                continue

    pagespeed = fetch_pagespeed_mobile(final_url, s) if with_pagespeed else None
    res = audit_html(html, url, dict(resp.headers), final_url=final_url, status_code=resp.status_code,
                     cert_error=cert_error and final_url.startswith("http://"), https_redirect=https_redirect,
                     extra_emails=extra_emails, pagespeed_mobile=pagespeed)
    res.page_weight_kb = max(res.page_weight_kb, len(resp.content) // 1024)
    log.info("Audit %s -> score %d branch %s (%s)", url, res.score, res.branch,
             ", ".join(r.key for r in res.reasons[:4]))
    return res
