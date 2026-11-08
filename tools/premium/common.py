"""Společné bloky vkládané do všech premium šablon (hodnocení Google, patička, lišta náhledu, odeslání formulářů)."""
from __future__ import annotations

T = {
    'cs': {
        'rating_of': 'z 5', 'on_google': 'Hodnocení na Googlu', 'reviews': 'recenzí', 'maps': 'Zobrazit na Mapách Google',
        'credit': 'Návrh webu', 'photos': 'Fotografie: Unsplash',
        'pv_before': 'Nezávazný návrh nového webu pro', 'pv_prep': 'připravil', 'pv_want': 'Chci tento web', 'pv_wa': 'WhatsApp', 'pv_hide': 'Skrýt',
        'phone': 'Telefon', 'email': 'E-mail', 'address': 'Adresa', 'hours': 'Otevírací doba',
    },
    'en': {
        'rating_of': 'out of 5', 'on_google': 'Rating on Google', 'reviews': 'reviews', 'maps': 'View on Google Maps',
        'credit': 'Website draft by', 'photos': 'Photos: Unsplash',
        'pv_before': 'Non-binding draft of a new website for', 'pv_prep': 'prepared by', 'pv_want': 'I want this website', 'pv_wa': 'WhatsApp', 'pv_hide': 'Hide',
        'phone': 'Phone', 'email': 'E-mail', 'address': 'Address', 'hours': 'Opening hours',
    },
}

CSS = """<style id="pz-css">
.pz-hod{padding:clamp(56px,9vw,104px) 24px;text-align:center;color:inherit;border-top:1px solid color-mix(in srgb,currentColor 14%,transparent)}
.pz-hod .pz-in{max-width:560px;margin:0 auto}
.pz-hod .pz-cislo{font-size:clamp(44px,7vw,72px);line-height:1;margin:0;font-weight:500;letter-spacing:-.02em}
.pz-hod .pz-cislo span{font-size:.32em;opacity:.7;letter-spacing:0;margin-left:.3em}
.pz-hod .pz-hv{position:relative;display:inline-block;font-size:22px;letter-spacing:4px;margin:14px 0 8px;color:color-mix(in srgb,currentColor 22%,transparent)}
.pz-hod .pz-hv b{position:absolute;inset:0 auto 0 0;overflow:hidden;white-space:nowrap;color:var(--akcent,var(--accent,#E3A008));font-weight:400}
.pz-hod .pz-pod{margin:0 0 14px;opacity:.78}
.pz-hod a{color:inherit}
.pz-pata{padding:28px 24px 34px;text-align:center;font-size:14px;opacity:.85;border-top:1px solid color-mix(in srgb,currentColor 14%,transparent)}
.pz-pata p{margin:4px 0}.pz-pata a{color:inherit}
.pz-credit{font-size:12px;opacity:.7;text-align:center;padding:0 24px 22px}
.pz-credit a{color:inherit}
.pz-pv{position:fixed;left:12px;right:12px;bottom:12px;z-index:2147483000;background:#111827;color:#fff;font:14px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;
 padding:10px 14px;border-radius:14px;display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center;justify-content:center;box-shadow:0 10px 30px rgba(0,0,0,.3)}
.pz-pv a{color:#fff}.pz-pv .pz-cta{background:#fff;color:#111827;text-decoration:none;font-weight:700;padding:.4em .85em;border-radius:999px}
.pz-pv button{background:none;border:0;color:#fff;opacity:.8;cursor:pointer;font:inherit;text-decoration:underline}
.pz-pv.pz-skryt{display:none}
@media print{.pz-pv{display:none}}
</style>"""


