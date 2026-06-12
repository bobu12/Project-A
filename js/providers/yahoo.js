/*
 * Yahoo Finance provider — Phase 1 free live option.
 *
 * Free, no key. Builds symbols from each exchange's yahooSuffix (e.g.
 * 2222.SR) and hits the unofficial batch quote endpoint. Best coverage for
 * Saudi/Qatar/Kuwait; UAE/Oman/Bahrain are partial. Unofficial and may be
 * blocked by browser CORS — falls back per-symbol, then to mock.
 */
(function (global) {
  "use strict";
  var P = global.GCC_PROVIDERS;
  var H = P.helpers;

  P.register({
    id: "yahoo",
    label: "Yahoo Finance (free)",
    needsKey: false,
    phase: 1,
    note: "Free, no key. Best for Saudi/Qatar/Kuwait; may be blocked by browser CORS.",
    getQuotes: function (exchange) {
      if (!exchange.yahooSuffix) return P.get("mock").getQuotes(exchange);
      var symbols = exchange.stocks
        .map(function (s) { return encodeURIComponent(s.code + exchange.yahooSuffix); })
        .join(",");
      var url = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=" + symbols;
      return fetch(url)
        .then(function (r) {
          if (!r.ok) throw new Error("Yahoo HTTP " + r.status);
          return r.json();
        })
        .then(function (json) {
          var rows = (json.quoteResponse && json.quoteResponse.result) || [];
          var byCode = {};
          rows.forEach(function (q) {
            byCode[String(q.symbol || "").replace(exchange.yahooSuffix, "")] = q;
          });
          return exchange.stocks.map(function (s) {
            var q = byCode[s.code];
            if (!q || q.regularMarketPrice == null) return H.clone(s);
            return H.normalize({
              code: s.code,
              name: q.longName || q.shortName || s.name,
              cmp: q.regularMarketPrice,
              prevClose: q.regularMarketPreviousClose,
              open: q.regularMarketOpen,
              high: q.regularMarketDayHigh,
              low: q.regularMarketDayLow,
              volume: q.regularMarketVolume,
              marketCap: q.marketCap
            });
          });
        });
    }
  });
})(window);
