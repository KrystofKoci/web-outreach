"""End-to-end processing of one lead: guard -> audit -> copy -> build -> shots -> publish.

``process_lead(lead_dict)`` never raises for a lead; every failure after the
audit becomes a ``warnings[]`` entry so n8n can store the row and the owner
sees what to fix.  The return value is a flat JSON-friendly dict
(:class:`pipeline.models.ProcessResult`).
"""

from __future__ import annotations

import logging
import traceback
from typing import Any, Dict, Optional

from . import audit as audit_mod
from . import copy_writer, deploy_preview, generate_site, industries, offer_extract, screenshot_compare
from .config import Settings, get_settings
from .models import Lead, ProcessResult
from .slug import make_slug

log = logging.getLogger("pipeline.run")


def lead_from_dict(data: Dict[str, Any], market: Optional[str] = None, lang: Optional[str] = None) -> Lead:
    """Tolerant construction from n8n / Sheets rows (string numbers, missing keys...)."""
    d = {k: v for k, v in (data or {}).items() if v is not None}
    for alias, key in (("lead_id", "id"), ("place_id", "id"), ("business_name", "name"), ("title", "name"),
                       ("websiteUri", "website"), ("url", "website"), ("formatted_address", "address"),
                       ("nationalPhoneNumber", "phone"), ("internationalPhoneNumber", "phone_intl"),
                       ("googleMapsUri", "maps_url"), ("userRatingCount", "rating_count"),
                       ("primaryType", "primary_type"), ("region", "admin_area"), ("state", "admin_area")):
        if alias in d and key not in d:
            d[key] = d[alias]
    allowed = set(Lead.model_fields)
    clean = {k: v for k, v in d.items() if k in allowed}
    if market:
        clean["market"] = market
    if lang:
        clean["lang"] = lang
    if not clean.get("name"):
        raise ValueError("Lead nemá název (name)")
    return Lead(**clean)


def _result_from_lead(lead: Lead) -> ProcessResult:
    info = lead.country_info
    return ProcessResult(
        lead_id=lead.id, name=lead.name, category=lead.category, primary_type=lead.primary_type,
        country=lead.country, admin_area=lead.admin_area, city=lead.city, address=lead.address,
        phone=lead.phone or lead.phone_intl, website=lead.website, has_website=lead.has_website,
        rating=lead.rating, rating_count=lead.rating_count, maps_url=lead.maps_url,
        market=lead.market, lang=lead.lang, tz=lead.tz, legal_regime=lead.legal_regime,
        legal_note_cs=info.legal_note_cs, legal_note_en=info.legal_note_en,
        industry=industries.industry_for(lead.primary_type, lead.types, lead.name, lead.category),
    )