def common_blocks(cfg, lang):
    t = T[lang]
    rating = f"""@@IF rating@@<section class="pz-hod" aria-label="{t['on_google']}"><div class="pz-in">
<p class="pz-cislo">@@V rating_txt@@<span>{t['rating_of']}</span></p>
<p class="pz-hv" aria-hidden="true">★★★★★<b style="width:@@V rating_pct@@%">★★★★★</b></p>
<p class="pz-pod">{t['on_google']}@@IF show_count@@ · @@V rating_count@@ {t['reviews']}@@ENDIF@@</p>
@@IF maps_url@@<p><a href="@@V maps_url@@" target="_blank" rel="noopener">{t['maps']}</a></p>@@ENDIF@@
</div></section>@@ENDIF@@"""
    footer = f"""<footer class="pz-pata"><p><strong>@@V name@@</strong></p>
@@IF address@@<p>@@V address@@</p>@@ENDIF@@
<p>@@IF phone@@<a href="tel:@@V phone_href@@">@@V phone@@</a>@@ENDIF@@@@IF phone and email@@ · @@ENDIF@@@@IF email@@<a href="mailto:@@V email@@">@@V email@@</a>@@ENDIF@@</p></footer>"""
    tail = f"""<p class="pz-credit">{t['credit']}: <a href="@@V owner_site@@" rel="noopener">@@V owner_name@@</a> · {t['photos']}</p>
@@IF show_banner@@<div class="pz-pv" id="pz-pv" role="note"><span>{t['pv_before']} <strong>@@V name@@</strong> · {t['pv_prep']} @@V owner_name@@</span>
<a class="pz-cta" href="@@V want_url@@">{t['pv_want']}</a>@@IF wa_url@@<a class="pz-cta" href="@@V wa_url@@" target="_blank" rel="noopener">{t['pv_wa']}</a>@@ENDIF@@
<button type="button" data-pz-skryt>{t['pv_hide']}</button></div>@@ENDIF@@
<script id="pz-js">(function(){{
var pv=document.getElementById('pz-pv');if(pv){{var x=pv.querySelector('[data-pz-skryt]');x&&x.addEventListener('click',function(){{pv.classList.add('pz-skryt');}});}}
var HOOK="@@V form_webhook_url@@",LEAD="@@V lead_id@@";
function lab(f,el){{var l=el.id&&f.querySelector('label[for="'+el.id+'"]');if(!l)l=el.closest('label');var s=(l?l.textContent:'')||el.name||'';return s.replace(/\\s+/g,' ').replace(/\\*/g,'').trim();}}
document.addEventListener('submit',function(e){{var f=e.target;if(!f||f.tagName!=='FORM'||f.hasAttribute('data-pz-ignore')||!HOOK)return;
  var d={{lead_id:LEAD,source:'preview',name:'',email:'',phone:'',message:''}},rest=[],seen={{}};
  Array.prototype.forEach.call(f.elements,function(el){{ if(!el.name||el.type==='submit'||el.type==='button')return; if((el.type==='checkbox'||el.type==='radio')&&!el.checked)return;
   var v=(el.value||'').trim(); if(!v)return; var n=el.name.toLowerCase();
   if(/^(jmeno|name|jmeno_prijmeni)$/.test(n))d.name=v; else if(/^(email|e-mail)$/.test(n))d.email=v; else if(/^(telefon|phone|tel)$/.test(n))d.phone=v;
   else {{var k=lab(f,el)||el.name; if(seen[k]){{seen[k].push(v);}}else{{seen[k]=[v];rest.push(k);}}}} }});
  d.message=rest.map(function(k){{return k+': '+seen[k].join(', ');}}).join('\\n');
  setTimeout(function(){{ if(f.querySelector('[aria-invalid="true"],.chyba,.is-invalid'))return; if(!f.hasAttribute('novalidate')&&!f.checkValidity())return; if(!d.name&&!d.email&&!d.phone)return;
   try{{fetch(HOOK,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(d)}});}}catch(err){{}}
  }},0);
}},true);
}})();</script>"""
    return {'css': CSS, 'rating': rating, 'footer': footer, 'tail': tail}


EXT_CSS = """<style id="pz-ext-css">
.pz-ext{color:var(--text,inherit);border-top:1px solid var(--linka,color-mix(in srgb,currentColor 14%,transparent))}
.pz-ext .pz-obal{max-width:1180px;margin:0 auto;padding:clamp(64px,9vw,120px) clamp(20px,5vw,56px)}
.pz-ext h2{font-family:var(--pz-h,inherit);font-size:clamp(30px,4.2vw,52px);line-height:1.05;margin:0 0 18px;font-weight:500;letter-spacing:-.01em}
.pz-ext .pz-uvod{max-width:620px;color:var(--tlumeny,inherit);opacity:.95;margin:0 0 40px;font-size:18px;line-height:1.55}
.pz-ext .pz-tri{display:grid;grid-template-columns:repeat(3,1fr);gap:28px}
.pz-ext .pz-tri h3{font-size:20px;margin:0 0 8px;font-weight:600}
.pz-ext .pz-tri p{margin:0;color:var(--tlumeny,inherit);line-height:1.55}
.pz-ext .pz-tri div{padding-top:18px;border-top:2px solid var(--akcent,currentColor)}
.pz-ext .pz-dva{display:grid;grid-template-columns:1fr 1.2fr;gap:clamp(28px,5vw,72px);align-items:start}
.pz-ext dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:10px 18px}
.pz-ext dt{color:var(--tlumeny,inherit)}.pz-ext dd{margin:0}
.pz-ext a{color:inherit}
.pz-ext .pz-hod-t{margin-top:26px;display:grid;grid-template-columns:auto 1fr;gap:6px 18px;font-variant-numeric:tabular-nums}
.pz-ext .pz-hod-t .dnes{font-weight:700}
.pz-ext form{display:grid;gap:14px}
.pz-ext label{display:grid;gap:6px;font-size:14px;color:var(--tlumeny,inherit)}
.pz-ext input,.pz-ext textarea{font:inherit;font-size:16px;color:var(--text,inherit);background:transparent;border:1px solid var(--linka,color-mix(in srgb,currentColor 25%,transparent));border-radius:12px;padding:12px 14px}
.pz-ext textarea{min-height:120px;resize:vertical}
.pz-ext input:focus,.pz-ext textarea:focus{outline:2px solid var(--akcent,currentColor);outline-offset:1px}
.pz-ext button{justify-self:start;font:inherit;font-weight:600;background:var(--akcent,currentColor);color:var(--na-akcentu,#fff);border:0;border-radius:999px;padding:13px 24px;cursor:pointer}
.pz-ext .pz-ok{min-height:1.4em;margin:0;font-size:15px}
.pz-ext details{border-top:1px solid var(--linka,color-mix(in srgb,currentColor 18%,transparent));padding:18px 0}
.pz-ext details:last-of-type{border-bottom:1px solid var(--linka,color-mix(in srgb,currentColor 18%,transparent))}
.pz-ext summary{cursor:pointer;font-size:clamp(19px,2vw,23px);font-weight:600;list-style:none;display:flex;justify-content:space-between;gap:16px}
.pz-ext summary::after{content:"+";font-weight:400}.pz-ext details[open] summary::after{content:"–"}
.pz-ext summary::-webkit-details-marker{display:none}
.pz-ext details p{max-width:760px;line-height:1.65;color:var(--tlumeny,inherit);margin:12px 0 0}
@media (max-width:820px){.pz-ext .pz-tri,.pz-ext .pz-dva{grid-template-columns:1fr}}
</style>"""


