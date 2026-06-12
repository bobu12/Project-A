/*
 * EODHD provider — optional paid alternative.
 *
 * Cheapest broad official coverage (~$20/mo), incl. Tadawul. Requires an API
 * key (Settings dialog, localStorage only). EODHD uses SYMBOL.EXCHANGECODE;
 * this reuses the Yahoo-style suffix without the dot as a best-effort default —
 * confirm the exact exchange code in your EODHD account if a market is empty.
 */
(function (global) {
  "use strict";
  var P = global.GCC_PROVIDERS;
  var H = P.helpers;

  P.register({
    id: "eodhd",
    label: "EODHD (API key)",
    needsKey: true,
    phase: 2,
    note: "Cheapest broad coverage (~$20/mo); confirm exchange suffixes in your account.",
    getQuotes: function (exchange, apiKey) {
      if (!apiKey) return P.get("mock").getQuotes(exchange);
      var ex = (exchange.yahooSuffix || "").replace(".", "");
      var tickers = exchange.stocks
        .map(function (s) { return s.code + "." + ex; })
        .join(",");
      var primary = exchange.stocks[0].code + "." + ex;
      var url = "https://eodhd.com/api/real-time/" + encodeURIComponent(primary) +
                "?s=" + encodeURIComponent(tickers) +
                "&fmt=json&api_token=" + encodeURIComponent(apiKey);
      return fetch(url)
        .then(function (r) { return r.json(); })
        .then(function (json) {
          var rows = Array.isArray(json) ? json : [json];
          var byCode = {};
          rows.forEach(function (q) {
            byCode[String(q.code || "").split(".")[0]] = q;
          });
          return exchange.stocks.map(function (s) {
            var q = byCode[s.code];
            if (!q || q.close == null || q.close === "NA") return H.clone(s);
            return H.normalize({
              code: s.code,
              name: s.name,
              cmp: H.num(q.close),
              prevClose: H.num(q.previousClose),
              open: H.num(q.open),
              high: H.num(q.high),
              low: H.num(q.low),
              volume: H.num(q.volume),
              marketCap: s.marketCap
            });
          });
        });
    }
  });
})(window);
