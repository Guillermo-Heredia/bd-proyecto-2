const { chromium } = require('playwright-core');

(async () => {
  const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
  const page = browser.contexts()[0].pages()[0];

  await page.getByRole('tab', { name: 'Connection', exact: true }).click();
  await page.waitForTimeout(800);

  const fill = async (name, value) => {
    const loc = page.locator(`input[name="${name}"]:visible`).first();
    await loc.waitFor({ state: 'visible', timeout: 10000 });
    await loc.fill(value);
    console.log('filled', name, '=', value);
  };

  await fill('host', 'localhost');
  await fill('port', '5432');
  await fill('db', 'postgres');
  await fill('username', 'postgres');
  await fill('password', 'postgres');

  const savePw = page.locator('input[name="save_password"]:visible').first();
  if (!(await savePw.isChecked())) {
    await savePw.check();
    console.log('checked save_password');
  }

  await page.screenshot({ path: '/tmp/server_filled.png' });
  const save = page.locator('button', { hasText: 'Save' }).last();
  console.log('save disabled:', await save.isDisabled());
  await save.click();
  console.log('clicked Save');
  await page.waitForTimeout(5000);
  await page.screenshot({ path: '/tmp/after_save.png' });

  const txt = (await page.locator('body').innerText()).replace(/\n+/g, ' | ');
  console.log('TEXT:', txt.slice(0, 3000));
  const pwds = await page.evaluate(() => Array.from(document.querySelectorAll('input[type="password"]')).map(e => ({ name: e.name, id: e.id, label: (document.querySelector(`label[for="${e.id}"]`) || {}).innerText || '', ph: e.placeholder })));
  console.log('PASSWORD FIELDS:', JSON.stringify(pwds));
  const dialogs = await page.evaluate(() => Array.from(document.querySelectorAll('[role="dialog"], .MuiDialog-root')).map(e => (e.innerText || '').replace(/\n+/g, ' | ').slice(0, 300)));
  console.log('DIALOGS:', JSON.stringify(dialogs));
  await browser.close();
})().catch(e => { console.error('ERR', e); process.exit(1); });
