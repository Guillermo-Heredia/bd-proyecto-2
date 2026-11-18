const { chromium } = require('playwright-core');

(async () => {
  const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
  const page = browser.contexts()[0].pages()[0];
  await page.screenshot({ path: '/tmp/server_dialog.png' });
  console.log('has Register - Server:', await page.getByText('Register - Server', { exact: true }).count());
  const fields = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('input,textarea,select')).map((e, i) => {
      let label = '';
      if (e.id) {
        const l = document.querySelector(`label[for="${e.id}"]`);
        if (l) label = l.innerText.trim();
      }
      const wrap = e.closest('.MuiFormControl-root');
      if (!label && wrap) {
        const l = wrap.querySelector('label');
        if (l) label = l.innerText.trim();
      }
      return { i, tag: e.tagName.toLowerCase(), type: e.type, name: e.name, id: e.id, aria: e.getAttribute('aria-label'), ph: e.placeholder, label, value: e.value, checked: e.checked };
    });
  });
  console.log(JSON.stringify(fields, null, 1).slice(0, 12000));
  const tabs = await page.evaluate(() => Array.from(document.querySelectorAll('[role="tab"],.MuiTab-root')).map(t => ({ text: t.innerText.trim(), sel: t.getAttribute('aria-selected'), id: t.id })));
  console.log('TABS', JSON.stringify(tabs, null, 1).slice(0, 4000));
  const buttons = await page.evaluate(() => Array.from(document.querySelectorAll('button')).map(b => ({ text: b.innerText.trim(), title: b.title, aria: b.getAttribute('aria-label'), testid: b.getAttribute('data-testid'), disabled: b.disabled })).filter(b => b.text || b.title || b.aria).slice(-40));
  console.log('BUTTONS', JSON.stringify(buttons, null, 1).slice(0, 8000));
  await browser.close();
})().catch(e => { console.error('ERR', e); process.exit(1); });
