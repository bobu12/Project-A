/*
 * Mock provider — Phase 1 default.
 *
 * Serves the built-in sample dataset (js/data.js). No network, no key; always
 * works, and acts as the fallback for every live provider.
 */
(function (global) {
  "use strict";
  var H = global.GCC_PROVIDERS.helpers;

  global.GCC_PROVIDERS.register({
    id: "mock",
    label: "Sample data (offline)",
    needsKey: false,
    phase: 1,
    note: "Built-in sample data. No network, no key — always works.",
    getQuotes: function (exchange) {
      return Promise.resolve(exchange.stocks.map(H.clone));
    }
  });
})(window);
