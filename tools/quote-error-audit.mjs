import { chromium } from '../frontend/node_modules/playwright/index.mjs';

const browser = await chromium.launch({
  headless: true,
  executablePath: '/cache/jit/ms-playwright/chromium-1243/chrome-linux64/chrome'
});
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
const pageErrors = [];
page.on('pageerror', (error) => pageErrors.push(error.message));
await page.goto(process.env.BASE_URL || 'http://127.0.0.1:8766', { waitUntil: 'networkidle' });
await page.click('[data-page="quote"]');
await page.waitForTimeout(1800);
if (process.argv[2]) {
  await page.selectOption('[data-testid="quote-source-select"]', process.argv[2]);
  await page.waitForTimeout(2200);
}
const status = await page.locator('.quote-state').innerText();
const error = await page.locator('.error-banner').count() ? await page.locator('.error-banner').first().innerText() : '';
const result = await page.locator('[data-testid="quote-result"]').count() ? await page.locator('[data-testid="quote-result"]').innerText() : '';
console.log(JSON.stringify({ source: process.argv[2] || 'default', status, error, result: result.slice(0, 180), pageErrors }));
await page.screenshot({ path: process.argv[3] || '/tmp/quote-page.png', fullPage: true });
await browser.close();
