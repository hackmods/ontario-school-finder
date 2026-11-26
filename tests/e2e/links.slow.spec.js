// Slow, network-dependent: every source link on a school page answers HTTP 200.
// Run with: SLOW=1 npx playwright test tests/e2e/links.slow.spec.js
const { test, expect } = require("@playwright/test");

test.skip(!process.env.SLOW, "set SLOW=1 to check external source links");

// The Ministry's School Information Finder pages sit behind a bot wall, so they are not fetched here.
const SKIP = [/app\.edu\.gov\.on\.ca/];

test("source links on a school page return 200", async ({ page, request }) => {
  test.setTimeout(240_000);
  await page.goto("/school/019186/");
  const hrefs = await page.locator("#sources a[href^='https://']").evaluateAll((as) => [...new Set(as.map((a) => a.href))]);
  expect(hrefs.length).toBeGreaterThan(3);
  const bad = [];
  for (const href of hrefs) {
    if (SKIP.some((re) => re.test(href))) continue;
    const r = await request.get(href, { timeout: 60_000, maxRedirects: 5, headers: { "User-Agent": "ontario-school-finder-linkcheck/1.0" } });
    if (r.status() !== 200) bad.push(`${r.status()} ${href}`);
  }
  expect(bad).toEqual([]);
});
