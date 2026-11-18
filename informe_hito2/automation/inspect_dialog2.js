const { chromium } = require('playwright-core');

(async () => {
  const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0];
  console.log('pages:', ctx.pages().length, 'url', page.url());
  console.log('text before:', (await page.locator('body').innerText()).replace(/\n+/g, ' | ').slice(0, 800));
  await page.getByText('Add New Server', { exact: true }).first().click();
  await page.waitForTimeout(2500);
  console.log('pages after:', ctx.pages().length, 'url', page.url());
  await page.screenshot({ path: '/tmp/after_add.png' });
  console.log('text after:', (await page.locator('body').innerText()).replace(/\n+/g, ' | ').slice(0, 2000));
  const info = await page.evaluate(() => {
    const out = [];
    for (const el of document.querySelectorAll('div,section,form,aside')) {
      const cls = (el.className && typeof el.className === 'string') ? el.className : '';
      const style = getComputedStyle(el);
      if (/dialog|modal|drawer|overlay|backdrop/i.test(cls) || (parseInt(style.zIndex) > 100 && style.position !== 'static')) {
        out.push({ tag: el.tagName, cls: cls.slice(0, 120), z: style.zIndex, pos: style.position, role: el.getAttribute('role'), txt: (el.innerText || '').replace(/\n+/g, ' | ').slice(0, 200) });
      }
    }
    return out.slice(0, 40);
  });
  console.log(JSON.stringify(info, null, 1).slice(0, 8000));
  await browser.close();
})().catch(e => { console.error('ERR', e); process.exit(1); });
