/*
 * Provider framework (shared base) — loaded before any provider module.
 *
 * Each provider lives in its own file (mock.js, yahoo.js, twelvedata.js,
 * eodhd.js) and self-registers here via GCC_PROVIDERS.register(...). They all
 * share one contract:
 *
 *     getQuotes(exchange, apiKey) -> Promise<Array<stock>>
 *
 * where `stock` matches the shape S() produces in js/data.js. If a live call
 * fails (network/CORS/missing key/uncovered exchange) the framework falls back
 * to the mock provider so the UI always renders.
 *
 * `phase` metadata documents the rollout: phase 1 = free/offline defaults,
 * phase 2 = live paid feed (Twelve Data).
 */
(function (global) {
  "use strict";

  function clone(stock) { return JSON.parse(JSON.stringify(stock)); }
  function num(v) { var n = parseFloat(v); return isFinite(n) ? n : null; }
  function defObj(k, v) { var o = {}; o[k] = v; return o; }

  // Rebuild derived fields once a live provider supplies raw price points.
  function normalize(raw) {
    var prevClose = raw.prevClose != null ? raw.prevClose : raw.cmp;
    var change = raw.cmp - prevClose;
    var open = raw.open != null ? raw.open : raw.cmp;
    return {
      code: raw.code,
      name: raw.name || raw.code,
      cmp: raw.cmp,
      change: change,
      changePct: prevClose ? (change / prevClose) * 100 : 0,
      opening: open,
      closing: prevClose,
      dayOpen: open,
      dayClose: raw.cmp,
      weekOpen: raw.weekOpen != null ? raw.weekOpen : open,
      weekClose: raw.cmp,
      sessionHigh: raw.high != null ? raw.high : raw.cmp,
      sessionLow: raw.low != null ? raw.low : raw.cmp,
      volume: raw.volume != null ? raw.volume : 0,
      marketCap: raw.marketCap != null ? raw.marketCap : 0
    };
  }

  var list = [];
  var byId = {};

  function register(provider) {
    if (byId[provider.id]) return;
    byId[provider.id] = provider;
    list.push(provider);
  }

  function get(id) { return byId[id] || byId.mock; }

  // Resolve a provider, run it, and fall back to mock on any error.
  function fetchQuotes(providerId, exchange, apiKey) {
    var p = get(providerId);
    var run;
    try {
      run = p.getQuotes(exchange, apiKey);
    } catch (e) {
      run = Promise.reject(e);
    }
    return Promise.resolve(run).catch(function (err) {
      console.warn("[providers] '" + providerId + "' failed, using sample data:", err && err.message);
      return byId.mock.getQuotes(exchange).then(function (rows) {
        rows._fellBack = true;
        return rows;
      });
    });
  }

  global.GCC_PROVIDERS = {
    list: list,
    register: register,
    get: get,
    fetchQuotes: fetchQuotes,
    helpers: { clone: clone, num: num, defObj: defObj, normalize: normalize }
  };
})(window);
