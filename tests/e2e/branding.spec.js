const { test, expect } = require("@playwright/test");
const { readFileSync } = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "../..");
const { active } = JSON.parse(readFileSync(path.join(root, "branding/brand.json"), "utf8"));

test("branding remains legible, navigable, and inside the header at every width", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  for (const width of [320, 390, 768, 1024, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/about/");
    const home = page.locator(".site-header .brand-lockup");
    await expect(home).toHaveAccessibleName("Ontario School Finder home");
    const logo = home.locator(".brand-logo-light");
    await expect(logo).toBeVisible();
    expect(await logo.evaluate(img => img.complete && img.naturalWidth > 0)).toBeTruthy();
    const header = await page.locator(".site-header .wrap").boundingBox();
    const bounds = await home.boundingBox();
    expect(bounds.y).toBeGreaterThanOrEqual(header.y);
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(header.y + header.height + 1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    const nav = page.locator(".site-header .nav");
    if (await nav.isVisible()) {
      const navBounds = await nav.boundingBox();
      expect(navBounds.x).toBeGreaterThanOrEqual(bounds.x + bounds.width);
      expect(navBounds.x + navBounds.width).toBeLessThanOrEqual(width);
    } else {
      await page.getByRole("button", { name: "Menu", exact: true }).click();
      await expect(page.locator(".mobile-menu")).toBeVisible();
    }
    await home.click();
    await expect(page).toHaveURL(/\/$/);
  }
});

test("saved and automatic theme choices show the right artwork; print uses colour", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/");
  await expect(page.locator(".site-header .brand-logo-dark")).toBeVisible();
  await expect(page.locator(".site-header .brand-logo-light")).toBeHidden();
  await page.locator("[data-theme-toggle]").click();
  await expect(page.locator("[data-theme-toggle]")).toHaveText(/Theme: light/);
  await page.reload();
  await expect(page.locator(".site-header .brand-logo-light")).toBeVisible();
  await expect(page.locator(".site-header .brand-logo-dark")).toBeHidden();
  await page.locator("[data-theme-toggle]").click();
  await expect(page.locator("[data-theme-toggle]")).toHaveText(/Theme: dark/);
  await page.emulateMedia({ colorScheme: "light" });
  await page.reload();
  await expect(page.locator(".site-header .brand-logo-dark")).toBeVisible();
  await page.emulateMedia({ media: "print" });
  // The stylesheet's print rules also cover layouts where the header is hidden for printing.
  expect(await page.locator(".site-header .brand-logo-light").evaluate(img => getComputedStyle(img).display)).toBe("block");
});

test("published logo, favicon, share card and installable icons use the selected asset set", async ({ page, request }) => {
  await page.goto("/");
  const logoUrl = await page.locator(".site-header .brand-logo-light").getAttribute("src");
  const iconUrl = await page.locator('link[rel="icon"]').getAttribute("href");
  const appleUrl = await page.locator('link[rel="apple-touch-icon"]').getAttribute("href");
  const ogUrl = new URL(await page.locator('meta[property="og:image"]').getAttribute("content"));
  for (const [url, name] of [[logoUrl, "brand-logo.svg"], [iconUrl, "icon.svg"], [appleUrl, "icon-180.png"], [ogUrl.pathname + ogUrl.search, "og.png"]]) {
    expect(url).toContain("?v=");
    const response = await request.get(url);
    expect(response.ok()).toBeTruthy();
    expect(Buffer.compare(await response.body(), readFileSync(path.join(root, "branding/trillium-retro", active, "web", name)))).toBe(0);
  }
  const manifest = await (await request.get("/manifest.webmanifest")).json();
  for (const icon of manifest.icons) {
    const response = await request.get(icon.src);
    expect(response.ok()).toBeTruthy();
    expect(Buffer.compare(await response.body(), readFileSync(path.join(root, "site/static/img", path.basename(icon.src))))).toBe(0);
  }
});
