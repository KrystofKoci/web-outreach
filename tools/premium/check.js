// node check.js <root> <port> <outdir> [ids...]
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path'); const { execSync } = require('child_process');
const FONTS = '/home/claude/ref/fonts';
const [root, port, out, ...only] = process.argv.slice(2); fs.mkdirSync(out, { recursive: true });
function kebab(f) { return f.trim().toLowerCase().replace(/\+/g, ' ').replace(/\s+/g, '-'); }
function zajisti(f) { const d = path.join(FONTS, 'node_modules/@fontsource', kebab(f)); if (!fs.existsSync(d)) { try { execSync(`npm i @fontsource/${kebab(f)}`, { cwd: FONTS, stdio: 'ignore' }); } catch (e) {} } return fs.existsSync(d) ? d : null; }
function css(url) { const u = new URL(url); let c = '';
  for (const fam of u.searchParams.getAll('family')) { const n = fam.split(':')[0].replace(/\+/g, ' '); const d = zajisti(n); if (!d) continue;
    for (const x of fs.readdirSync(path.join(d, 'files')).filter(x => /-(latin|latin-ext)-\d+-(normal|italic)\.woff2$/.test(x))) {
      const m = x.match(/-(latin-ext|latin)-(\d+)-(normal|italic)\.woff2$/);
      c += `@font-face{font-family:'${n}';font-style:${m[3]};font-weight:${m[2]};font-display:block;src:url(https://fonts.gstatic.com/__local/${kebab(n)}/${x}) format('woff2');}\n`; } }
  return c; }
(async () => {
  const dirs = fs.readdirSync(root).filter(d => !d.startsWith('_') && (!only.length || only.some(o => d.startsWith(o)))).sort();
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'] });
  const rep = {};
  for (const d of dirs) for (const [w, h] of [[1440, 900], [390, 844]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h }, reducedMotion: 'reduce' });
    const p = await ctx.newPage(); const errs = []; const bad = [];
    p.on('pageerror', e => errs.push('JS: ' + e.message.slice(0, 160)));
    p.on('console', m => { if (m.type() === 'error' && !/favicon|ERR_|Failed to load resource/.test(m.text())) errs.push('C: ' + m.text().slice(0, 160)); });
    p.on('response', r => { if (r.status() >= 400 && r.url().includes('localhost')) bad.push(r.status() + ' ' + r.url().replace(/^.*localhost:\d+/, '')); });
    await p.route(/fonts\.googleapis\.com\/css/, r => r.fulfill({ status: 200, contentType: 'text/css', body: css(r.request().url()) }));
    await p.route(/fonts\.gstatic\.com\/__local\//, r => { const [, f, x] = r.request().url().match(/__local\/([^/]+)\/(.+)$/); r.fulfill({ status: 200, contentType: 'font/woff2', body: fs.readFileSync(path.join(FONTS, 'node_modules/@fontsource', f, 'files', x)) }); });
    await p.route(/n8n\.krystofkoci\.com/, r => r.fulfill({ status: 200, body: '{}' }));
    try { await p.goto(`http://localhost:${port}/${d}/`, { waitUntil: 'networkidle', timeout: 30000 }); } catch (e) { errs.push('GOTO ' + e.message.slice(0, 80)); }
    await p.waitForTimeout(1200);
    const H = await p.evaluate(() => document.documentElement.scrollHeight);
    for (let y = 0; y < H; y += 700) { await p.evaluate(yy => window.scrollTo(0, yy), y); await p.waitForTimeout(120); }
    await p.evaluate(() => window.scrollTo(0, 0)); await p.waitForTimeout(600);
    const info = await p.evaluate(() => { const t = document.body.innerText; const m = t.match(/(\[doplnit[^\]]*\]|@@[A-Z]+|\{\{|\{%|\[[A-ZÁ-Ž][^\]]{0,25}\])/g); return { left: m ? [...new Set(m)].slice(0, 8) : [], sw: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight }; });
    await p.screenshot({ path: `${out}/${d}-${w}.jpg`, type: 'jpeg', quality: 55 });
    if (w === 1440) await p.screenshot({ path: `${out}/${d}-${w}-full.jpg`, type: 'jpeg', quality: 40, fullPage: true }).catch(() => {});
    rep[`${d}@${w}`] = { errs: errs.slice(0, 5), bad: bad.slice(0, 5), left: info.left, overflow: info.sw > w + 1 ? info.sw : 0, h: info.h };
    await ctx.close();
  }
  await b.close();
  for (const [k, v] of Object.entries(rep)) { const issues = v.errs.length || v.bad.length || v.left.length || v.overflow; console.log((issues ? '!! ' : 'ok ') + k, issues ? JSON.stringify(v) : 'h=' + v.h); }
})();
