/* Společný základ vzorů hero (AI_FIRMA, 3. 11. 2026)
   - Téma: světlé při načtení, tmavé přepínačem [data-prepnout-tema]; ?tema=tmava otevře tmavé (náhledy, kontrola).
   - Pohyb (vše vypne prefers-reduced-motion nebo ?pohyb=0):
     [data-slozit]          nadpis se složí po slovech při načtení
     [data-odhalit]         postupné odhalení při scrollu ("deti" = postupně děti)
     [data-magnet]          magnetické tlačítko (ne v liště)
     [data-parallax="0.12"] mírný parallax při scrollu (násobek posunu)
     [data-parallax-mys="10"] mírný posun za myší v px (jen hero)
     [data-stopa]           stopa drobných částic za kurzorem; barva z CSS proměnné --stopa
*/
(function () {
  var html = document.documentElement;
  var qs = new URLSearchParams(location.search);
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches || qs.get('pohyb') === '0';
  var jemny = window.matchMedia('(pointer: fine)').matches;
  window.Zaklad = { pohyb: !reduce, jemny: jemny };

  /* ---------- téma ---------- */
  function nastavTema(t) {
    html.dataset.tema = t;
    document.querySelectorAll('[data-prepnout-tema]').forEach(function (b) {
      b.setAttribute('aria-pressed', t === 'tmava' ? 'true' : 'false');
      b.setAttribute('aria-label', t === 'tmava' ? 'Přepnout na světlý režim' : 'Přepnout na tmavý režim');
    });
    document.dispatchEvent(new CustomEvent('zmena-tematu', { detail: t }));
  }
  if (!html.dataset.tema) html.dataset.tema = (qs.get('tema') === 'tmava' || location.hash === '#tmava') ? 'tmava' : 'svetla';
  function initTema() {
    nastavTema(html.dataset.tema);
    document.querySelectorAll('[data-prepnout-tema]').forEach(function (b) {
      b.addEventListener('click', function () {
        nastavTema(html.dataset.tema === 'tmava' ? 'svetla' : 'tmava');
      });
    });
  }

  /* ---------- nadpis se složí ---------- */
  function rozdelSlova(el) {
    var slova = [];
    (function projdi(uzel) {
      Array.prototype.slice.call(uzel.childNodes).forEach(function (n) {
        if (n.nodeType === 3) {
          var casti = n.textContent.split(/([ \t\n\r]+)/); /* NBSP nedělí: drží slova u sebe */
          var frag = document.createDocumentFragment();
          casti.forEach(function (c) {
            if (!c) return;
            if (/^[ \t\n\r]+$/.test(c)) { frag.appendChild(document.createTextNode(c)); return; }
            var w = document.createElement('span'); w.className = 'sl-w';
            var i = document.createElement('span'); i.className = 'sl-i'; i.textContent = c;
            w.appendChild(i); frag.appendChild(w); slova.push(i);
          });
          uzel.replaceChild(frag, n);
        } else if (n.nodeType === 1 && n.tagName !== 'BR' && !n.hasAttribute('data-nedelit')) {
          projdi(n);
        } else if (n.nodeType === 1 && n.hasAttribute('data-nedelit')) {
          var w2 = document.createElement('span'); w2.className = 'sl-w';
          n.parentNode.insertBefore(w2, n); w2.appendChild(n); n.classList.add('sl-i'); slova.push(n);
        }
      });
    })(el);
    return slova;
  }
  function initSlozit() {
    var cile = document.querySelectorAll('[data-slozit]');
    if (!cile.length) return;
    if (!window.Zaklad.pohyb) { cile.forEach(function (c) { c.style.visibility = 'visible'; }); return; }
    var start = function () {
      cile.forEach(function (el, idx) {
        if (!el.hasAttribute('aria-label')) { var kl = el.cloneNode(true); kl.querySelectorAll('br').forEach(function (b) { b.replaceWith(' '); }); el.setAttribute('aria-label', kl.textContent.replace(/\s+/g, ' ').trim()); }
        var slova = rozdelSlova(el);
        slova.forEach(function (s) { s.setAttribute('aria-hidden', 'true'); });
        el.style.visibility = 'visible';
        var zpozdeni = parseFloat(el.getAttribute('data-slozit')) || 0;
        slova.forEach(function (s, i) {
          s.animate([
            { transform: 'translate3d(0,105%,0)', opacity: 0 },
            { transform: 'translate3d(0,0,0)', opacity: 1 }
          ], { duration: 900, delay: zpozdeni * 1000 + 120 + i * 70 + idx * 120, easing: 'cubic-bezier(.2,.7,.1,1)', fill: 'both' });
        });
      });
      /* používá vlastnost translate (ne transform), takže nepřepíše transform prvku ani magnet; po doběhnutí se animace uklidí */
      document.querySelectorAll('[data-po-nadpisu]').forEach(function (el) {
        var d = parseFloat(el.getAttribute('data-po-nadpisu')) || 0;
        var a = el.animate([{ opacity: 0, translate: '0 14px' }, { opacity: 1, translate: '0 0' }],
          { duration: 800, delay: 650 + d * 1000, easing: 'cubic-bezier(.2,.7,.1,1)', fill: 'both' });
        a.onfinish = function () { el.style.opacity = '1'; a.cancel(); };
      });
    };
    var hotovo = false;
    var spust = function () { if (!hotovo) { hotovo = true; start(); } };
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(spust);
    setTimeout(spust, 1200);
  }

  /* ---------- odhalování ---------- */
  function initOdhalit() {
    var el = document.querySelectorAll('[data-odhalit]');
    if (!el.length) return;
    if (!window.Zaklad.pohyb || !('IntersectionObserver' in window)) {
      el.forEach(function (e) { e.classList.add('odhaleno'); }); return;
    }
    var io = new IntersectionObserver(function (zaznamy) {
      zaznamy.forEach(function (z) {
        if (!z.isIntersecting) return;
        var e = z.target; io.unobserve(e);
        if (e.getAttribute('data-odhalit') === 'deti') {
          Array.prototype.forEach.call(e.children, function (d, i) { d.style.transitionDelay = (i * 90) + 'ms'; });
        }
        e.classList.add('odhaleno');
      });
    }, { rootMargin: '0px 0px -10% 0px', threshold: 0.12 });
    el.forEach(function (e) { io.observe(e); });
  }

  /* ---------- magnetická tlačítka ---------- */
  function initMagnet() {
    if (!window.Zaklad.pohyb || !jemny) return;
    document.querySelectorAll('[data-magnet]').forEach(function (b) {
      var sila = parseFloat(b.getAttribute('data-magnet')) || 0.28;
      var vnitrek = b.querySelector('[data-magnet-vnitrek]');
      b.addEventListener('pointermove', function (e) {
        var r = b.getBoundingClientRect();
        var x = e.clientX - (r.left + r.width / 2), y = e.clientY - (r.top + r.height / 2);
        b.style.transform = 'translate3d(' + (x * sila).toFixed(1) + 'px,' + (y * sila).toFixed(1) + 'px,0)';
        if (vnitrek) vnitrek.style.transform = 'translate3d(' + (x * sila * 0.5).toFixed(1) + 'px,' + (y * sila * 0.5).toFixed(1) + 'px,0)';
      });
      b.addEventListener('pointerleave', function () {
        b.style.transform = ''; if (vnitrek) vnitrek.style.transform = '';
      });
    });
  }

  /* ---------- parallax ---------- */
  function initParallax() {
    if (!window.Zaklad.pohyb) return;
    var scr = Array.prototype.slice.call(document.querySelectorAll('[data-parallax]'));
    var mys = jemny ? Array.prototype.slice.call(document.querySelectorAll('[data-parallax-mys]')) : [];
    if (!scr.length && !mys.length) return;
    var mx = 0, my = 0, tx = 0, ty = 0, ceka = false;
    function kresli() {
      ceka = false;
      var sy = window.scrollY;
      tx += (mx - tx) * 0.08; ty += (my - ty) * 0.08;
      scr.forEach(function (e) {
        var f = parseFloat(e.getAttribute('data-parallax')) || 0.12;
        e.style.setProperty('--px-scroll', (sy * f).toFixed(1) + 'px');
      });
      mys.forEach(function (e) {
        var m = parseFloat(e.getAttribute('data-parallax-mys')) || 10;
        e.style.setProperty('--px-mys-x', (tx * m).toFixed(2) + 'px');
        e.style.setProperty('--px-mys-y', (ty * m).toFixed(2) + 'px');
      });
      if (Math.abs(mx - tx) > 0.001 || Math.abs(my - ty) > 0.001) pozadej();
    }
    function pozadej() { if (!ceka) { ceka = true; requestAnimationFrame(kresli); } }
    window.addEventListener('scroll', pozadej, { passive: true });
    window.addEventListener('pointermove', function (e) {
      mx = (e.clientX / window.innerWidth - 0.5) * 2; my = (e.clientY / window.innerHeight - 0.5) * 2; pozadej();
    }, { passive: true });
    pozadej();
  }

  /* ---------- stopa částic za kurzorem (jen hero) ---------- */
  function initStopa() {
    if (!window.Zaklad.pohyb || !jemny) return;
    document.querySelectorAll('[data-stopa]').forEach(function (hero) {
      var cv = document.createElement('canvas');
      cv.className = 'stopa-platno'; cv.setAttribute('aria-hidden', 'true');
      hero.appendChild(cv);
      var ctx = cv.getContext('2d'), dpr = Math.min(window.devicePixelRatio || 1, 2);
      var w = 0, h = 0, castice = [], barva = '0,0,0', bezi = false, posl = null;
      function velikost() {
        var r = hero.getBoundingClientRect(); w = r.width; h = r.height;
        cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }
      function nactiBarvu() {
        var v = getComputedStyle(hero).getPropertyValue('--stopa').trim() || '#888';
        var t = document.createElement('span'); t.style.color = v; document.body.appendChild(t);
        var c = getComputedStyle(t).color; t.remove();
        var m = c.match(/[\d.]+/g); barva = m ? m.slice(0, 3).join(',') : '128,128,128';
      }
      velikost(); nactiBarvu();
      if ('ResizeObserver' in window) new ResizeObserver(velikost).observe(hero);
      document.addEventListener('zmena-tematu', function () { setTimeout(nactiBarvu, 30); });
      hero.addEventListener('pointermove', function (e) {
        var r = hero.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
        var n = 1;
        if (posl) { var d = Math.hypot(x - posl.x, y - posl.y); n = Math.min(3, Math.floor(d / 14) + 1); }
        posl = { x: x, y: y };
        for (var i = 0; i < n && castice.length < 90; i++) {
          castice.push({ x: x + (Math.random() - 0.5) * 6, y: y + (Math.random() - 0.5) * 6,
            vx: (Math.random() - 0.5) * 0.35, vy: (Math.random() - 0.5) * 0.35 - 0.12,
            r: 0.8 + Math.random() * 1.5, z: performance.now(), t: 650 + Math.random() * 500 });
        }
        if (!bezi) { bezi = true; requestAnimationFrame(krok); }
      });
      hero.addEventListener('pointerleave', function () { posl = null; });
      function krok(now) {
        ctx.clearRect(0, 0, w, h);
        castice = castice.filter(function (p) { return now - p.z < p.t; });
        castice.forEach(function (p) {
          var k = 1 - (now - p.z) / p.t;
          p.x += p.vx; p.y += p.vy;
          ctx.beginPath(); ctx.arc(p.x, p.y, p.r * (0.6 + 0.4 * k), 0, 6.283);
          ctx.fillStyle = 'rgba(' + barva + ',' + (0.55 * k).toFixed(3) + ')'; ctx.fill();
        });
        if (castice.length) requestAnimationFrame(krok); else { bezi = false; ctx.clearRect(0, 0, w, h); }
      }
    });
  }

  /* ---------- mobilní menu: doplnění přístupnosti ----------
     Na tlačítko menu dej [data-menu-zaklad] a aria-expanded. Stránka si menu otevírá a zavírá sama (klikem na tlačítko).
     Základ k tomu přidá: aria-controls, zavření klávesou Esc (focus zpět na tlačítko), klikem na odkaz a klikem mimo,
     a po otevření přesune focus na první odkaz. Panel najde přes aria-controls, jinak .menu-panel v liště. */
  function initMenu() {
    document.querySelectorAll('button[data-menu-zaklad][aria-expanded]').forEach(function (b) {
      var id = b.getAttribute('aria-controls');
      var panel = id ? document.getElementById(id) : null;
      if (!panel) { var l = b.closest('header, .lista, nav') || document; panel = l.querySelector('.menu-panel'); }
      if (!panel) return;
      if (!panel.id) panel.id = 'menu-panel-zaklad';
      b.setAttribute('aria-controls', panel.id);
      function otevreno() { return b.getAttribute('aria-expanded') === 'true'; }
      function zavri(vratFocus) { if (otevreno()) { b.click(); if (vratFocus) b.focus(); } }
      document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && otevreno()) { e.preventDefault(); zavri(true); } });
      panel.addEventListener('click', function (e) { if (e.target.closest('a')) setTimeout(function () { zavri(false); }, 0); });
      document.addEventListener('click', function (e) {
        if (otevreno() && !panel.contains(e.target) && !b.contains(e.target)) zavri(false);
      });
      new MutationObserver(function () {
        if (otevreno()) { var a = panel.querySelector('a, button'); if (a) setTimeout(function () { a.focus({ preventScroll: true }); }, 30); }
      }).observe(b, { attributes: true, attributeFilter: ['aria-expanded'] });
    });
  }

  /* ---------- návrat na rozcestník ukázek (jen když přišel z rozcestníku; není součást designu) ---------- */
  function initZpet() {
    try {
      var r = document.referrer ? new URL(document.referrer) : null;
      if (!r || r.origin !== location.origin || !/(\/|index\.html)$/.test(r.pathname)) return;
      var a = document.createElement('a');
      a.href = r.pathname; a.textContent = '← Všechny vzory'; a.className = 'zpet-rozcestnik';
      a.style.cssText = 'position:fixed;left:14px;bottom:14px;z-index:9999;font:500 12px/1 system-ui,sans-serif;' +
        'padding:9px 13px;border-radius:999px;background:rgba(18,18,18,.72);color:#fff;' +
        '-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);letter-spacing:0;text-transform:none';
      document.body.appendChild(a);
    } catch (e) {}
  }

  function init() { initTema(); initZpet(); initMenu(); initSlozit(); initOdhalit(); initMagnet(); initParallax(); initStopa(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
