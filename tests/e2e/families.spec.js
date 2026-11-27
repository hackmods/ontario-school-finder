// Family-facing pages: honest interpretation (EQAO eras, gaps), getting in, supports, Compare and search filters.
// Representative cases: Prince Philip PS (Niagara Falls, 456110: Immersion-only, same-named school in its board),
// Bridgeview (DSBN lists it as Immersion, the Ministry list doesn't), A N Myer SS (secondary with SHSM),
// a French-language school, a school outside the boards collected so far, and an approved boundary decision.
const { test, expect } = require("@playwright/test");

const PP = "456110"; // Prince Philip Public School, Niagara Falls
const PP_STC = "455989"; // Prince Philip Public School, St Catharines (same name, same board)

function watch(page) {
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  return errors;
}

test.describe("school page for families", () => {
  test("Prince Philip: grades, Immersion entry, eras, class sizes, student experience", async ({ page }) => {
    const errors = watch(page);
    await page.goto(`/school/${PP}/`);
    const att = page.locator("#attendance");
    await expect(att).toContainText("Grade 1 to Grade 8");
    await expect(att).toContainText("No kindergarten at this school");
    await expect(att.locator(".grade-strip li.off").first()).toContainText("Junior kindergarten not offered");
    await expect(att).toContainText("French Immersion starts in Grade 1");
    await expect(att).toContainText("Published rule");
    await expect(att).toContainText("How to ask: decided case by case");
    // EQAO: the current trend only, no change measured across the 2021-22 break
    const results = page.locator("#results");
    await expect(results.locator(".chart-card .sum").first()).toContainText("different group of students");
    await expect(results.locator(".chart-card .sum")).not.toContainText(["since 2016-17"]);
    for (const t of await results.locator(".chart-card .sum").allInnerTexts()) expect(t).not.toMatch(/2016-17|2017-18|2018-19/);
    const paper = page.locator("#results-paper");
    await expect(paper).toContainText("not comparable");
    await paper.locator("summary").click();
    await expect(paper.locator("tbody")).toContainText("2016-17");
    // class sizes: the source has the school, but under a name shared with another DSBN school
    await expect(page.locator("#class-sizes")).toContainText("Source match unresolved");
    await expect(page.locator("#class-sizes")).toContainText("St Catharines");
    // no nearest-school area for an Immersion school, and the page says why
    await expect(page.locator("#overview .note").first()).toContainText("No nearest-school area is drawn");
    // student experience: exact question wording, school vs whole board vs Ontario
    const exp = page.locator("#experience");
    await expect(exp).toContainText("“I like to read”");
    await expect(exp.locator("thead").first()).toContainText("Whole board");
    await expect(exp).toContainText("not a measure of the school’s quality");
    // historical-only nutrition listing, labelled as such
    await expect(page.locator("#programs")).toContainText("Current availability unverified");
    // plans: the board's published capacity and projections, labelled as forecasts
    await expect(page.locator("#board-info")).toContainText("on-the-ground capacity of 322");
    await expect(page.locator("#board-info")).toContainText("forecast");
    await expect(page.locator("#questions li").first()).toBeVisible();
    expect(errors).toEqual([]);
  });

  test("Bridgeview: the board's Immersion list and the Ministry's disagree, and the page says so", async ({ page }) => {
    await page.goto("/school/628318/");
    await expect(page.locator(".head-meta")).toContainText("French Immersion");
    await expect(page.locator("#attendance")).toContainText("Sources differ");
  });

  test("secondary school: SHSM badge and the board's secondary Immersion note", async ({ page }) => {
    await page.goto("/school/890200/");
    await expect(page.locator(".head-meta")).toContainText("SHSM");
    await expect(page.locator("#attendance")).toContainText("continues in Grades 9 to 12");
    await expect(page.locator("#attendance")).toContainText("3.2 km");
  });

  test("French-language school is not described as French as a second language", async ({ page }) => {
    const idx = await (await page.request.get("/data/schools-index.json")).json();
    const fr = idx.find((r) => r.lang === "F" && r.l === "E");
    await page.goto(`/school/${fr.id}/`);
    await expect(page.locator(".head-meta")).toContainText("French-language school");
    await expect(page.locator("#programs")).toContainText("different from French Immersion");
  });

  test("a board we haven't collected yet says so instead of guessing", async ({ page }) => {
    // TDSB: its site refuses automated reading, so its records stay uncollected (docs/HANDOFF.md)
    await page.goto("/school/018929/");
    await expect(page.locator("#attendance")).toContainText("Not yet collected for this board");
    await expect(page.locator("#supports")).toContainText("Special education in Ontario");
  });

  test("an approved board decision reaches the schools it names", async ({ page }) => {
    await page.goto("/school/694304/");
    await expect(page.locator("#board-info")).toContainText("Approved by the board");
    await expect(page.locator("#board-info")).toContainText("June 16, 2026");
  });

  test("board page gathers the families information", async ({ page }) => {
    await page.goto("/board/B66150/");
    await expect(page.locator("#families")).toContainText("Register for School");
    await expect(page.locator("#families")).toContainText("Special Education");
    await expect(page.locator("#results-paper")).toContainText("not comparable");
    const nav = page.getByRole("navigation", { name: "On this page" });
    await expect(nav.getByRole("link", { name: "For families" })).toHaveAttribute("href", "#families");
    for (const href of await nav.locator("a").evaluateAll((as) => as.map((a) => a.getAttribute("href")))) {
      await expect(page.locator(href), href).toHaveCount(1);
    }
  });

  test("student figures say that 0% is rounded, not none", async ({ page }) => {
    await page.goto(`/school/${PP}/`);
    await expect(page.locator("#students")).toContainText("0% can still mean a few students");
  });

  test("nearby schools show their programs", async ({ page }) => {
    await page.goto(`/school/${PP}/`);
    const row = page.locator("#nearby li", { hasText: "Notre Dame Catholic Elementary School" });
    await expect(row.locator(".badge-prog")).toHaveText("French Immersion");
  });
});

