const { chromium } = require('playwright-core');

(async () => {
  const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
  const page = browser.contexts()[0].pages()[0];

  const entry = (name) => page.locator(`.file-entry:has(.file-name:text-is("${name}"))`).first();

  for (const name of ['pg-turbinas', 'Databases', 'bd_1k']) {
    const e = entry(name);
    console.log(name, 'count', await e.count());
    if (await e.count()) {
      const toggle = e.locator('.directory-toggle');
      const cls = await toggle.getAttribute('class').catch(() => null);
      console.log(name, 'toggle class', cls);
      if (cls !== null && !cls.includes('open')) {
        await toggle.click();
        await page.waitForTimeout(1500);
      }
    }
  }

  const names = await page.evaluate(() => Array.from(document.querySelectorAll('.file-entry .file-name')).map(e => e.textContent.trim()));
  console.log('TREE:', JSON.stringify(names));
  await browser.close();
})().catch(e => { console.error('ERR', e); process.exit(1); });
