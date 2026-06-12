/*
 * Sample / reference dataset for the GCC Stock Market Dashboard.
 *
 * Ticker codes and company names are real; prices, volumes and market caps are
 * illustrative so the app runs fully offline with no API key. This is the
 * default ("mock") data source. Swap in a live provider via the Settings panel
 * (see js/providers.js) without touching this file.
 *
 * Each stock is built with S(...) which derives the display fields the UI needs
 * from a small set of consistent inputs, so values stay internally coherent
 * (low <= open/cmp/prevClose <= high).
 */
(function (global) {
  "use strict";

  /**
   * Build a normalized stock record.
   * @param {string} code        Exchange ticker / symbol
   * @param {string} name        Company name
   * @param {number} cmp         Current market price (last traded)
   * @param {number} prevClose   Previous session close
   * @param {number} open        Today's opening price
   * @param {number} low         Session low
   * @param {number} high        Session high
   * @param {number} weekOpen    This week's opening price
   * @param {number} volume      Volume traded today (shares)
   * @param {number} marketCap   Market capitalization (local currency)
   */
  function S(code, name, cmp, prevClose, open, low, high, weekOpen, volume, marketCap) {
    var change = cmp - prevClose;
    return {
      code: code,
      name: name,
      cmp: cmp,
      change: change,
      changePct: prevClose ? (change / prevClose) * 100 : 0,
      opening: open,        // "Opening"
      closing: prevClose,   // "Closing" (previous session close)
      dayOpen: open,        // Daily open
      dayClose: cmp,        // Daily close (last traded)
      weekOpen: weekOpen,   // Weekly open
      weekClose: cmp,       // Weekly close (latest)
      sessionHigh: high,    // Session high
      sessionLow: low,      // Session low
      volume: volume,       // Volume traded for the day
      marketCap: marketCap
    };
  }

  var EXCHANGES = [
    {
      id: "tadawul", name: "Saudi Exchange (Tadawul)", short: "Tadawul",
      country: "Saudi Arabia", flag: "🇸🇦", currency: "SAR", mic: "XSAU",
      yahooSuffix: ".SR",
      stocks: [
        S("2222", "Saudi Aramco",            28.40, 28.25, 28.30, 28.05, 28.70, 28.10, 18_540_000, 6_870_000_000_000),
        S("1120", "Al Rajhi Bank",           92.50, 91.80, 91.90, 91.40, 93.20, 90.60,  4_120_000,  370_000_000_000),
        S("2010", "SABIC",                   72.30, 72.90, 72.80, 71.90, 73.10, 73.50,  2_980_000,  216_000_000_000),
        S("7010", "Saudi Telecom (stc)",     41.20, 40.85, 40.90, 40.70, 41.55, 40.40,  3_410_000,  205_000_000_000),
        S("1180", "Saudi National Bank",     35.80, 35.55, 35.60, 35.30, 36.05, 35.10,  5_660_000,  214_000_000_000),
        S("1010", "Riyad Bank",              28.95, 29.10, 29.05, 28.70, 29.20, 29.30,  1_870_000,   86_000_000_000),
        S("2350", "Saudi Kayan",             11.40, 11.20, 11.25, 11.10, 11.60, 11.00,  6_240_000,   17_100_000_000),
        S("4002", "Mouwasat Medical",        95.00, 94.20, 94.40, 93.80, 96.10, 92.50,    410_000,   19_000_000_000)
      ]
    },
    {
      id: "dfm", name: "Dubai Financial Market (DFM)", short: "DFM",
      country: "United Arab Emirates", flag: "🇦🇪", currency: "AED", mic: "XDFM",
      yahooSuffix: ".DU",
      stocks: [
        S("EMAAR",       "Emaar Properties",        8.45,  8.38,  8.40,  8.30,  8.52,  8.20, 12_300_000,  74_500_000_000),
        S("DIB",         "Dubai Islamic Bank",      6.20,  6.15,  6.16,  6.10,  6.27,  6.05,  9_870_000,  44_800_000_000),
        S("EMIRATESNBD", "Emirates NBD",           19.80, 19.65, 19.70, 19.50, 20.05, 19.40,  3_210_000, 125_000_000_000),
        S("DEWA",        "Dubai Electricity & Water", 2.55, 2.53, 2.54, 2.50, 2.58, 2.49, 21_400_000, 127_500_000_000),
        S("SALIK",       "Salik Company",           4.30,  4.26,  4.27,  4.22,  4.35,  4.18,  7_640_000,  32_250_000_000),
        S("TECOM",       "TECOM Group",             3.85,  3.81,  3.82,  3.77,  3.90,  3.74,  2_540_000,  19_250_000_000),
        S("DFM",         "Dubai Financial Market",  1.62,  1.60,  1.61,  1.58,  1.66,  1.57,  5_980_000,  12_960_000_000),
        S("AMANAT",      "Amanat Holdings",         1.45,  1.47,  1.46,  1.43,  1.49,  1.50,  1_870_000,   3_625_000_000)
      ]
    },
    {
      id: "adx", name: "Abu Dhabi Securities Exchange (ADX)", short: "ADX",
      country: "United Arab Emirates", flag: "🇦🇪", currency: "AED", mic: "XADS",
      yahooSuffix: ".AD",
      stocks: [
        S("FAB",        "First Abu Dhabi Bank",     13.20, 13.10, 13.12, 13.00, 13.34, 12.95, 6_540_000, 145_000_000_000),
        S("ADCB",       "Abu Dhabi Commercial Bank", 9.85,  9.78,  9.80,  9.70,  9.94,  9.65, 4_120_000,  71_000_000_000),
        S("ALDAR",      "Aldar Properties",          7.10,  7.02,  7.04,  6.96,  7.20,  6.90, 8_760_000,  55_800_000_000),
        S("IHC",        "International Holding Co.", 400.0, 398.5, 399.0, 396.0, 404.0, 395.0,   210_000, 740_000_000_000),
        S("ADNOCGAS",   "ADNOC Gas",                 3.45,  3.42,  3.43,  3.39,  3.49,  3.37,11_900_000, 265_000_000_000),
        S("ADNOCDIST",  "ADNOC Distribution",        3.78,  3.80,  3.79,  3.74,  3.84,  3.82, 3_980_000,  47_250_000_000),
        S("ADIB",       "Abu Dhabi Islamic Bank",   14.60, 14.48, 14.50, 14.35, 14.78, 14.20, 1_760_000,  53_000_000_000),
        S("TAQA",       "Abu Dhabi National Energy", 3.10,  3.08,  3.09,  3.05,  3.14,  3.06, 2_410_000, 348_000_000_000)
      ]
    },
    {
      id: "qse", name: "Qatar Stock Exchange (QSE)", short: "QSE",
      country: "Qatar", flag: "🇶🇦", currency: "QAR", mic: "DSMD",
      yahooSuffix: ".QA",
      stocks: [
        S("QNBK", "Qatar National Bank",        16.80, 16.70, 16.72, 16.55, 16.95, 16.60, 5_340_000, 155_000_000_000),
        S("IQCD", "Industries Qatar",           13.10, 13.00, 13.02, 12.90, 13.25, 12.85, 2_870_000,  79_200_000_000),
        S("QIBK", "Qatar Islamic Bank",         22.40, 22.20, 22.25, 22.05, 22.60, 21.95, 1_980_000,  52_900_000_000),
        S("MARK", "Masraf Al Rayan",             2.55,  2.57,  2.56,  2.52,  2.60,  2.59, 6_640_000,  23_700_000_000),
        S("QEWS", "Qatar Electricity & Water",  17.20, 17.05, 17.08, 16.90, 17.40, 16.80,   540_000,  18_900_000_000),
        S("ORDS", "Ooredoo",                    11.30, 11.22, 11.24, 11.10, 11.45, 11.05, 1_240_000,  36_200_000_000),
        S("CBQK", "Commercial Bank of Qatar",    4.65,  4.61,  4.62,  4.57,  4.71,  4.55, 2_310_000,  18_800_000_000)
      ]
    },
    {
      id: "kuwait", name: "Boursa Kuwait", short: "Boursa Kuwait",
      country: "Kuwait", flag: "🇰🇼", currency: "KWD", mic: "XKUW",
      yahooSuffix: ".KW",
      stocks: [
        S("KFH",     "Kuwait Finance House",        0.760, 0.752, 0.754, 0.748, 0.768, 0.745, 9_870_000, 13_400_000_000),
        S("NBK",     "National Bank of Kuwait",     0.910, 0.902, 0.904, 0.896, 0.918, 0.900, 7_120_000, 13_800_000_000),
        S("ZAIN",    "Zain Group",                  0.555, 0.560, 0.558, 0.551, 0.564, 0.562, 4_540_000,  4_780_000_000),
        S("BOUBYAN", "Boubyan Bank",                0.640, 0.634, 0.636, 0.630, 0.648, 0.628, 2_980_000,  4_150_000_000),
        S("AGLTY",   "Agility Public Warehousing",  0.285, 0.288, 0.287, 0.283, 0.291, 0.290, 6_240_000,  3_120_000_000),
        S("GBK",     "Gulf Bank",                   0.310, 0.307, 0.308, 0.305, 0.314, 0.306, 3_410_000,  1_980_000_000),
        S("MABANEE", "Mabanee Company",             0.720, 0.714, 0.716, 0.710, 0.728, 0.708,   870_000,  2_040_000_000)
      ]
    },
    {
      id: "msx", name: "Muscat Stock Exchange (MSX)", short: "MSX",
      country: "Oman", flag: "🇴🇲", currency: "OMR", mic: "XMUS",
      yahooSuffix: ".OM",
      stocks: [
        S("BKMB",    "Bank Muscat",                 0.298, 0.295, 0.296, 0.293, 0.301, 0.294, 4_120_000, 2_240_000_000),
        S("OQGN",    "OQ Gas Networks",             0.142, 0.140, 0.141, 0.139, 0.144, 0.139, 3_870_000, 1_540_000_000),
        S("OMINVST", "Oman Investment & Finance",   0.120, 0.121, 0.120, 0.118, 0.123, 0.122, 1_240_000,   420_000_000),
        S("OTEL",    "Omantel",                     0.880, 0.872, 0.874, 0.866, 0.892, 0.870,   640_000, 6_600_000_000),
        S("OQEP",    "OQ Exploration & Production", 0.350, 0.347, 0.348, 0.344, 0.355, 0.346, 2_980_000, 4_560_000_000),
        S("BKDB",    "Bank Dhofar",                 0.165, 0.164, 0.164, 0.162, 0.168, 0.163,   980_000,   500_000_000)
      ]
    },
    {
      id: "bahrain", name: "Bahrain Bourse", short: "Bahrain Bourse",
      country: "Bahrain", flag: "🇧🇭", currency: "BHD", mic: "XBAH",
      yahooSuffix: ".BH",
      stocks: [
        S("BBK",     "BBK (Bank of Bahrain & Kuwait)", 0.520, 0.516, 0.517, 0.512, 0.526, 0.514, 1_240_000, 760_000_000),
        S("NBB",     "National Bank of Bahrain",        0.640, 0.634, 0.636, 0.630, 0.648, 0.632,   870_000, 1_120_000_000),
        S("GFH",     "GFH Financial Group",             0.290, 0.292, 0.291, 0.287, 0.295, 0.293, 3_410_000, 1_080_000_000),
        S("BATELCO", "Bahrain Telecom (Batelco)",       0.520, 0.515, 0.516, 0.510, 0.527, 0.512,   540_000,   860_000_000),
        S("ALBH",    "Aluminium Bahrain (Alba)",        0.880, 0.872, 0.874, 0.866, 0.892, 0.868,   410_000, 1_250_000_000),
        S("ZAINBH",  "Zain Bahrain",                    0.165, 0.166, 0.165, 0.163, 0.168, 0.167,   320_000,   240_000_000)
      ]
    }
  ];

  global.GCC_DATA = { EXCHANGES: EXCHANGES };
})(window);
