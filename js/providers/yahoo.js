/*
 * Yahoo Finance provider — Phase 1 free live option (no API key).
 *
 * Covers Saudi (.SR), Qatar (.QA), Kuwait (.KW) well; UAE/Oman/Bahrain partial.
 *
 * Browser reality: Yahoo's endpoints don't send CORS headers, so a page opened
 * directly (file:// or any other origin) can't call them straight. We therefore
 * use the public `v8/finance/chart` endpoint *through a CORS proxy* so it works
 * from a plain static page. Set CORS_PROXY to "" if you're calling from a
 * context where Yahoo is reachable directly (server-side, or a CORS-disabling
 * browser extension). Every symbol falls back to sample data on any error.
 */
(function (global) {
  "use strict";
  var P = global.GCC_PROVIDERS;
  var H = P.helpers;

  // Public CORS proxy (returns the raw upstream body). Swap or clear as needed.
  var CORS_PROXY = "https://api.allorigins.win/raw?url=";
  var CHART = "https://query1.finance.yahoo.com/v8/finance/chart/";

  function chartUrl(symbol) {
    var upstream = CHART + encodeURIComponent(symbol) + "?interval=1d&range=5d";
    return CORS_PROXY ? CORS_PROXY + encodeURIComponent(upstream) : upstream;
  }

  function nums(arr) { return (arr || []).filter(function (v) { return v != null; }); }

  function mapResult(stock, json) {
    var res = json && json.chart && json.chart.result && json.chart.result[0];
    if (!res || !res.meta || res.meta.regularMarketPrice == null) return H.clone(stock);
    var m = res.meta;
    var q = (res.indicators && res.indicators.quote && res.indicators.quote[0]) || {};
    var opens = nums(q.open), highs = nums(q.high), lows = nums(q.low), vols = nums(q.volume);

    return H.normalize({
      code: stock.code,
      name: stock.name,
      cmp: m.regularMarketPrice,
      prevClose: m.chartPreviousClose != null ? m.chartPreviousClose : m.previousClose,
      open: opens.length ? opens[opens.length - 1] : null,        // today's open
      high: m.regularMarketDayHigh != null ? m.regularMarketDayHigh : (highs.length ? Math.max.apply(null, highs) : null),
      low: m.regularMarketDayLow != null ? m.regularMarketDayLow : (lows.length ? Math.min.apply(null, lows) : null),
      weekOpen: opens.length ? opens[0] : null,                   // first open in the 5-day window
      volume: m.regularMarketVolume != null ? m.regularMarketVolume : (vols.length ? vols[vols.length - 1] : 0),
      marketCap: stock.marketCap                                  // chart endpoint has no cap; keep reference
    });
  }

  P.register({
    id: "yahoo",
    label: "Yahoo Finance (free, no key)",
    needsKey: false,
    phase: 1,
    note: "Free, no key — covers Saudi/Qatar/Kuwait (UAE/Oman/Bahrain partial). Routed via a CORS proxy so it works from a static page.",
    getQuotes: function (exchange) {
      if (!exchange.yahooSuffix) return P.get("mock").getQuotes(exchange);
      return Promise.all(exchange.stocks.map(function (s) {
        return fetch(chartUrl(s.code + exchange.yahooSuffix))
          .then(function (r) { if (!r.ok) throw new Error("Yahoo HTTP " + r.status); return r.json(); })
          .then(function (json) { return mapResult(s, json); })
          .catch(function () { return H.clone(s); }); // per-symbol fallback to sample
      }));
    }
  });
})(window);
