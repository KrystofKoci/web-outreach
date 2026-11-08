"""Screenshots with Playwright + "today vs. new design" comparison with Pillow.

Outputs inside the preview directory:

``old_mobile.png``   current website, 390x844 @2x (grey placeholder when the
                     site is missing / unreachable / times out after 20 s)
``new_mobile.png``   the generated preview rendered from ``file://``
``compare.png``      both side by side, labels "DNES" / "NOVÝ NÁVRH"
                     (en: "TODAY" / "NEW DESIGN"), business name on top,
                     owner line at the bottom
``og.png``           1200x630 Open Graph card (new preview + name)

Everything degrades gracefully: without Chromium you still get the
placeholder-based compare image; fonts fall back DejaVu -> Inter -> Poppins
-> Pillow default.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .config import Settings, get_settings

log = logging.getLogger("pipeline.shot")

MOBILE_VIEWPORT = {"width": 390, "height": 844}
DEVICE_SCALE = 2
OLD_SITE_TIMEOUT_MS = 20_000
NEW_SITE_TIMEOUT_MS = 15_000

LABELS = {
    "cs": {"today": "DNES", "new": "NOVÝ NÁVRH", "no_site": "Web nenalezen / nedostupný",
           "owner": "Nezávazný návrh připravil {owner}", "draft": "Návrh nového webu"},
    "en": {"today": "TODAY", "new": "NEW DESIGN", "no_site": "No website found",
           "owner": "Non-binding draft prepared by {owner}", "draft": "New website draft"},
}

_FONT_CANDIDATES = {
    "bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
        "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "C:/Windows/Fonts/arialbd.ttf", "/Library/Fonts/Arial Bold.ttf",
    ],
    "regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
        "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "C:/Windows/Fonts/arial.ttf", "/Library/Fonts/Arial.ttf",
    ],
}


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Return a TrueType font with Czech glyphs, falling back to Pillow's default."""
    for path in _FONT_CANDIDATES["bold" if bold else "regular"]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                         # very old Pillow
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Playwright
# ---------------------------------------------------------------------------
def _shoot(url: str, out: Path, timeout_ms: int, *, full_page: bool = False, viewport: Optional[dict] = None,
           scale: int = DEVICE_SCALE, user_agent: str = "", wait_until: str = "load") -> bool:
    """Screenshot ``url`` into ``out``. Returns ``True`` on success, never raises."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:          # noqa: BLE001
        log.warning("Playwright není k dispozici: %s", exc)
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            try:
                ctx = browser.new_context(
                    viewport=viewport or MOBILE_VIEWPORT, device_scale_factor=scale,
                    is_mobile=(viewport or MOBILE_VIEWPORT)["width"] < 600, has_touch=(viewport or MOBILE_VIEWPORT)["width"] < 600,
                    user_agent=user_agent or None, ignore_https_errors=True, locale="cs-CZ",
                )
                page = ctx.new_page()
                page.set_default_timeout(timeout_ms)
                page.goto(url, wait_until=wait_until, timeout=timeout_ms)
                try:
                    page.wait_for_timeout(600)      # let fonts / lazy bits settle
                except Exception:                  # noqa: BLE001
                    pass
                out.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(out), full_page=full_page)
                return True
            finally:
                browser.close()
    except Exception as exc:          # noqa: BLE001
        log.warning("Screenshot %s selhal: %s", url, str(exc)[:200])
        return False


def screenshot_old_site(url: str, out: Path, s: Settings) -> bool:
    if not url:
        return False
    return _shoot(url, out, min(OLD_SITE_TIMEOUT_MS, s.screenshot_timeout_s * 1000),
                  user_agent=s.user_agent, wait_until="load")


def screenshot_new_site(html_path: Path, out: Path, *, full_page: bool = False,
                        viewport: Optional[dict] = None) -> bool:
    return _shoot(Path(html_path).resolve().as_uri(), out, NEW_SITE_TIMEOUT_MS, full_page=full_page,
                  viewport=viewport, wait_until="load")


# ---------------------------------------------------------------------------
# Pillow composition
# ---------------------------------------------------------------------------
def placeholder_phone(size: Tuple[int, int], text: str) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, (229, 231, 235))
    d = ImageDraw.Draw(img)
    f = load_font(int(w * 0.055), bold=True)
    f2 = load_font(int(w * 0.04))
    # fake browser chrome
    d.rectangle([0, 0, w, int(h * 0.07)], fill=(209, 213, 219))
    d.rounded_rectangle([int(w * 0.05), int(h * 0.018), int(w * 0.95), int(h * 0.052)], radius=14, fill=(243, 244, 246))
    lines = _wrap(text, f, int(w * 0.8), d)
    y = int(h * 0.42)
    for ln in lines:
        tw = d.textlength(ln, font=f)
        d.text(((w - tw) / 2, y), ln, fill=(75, 85, 99), font=f)
        y += int(f.size * 1.3)
    d.text((w / 2, y + 10), "—", fill=(156, 163, 175), font=f2, anchor="mt")
    return img


def _wrap(text: str, font, max_w: int, d: ImageDraw.ImageDraw):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        test = (cur + " " + wd).strip()
        if d.textlength(test, font=font) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def _fit_phone(path: Optional[Path], size: Tuple[int, int], fallback_text: str) -> Image.Image:
    if path and path.exists():
        try:
            img = Image.open(path).convert("RGB")
            img = img.resize(size, Image.LANCZOS)
            return img
        except OSError:
            pass
    return placeholder_phone(size, fallback_text)


def compose_compare(old_png: Optional[Path], new_png: Optional[Path], out: Path, *, name: str, lang: str,
                    owner_name: str) -> Path:
    lang = "cs" if lang == "cs" else "en"
    L = LABELS[lang]
    phone = (780, 1688)            # 390x844 @2x
    pad, gap, top, bottom = 60, 60, 190, 120
    W = pad * 2 + phone[0] * 2 + gap
    H = top + phone[1] + bottom
    canvas = Image.new("RGB", (W, H), (248, 247, 244))
    d = ImageDraw.Draw(canvas)
    f_title = load_font(54, bold=True)
    f_label = load_font(34, bold=True)
    f_small = load_font(28)
    # title
    title = name if d.textlength(name, font=f_title) <= W - 2 * pad else name[:40] + "…"
    d.text((pad, 50), title, fill=(17, 24, 39), font=f_title)
    # labels
    for i, (label, color) in enumerate(((L["today"], (107, 114, 128)), (L["new"], (22, 101, 52)))):
        x = pad + i * (phone[0] + gap)
        d.rounded_rectangle([x, 126, x + d.textlength(label, font=f_label) + 36, 176], radius=12,
                            fill=color)
        d.text((x + 18, 134), label, fill=(255, 255, 255), font=f_label)
    # phones
    old_img = _fit_phone(old_png, phone, L["no_site"])
    new_img = _fit_phone(new_png, phone, L["draft"])
    for i, img in enumerate((old_img, new_img)):
        x = pad + i * (phone[0] + gap)
        frame = Image.new("RGB", (phone[0] + 16, phone[1] + 16), (31, 41, 55))
        canvas.paste(frame, (x - 8, top - 8))
        canvas.paste(img, (x, top))
    # owner line
    d.text((pad, H - 80), L["owner"].format(owner=owner_name), fill=(75, 85, 99), font=f_small)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)
    return out


def compose_og(new_png: Optional[Path], out: Path, *, name: str, lang: str, owner_name: str,
               brand_hex: str = "#243B6B") -> Path:
    lang = "cs" if lang == "cs" else "en"
    W, H = 1200, 630
    brand = tuple(int(brand_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) if len(brand_hex) == 7 else (36, 59, 107)
    canvas = Image.new("RGB", (W, H), brand)
    d = ImageDraw.Draw(canvas)
    f_title = load_font(60, bold=True)
    f_sub = load_font(30)
    # phone on the right
    if new_png and Path(new_png).exists():
        try:
            ph = Image.open(new_png).convert("RGB")
            ph_w = 330
            ph_h = int(ph.height * ph_w / ph.width)
            ph = ph.resize((ph_w, ph_h), Image.LANCZOS)
            ph = ph.crop((0, 0, ph_w, min(ph_h, H - 40)))
            frame = Image.new("RGB", (ph_w + 16, ph.height + 16), (17, 24, 39))
            canvas.paste(frame, (W - ph_w - 76, 48))
            canvas.paste(ph, (W - ph_w - 68, 56))
        except OSError:
            pass
    lines = _wrap(name, f_title, 700, d)[:3]
    y = 150
    for ln in lines:
        d.text((70, y), ln, fill=(255, 255, 255), font=f_title)
        y += 72
    d.text((70, y + 24), LABELS[lang]["draft"], fill=(255, 255, 255, 200), font=f_sub)
    d.text((70, H - 90), LABELS[lang]["owner"].format(owner=owner_name), fill=(220, 225, 235), font=f_sub)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)
    return out


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------
def make_screenshots(preview_dir: Path, *, old_url: str, name: str, lang: str, brand_hex: str = "#243B6B",
                     settings: Optional[Settings] = None, with_playwright: bool = True) -> Dict[str, object]:
    """Produce old/new/compare/og PNGs in ``preview_dir``. Never raises."""
    s = settings or get_settings()
    preview_dir = Path(preview_dir)
    html = preview_dir / "index.html"
    old_png = preview_dir / "old_mobile.png"
    new_png = preview_dir / "new_mobile.png"
    result: Dict[str, object] = {"old_ok": False, "new_ok": False, "warnings": []}
    if with_playwright:
        result["old_ok"] = screenshot_old_site(old_url, old_png, s) if old_url else False
        if old_url and not result["old_ok"]:
            result["warnings"].append("Screenshot starého webu se nepodařil - použit zástupný obrázek.")
        result["new_ok"] = screenshot_new_site(html, new_png) if html.exists() else False
        if not result["new_ok"]:
            result["warnings"].append("Screenshot nového návrhu se nepodařil (Playwright/Chromium).")
    else:
        result["warnings"].append("Screenshoty přeskočeny (with_playwright=False).")
    try:
        compose_compare(old_png if result["old_ok"] else None, new_png if result["new_ok"] else None,
                        preview_dir / "compare.png", name=name, lang=lang, owner_name=s.owner_name)
        compose_og(new_png if result["new_ok"] else None, preview_dir / "og.png", name=name, lang=lang,
                   owner_name=s.owner_name, brand_hex=brand_hex)
        result["compare_png"] = str(preview_dir / "compare.png")
        result["og_png"] = str(preview_dir / "og.png")
    except Exception as exc:          # noqa: BLE001
        log.warning("Skládání obrázků selhalo: %s", exc)
        result["warnings"].append(f"Skládání compare/og obrázku selhalo: {exc}")
    if result["new_ok"]:
        result["new_mobile_png"] = str(new_png)
    return result
