const { chromium } = require('playwright-core');

(async () => {
  const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0];
  const links = page.getByText('Add New Server', { exact: true });
  console.log('add links:', await links.count());
  await links.first().click();
  await page.waitForTimeout(2000);

  const dialogs = page.locator('[role="dialog"]');
  console.log('dialogs:', await dialogs.count());
  const dlg = dialogs.last();
  console.log('dialog text:', (await dlg.innerText()).replace(/\n+/g, ' | ').slice(0, 1200));

  const fields = await page.evaluate(() => {
    const root = document.querySelector('[role="dialog"]') || document;
    return Array.from(root.querySelectorAll('input,textarea,select,button,[role="tab"]')).map((e, i) => ({
      i,
      tag: e.tagName.toLowerCase(),
      type: e.getAttribute('type'),
      name: e.getAttribute('name'),
      id: e.id || null,
      aria: e.getAttribute('aria-label'),
      ph: e.getAttribute('placeholder'),
      val: e.value ?? null,
      text: (e.innerText || '').trim().slice(0, 40),
      role: e.getAttribute('role'),
      testid: e.getAttribute('data-testid'),
    })).filter(x => x.tag !== 'button' || x.text || x.aria);
  });
  console.log(JSON.stringify(fields, null, 1).slice(0, 8000));
  await browser.close();
})().catch(e => { console.error('ERR', e); process.exit(1); });
