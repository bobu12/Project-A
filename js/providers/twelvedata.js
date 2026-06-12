/*
 * Twelve Data provider — PHASE 2 live feed.
 *
 * This is the designated Phase-2 data source. Requires a Twelve Data API key,
 * entered in the Settings dialog and stored only in the browser's localStorage
 * (never committed to the repo). GCC equities require the Grow plan ($29/mo) or
 * higher — the free tier returns US/FX/crypto only.
 *
 * Uses the batch /quote endpoint scoped by each exchange's MIC code (XSAU,
 * XDFM, XADS, DSMD, XKUW, XMUS, XBAH). Confirm symbol/MIC formatting against
 * your account if a market returns empty.
 *
 * NOTE: outbound calls to api.twelvedata.com must be reachable — from a browser
 * (subject to CORS) or, in a sandboxed environment, by adding the host to the
 * network egress allowlist.
 */
(function (global) {
  "use strict";
  var P = global.GCC_PROVIDERS;
  var H = P.helpers;

  var BASE = "https://api.twelvedata.com";

  P.register({
    id: "twelvedata",
    label: "Twelve Data — live (Phase 2)",
    needsKey: true,
    phase: 2,
    // Prefilled demo key (free tier). Used when no key is saved in localStorage.
    // GCC equities still require the Grow plan ($29/mo)+ — the demo key returns
    // US/FX/crypto only. Replace via the Settings dialog with your own key.
    defaultKey: "0d20071312944c31ac2a32ebc81c2cb1",
    note: "Phase-2 live feed. Demo key prefilled; GCC equities require the Grow plan ($29/mo)+.",
    getQuotes: function (exchange, apiKey) {
      if (!apiKey) return P.get("mock").getQuotes(exchange);
      var symbols = exchange.stocks.map(function (s) { return s.code; }).join(",");
      var url = BASE + "/quote?symbol=" + encodeURIComponent(symbols) +
                "&mic_code=" + encodeURIComponent(exchange.mic) +
                "&apikey=" + encodeURIComponent(apiKey);
      return fetch(url)
        .then(function (r) { return r.json(); })
        .then(function (json) {
          if (json && json.status === "error") {
            throw new Error(json.message || "Twelve Data error");
          }
          // Single symbol -> object; multiple -> { CODE: {...} }
          var map = json && json.symbol ? H.defObj(json.symbol, json) : (json || {});
          return exchange.stocks.map(function (s) {
            var q = map[s.code];
            if (!q || q.close == null) return H.clone(s);
            return H.normalize({
              code: s.code,
              name: q.name || s.name,
              cmp: H.num(q.close),
              prevClose: H.num(q.previous_close),
              open: H.num(q.open),
              high: H.num(q.high),
              low: H.num(q.low),
              volume: H.num(q.volume),
              marketCap: s.marketCap // not in /quote; keep reference value
            });
          });
        });
    }
  });
})(window);
