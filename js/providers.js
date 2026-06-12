/*
 * Data-provider layer for the GCC Stock Market Dashboard.
 *
 * One interface, swappable backends:
 *   - mock        : built-in sample data (default, free, offline)
 *   - yahoo       : Yahoo Finance unofficial quote endpoint (free, no key)
 *   - twelvedata  : Twelve Data /quote (paid: Grow plan+ for GCC, needs key)
 *   - eodhd       : EODHD real-time quote (paid, needs key)
 *
 * Every provider exposes the same contract:
 *     getQuotes(exchange) -> Promise<Array<stock>>
 * where `stock` matches the shape produced by S() in data.js. Live providers
 * map their raw response onto that shape. If a live call fails (network, CORS,
 * missing key, uncovered exchange), the app falls back to mock data for that
 * exchange so the UI always renders.
 *
 * NOTE: symbol/suffix and field mappings for the paid providers are best-effort
 * scaffolds — confirm the exact symbol format against your provider account's
 * docs (it can vary by subscription).
 */
(function (global) {
  "use strict";

  var DATA = global.GCC_DATA;

  function clone(stock) {
    return JSON.parse(JSON.stringify(stock));
  }

  // Rebuild derived fields after a live provider supplies raw price points.
  function normalize(raw) {
    var prevClose = raw.prevClose != null ? raw.prevClose : raw.cmp;
    var change = raw.cmp - prevClose;
    return {
      code: raw.code,
      name: raw.name || raw.code,
      cmp: raw.cmp,
      change: change,
      changePct: prevClose ? (change / prevClose) * 100 : 0,
      opening: raw.open != null ? raw.open : raw.cmp,
      closing: prevClose,
      dayOpen: raw.open != null ? raw.open : raw.cmp,
      dayClose: raw.cmp,
      weekOpen: raw.weekOpen != null ? raw.weekOpen : (raw.open != null ? raw.open : raw.cmp),
      weekClose: raw.cmp,
      sessionHigh: raw.high != null ? raw.high : raw.cmp,
      sessionLow: raw.low != null ? raw.low : raw.cmp,
      volume: raw.volume != null ? raw.volume : 0,
      marketCap: raw.marketCap != null ? raw.marketCap : 0
    };
  }

  /* ---------------- mock ---------------- */
  var mock = {
    id: "mock",
    label: "Sample data (offline)",
    needsKey: false,
    getQuotes: function (exchange) {
      return Promise.resolve(exchange.stocks.map(clone));
    }
  };

  /* ---------------- yahoo (free, unofficial) ---------------- */
  var yahoo = {
    id: "yahoo",
    label: "Yahoo Finance (free)",
    needsKey: false,
    getQuotes: function (exchange) {
      if (!exchange.yahooSuffix) return mock.getQuotes(exchange);
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
            var code = String(q.symbol || "").replace(exchange.yahooSuffix, "");
            byCode[code] = q;
          });
          return exchange.stocks.map(function (s) {
            var q = byCode[s.code];
            if (!q || q.regularMarketPrice == null) return clone(s); // per-symbol fallback
            return normalize({
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
  };

  /* ---------------- twelvedata (paid) ---------------- */
  var twelvedata = {
    id: "twelvedata",
    label: "Twelve Data (API key)",
    needsKey: true,
    getQuotes: function (exchange, apiKey) {
      if (!apiKey) return mock.getQuotes(exchange);
      // Batch quote: comma-separated symbols, scoped by MIC code.
      var symbols = exchange.stocks.map(function (s) { return s.code; }).join(",");
      var url = "https://api.twelvedata.com/quote?symbol=" + encodeURIComponent(symbols) +
                "&mic_code=" + encodeURIComponent(exchange.mic) +
                "&apikey=" + encodeURIComponent(apiKey);
      return fetch(url)
        .then(function (r) { return r.json(); })
        .then(function (json) {
          // Single symbol -> object; multiple -> { CODE: {...} }
          var map = json && json.symbol ? defObj(json.symbol, json) : (json || {});
          return exchange.stocks.map(function (s) {
            var q = map[s.code];
            if (!q || q.close == null) return clone(s);
            return normalize({
              code: s.code,
              name: q.name || s.name,
              cmp: num(q.close),
              prevClose: num(q.previous_close),
              open: num(q.open),
              high: num(q.high),
              low: num(q.low),
              volume: num(q.volume),
              marketCap: s.marketCap // not in /quote; keep reference value
            });
          });
        });
    }
  };

  /* ---------------- eodhd (paid) ---------------- */
  var eodhd = {
    id: "eodhd",
    label: "EODHD (API key)",
    needsKey: true,
    getQuotes: function (exchange, apiKey) {
      if (!apiKey) return mock.getQuotes(exchange);
      // EODHD uses SYMBOL.EXCHANGECODE; reuse the Yahoo-style suffix without the dot.
      var ex = (exchange.yahooSuffix || "").replace(".", "");
      var tickers = exchange.stocks
        .map(function (s) { return s.code + "." + ex; })
        .join(",");
      var url = "https://eodhd.com/api/real-time/" + encodeURIComponent(exchange.stocks[0].code + "." + ex) +
                "?s=" + encodeURIComponent(tickers) + "&fmt=json&api_token=" + encodeURIComponent(apiKey);
      return fetch(url)
        .then(function (r) { return r.json(); })
        .then(function (json) {
          var rows = Array.isArray(json) ? json : [json];
          var byCode = {};
          rows.forEach(function (q) {
            var code = String(q.code || "").split(".")[0];
            byCode[code] = q;
          });
          return exchange.stocks.map(function (s) {
            var q = byCode[s.code];
            if (!q || q.close == null || q.close === "NA") return clone(s);
            return normalize({
              code: s.code,
              name: s.name,
              cmp: num(q.close),
              prevClose: num(q.previousClose),
              open: num(q.open),
              high: num(q.high),
              low: num(q.low),
              volume: num(q.volume),
              marketCap: s.marketCap
            });
          });
        });
    }
  };

  function num(v) { var n = parseFloat(v); return isFinite(n) ? n : null; }
  function defObj(k, v) { var o = {}; o[k] = v; return o; }

  var registry = { mock: mock, yahoo: yahoo, twelvedata: twelvedata, eodhd: eodhd };

  // Public API: resolve a provider, run it, and fall back to mock on any error.
  function fetchQuotes(providerId, exchange, apiKey) {
    var p = registry[providerId] || mock;
    var run;
    try {
      run = p.getQuotes(exchange, apiKey);
    } catch (e) {
      run = Promise.reject(e);
    }
    return Promise.resolve(run).catch(function (err) {
      console.warn("[providers] '" + providerId + "' failed, using sample data:", err && err.message);
      return mock.getQuotes(exchange).then(function (rows) {
        rows._fellBack = true;
        return rows;
      });
    });
  }

  global.GCC_PROVIDERS = {
    list: [mock, yahoo, twelvedata, eodhd],
    fetchQuotes: fetchQuotes
  };
})(window);