test.describe("compare for families", () => {
  test("at a glance first, eras respected, differences-only keeps gaps visible", async ({ page }) => {
    const errors = watch(page);
    await page.goto(`/compare/?ids=${PP},${PP_STC}`);
    const glance = page.locator("#cmp-practical");
    await expect(glance).toContainText("Grade 1 to Grade 8");
    await expect(glance).toContainText("Junior kindergarten to Grade 8");
    await expect(glance.locator("tr", { hasText: "Class sizes" })).toContainText("Source match unresolved");
    await expect(page.locator("#cmp-eqao")).toContainText("Change since 2021-22");
    await expect(page.locator("#cmp-eqao")).not.toContainText("Change over the period");
    await expect(page.locator("#cmp-experience")).toContainText("I like to read");
    // both are regular schools: that row hides with "only rows that differ"; grades differ and stay
    const typeRow = glance.locator("tr", { hasText: "School type" });
    await expect(typeRow).toBeVisible();
    await page.locator('[data-opt="diff"]').check();
    await expect(typeRow).toBeHidden();
    await expect(glance.locator("tr", { hasText: "Grades offered" })).toBeVisible();
    // the toggle doesn't print, so a printed copy says rows are left out (and the screen doesn't need to)
    const note = page.locator(".cmp-diff-note");
    await expect(note).toBeHidden();
    await page.emulateMedia({ media: "print" });
    await expect(note).toBeVisible();
    await expect(page.locator(".cmp-options")).toBeHidden();
    await page.emulateMedia({ media: "screen" });
    expect(errors).toEqual([]);
  });
});

test.describe("map for families", () => {
  test("program chips filter the schools on the map", async ({ page }) => {
    const errors = watch(page);
    await page.goto("/map/");
    await page.locator(".maplibregl-canvas").waitFor({ state: "visible", timeout: 30_000 });
    await page.waitForFunction(() => document.querySelector('[data-map="explore"]')?._map?.getLayer("schools"));
    const filter = () => page.evaluate(() => JSON.stringify(document.querySelector('[data-map="explore"]')._map.getFilter("schools")));
    const note = page.locator("[data-prog-note]");
    await expect(note).toBeHidden();
    await page.getByRole("button", { name: "French Immersion" }).click();
    await expect(page.getByRole("button", { name: "French Immersion" })).toHaveAttribute("aria-pressed", "true");
    await expect(note).toBeVisible();
    // the board's own Immersion list (fb) counts as well as the Ministry's (fi), as in search
    expect(await filter()).toContain('["get","fb"]');
    await page.getByRole("button", { name: "SHSM" }).click();
    expect(await filter()).toContain('["get","sh"]');
    expect(await filter()).not.toContain('["get","fi"]');
    await page.getByRole("button", { name: "Any program" }).click();
    expect(await filter()).not.toContain('["get","sh"]');
    await expect(note).toBeHidden();
    expect(errors).toEqual([]);
  });
});

test.describe("search for families", () => {
  test("grade filter respects grade ranges, badges show programs, A to Z ordering", async ({ page }) => {
    await page.goto("/search/?q=Niagara%20Falls&grade=JK");
    await expect(page.locator("[data-results] .list")).toBeVisible();
    await expect(page.locator(`a[href="/school/${PP}/"]`)).toHaveCount(0); // starts in Grade 1
    await page.selectOption("[data-grade]", "1");
    await expect(page).toHaveURL(/grade=1/);
    let shown = 0;
    while (!(await page.locator(`a[href="/school/${PP}/"]`).count()) && shown++ < 10) await page.locator("[data-more]").click();
    const row = page.locator(`a[href="/school/${PP}/"]`);
    await expect(row).toContainText("French Immersion");
    await page.selectOption("[data-sort]", "az");
    const names = await page.locator("[data-results] .list .t").allInnerTexts();
    const sorted = [...names].sort((a, b) => a.localeCompare(b, "en-CA", { sensitivity: "base" }));
    expect(names).toEqual(sorted);
  });
});

test.describe("methodology for families", () => {
  test("licence summary is computed, and missing-information states are explained", async ({ page }) => {
    await page.goto("/methodology/");
    const glance = page.locator(".glance-card");
    await expect(glance).toContainText("Open licence");
    await expect(glance).toContainText("no licence stated");
    await expect(glance).not.toContainText("all on open licences");
    await expect(page.locator("#coverage ~ ul").first()).toContainText("Source match unresolved");
    await expect(page.locator("#eqao ~ ul").first()).toContainText("new trend lines");
    await expect(page.locator(".prose")).not.toContainText("not used yet");
  });
});

test.describe("phone (390px) for families", () => {
  for (const url of [`/school/${PP}/`, `/compare/?ids=${PP},${PP_STC},890200`, "/search/?q=Niagara%20Falls&grade=1", "/board/B67156/"]) {
    test(`no horizontal scroll on ${url}`, async ({ browser }) => {
      const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
      await page.goto(url);
      await page.waitForLoadState("networkidle");
      const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(over).toBeLessThanOrEqual(1);
      await page.close();
    });
  }
});
