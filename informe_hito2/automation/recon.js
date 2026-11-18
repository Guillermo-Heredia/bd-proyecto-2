const { chromium } = require('playwright-core');

(async () => {
  const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
  console.log('connected, contexts:', browser.contexts().length);
  for (const [ci, ctx] of browser.contexts().entries()) {
    console.log(`--- context ${ci}, pages ${ctx.pages().length}`);
    for (const page of ctx.pages()) {
      console.log('PAGE:', JSON.stringify(await page.title()), page.url());
      const txt = await page.evaluate(() => document.body ? document.body.innerText.slice(0, 1500) : 'NO BODY');
      console.log('TEXT:', txt.replace(/\n+/g, ' | ').slice(0, 1500));
      const btns = await page.evaluate(() => Array.from(document.querySelectorAll('button,[role=button]'))
        .slice(0, 80)
        .map(b => ({ t: b.getAttribute('title'), a: b.getAttribute('aria-label'), x: (b.innerText || '').trim().slice(0, 40) }))
        .filter(b => b.t || b.a || b.x));
      console.log('BUTTONS:', JSON.stringify(btns, null, 1).slice(0, 4000));
    }
  }
  await browser.close();
})().catch(e => { console.error('ERR', e); process.exit(1); });
