// End-to-end checks of the generated site (served from site/dist) plus the evidence screenshots.
const { test, expect } = require("@playwright/test");
const path = require("path");

const EVIDENCE = path.join(__dirname, "..", "..", "evidence");
// the site itself (whatever port it is served on for the test) plus the two third parties it may call
const SITE_HOST = new URL(process.env.BASE_URL || "http://127.0.0.1:8078").host;
const ALLOWED_HOSTS = new Set([SITE_HOST, "127.0.0.1:8078", "localhost:8078", "tiles.openfreemap.org", "www.geolocator.api.geo.ca"]);
const SCHOOL = "019186"; // Anna McCrea Public School, Sault Ste. Marie
const FSA = "P6A";

/** Collect console errors and every request host while a test runs. */
function watch(page) {
  const errors = [];
  const hosts = new Set();
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("request", (r) => {
    const u = new URL(r.url());
    if (u.protocol.startsWith("http")) hosts.add(u.host);
  });
  return { errors, hosts };
}

async function waitForMap(page, sel = ".maplibregl-canvas") {
  await page.locator(sel).first().waitFor({ state: "visible", timeout: 30_000 });
  await page.waitForTimeout(2500); // let tiles paint for screenshots
}

async function pickSchools(page, n) {
  const idx = await (await page.request.get("/data/schools-index.json")).json();
  const sameBoard = idx.filter((r) => r.b === "B28010" && r.l === "E");
  return sameBoard.slice(0, n).map((r) => r.id);
}

