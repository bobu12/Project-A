/*
 * GCC Stock Market Dashboard — UI controller.
 *
 * Renders exchange tabs and a sortable/searchable stock table with every
 * requested column, pulling rows from the active data provider (default: mock).
 * Provider + API key are chosen in the Settings dialog and persisted in
 * localStorage.
 */
(function () {
  "use strict";

  var EXCHANGES = window.GCC_DATA.EXCHANGES;
  var PROVIDERS = window.GCC_PROVIDERS;

  var LS_PROVIDER = "gcc.provider";
  var LS_KEY_PREFIX = "gcc.key.";

  // Column definitions: key, header label, numeric?, money?, and the matching
  // requirement from the brief.
  var COLUMNS = [
    { key: "code",        label: "Code",        type: "text" },
    { key: "name",        label: "Name",        type: "text" },
    { key: "cmp",         label: "CMP",         type: "money" },
    { key: "changePct",   label: "Chg %",       type: "pct" },
    { key: "opening",     label: "Opening",     type: "money" },
    { key: "closing",     label: "Closing",     type: "money" },
    { key: "dayOpen",     label: "Day Open",    type: "money" },
    { key: "dayClose",    label: "Day Close",   type: "money" },
    { key: "weekOpen",    label: "Wk Open",     type: "money" },
    { key: "weekClose",   label: "Wk Close",    type: "money" },
    { key: "sessionHigh", label: "Sess. High",  type: "money" },
    { key: "sessionLow",  label: "Sess. Low",   type: "money" },
    { key: "volume",      label: "Volume",      type: "int" },
    { key: "marketCap",   label: "Mkt Cap",     type: "cap" }
  ];

  var els = {
    tabs: document.getElementById("exchange-tabs"),
    title: document.getElementById("market-title"),
    sub: document.getElementById("market-sub"),
    search: document.getElementById("search-input"),
    updated: document.getElementById("updated-at"),
    thead: document.getElementById("stock-thead"),
    tbody: document.getElementById("stock-tbody"),
    tableEmpty: document.getElementById("table-empty"),
    sourceBadge: document.getElementById("source-badge"),
    refreshBtn: document.getElementById("refresh-btn"),
    settingsBtn: document.getElementById("settings-btn"),
    // modal
    modal: document.getElementById("settings-modal"),
    providerSelect: document.getElementById("provider-select"),
    apikeyField: document.getElementById("apikey-field"),
    apikeyInput: document.getElementById("apikey-input"),
    providerNote: document.getElementById("provider-note"),
    settingsClose: document.getElementById("settings-close"),
    settingsCancel: document.getElementById("settings-cancel"),
    settingsSave: document.getElementById("settings-save")
  };

  var state = {
    exchangeId: EXCHANGES[0].id,
    providerId: localStorage.getItem(LS_PROVIDER) || "mock",
    rows: [],
    sortKey: "marketCap",
    sortDir: -1, // -1 desc, 1 asc
    search: ""
  };

  /* ---------------- formatting ---------------- */

  function exchange() {
    return EXCHANGES.filter(function (e) { return e.id === state.exchangeId; })[0];
  }

  function fmtMoney(v, ccy) {
    if (v == null || !isFinite(v)) return "—";
    var dp = v < 10 ? 3 : 2;
    return v.toLocaleString("en-US", { minimumFractionDigits: dp, maximumFractionDigits: dp }) + " " + ccy;
  }

  function fmtInt(v) {
    if (v == null || !isFinite(v)) return "—";
    return Math.round(v).toLocaleString("en-US");
  }

  function fmtCap(v, ccy) {
    if (v == null || !isFinite(v)) return "—";
    var abs = Math.abs(v), unit = "", div = 1;
    if (abs >= 1e12) { unit = "T"; div = 1e12; }
    else if (abs >= 1e9) { unit = "B"; div = 1e9; }
    else if (abs >= 1e6) { unit = "M"; div = 1e6; }
    return (v / div).toFixed(2) + unit + " " + ccy;
  }

  function fmtPct(v) {
    if (v == null || !isFinite(v)) return "—";
    return (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
  }

  function fmtCell(col, row, ccy) {
    switch (col.type) {
      case "money": return fmtMoney(row[col.key], ccy);
      case "int":   return fmtInt(row[col.key]);
      case "cap":   return fmtCap(row[col.key], ccy);
      case "pct":   return fmtPct(row[col.key]);
      default:      return row[col.key] != null ? String(row[col.key]) : "—";
    }
  }

  /* ---------------- rendering ---------------- */

  function renderTabs() {
    els.tabs.innerHTML = "";
    EXCHANGES.forEach(function (ex) {
      var btn = document.createElement("button");
      btn.className = "tab" + (ex.id === state.exchangeId ? " is-active" : "");
      btn.type = "button";
      btn.innerHTML = '<span class="tab-flag">' + ex.flag + '</span>' +
                      '<span class="tab-name">' + ex.short + '</span>' +
                      '<span class="tab-ccy">' + ex.currency + '</span>';
      btn.addEventListener("click", function () { selectExchange(ex.id); });
      els.tabs.appendChild(btn);
    });
  }

  function renderHead() {
    var tr = document.createElement("tr");
    COLUMNS.forEach(function (col) {
      var th = document.createElement("th");
      th.textContent = col.label;
      th.className = "th-" + col.type + (col.key === state.sortKey ? " is-sorted" : "");
      if (col.key === state.sortKey) {
        th.setAttribute("aria-sort", state.sortDir === 1 ? "ascending" : "descending");
        th.innerHTML = col.label + ' <span class="sort-caret">' + (state.sortDir === 1 ? "▲" : "▼") + "</span>";
      }
      th.addEventListener("click", function () { toggleSort(col.key); });
      tr.appendChild(th);
    });
    els.thead.innerHTML = "";
    els.thead.appendChild(tr);
  }

  function visibleRows() {
    var q = state.search.trim().toLowerCase();
    var rows = state.rows.filter(function (r) {
      if (!q) return true;
      return r.code.toLowerCase().indexOf(q) !== -1 ||
             r.name.toLowerCase().indexOf(q) !== -1;
    });
    var key = state.sortKey, dir = state.sortDir;
    rows.sort(function (a, b) {
      var av = a[key], bv = b[key];
      if (typeof av === "string") return av.localeCompare(bv) * dir;
      return ((av || 0) - (bv || 0)) * dir;
    });
    return rows;
  }

  function renderBody() {
    var ccy = exchange().currency;
    var rows = visibleRows();
    els.tbody.innerHTML = "";
    els.tableEmpty.hidden = rows.length !== 0;

    rows.forEach(function (row) {
      var tr = document.createElement("tr");
      COLUMNS.forEach(function (col) {
        var td = document.createElement("td");
        td.className = "td-" + col.type;
        td.textContent = fmtCell(col, row, ccy);
        if (col.key === "changePct") {
          td.classList.add(row.changePct > 0 ? "up" : (row.changePct < 0 ? "down" : "flat"));
        }
        if (col.key === "name") td.classList.add("td-name");
        if (col.key === "code") td.classList.add("td-code");
        tr.appendChild(td);
      });
      els.tbody.appendChild(tr);
    });
  }

  function renderMeta(fellBack) {
    var ex = exchange();
    els.title.textContent = ex.flag + " " + ex.name;
    els.sub.textContent = ex.country + " · prices in " + ex.currency + " · " + ex.stocks.length + " listed";
    var p = providerById(state.providerId);
    els.sourceBadge.textContent = (fellBack ? "Sample (fallback)" : p.label);
    els.sourceBadge.classList.toggle("is-live", !fellBack && p.id !== "mock");
  }

  /* ---------------- data flow ---------------- */

  function providerById(id) {
    return PROVIDERS.list.filter(function (p) { return p.id === id; })[0] || PROVIDERS.list[0];
  }

  function currentKey() {
    var stored = localStorage.getItem(LS_KEY_PREFIX + state.providerId);
    if (stored) return stored;
    return providerById(state.providerId).defaultKey || "";
  }

  function loadQuotes() {
    var ex = exchange();
    els.updated.textContent = "loading…";
    PROVIDERS.fetchQuotes(state.providerId, ex, currentKey()).then(function (rows) {
      state.rows = rows;
      renderHead();
      renderBody();
      renderMeta(!!rows._fellBack);
      els.updated.textContent = "Updated " + new Date().toLocaleTimeString();
    });
  }

  function selectExchange(id) {
    state.exchangeId = id;
    renderTabs();
    loadQuotes();
  }

  function toggleSort(key) {
    if (state.sortKey === key) state.sortDir *= -1;
    else { state.sortKey = key; state.sortDir = (key === "code" || key === "name") ? 1 : -1; }
    renderHead();
    renderBody();
  }

  /* ---------------- settings modal ---------------- */

  function openSettings() {
    els.providerSelect.innerHTML = "";
    PROVIDERS.list.forEach(function (p) {
      var opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = p.label;
      els.providerSelect.appendChild(opt);
    });
    els.providerSelect.value = state.providerId;
    syncModalForProvider();
    els.modal.hidden = false;
  }

  function syncModalForProvider() {
    var p = providerById(els.providerSelect.value);
    els.apikeyField.style.display = p.needsKey ? "" : "none";
    els.apikeyInput.value = localStorage.getItem(LS_KEY_PREFIX + p.id) || p.defaultKey || "";
    els.providerNote.textContent = p.note || "";
  }

  function closeSettings() { els.modal.hidden = true; }

  function saveSettings() {
    var p = providerById(els.providerSelect.value);
    state.providerId = p.id;
    localStorage.setItem(LS_PROVIDER, p.id);
    if (p.needsKey) localStorage.setItem(LS_KEY_PREFIX + p.id, els.apikeyInput.value.trim());
    closeSettings();
    loadQuotes();
  }

  /* ---------------- wiring ---------------- */

  els.search.addEventListener("input", function () {
    state.search = this.value;
    renderBody();
  });
  els.refreshBtn.addEventListener("click", loadQuotes);
  els.settingsBtn.addEventListener("click", openSettings);
  els.settingsClose.addEventListener("click", closeSettings);
  els.settingsCancel.addEventListener("click", closeSettings);
  els.settingsSave.addEventListener("click", saveSettings);
  els.providerSelect.addEventListener("change", syncModalForProvider);
  els.modal.addEventListener("click", function (e) {
    if (e.target === els.modal) closeSettings();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !els.modal.hidden) closeSettings();
  });

  /* ---------------- init ---------------- */
  renderTabs();
  loadQuotes();
})();
