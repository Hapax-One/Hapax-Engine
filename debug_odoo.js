const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on('console', msg => console.log('CONSOLE:', msg.text()));
  try {
    await page.goto('http://tankweld.haykinsodoo.docker/web/login?debug=1');
    await page.fill('input[name="login"]', 'admin');
    await page.fill('input[name="password"]', 'admin');
    await page.click('button[type="submit"]');
    await page.waitForTimeout(5000);
    
    const missing = await page.evaluate(() => {
      if (window.odoo && window.odoo.__DEBUG__) {
        return window.odoo.__DEBUG__.jsModules.missing;
      }
      return 'No debug info';
    });
    console.log('Missing Modules:', missing);

    const failed = await page.evaluate(() => {
      if (window.odoo && window.odoo.__DEBUG__) {
        return window.odoo.__DEBUG__.jsModules.failed;
      }
      return 'No debug info';
    });
    console.log('Failed Modules:', failed);

  } catch(e) {}
  await browser.close();
})();
