// Site tests and evidence screenshots. check.sh serves site/dist on port 8078 first.
const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "tests/e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 2,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.BASE_URL || "http://127.0.0.1:8078",
    browserName: "chromium",
    headless: true,
    serviceWorkers: "block",
  },
});
