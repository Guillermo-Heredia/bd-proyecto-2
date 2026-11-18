const { chromium } = require('playwright-core');

(async () => {
  const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
  const ctx = browser.contexts()[0];
  const page = ctx.pages()[0];
  const entry = page.locator('.file-entry:has(.file-name:text-is("bd_1k"))').first();

  await entry.click();
  await page.waitForTimeout(500);
  await entry.click({ button: 'right' });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: '/tmp/context_menu.png' });

  const menuText = await page.evaluate(() => {
    const out = [];
    for (const el of document.querySelectorAll('.context-menu, .dropdown-menu, [role="menu"], .MuiMenu-root, .pgadmin-context-menu, ul li')) {
      const t = (el.innerText || '').replace(/\n+/g, ' | ').trim();
      if (t) out.push({ cls: (el.className || '').toString().slice(0, 80), t: t.slice(0, 600) });
    }
    return out.slice(-10);
  });
  console.log('MENUS:', JSON.stringify(menuText, null, 1).slice(0, 5000));

  const qts = page.getByText('Query Tool', { exact: true });
  console.log('Query Tool count:', await qts.count());
  if (await qts.count()) {
    await qts.last().click();
    console.log('clicked Query Tool');
  }
  await page.waitForTimeout(4000);
  console.log('pages:', ctx.pages().length);
  for (const p of ctx.pages()) console.log('  PAGE', p.url(), await p.title());
  console.log('body:', (await page.locator('body').innerText()).replace(/\n+/g, ' | ').slice(0, 1200));
  await page.screenshot({ path: '/tmp/query_tool.png' });
  await browser.close();
})().catch(e => { console.error('ERR', e); process.exit(1); });