def extension_html(cfg, lang):
    e = cfg['ext'][lang]
    t = T[lang]
    proc = ''.join(f'<div><h3>{h}</h3><p>{p}</p></div>' for h, p in e['proc'])
    rady = ''.join(f'<details><summary>{h}</summary>' + ''.join(f'<p>{p}</p>' for p in ps) + '</details>' for h, ps in e['rady'])
    days = ''
    return f"""<section class="pz-ext" id="proc"><div class="pz-obal">
<h2>{e['proc_h']}</h2><p class="pz-uvod">{e['proc_uvod']}</p><div class="pz-tri">{proc}</div></div></section>
<section class="pz-ext" id="kontakt-formular"><div class="pz-obal pz-dva">
<div><h2>{e['kontakt_h']}</h2><p class="pz-uvod">{e['kontakt_uvod']}</p>
<dl>@@IF address@@<dt>{t['address']}</dt><dd>@@V address@@@@IF maps_url@@ · <a href="@@V maps_url@@" target="_blank" rel="noopener">{e['mapa']}</a>@@ENDIF@@</dd>@@ENDIF@@
@@IF phone@@<dt>{t['phone']}</dt><dd><a href="tel:@@V phone_href@@">@@V phone@@</a></dd>@@ENDIF@@
@@IF email@@<dt>{t['email']}</dt><dd><a href="mailto:@@V email@@">@@V email@@</a></dd>@@ENDIF@@</dl>
@@IF hours@@<div class="pz-hod-t" aria-label="{t['hours']}">@@RAW hours_rows@@</div>@@ENDIF@@</div>
<form data-formular="dotaz" class="pz-form" novalidate>
<label for="pz-j">{e['f_jmeno']}<input id="pz-j" name="jmeno" autocomplete="name" required></label>
<label for="pz-t">{e['f_tel']}<input id="pz-t" name="telefon" type="tel" autocomplete="tel"></label>
<label for="pz-e">{e['f_email']}<input id="pz-e" name="email" type="email" autocomplete="email" required></label>
<label for="pz-z">{e['f_zprava']}<textarea id="pz-z" name="zprava" required></textarea></label>
<button type="submit">{e['f_odeslat']}</button><p class="pz-ok" role="status" aria-live="polite"></p></form>
<script>(function(){{var f=document.currentScript.previousElementSibling;f.addEventListener('submit',function(e){{e.preventDefault();var bad=null;
f.querySelectorAll('[required]').forEach(function(el){{var ok=el.value.trim()&&(el.type!=='email'||/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(el.value));el.setAttribute('aria-invalid',ok?'false':'true');if(!ok&&!bad)bad=el;}});
var m=f.querySelector('.pz-ok');if(bad){{m.textContent='{e['f_chyba']}';bad.focus();return;}}m.textContent='{e['f_dik']}';setTimeout(function(){{f.reset();}},50);}});}})();</script>
</div></section>
<section class="pz-ext" id="rady"><div class="pz-obal"><h2>{e['rady_h']}</h2><p class="pz-uvod">{e['rady_uvod']}</p>{rady}</div></section>"""
