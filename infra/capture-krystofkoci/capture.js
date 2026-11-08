// Takes a screenshot and a short recording of the opening screen of every published client website.
// Runs inside the Playwright Docker image, started by capture.sh. Usage: node capture.js refs.json mediaDir
const fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const [, , refsFile, mediaDir] = process.argv;
const refs = (JSON.parse(fs.readFileSync(refsFile, 'utf8')).reference || []).filter((r) => /^https?:\/\//.test(r.web || ''));
(async () => {
  const browser = await chromium.launch();
  for (const r of refs) {
    const jpg = path.join(mediaDir, r.id + '.jpg'), raw = path.join(mediaDir, r.id + '.webm');
    if (fs.existsSync(jpg)) continue;
    const tmp = fs.mkdtempSync(path.join(mediaDir, 'tmp-'));
    try {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, recordVideo: { dir: tmp, size: { width: 1440, height: 900 } }, locale: 'cs-CZ' });
      const page = await ctx.newPage();
      await page.goto(r.web, { waitUntil: 'load', timeout: 45000 });
      await page.waitForTimeout(6500);                       // let the hero animation play
      await page.screenshot({ path: jpg, type: 'jpeg', quality: 82 });
      const v = page.video(); await ctx.close();
      if (v) fs.renameSync(await v.path(), raw);
      console.log('ok', r.id, r.web);
    } catch (e) { console.log('chyba', r.id, r.web, String(e).slice(0, 200)); }
    fs.rmSync(tmp, { recursive: true, force: true });
  }
  await browser.close();
})();