def process_lead(lead_dict: Dict[str, Any], market: Optional[str] = None, lang: Optional[str] = None,
                 force: bool = False, *, settings: Optional[Settings] = None, with_screenshots: bool = True,
                 with_llm: bool = True, with_images: bool = True, with_pagespeed: bool = True,
                 owner_note: str = "") -> Dict[str, Any]:
    """Run the whole pipeline for one lead and return a flat dict for n8n."""
    s = settings or get_settings()
    try:
        lead = lead_from_dict(lead_dict, market, lang)
    except Exception as exc:          # noqa: BLE001
        return ProcessResult(name=str((lead_dict or {}).get("name", "")), branch="skip",
                             warnings=[f"Neplatný lead: {exc}"]).model_dump()
    res = _result_from_lead(lead)

    # 1. blocked-country guard (Costa Rica always) -------------------------
    if s.is_blocked(lead.country) or (not lead.country and not force):
        res.branch = "blocked"
        res.blocked_reason = s.block_reason(lead.country, "cs")
        res.reasons_cs = [res.blocked_reason]
        res.reasons_en = [s.block_reason(lead.country, "en")]
        if not lead.country:
            res.warnings.append("Země leadu není známa - doplňte country (ISO2) nebo spusťte s force=true.")
        log.info("Lead %s blokován: %s", lead.name, res.blocked_reason)
        return res.model_dump()
    if lead.legal_regime == "blocked":
        res.branch = "blocked"
        res.blocked_reason = s.block_reason(lead.country, "cs")
        res.reasons_cs = [res.blocked_reason]
        return res.model_dump()

    # 1b. UNIQUE_CITY_V2 – stejný obor ve stejném městě nesmí mít stejnou šablonu ------------
    #     (kontrola ještě před auditem a LLM; když je vše obsazené, lead čeká na uvolnění šablony)
    from . import premium as _premium_u
    _act = (lead_dict or {}).get("_active_ids") or []
    if isinstance(_act, str):
        _act = [x for x in _act.replace(";", ",").split(",")]
    _premium_u.ACTIVE_IDS = {str(x).strip() for x in _act if str(x).strip()}
    if getattr(s, "premium_templates", False):
        _free, _why = _premium_u.unique_check(lead, s.preview_dir)
        if not _free:
            res.branch = "skip"
            res.warnings.append("SABLONA_OBSAZENA: " + _why)
            log.info("Lead %s: %s", lead.name, _why)
            return res.model_dump()

    # 2. audit ---------------------------------------------------------------
    try:
        if lead.website:
            audit = audit_mod.audit_website(lead.website, s, with_pagespeed=with_pagespeed)
        else:
            audit = audit_mod.no_website_result()
    except Exception as exc:          # noqa: BLE001 - audit must not kill the lead
        log.error("Audit selhal pro %s: %s", lead.name, traceback.format_exc())
        audit = audit_mod.no_website_result() if not lead.website else audit_mod.unreachable_result(lead.website, str(exc)[:80])
        res.warnings.append(f"Audit selhal, použit nouzový výsledek: {exc}")
    res.branch = audit.branch
    res.score = audit.score
    res.reasons_cs = audit.reasons_text("cs")
    res.reasons_en = audit.reasons_text("en")
    res.reason_keys = [r.key for r in audit.reasons]
    res.emails = audit.emails
    res.phones = audit.phones or ([lead.phone] if lead.phone else [])
    res.best_email = audit.emails[0] if audit.emails else ""
    res.final_url = audit.final_url
    res.cms = audit.cms
    res.tech = audit.tech
    res.pagespeed_mobile = audit.pagespeed_mobile
    # POKRYVACI_V1: pokrývači / střechaři jen bez webu – firmy s webem přeskočit
    _roof_txt = " ".join([lead.primary_type or "", lead.category or "", " ".join(lead.types or [])]).lower()
    if audit.branch == "redesign" and any(k in _roof_txt for k in ("roofing", "roofer", "pokrýv", "pokryv", "střech", "strech", "klempíř")):
        audit.branch = "skip"
        res.branch = "skip"
        res.reasons_cs = ["Pokrývači: návrh webu posíláme jen firmám bez webu"] + list(res.reasons_cs)
        res.reasons_en = ["Roofers: we only pitch businesses without a website"] + list(res.reasons_en)
        log.info("Lead %s: pokrývač s webem -> skip", lead.name)
    if audit.branch == "skip" and not force:
        log.info("Lead %s: skip (skóre %d)", lead.name, audit.score)
        return res.model_dump()

    # 2b. extrakce nabídky z původního webu (jen pro tuto firmu, šablony se nemění) --
    owner_note = (owner_note or "").strip()
    res.owner_note = owner_note
    try:
        offer = offer_extract.extract_offer(
            (audit.final_url or lead.website) if (lead.website and audit.reachable) else "",
            lead.lang, settings=s, owner_note=owner_note, use_llm=with_llm)
    except Exception as exc:          # noqa: BLE001
        offer = offer_extract.empty_offer(f"nabídka: {exc}")
    res.extracted_offer = offer.model_dump()
    res.offer_summary = offer.summary(lead.lang or "cs")
    res.offer_photos = " ".join(offer.photos[:8])
    res.warnings.extend(offer.warnings)

    # 3. copy ------------------------------------------------------------------
    industry_key = res.industry
    try:
        copy = copy_writer.write_copy(lead, industry_key, audit.summary(), s, use_llm=with_llm,
                                      offer=offer, owner_note=owner_note)
    except Exception as exc:          # noqa: BLE001
        res.warnings.append(f"Generování textů selhalo, použit fallback: {exc}")
        copy = copy_writer.fallback_copy(lead, industry_key)
    res.copy_source = copy.source

    # 4. build -----------------------------------------------------------------
    slug = make_slug(lead.name, lead.city, unique=lead.id or lead.address, lang=lead.lang)
    try:
        build = generate_site.build_site(lead, copy, industry_key, slug=slug, settings=s, use_images=with_images,
                                         best_email=res.best_email, audit_summary=audit.summary(),
                                         offer=offer, owner_note=owner_note)
    except Exception as exc:          # noqa: BLE001
        log.error("Build selhal pro %s: %s", lead.name, traceback.format_exc())
        res.warnings.append(f"Stavba náhledu selhala: {exc}")
        return res.model_dump()
    res.slug = build.slug
    res.preview_url = build.url
    res.image_source = build.image_source
    res.built = True

    # 5. screenshots ---------------------------------------------------------
    try:
        shots = screenshot_compare.make_screenshots(
            build.path, old_url=(audit.final_url or lead.website) if audit.reachable else "",
            name=lead.name, lang=lead.lang, brand_hex=industries.get_industry(industry_key)["palette"]["brand"],
            settings=s, with_playwright=with_screenshots)
        res.warnings.extend(str(w) for w in shots.get("warnings", []))
    except Exception as exc:          # noqa: BLE001
        res.warnings.append(f"Screenshoty selhaly: {exc}")

    # 6. publish ---------------------------------------------------------------
    try:
        urls = deploy_preview.publish(build.slug, status="built", settings=s,
                                      extra={"branch": res.branch, "score": res.score})
        res.preview_url = urls["preview_url"]
        res.compare_png_url = urls.get("compare_png_url", "")
        res.og_png_url = urls.get("og_png_url", "")
        res.new_mobile_png_url = urls.get("new_mobile_png_url", "")
    except Exception as exc:          # noqa: BLE001
        res.warnings.append(f"Publikace selhala: {exc}")
    log.info("Lead %s hotov: %s skóre %d -> %s", lead.name, res.branch, res.score, res.preview_url)
    return res.model_dump()
