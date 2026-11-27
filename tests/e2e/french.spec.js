// French version: every page exists at /fr/..., says it is a machine translation, and the EN/FR switch
// goes to the same page in the other language. Numbers use French formats; data files stay shared.
const { test, expect } = require("@playwright/test");

const PP = "456110"; // Prince Philip Public School, Niagara Falls (DSBN B66150, board records collected)

function watch(page) {
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  return errors;
}

test.describe("French version", () => {
  test("home: switch from English goes to the French home, which says it is machine-translated", async ({ page }) => {
    const errors = watch(page);
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("lang", "en-CA");
    await expect(page.locator(".mt-notice")).toHaveCount(0);
    const fr = page.locator(".lang-toggle-header a[hreflang='fr']");
    await expect(fr).toHaveAttribute("lang", "fr");
    await fr.click();
    await expect(page).toHaveURL(/\/fr\/$/);
    await expect(page.locator("html")).toHaveAttribute("lang", "fr-CA");
    await expect(page.locator(".mt-notice")).toContainText("traduite automatiquement");
    await expect(page.locator(".mt-notice a[hreflang='en']")).toHaveAttribute("href", "/");
    await expect(page.locator(".lang-toggle-header a[aria-current='true']")).toHaveAttribute("hreflang", "fr");
    await expect(page.locator("header nav").first()).toContainText("Carte");
    await expect(page.locator("header nav").first()).toContainText("Conseils");
    // links stay in French (except the ones to the English page), data stays shared
    const hrefs = await page.locator("a[href^='/']:not([hreflang='en'])").evaluateAll((as) => as.map((a) => a.getAttribute("href")));
    expect(hrefs.length).toBeGreaterThan(10);
    expect(hrefs.filter((h) => !h.startsWith("/fr/") && !h.startsWith("/data/") && !h.startsWith("/static/"))).toEqual([]);
    expect(errors).toEqual([]);
  });

  test("school page in French: same school, French headings and numbers, switch back to English", async ({ page }) => {
    const errors = watch(page);
    await page.goto(`/fr/school/${PP}/`);
    await expect(page.locator("h1")).toContainText("Prince Philip");
    await expect(page.locator("#attendance")).toContainText("Règle publiée");
    await expect(page.locator("#attendance")).toContainText("jardin d’enfants");
    // hreflang alternates point at both languages
    await expect(page.locator(`link[rel='alternate'][hreflang='en-CA']`)).toHaveAttribute("href", new RegExp(`/school/${PP}/$`));
    await expect(page.locator(`link[rel='alternate'][hreflang='fr-CA']`)).toHaveAttribute("href", new RegExp(`/fr/school/${PP}/$`));
    // French numbers: no "1,234" style thousands in the enrolment table
    const enrol = await page.locator("main").innerText();
    expect(enrol).not.toMatch(/\b\d{1,3},\d{3}\b/);
    // the switch goes to the same school in English
    await page.locator(".lang-toggle-header a[hreflang='en']").click();
    await expect(page).toHaveURL(new RegExp(`/school/${PP}/$`));
    await expect(page.locator("html")).toHaveAttribute("lang", "en-CA");
    expect(errors).toEqual([]);
  });

  test("French search finds schools and links to French school pages", async ({ page }) => {
    const errors = watch(page);
    await page.goto("/fr/search/?q=Niagara%20Falls");
    const first = page.locator("main a[href*='/school/']").first();
    await expect(first).toHaveAttribute("href", /^\/fr\/school\/\d+\/$/);
    await expect(page.locator("main")).toContainText("Élémentaire");
    expect(errors).toEqual([]);
  });

  test("French Compare loads schools with French labels", async ({ page }) => {
    const errors = watch(page);
    await page.goto(`/fr/compare/?ids=${PP},455989`);
    await expect(page.locator("main")).toContainText("Prince Philip");
    await expect(page.locator("main")).toContainText("Élèves");
    await expect(page).toHaveURL(/\/fr\/compare\//);
    expect(errors).toEqual([]);
  });

  test("French board page keeps the board's name and lists its schools in French", async ({ page }) => {
    const errors = watch(page);
    await page.goto("/fr/board/B66150/");
    await expect(page.locator("h1")).toContainText("Niagara");
    const school = page.locator("main a.row-link").first();
    await expect(school).toHaveAttribute("href", /^\/fr\/school\/\d+\/$/);
    expect(errors).toEqual([]);
  });

  test("French pages fit a phone screen", async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    for (const url of ["/fr/", `/fr/school/${PP}/`, "/fr/board/B66150/", `/fr/compare/?ids=${PP},455989`, "/fr/methodology/", "/fr/search/?q=Ottawa"]) {
      await page.goto(url);
      await page.waitForLoadState("networkidle");
      const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(over, url).toBeLessThanOrEqual(0);
    }
    // on a phone the header keeps one link to the same page in the other language, a 44px tap target
    await page.goto(`/fr/school/${PP}/`);
    const sw = page.locator("header a.lang-switch");
    await expect(sw).toBeVisible();
    await expect(sw).toHaveAttribute("href", `/school/${PP}/`);
    const box = await sw.boundingBox();
    expect(Math.min(box.width, box.height)).toBeGreaterThanOrEqual(44);
    // the phone menu has the switch too, as a tap target at least 44px tall
    await page.goto("/fr/");
    await page.locator("[data-menu-toggle], .menu-toggle, button[aria-controls]").first().click();
    const link = page.locator(".lang-toggle-menu a[hreflang='en']");
    await expect(link).toBeVisible();
    expect((await link.boundingBox()).height).toBeGreaterThanOrEqual(44);
    await ctx.close();
  });
});
