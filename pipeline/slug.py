"""URL slugs without external dependencies.

``slugify("Instalatérství Novák & syn")`` -> ``"instalaterstvi-novak-syn"``

Czech (and other Latin) diacritics are folded to ASCII with ``unicodedata``;
a short hash suffix (:func:`make_slug`) keeps two "Kadeřnictví Jana" in two
towns from colliding on disk / in URLs.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Iterable, Optional

# Characters NFKD does not decompose but we still want folded.
_SPECIAL = {
    "ß": "ss", "æ": "ae", "Æ": "ae", "ø": "o", "Ø": "o", "đ": "d", "Đ": "d",
    "ł": "l", "Ł": "l", "þ": "th", "Þ": "th", "œ": "oe", "Œ": "oe", "&": " a ",
}
_SPECIAL_EN = dict(_SPECIAL)
_SPECIAL_EN["&"] = " and "

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: Optional[str], max_len: int = 48, lang: str = "cs") -> str:
    """Return an ASCII, lowercase, hyphen separated slug.

    - diacritics are stripped (``ř`` -> ``r``, ``ů`` -> ``u``)
    - ``&`` becomes ``a`` (cs) or ``and`` (en)
    - anything that is not ``[a-z0-9]`` becomes a single hyphen
    - result is trimmed to ``max_len`` on a hyphen boundary when possible
    - empty input yields ``"web"`` so the slug is never empty
    """
    if not text:
        return "web"
    specials = _SPECIAL if lang == "cs" else _SPECIAL_EN
    text = "".join(specials.get(ch, ch) for ch in str(text))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = _NON_ALNUM.sub("-", text).strip("-")
    if not text:
        return "web"
    if len(text) > max_len:
        cut = text[:max_len]
        if "-" in cut[10:]:
            cut = cut.rsplit("-", 1)[0]
        text = cut.strip("-")
    return text


def short_hash(*parts: Optional[str], length: int = 4) -> str:
    """Stable short hex hash of the given parts (used as slug suffix)."""
    raw = "|".join((p or "").strip().lower() for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length]


def make_slug(name: str, city: Optional[str] = None, *, unique: Optional[str] = None,
              lang: str = "cs", with_hash: bool = True) -> str:
    """Build ``<name>-<city>-<hash>``.

    ``unique`` should be something stable for the business (Google place id,
    or ``name + address``); it feeds the hash so re-running the pipeline for
    the same lead gives the same slug.
    """
    base = slugify(name, max_len=40, lang=lang)
    if city:
        city_slug = slugify(city, max_len=20, lang=lang)
        if city_slug and city_slug not in base:
            base = f"{base}-{city_slug}"
    if with_hash:
        base = f"{base}-{short_hash(unique or name, city or '')}"
    return base


def unique_slug(candidate: str, taken: Iterable[str]) -> str:
    """Append ``-2``, ``-3``… until ``candidate`` is not in ``taken``."""
    taken = set(taken)
    if candidate not in taken:
        return candidate
    n = 2
    while f"{candidate}-{n}" in taken:
        n += 1
    return f"{candidate}-{n}"