test.describe("search", () => {
  test("home finds a school by partial name", async ({ page }) => {
    const w = watch(page);
    await page.goto("/");
    await page.fill("#q", "McCrea");
    const opt = page.locator("#q-list [role=option]", { hasText: "Anna McCrea" });
    await expect(opt.first()).toBeVisible();
    await opt.first().click();
    await expect(page).toHaveURL(new RegExp(`/school/${SCHOOL}/`));
    await expect(page.locator("h1")).toHaveText(/Anna McCrea/);
    expect(w.errors).toEqual([]);
  });

  test("home finds schools by city", async ({ page }) => {
    await page.goto("/");
    await page.fill("#q", "Kingston");
    await expect(page.locator("#q-list [role=option]", { hasText: "Schools in Kingston" })).toBeVisible();
    await page.press("#q", "Enter");
    await expect(page).toHaveURL(/\/search\/\?q=Kingston/);
    await expect(page.locator("[data-results] .row-link").first()).toBeVisible();
    await expect(page.locator("[data-results] h2")).toHaveText(/Kingston/);
  });

  test("home finds a postal area (FSA)", async ({ page }) => {
    await page.goto("/");
    await page.fill("#q", "k7l");
    const opt = page.locator("#q-list [role=option]", { hasText: "Postal area K7L" });
    await expect(opt).toBeVisible();
    await opt.click();
    await expect(page).toHaveURL(/\/fsa\/K7L\//);
  });

  test("a full postal code goes to its FSA results", async ({ page }) => {
    await page.goto("/search/?q=P6A%203M7");
    await expect(page.locator("[data-results]")).toContainText("Schools in postal area P6A");
  });
});

test.describe("pages", () => {
  test("school page has EQAO charts, text tables and sources", async ({ page }) => {
    const w = watch(page);
    await page.goto(`/school/${SCHOOL}/`);
    const chart = page.locator("#results .chart-card").first();
    await expect(chart.locator("svg")).toBeVisible();
    await expect(chart.locator("table")).toHaveCount(1);
    await chart.locator("summary").click();
    await expect(chart.locator("table tbody tr").first()).toBeVisible();
    const links = page.locator("#sources a[data-source-link]");
    expect(await links.count()).toBeGreaterThan(2);
    for (const href of await links.evaluateAll((as) => as.map((a) => a.href))) expect(href).toMatch(/^https:\/\//);
    await expect(page.locator(".site-footer")).toContainText("Not affiliated with EQAO, the Ministry of Education or any school board.");
    await expect(page.locator(".site-footer")).toContainText("Data last updated");
    await waitForMap(page);
    expect(w.errors).toEqual([]);
  });

  test("school page works without JavaScript for the core facts", async ({ browser }) => {
    const ctx = await browser.newContext({ javaScriptEnabled: false });
    const page = await ctx.newPage();
    await page.goto(`/school/${SCHOOL}/`);
    await expect(page.locator("h1")).toHaveText(/Anna McCrea/);
    await expect(page.locator("#results svg").first()).toBeVisible();
    await expect(page.locator("#sources li").first()).toBeVisible();
    await ctx.close();
  });

  test("FSA page shows its map and schools", async ({ page }) => {
    const w = watch(page);
    await page.goto(`/fsa/${FSA}/`);
    await expect(page.locator("h1")).toContainText(FSA);
    await waitForMap(page);
    expect(await page.locator("#schools .row-link").count()).toBeGreaterThan(3);
    await expect(page.locator("#area")).toContainText("2021 Census");
    expect(w.errors).toEqual([]);
  });

  test("board page lists schools and official results", async ({ page }) => {
    await page.goto("/board/B28010/");
    await expect(page.locator("h1")).toHaveText("Algoma DSB");
    expect(await page.locator("[data-filter-list] li").count()).toBeGreaterThan(10);
    await expect(page.locator("#indicators table")).toBeVisible();
  });

  test("school pages show French programs and SHSM sectors from the Ministry lists", async ({ page }) => {
    // flags on the page match the school's own data file
    const s = await (await page.request.get(`/data/schools/${SCHOOL}.json`)).json();
    await page.goto(`/school/${SCHOOL}/`);
    const prog = page.locator("#programs");
    await expect(page.locator('.subnav a[href="#programs"]')).toBeVisible();
    if (s.programs.fsl) {
      for (const [key, label] of [["core", "Core French"], ["extended", "Extended French"], ["immersion", "French Immersion"]]) {
        await expect(prog).toContainText(`${label} ${s.programs.fsl[key] ? "offered" : "not offered"}`);
      }
    }
    // a secondary school with SHSM programs lists every sector
    const idx = await (await page.request.get("/data/schools-index.json")).json();
    const sec = idx.filter((r) => r.sh).sort((a, b) => b.sh - a.sh)[0];
    await page.goto(`/school/${sec.id}/`);
    await expect(page.locator("#programs .shsm-list li")).toHaveCount(sec.sh);
  });

  test("school and board pages link to the board's own address lookup where one exists", async ({ page }) => {
    await page.goto("/board/B66052/"); // Toronto DSB
    await expect(page.locator(".head-actions a").first()).toHaveText(/Which school serves an address/);
    await page.goto(`/school/${SCHOOL}/`);
    const link = page.locator("#overview .note a.btn");
    await expect(link).toBeVisible();
    expect(await link.getAttribute("href")).toMatch(/^https?:\/\//);
  });

  test("search results can be narrowed to schools offering French Immersion", async ({ page }) => {
    await page.goto("/search/?q=Ottawa");
    const count = page.locator("[data-results] [data-count]");
    await expect(count).toContainText("schools");
    const all = parseInt(await count.textContent(), 10);
    await page.locator('[data-f="prog"][data-v="fi"]').click();
    const fi = parseInt(await count.textContent(), 10);
    expect(fi).toBeGreaterThan(0);
    expect(fi).toBeLessThan(all);
  });

  test("board school list: A-Z letters, filter hides empty letters and says when nothing matches", async ({ page }) => {
    await page.goto("/board/B66052/"); // Toronto DSB, hundreds of schools
    const letters = page.locator("[data-az-nav] a:visible");
    const before = await letters.count();
    expect(before).toBeGreaterThan(15);
    await page.locator("[data-filter-text]").fill("collegiate");
    expect(await letters.count()).toBeLessThan(before);
    await expect(page.locator("[data-filter-list] li:visible").first()).toContainText(/Collegiate/i);
    await page.locator("[data-filter-text]").fill("zzzz no such school");
    await expect(page.locator("[data-filter-empty]")).toBeVisible();
    // "École ..." sorts with the E schools, not after Z
    const groups = await page.locator("[data-az]").evaluateAll((els) => els.map((e) => e.dataset.az));
    expect(groups.every((g) => /^[A-Z#]$/.test(g))).toBe(true);
  });

  test("when location is unavailable the message offers a postal code instead", async ({ browser }) => {
    // no geolocation permission granted: the browser answers "denied" without asking, like a phone with location off
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    for (const [url, box] of [["/", "q"], ["/search/", "sq"]]) {
      await page.goto(url);
      await page.locator("[data-near-me]").click();
      await expect(page.locator("[data-near-status]")).toContainText("didn’t share a location");
      await page.locator("[data-postal-fallback]").click();
      expect(await page.evaluate(() => document.activeElement?.id)).toBe(box);
      await expect(page.locator(`#${box}`)).toHaveAttribute("placeholder", /Postal code/);
    }
    await ctx.close();
  });

  test("compare charts are drawn at phone width with readable labels", async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    const ids = await pickSchools(page, 3);
    await page.goto(`/compare/?ids=${ids.join(",")}`);
    const svg = page.locator("#cmp-eqao .chart svg").first();
    await svg.waitFor();
    // the drawing is 1:1 with the screen, so 12px labels stay 12px
    const ratio = await svg.evaluate((s) => s.getBoundingClientRect().width / s.viewBox.baseVal.width);
    expect(ratio).toBeGreaterThan(0.95);
    expect(ratio).toBeLessThan(1.05);
    await ctx.close();
  });

  for (const n of [2, 3, 6]) {
    test(`compare works with ${n} schools`, async ({ page }) => {
      const ids = await pickSchools(page, n);
      const w = watch(page);
      await page.goto(`/compare/?ids=${ids.join(",")}`);
      await expect(page.locator("[data-cmp-chips] .cmp-chip:not(.cmp-chip-empty)")).toHaveCount(n);
      // every comparison table has one column per school plus the measure column
      await expect(page.locator("#cmp-overview thead th")).toHaveCount(n + 1);
      for (const id of ["#cmp-eqao", "#cmp-enrolment", "#cmp-grades", "#cmp-class", "#cmp-students", "#cmp-area", "#cmp-sources"]) {
        await expect(page.locator(id)).toBeVisible();
      }
      await expect(page.locator("#cmp-eqao svg").first()).toBeVisible();
      expect(w.errors).toEqual([]);
    });
  }

  test("compare adds a school from search, removes one, and downloads CSV", async ({ page }) => {
    const ids = await pickSchools(page, 2);
    await page.goto(`/compare/?ids=${ids.join(",")}`);
    await page.fill("#cq", "McCrea");
    await page.locator("#cq-list [role=option]", { hasText: "Anna McCrea" }).first().click();
    await expect(page.locator("[data-cmp-chips] .cmp-chip:not(.cmp-chip-empty)")).toHaveCount(ids.includes("019186") ? 2 : 3);
    await expect(page).toHaveURL(/019186/);
    const [download] = await Promise.all([page.waitForEvent("download"), page.locator("[data-cmp-csv]").click()]);
    expect(download.suggestedFilename()).toMatch(/^school-comparison-.*\.csv$/);
    await page.locator("[data-remove]").first().click();
    await expect(page.locator("[data-cmp-chips] .cmp-chip:not(.cmp-chip-empty)")).toHaveCount(ids.includes("019186") ? 1 : 2);
  });

  test("school page shows class sizes and students by grade", async ({ page }) => {
    await page.goto(`/school/${SCHOOL}/`);
    // long series are drawn twice (phone and wide copies); exactly one shows, picked by the chart's width
    const shown = page.locator("#class-sizes .chart svg").filter({ visible: true });
    await expect(shown).toHaveCount(1);
    await expect(shown).toHaveClass(/v-wide/);
    await expect(page.locator("#grades table")).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(shown).toHaveClass(/v-narrow/);
  });

  // The brief's label is "Official boundary from <board>, <date>"; until a board publishes its areas the
  // layer is a disabled placeholder, so it reads "from the board" instead of showing the literal brackets.
  test("map legend shows every layer label", async ({ page }) => {
    await page.goto("/map/");
    const legend = page.locator("[data-legend]");
    for (const label of ["Postal code area (first 3 characters)", "Approximate school board area", "Nearest school, NOT the official boundary", "Official boundary from the board"]) {
      await expect(legend).toContainText(label);
    }
  });

  test("map layers load on demand", async ({ page }) => {
    const w = watch(page);
    await page.goto("/map/");
    await waitForMap(page);
    await Promise.all([page.waitForResponse((r) => r.url().includes("/data/geo/nearest-")), page.locator('input[name="area"][value="nearest"]').check()]);
    await Promise.all([page.waitForResponse((r) => r.url().includes("/data/geo/fsa.geojson")), page.locator('input[name="area"][value="fsa"]').check()]);
    expect(w.errors).toEqual([]);
  });

  test("methodology lists every source with licence and retrieval date", async ({ page }) => {
    await page.goto("/methodology/");
    const meta = await (await page.request.get("/data/meta.json")).json();
    for (const [key, d] of Object.entries(meta.datasets)) {
      const row = page.locator(`tr#dataset-${key}`);
      await expect(row.first()).toBeVisible();
      await expect(row.first()).toContainText(d.licence.split(" (")[0]);
      if (d.status === "used") await expect(row.first().locator("td").last()).toHaveText(/\d{4}-\d{2}-\d{2}/);
    }
  });
});

test.describe("privacy and robustness", () => {
  test("no console errors and no third-party requests except map tiles", async ({ page }) => {
    const w = watch(page);
    for (const url of ["/", `/school/${SCHOOL}/`, `/fsa/${FSA}/`, "/board/B28010/", "/map/", "/compare/", "/methodology/", "/search/?q=Toronto"]) {
      await page.goto(url);
      await page.waitForLoadState("networkidle");
    }
    expect(w.errors).toEqual([]);
    const third = [...w.hosts].filter((h) => !ALLOWED_HOSTS.has(h));
    expect(third).toEqual([]);
  });
});

test.describe("phone (390px)", () => {
  test.use({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });

  for (const url of ["/", `/school/${SCHOOL}/`, `/fsa/${FSA}/`, "/board/B28010/", "/compare/", "/map/", "/methodology/", "/search/?q=Toronto", "/areas/", "/boards/", "/about/", "/data/", `/corrections/?school=${SCHOOL}`, "/404.html"]) {
    test(`no horizontal scroll and 44px tap targets on ${url}`, async ({ page }) => {
      await page.goto(url);
      await page.waitForLoadState("networkidle");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(0);
      const small = await page.evaluate(() => {
        const sel = "button, .btn, .chip, .nav a, .row-link, input[type=search], input[type=text], select, .subnav a, .icon-btn, .crumbs a, .cols a, .site-footer li a, .layer-toggle";
        return [...document.querySelectorAll(sel)]
          .filter((el) => {
            const r = el.getBoundingClientRect();
            const st = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && st.visibility !== "hidden" && !el.closest("[hidden], .maplibregl-map, .visually-hidden, .suggest");
          })
          .map((el) => {
            const r = el.getBoundingClientRect();
            return { el: el.outerHTML.slice(0, 90), h: Math.round(r.height), w: Math.round(r.width) };
          })
          .filter((x) => x.h < 44);
      });
      expect(small).toEqual([]);
    });
  }
});

test.describe("evidence screenshots", () => {
  test.describe.configure({ mode: "serial" });

  test("390px screenshots", async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const page = await ctx.newPage();
    await page.goto("/");
    await page.screenshot({ path: path.join(EVIDENCE, "home-390.png"), fullPage: true });
    await page.goto("/search/?q=Sault%20Ste%20Marie");
    await page.locator("[data-results] .row-link").first().waitFor();
    await waitForMap(page);
    await page.screenshot({ path: path.join(EVIDENCE, "search-results-390.png"), fullPage: false });
    await page.goto(`/school/${SCHOOL}/`);
    await page.locator('[data-map="school"]').scrollIntoViewIfNeeded();
    await waitForMap(page);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(EVIDENCE, "school-page-390.png"), fullPage: true });
    await page.goto(`/fsa/${FSA}/`);
    await waitForMap(page);
    await page.screenshot({ path: path.join(EVIDENCE, "fsa-page-390.png"), fullPage: true });
    await page.goto("/map/");
    await waitForMap(page);
    await page.locator(".map-panel").scrollIntoViewIfNeeded();
    await page.locator(".map-panel").screenshot({ path: path.join(EVIDENCE, "map-legend-390.png") });
    await ctx.close();
  });

  test("1280px screenshots", async ({ browser, request }) => {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await ctx.newPage();
    await page.goto(`/school/${SCHOOL}/`);
    await page.locator('[data-map="school"]').scrollIntoViewIfNeeded();
    await waitForMap(page);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(EVIDENCE, "school-page-1280.png"), fullPage: true });
    const ids = await pickSchools(page, 4);
    await page.goto(`/compare/?ids=${ids.join(",")}`);
    await page.locator("#cmp-eqao svg").first().waitFor();
    await page.screenshot({ path: path.join(EVIDENCE, "compare-1280.png"), fullPage: true });
    await page.goto("/methodology/");
    await page.screenshot({ path: path.join(EVIDENCE, "methodology-1280.png"), fullPage: true });
    await ctx.close();
  });
});
