/*
 * GCC Markets Dashboard — test suite (no dependencies).
 *
 * Run with:  node tests/run.js
 *
 * Loads the browser modules under a minimal `window`/`fetch` shim and asserts
 * data integrity, provider registration, and the live->sample fallback.
 */
"use strict";

const path = require("path");
const ROOT = path.join(__dirname, "..");

// ---- tiny assert harness ----
let passed = 0, failed = 0;
const fails = [];
function ok(cond, msg) {
  if (cond) { passed++; }
  else { failed++; fails.push(msg); console.log("  ✗ " + msg); }
}
function eq(a, b, msg) { ok(a === b, `${msg} (expected ${b}, got ${a})`); }
function section(name) { console.log("\n• " + name); }

// ---- load modules under a browser shim ----
global.window = {};
let fetchMode = "fail"; // "fail" => simulate no network
global.fetch = function () {
  if (fetchMode === "fail") return Promise.reject(new Error("network blocked (test)"));
  return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
};

require(path.join(ROOT, "js/data.js"));
["base", "mock", "yahoo", "twelvedata", "eodhd"].forEach(m =>
  require(path.join(ROOT, "js/providers", m + ".js"))
);

const DATA = global.window.GCC_DATA;
const PROV = global.window.GCC_PROVIDERS;

// ---- 1. dataset shape ----
section("Dataset");
const EX = DATA.EXCHANGES;
eq(EX.length, 7, "has 7 exchanges");
const expectedIds = ["tadawul", "dfm", "adx", "qse", "kuwait", "msx", "bahrain"];
expectedIds.forEach(id => ok(EX.some(e => e.id === id), `includes exchange '${id}'`));

let totalStocks = 0;
EX.forEach(e => {
  ok(e.currency && e.currency.length === 3, `${e.id}: has 3-letter currency`);
  ok(e.mic, `${e.id}: has MIC code`);
  ok(Array.isArray(e.stocks) && e.stocks.length > 0, `${e.id}: has stocks`);
  totalStocks += e.stocks.length;
});
eq(totalStocks, 50, "has 50 stocks total");

// ---- 2. per-stock integrity ----
section("Stock integrity");
const REQUIRED = ["code","name","cmp","changePct","opening","closing",
  "dayOpen","dayClose","weekOpen","weekClose","sessionHigh","sessionLow","volume","marketCap"];
let badRange = 0, badNum = 0, badPct = 0, missing = 0;
EX.forEach(e => e.stocks.forEach(s => {
  REQUIRED.forEach(k => { if (s[k] === undefined) { missing++; } });
  if (s.sessionLow > s.cmp + 1e-9 || s.cmp > s.sessionHigh + 1e-9) badRange++;
  if (s.sessionLow > s.opening + 1e-9 || s.opening > s.sessionHigh + 1e-9) badRange++;
  if (!(s.volume > 0) || !(s.marketCap > 0)) badNum++;
  // changePct must match cmp vs previous close (closing)
  const expectPct = ((s.cmp - s.closing) / s.closing) * 100;
  if (Math.abs(expectPct - s.changePct) > 1e-6) badPct++;
}));
eq(missing, 0, "every stock has all required fields");
eq(badRange, 0, "cmp & opening within session low/high for all stocks");
eq(badNum, 0, "volume and market cap are positive for all stocks");
eq(badPct, 0, "changePct matches (cmp - prevClose)/prevClose");

// ---- 3. unique codes per exchange ----
section("Ticker codes");
let dupes = 0;
EX.forEach(e => {
  const seen = new Set();
  e.stocks.forEach(s => { if (seen.has(s.code)) dupes++; seen.add(s.code); });
});
eq(dupes, 0, "no duplicate ticker codes within an exchange");

// ---- 4. providers ----
section("Providers");
const ids = PROV.list.map(p => p.id);
["mock","yahoo","twelvedata","eodhd"].forEach(id => ok(ids.includes(id), `registered '${id}'`));
eq(PROV.get("mock").phase, 1, "mock is phase 1");
eq(PROV.get("yahoo").phase, 1, "yahoo is phase 1");
eq(PROV.get("twelvedata").phase, 2, "twelvedata is phase 2 (live)");
eq(PROV.get("eodhd").phase, 2, "eodhd is phase 2");
ok(PROV.get("twelvedata").needsKey === true, "twelvedata needs a key");
ok(/^[0-9a-f]{32}$/i.test(PROV.get("twelvedata").defaultKey || ""), "twelvedata has a prefilled demo key");

// ---- 5. async: mock + fallback ----
section("Quote fetching");
(async () => {
  const mockRows = await PROV.fetchQuotes("mock", EX[0], "");
  eq(mockRows.length, EX[0].stocks.length, "mock returns all rows");
  ok(!mockRows._fellBack, "mock did not fall back");

  // live provider with network failing -> falls back to sample data
  fetchMode = "fail";
  const td = await PROV.fetchQuotes("twelvedata", EX[0], "DUMMYKEY");
  ok(td._fellBack === true, "twelvedata falls back to sample on network failure");
  eq(td.length, EX[0].stocks.length, "fallback returns full row set");

  // unknown provider id -> resolves via mock
  const unknown = await PROV.fetchQuotes("does-not-exist", EX[0], "");
  eq(unknown.length, EX[0].stocks.length, "unknown provider id resolves safely");

  // ---- summary ----
  console.log("\n" + "─".repeat(40));
  console.log(`  ${passed} passed, ${failed} failed`);
  if (failed) { console.log("\nFAILURES:"); fails.forEach(f => console.log("  - " + f)); }
  console.log(failed === 0 ? "  ✓ ALL TESTS PASSED" : "  ✗ TESTS FAILED");
  process.exit(failed === 0 ? 0 : 1);
})();
