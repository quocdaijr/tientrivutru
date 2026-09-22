/*
 * The trader page. Same two layers as the other two, same rule about which one is allowed
 * to shout - and here the silent layer does something the other pages cannot: it grades the
 * loud layer on the loud layer's own data, in the same second, in front of the reader.
 *
 * Nothing is committed. Binance's klines carry no licence that would let this repo
 * redistribute them, so the browser fetches them and the tab forgets them. Same decision,
 * same reason, as finance.js.
 *
 * This is the only page on the site that loads a third-party script, and it renders every
 * number without it. The library is pinned by version and by SRI, credited in the colophon
 * because Apache-2.0's NOTICE asks for that, and its absence is a state this page handles
 * rather than a state it crashes in.
 *
 * Wrapped in an IIFE for the reason dom.js and finance.js are: classic scripts share one
 * top-level lexical scope and this page loads six of them. warning.js already owns `boot`.
 * Only window.TienTriVuTruTrader escapes.
 */
(function () {
'use strict';

const T = window.TienTriVuTruTheme;
const THAY = window.TienTriVuTruThay;
/* The site already has one seeded PRNG and it is the tested one. */
const seededRandom = window.TienTriVuTruPersonal.seededRandom;
const { el, stage, tw } = window.TienTriVuTruDom;

/* ---------------- source ----------------
 * Binance publishes these for its own front end. Verified 2026-09-22: the REST endpoint
 * answers a cross-origin GET with `access-control-allow-origin: *`, and the stream accepts
 * a websocket handshake from a github.io origin. Neither needs a key. Neither carries a
 * contract, so the page credits it and degrades when it goes quiet.
 */
const SOURCE = {
  label: 'Binance',
  site: 'https://www.binance.com/',
  rest: 'https://api.binance.com/api/v3/klines',
  stream: 'wss://stream.binance.com:9443/ws',
};

const SYMBOL = 'BTCUSDT';
const INTERVAL = '1m';
/* Binance's own per-call maximum. ~16.7 hours of one-minute candles, in one request. */
const LIMIT = 1000;
/* Enough shuffles that one unlucky permutation carries nothing. */
const SHUFFLES = 20;
/* Relabelling draws for the p-value. 2000 gives a resolution of 0.0005. */
const PERMUTATIONS = 2000;
/* Binance spot taker fee, one side, published. Every measured edge is compared against TWO
   of these, because a trade is an entry and an exit. */
const TAKER_FEE = 0.001;
const HCM = 'Asia/Ho_Chi_Minh';
/* How long a hidden tab keeps its socket. A two-second tab switch is not worth a reconnect. */
const HIDDEN_GRACE_MS = 30000;
/* Failures before the page stops hiding the outage from the reader. */
const QUIET_RETRIES = 5;

/* ---------------- patterns ----------------
 * Every threshold here is a RATIO, never an absolute price. That is not a style choice:
 * stage 02 re-chains these same candles onto a different price path, and a threshold in
 * dollars would make that comparison measure the price level instead of the pattern.
 * Pinned by test_patterns_are_scale_invariant.
 */
const PATTERNS = {
  doji:         { label: 'Doji — nến do dự', rule: 'thân ≤ 10% biên độ' },
  bua:          { label: 'Nến búa', rule: 'thân ≤ 30% biên độ, bóng dưới ≥ 2× thân, bóng trên ≤ 25%' },
  nhanChimTang: { label: 'Nhấn chìm tăng', rule: 'nến xanh phủ trọn thân nến đỏ trước' },
  nhanChimGiam: { label: 'Nhấn chìm giảm', rule: 'nến đỏ phủ trọn thân nến xanh trước' },
  baConQua:     { label: 'Ba con quạ đen', rule: 'ba nến đỏ đặc, mỗi cây mở trong thân cây trước, đóng thấp dần' },
};
const PATTERN_KEYS = Object.keys(PATTERNS);
/* The Bonferroni divisor, read from the detector rather than typed a second time. */
const PATTERN_COUNT = PATTERN_KEYS.length;

/* ============================ parsers ============================
 * Split from fetch on purpose, the way finance.js is: it is what lets these run in Node
 * against a recorded payload, with no HTTP mocking library anywhere in the suite.
 */

/**
 * Binance sends prices as strings and times as epoch milliseconds. Lightweight Charts wants
 * numbers and epoch SECONDS - feeding it milliseconds renders somewhere past the year 50000
 * with no error thrown anywhere, so the unit is in the field's name and pinned by a test.
 */
function parseKlines(rows) {
  if (!Array.isArray(rows)) throw new Error('klines: không phải mảng');
  return rows.map((r) => {
    if (!Array.isArray(r) || r.length < 6) throw new Error('klines: dòng thiếu cột');
    const bar = {
      t: Math.floor(r[0] / 1000),
      o: parseFloat(r[1]), h: parseFloat(r[2]),
      l: parseFloat(r[3]), c: parseFloat(r[4]), v: parseFloat(r[5]),
    };
    if (!Number.isFinite(bar.t)) throw new Error('klines: mốc thời gian không hợp lệ');
    for (const k of ['o', 'h', 'l', 'c']) {
      if (!Number.isFinite(bar[k]) || bar[k] <= 0) throw new Error('klines: giá không hợp lệ');
    }
    return bar;
  });
}

/** One websocket frame. `k.x` is Binance's own "this candle is final" flag. */
function parseKlineEvent(msg) {
  const k = msg && msg.k;
  if (!k) throw new Error('ws: khung không phải kline');
  const bar = {
    t: Math.floor(k.t / 1000),
    o: parseFloat(k.o), h: parseFloat(k.h),
    l: parseFloat(k.l), c: parseFloat(k.c), v: parseFloat(k.v),
  };
  if (!Number.isFinite(bar.t) || !Number.isFinite(bar.c)) throw new Error('ws: khung hỏng');
  return { bar, closed: k.x === true };
}

/* ============================ indicators ============================
 * The two the fortune-teller teaches in stage 01, so stage 02 has something named to take
 * apart. They are correct implementations: the joke does not need them to be wrong.
 */

/** Simple moving average of closes. Null until there are `n` bars at or behind `i`. */
function sma(bars, i, n) {
  if (i < n - 1) return null;
  let s = 0;
  for (let k = i - n + 1; k <= i; k++) s += bars[k].c;
  return s / n;
}

/** Wilder's RSI - the one every course teaches. Seeded on the first `n` bars, then smoothed. */
function rsi14(bars, n = 14) {
  const out = new Array(bars.length).fill(null);
  if (bars.length <= n) return out;
  let gain = 0;
  let loss = 0;
  for (let i = 1; i <= n; i++) {
    const d = bars[i].c - bars[i - 1].c;
    if (d >= 0) gain += d; else loss -= d;
  }
  gain /= n;
  loss /= n;
  out[n] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  for (let i = n + 1; i < bars.length; i++) {
    const d = bars[i].c - bars[i - 1].c;
    gain = (gain * (n - 1) + Math.max(d, 0)) / n;
    loss = (loss * (n - 1) + Math.max(-d, 0)) / n;
    out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  }
  return out;
}

/* ============================ the detector ============================ */

const body = (b) => Math.abs(b.c - b.o);
const range = (b) => b.h - b.l;

/**
 * Which patterns fire ON bar `i`.
 *
 * One function, two stages: stage 00 asks it for the last bar so thầy can name something,
 * stage 02 runs it over everything so the page can grade him. A second copy would grade a
 * different detector, which would grade nothing.
 *
 * The hammer carries no prior-downtrend filter, on purpose. The textbook wants one; a trend
 * filter is a second free parameter, and the two stages have to run the identical function.
 * The page says so out loud rather than hiding it - and adding it does not move the result.
 */
function patternsAt(bars, i) {
  const b = bars[i];
  const r = range(b);
  /* A minute with no range is not a pattern, and it is also every ratio's divisor. */
  if (!(r > 0)) return [];
  const bd = body(b);
  const up = b.h - Math.max(b.o, b.c);
  const dn = Math.min(b.o, b.c) - b.l;
  const hit = [];

  if (bd <= 0.10 * r) hit.push('doji');
  if (bd <= 0.30 * r && dn >= 2 * bd && up <= 0.25 * r) hit.push('bua');

  if (i >= 1) {
    const p = bars[i - 1];
    const pb = body(p);
    if (pb > 0 && bd > pb) {
      if (p.c < p.o && b.c > b.o && b.c >= p.o && b.o <= p.c) hit.push('nhanChimTang');
      if (p.c > p.o && b.c < b.o && b.c <= p.o && b.o >= p.c) hit.push('nhanChimGiam');
    }
  }

  if (i >= 2) {
    const t = [bars[i - 2], bars[i - 1], bars[i]];
    const solidRed = t.every((x) => x.c < x.o && range(x) > 0 && body(x) >= 0.5 * range(x));
    const stepping = t[1].c < t[0].c && t[2].c < t[1].c
      && t[1].o < t[0].o && t[1].o > t[0].c
      && t[2].o < t[1].o && t[2].o > t[1].c;
    if (solidRed && stepping) hit.push('baConQua');
  }
  return hit;
}

/** Per-pattern counts over a whole series. */
function detectPatterns(bars) {
  const counts = {};
  for (const k of PATTERN_KEYS) counts[k] = 0;
  for (let i = 0; i < bars.length; i++) {
    for (const k of patternsAt(bars, i)) counts[k]++;
  }
  return counts;
}

/** Per-bar flag lists, so the forward-return test does not run the detector twice. */
function patternFlags(bars) {
  return bars.map((_, i) => patternsAt(bars, i));
}

/* ============================ the random series ============================ */

/**
 * A random series made of the real candles, reordered.
 *
 * Each bar contributes four log ratios - the gap from the previous close, and its own high,
 * low and close relative to its own open - so a permutation re-chains real candle shapes
 * onto a new path. Nothing is drawn from a distribution.
 *
 * Deliberately NOT a normal or GBM draw: that invites the one serious objection, "your fake
 * data has thin tails and no volatility clustering, that is why it has fewer patterns".
 * Here every synthetic candle IS a real candle and there is nothing left to argue with.
 *
 * Deliberately not a block bootstrap either: for a two-bar pattern a length-10 block keeps
 * nine of every ten adjacent pairs intact, so the null would preserve about ninety percent
 * of exactly the structure it exists to destroy.
 */
function shuffledBars(bars, seed) {
  const n = bars.length;
  const parts = [];
  for (let i = 0; i < n; i++) {
    const b = bars[i];
    parts.push({
      gap: i === 0 ? 0 : Math.log(b.o / bars[i - 1].c),
      up: Math.log(b.h / b.o),
      dn: Math.log(b.l / b.o),
      ret: Math.log(b.c / b.o),
    });
  }
  const rand = seededRandom(seed);
  for (let i = n - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    const tmp = parts[i];
    parts[i] = parts[j];
    parts[j] = tmp;
  }
  const out = [];
  let prev = bars.length ? bars[0].o : 0;
  for (let i = 0; i < n; i++) {
    const p = parts[i];
    const o = i === 0 ? prev : prev * Math.exp(p.gap);
    const bar = {
      t: bars[i].t, o,
      h: o * Math.exp(p.up), l: o * Math.exp(p.dn), c: o * Math.exp(p.ret),
      v: bars[i].v,
    };
    out.push(bar);
    prev = bar.c;
  }
  return out;
}

/** Same window, same printed numbers on a reload. Same rule the prophecy seeds live under. */
function canonical(bars) {
  const last = bars[bars.length - 1];
  return [bars.length, bars[0].t, last.t, last.c].join(':');
}

function compareToRandom(bars) {
  const real = detectPatterns(bars);
  const sums = {};
  for (const k of PATTERN_KEYS) sums[k] = 0;
  const base = canonical(bars);
  for (let r = 0; r < SHUFFLES; r++) {
    const counts = detectPatterns(shuffledBars(bars, base + ':' + r));
    for (const k of PATTERN_KEYS) sums[k] += counts[k];
  }
  const random = {};
  for (const k of PATTERN_KEYS) random[k] = sums[k] / SHUFFLES;
  return { real, random, shuffles: SHUFFLES, bars: bars.length };
}

/* ============================ the statistic that answers the question ============================ */

const mean = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;

/**
 * Does a pattern say anything about the NEXT candle?
 *
 * This, and not the pattern count, is the honest test - and finding that out cost a wrong
 * design first. Counting patterns on a shuffled series is vacuous for one-bar patterns (a
 * doji is a property of one candle, so reordering cannot touch it and the counts come back
 * IDENTICAL, not merely close) and misleading for multi-bar ones, which differ because of
 * volatility clustering - a different claim from predictiveness, and not the claim anybody
 * is selling a course about.
 *
 * So: take the open-to-close return of the bar AFTER each firing, compare its mean against
 * the mean over every bar, and get the p-value by relabelling - draw as many bars at random
 * as the pattern fired, PERMUTATIONS times, and count how often a deviation at least this
 * large turns up by itself. No distributional assumption, which matters on a series whose
 * tails are the whole reason people trade it.
 */
function forwardReturnStats(bars, flags) {
  const next = [];
  for (let i = 0; i < bars.length - 1; i++) next.push(bars[i + 1].c / bars[i + 1].o - 1);
  const base = next.length ? mean(next) : 0;
  const rand = seededRandom(bars.length ? canonical(bars) + ':perm' : 'empty');
  const rows = [];

  for (const key of PATTERN_KEYS) {
    const idx = [];
    for (let i = 0; i < next.length; i++) {
      if (flags[i] && flags[i].indexOf(key) >= 0) idx.push(i);
    }
    /* Under ten firings is not a p-value. It reports the count and nothing else, rather
       than a number dressed up as evidence. */
    if (idx.length < 10) {
      rows.push({ key, n: idx.length, mean: null, edge: null, p: null });
      continue;
    }
    const m = mean(idx.map((i) => next[i]));
    const edge = Math.abs(m - base);
    let hits = 0;
    for (let r = 0; r < PERMUTATIONS; r++) {
      let s = 0;
      for (let j = 0; j < idx.length; j++) s += next[Math.floor(rand() * next.length)];
      if (Math.abs(s / idx.length - base) >= edge) hits++;
    }
    rows.push({ key, n: idx.length, mean: m, edge: m - base, p: hits / PERMUTATIONS });
  }

  const measured = rows.filter((r) => r.edge !== null).map((r) => Math.abs(r.edge));
  return {
    base,
    rows,
    samples: next.length,
    alpha: 0.05 / PATTERN_COUNT,
    roundTripFee: 2 * TAKER_FEE,
    bestEdge: measured.length ? Math.max.apply(null, measured) : null,
  };
}

/* ============================ the socket ============================ */

/**
 * Binance drops a connection at about twenty-four hours, so this path runs in normal
 * operation and not only when something is broken. Pure, so the test can walk it; the
 * jitter is applied at the call site so it stays deterministic here.
 */
const backoffDelay = (attempt) => Math.min(30000, 1000 * Math.pow(2, Math.min(attempt, 5)));

/* ============================ formatting ============================
 * Vietnamese reads 86.142,00, and every figure on this page is a number rather than a word,
 * so it goes out in --font-num - design.md's rule, because the body face ships no tabular
 * figure set and a column of prices in it misaligns by up to 77px.
 */
const usd = (n) => n.toLocaleString('vi-VN', { minimumFractionDigits: 2,
                                               maximumFractionDigits: 2 });
const pctAt = (x, d) => (x * 100).toLocaleString('vi-VN', { minimumFractionDigits: d,
                                                            maximumFractionDigits: d }) + '%';
const signed = (x, d) => (x >= 0 ? '+' : '−') + pctAt(Math.abs(x), d);
const num = (n, d) => n.toLocaleString('vi-VN', { minimumFractionDigits: d,
                                                  maximumFractionDigits: d });

/* Binance is UTC. Nothing shifts bars[].t into +07 to fake a local axis - that would put a
   lie in the data itself. Timestamps stay UTC seconds everywhere and are formatted only at
   the edge, where the axis can be honestly labelled "giờ VN". */
const vnClock = new Intl.DateTimeFormat('vi-VN',
  { timeZone: HCM, hour: '2-digit', minute: '2-digit' });
const vnStamp = new Intl.DateTimeFormat('vi-VN',
  { timeZone: HCM, hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' });
const vnTime = (t) => vnClock.format(new Date(t * 1000));

/* ============================ the token -> canvas bridge ============================ */

/* Built on first use, never at load: this file is required from Node by the test suite,
   where there is no document to ask for a canvas. It is also a page that renders without a
   chart, and a page that never draws one should never allocate one. */
let probe = null;

/**
 * A token, normalised to the sRGB bytes the chart canvas will actually paint.
 *
 * Readback, not string-parsing. design.md's rule: getComputedStyle returns `oklch(...)`
 * verbatim and reading that as RGB produces confident nonsense. Grepping the library bundle
 * confirms it carries no oklch parser of its own, so the conversion has to happen here -
 * and doing it on a canvas gives the exact bytes the chart will paint, out-of-gamut
 * clipping included.
 */
function tokenColor(name, alpha) {
  if (!probe) {
    const canvas = document.createElement('canvas');
    canvas.width = 1;
    canvas.height = 1;
    probe = canvas.getContext('2d', { willReadFrequently: true });
    if (!probe) return null;
  }
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  if (!raw) return null;
  /* 'copy' is load-bearing. Assigning an unparsable string to fillStyle is silently
     ignored, and without it the readback would hand back the PREVIOUS colour and nothing
     would ever say so. With it, a fill that never took reads as transparent. */
  probe.globalCompositeOperation = 'copy';
  probe.fillStyle = raw;
  probe.fillRect(0, 0, 1, 1);
  const d = probe.getImageData(0, 0, 1, 1).data;
  if (d[3] === 0) return null;
  return alpha == null || alpha === 1
    ? 'rgb(' + d[0] + ',' + d[1] + ',' + d[2] + ')'
    : 'rgba(' + d[0] + ',' + d[1] + ',' + d[2] + ',' + alpha + ')';
}

/*
 * The background MUST be --color-paper-2, and that is a contrast decision rather than a
 * decorative one. The chart sits inside a .block, whose background is --color-paper-2; the
 * library's own default is white, which on thantai would be a white rectangle on lacquer
 * red. Forcing the token is also the only reason this canvas can make an AA claim at all:
 * its axis text then sits as --color-ink-dim on --color-paper-2, the identical pair .note
 * inside a .block already uses, measured worst 4.56:1 on veso.
 */
function chartPalette() {
  return {
    autoSize: true,
    layout: {
      background: { type: 'solid', color: tokenColor('--color-paper-2') },
      textColor: tokenColor('--color-ink-dim'),
      fontFamily: getComputedStyle(document.documentElement)
        .getPropertyValue('--font-num').trim(),
      attributionLogo: false,
    },
    grid: {
      vertLines: { color: tokenColor('--color-rule', 0.18) },
      horzLines: { color: tokenColor('--color-rule', 0.18) },
    },
    crosshair: {
      vertLine: { color: tokenColor('--color-accent') },
      horzLine: { color: tokenColor('--color-accent') },
    },
    rightPriceScale: { borderColor: tokenColor('--color-rule', 0.5) },
    /* Without this a vertical swipe on a phone is eaten by the chart and the reader cannot
       scroll past it. Verified with a finger at 375px, not with a mouse. */
    handleScroll: { vertTouchDrag: false },
    localization: { timeFormatter: vnTime },
    timeScale: { tickMarkFormatter: vnTime, borderColor: tokenColor('--color-rule', 0.5) },
  };
}

function seriesPalette() {
  return {
    upColor: tokenColor('--color-good'),
    downColor: tokenColor('--color-bad'),
    wickUpColor: tokenColor('--color-good'),
    wickDownColor: tokenColor('--color-bad'),
    borderVisible: false,
  };
}

/* ============================ page state ============================ */

let chart = null;
let candles = null;
let maLine = null;
let bars = [];
let socket = null;
let attempt = 0;
let retryTimer = null;
let hideTimer = null;
let liveSince = null;
const reducedMotion = typeof matchMedia === 'function'
  && matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ============================ fetch ============================ */

async function fetchKlines() {
  const url = SOURCE.rest + '?symbol=' + SYMBOL + '&interval=' + INTERVAL + '&limit=' + LIMIT;
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error('HTTP ' + res.status);
  return parseKlines(await res.json());
}

/* ============================ chart ============================ */

const toBar = (b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c });

function maSeries(list, n) {
  const out = [];
  for (let i = 0; i < list.length; i++) {
    const v = sma(list, i, n);
    if (v !== null) out.push({ time: list[i].t, value: v });
  }
  return out;
}

function buildChart() {
  const box = document.getElementById('chart');
  if (!box) return;
  const L = window.LightweightCharts;
  if (!L) {
    chartNote('Thư viện vẽ biểu đồ không tải được — bảng số dưới đây là cùng dữ liệu đó.');
    return;
  }
  /* Never guess a colour. If the tokens cannot be read there is no honest chart to draw,
     and the numeric block below already carries every figure. */
  if (!tokenColor('--color-paper-2')) {
    chartNote('Không đọc được màu của bộ da này, nên trang không vẽ biểu đồ — bảng số dưới '
      + 'đây là cùng dữ liệu đó.');
    return;
  }
  chart = L.createChart(box, chartPalette());
  candles = chart.addSeries(L.CandlestickSeries, seriesPalette());
  candles.setData(bars.map(toBar));
  maLine = chart.addSeries(L.LineSeries, {
    color: tokenColor('--color-accent'), lineWidth: 2,
    priceLineVisible: false, lastValueVisible: false,
  });
  maLine.setData(maSeries(bars, 20));
  chart.timeScale().setVisibleLogicalRange({
    from: Math.max(0, bars.length - 120), to: bars.length,
  });
  /* A webfont that has not loaded yet renders the axis in the fallback face and never
     repaints on its own, so the palette is applied a second time once the face is in. */
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => { if (chart) chart.applyOptions(chartPalette()); });
  }
}

function chartNote(text) {
  const box = document.getElementById('chart');
  if (!box) return;
  box.style.height = 'auto';
  box.appendChild(el('p', 'note err', text));
}

/* applyTheme() writes documentElement.dataset.theme and dispatches nothing, so the attribute
   is observed rather than an event added to a file the other two pages depend on. This also
   catches the anti-FOUC inline script in <head>, which no event ever would. If a second page
   ever needs the same hook, move it to a CustomEvent in theme.js and delete this. */
function retheme() {
  if (!chart) return;
  chart.applyOptions(chartPalette());
  candles.applyOptions(seriesPalette());
  if (maLine) maLine.applyOptions({ color: tokenColor('--color-accent') });
}

/* ============================ the socket ============================ */

function setLiveNote(text) {
  const box = document.getElementById('live-note');
  if (!box) return;
  box.textContent = text || '';
  box.hidden = !text;
}

function updateTape(bar, closed) {
  const cells = {
    o: usd(bar.o), h: usd(bar.h), l: usd(bar.l), c: usd(bar.c), v: num(bar.v, 3),
  };
  for (const k of Object.keys(cells)) {
    const node = document.getElementById('tape-' + k);
    if (node) node.textContent = cells[k];
  }
  const stamp = document.getElementById('tape-t');
  if (stamp) {
    stamp.textContent = vnStamp.format(new Date(bar.t * 1000)) + (closed ? '' : ' · đang chạy');
  }
  const delta = document.getElementById('tape-d');
  if (delta) {
    const d = bar.c / bar.o - 1;
    delta.textContent = signed(d, 2);
    delta.className = 'delta ' + (d >= 0 ? 'delta--up' : 'delta--down');
  }
}

function connect() {
  if (typeof WebSocket === 'undefined') {
    setLiveNote('Trình duyệt này không mở được WebSocket, nên biểu đồ đứng ở cây nến cuối.');
    return;
  }
  /* Two callers can reach this: the retry timer, and resume() when the tab comes back. If a
     retry is already pending when the reader returns to the tab, both would fire and the
     page would hold two live sockets - and two sockets push the SAME closed candle into
     bars twice, which corrupts the moving average rather than merely wasting a connection.
     One socket at a time, and whoever connects deliberately cancels the pending retry. */
  clearTimeout(retryTimer);
  retryTimer = null;
  if (socket) return;
  let sock;
  try {
    sock = new WebSocket(SOURCE.stream + '/' + SYMBOL.toLowerCase() + '@kline_' + INTERVAL);
  } catch (e) {
    scheduleReconnect();
    return;
  }
  socket = sock;

  sock.onopen = () => {
    attempt = 0;
    liveSince = Date.now();
    setLiveNote('');
  };

  sock.onmessage = (ev) => {
    let tick;
    try {
      tick = parseKlineEvent(JSON.parse(ev.data));
    } catch (e) {
      return;                       // one malformed frame is not a reason to drop the stream
    }
    /* Reduced motion repaints once a minute instead of several times a second. The numbers
       are identical either way; only the frequency of the animation changes. */
    if (reducedMotion && !tick.closed) return;
    if (candles) candles.update(toBar(tick.bar));
    /* Only ever append the NEXT candle. Binance resends the closing frame, and a reconnect
       can replay one, so an unguarded push duplicates a bar - which the chart tolerates but
       the moving average does not. */
    if (tick.closed && tick.bar.t > bars[bars.length - 1].t) {
      bars.push(tick.bar);
      while (bars.length > LIMIT) bars.shift();
      if (maLine) {
        const v = sma(bars, bars.length - 1, 20);
        if (v !== null) maLine.update({ time: tick.bar.t, value: v });
      }
    }
    updateTape(tick.bar, tick.closed);
  };

  sock.onerror = () => {};          // a close always follows, and that is where retry lives

  sock.onclose = () => {
    socket = null;
    scheduleReconnect();
  };
}

function scheduleReconnect() {
  if (document.hidden) return;      // the visibility handler owns the wake-up
  const delay = backoffDelay(attempt);
  attempt++;
  /* Five quiet retries first - about 34 seconds, measured. Until then the tape already tells
     the truth on its own: it carries the last candle's timestamp and drops the "đang chạy"
     label the moment ticks stop. Shouting on the first dropped frame would cry wolf at every
     tunnel and lift. */
  if (attempt > QUIET_RETRIES) {
    setLiveNote('Thầy mất sóng trực tiếp — biểu đồ là ' + bars.length + ' cây nến gần nhất, '
      + 'không cập nhật thêm. Trang vẫn thử nối lại.');
  }
  clearTimeout(retryTimer);
  retryTimer = setTimeout(connect, delay * (0.8 + Math.random() * 0.4));
}

function closeSocket() {
  clearTimeout(retryTimer);
  retryTimer = null;
  if (!socket) return;
  const sock = socket;
  socket = null;
  sock.onclose = null;              // a deliberate close must not trigger the retry ladder
  try { sock.close(); } catch (e) { /* already gone */ }
}

let resuming = false;

async function resume() {
  /* Hiding and showing a tab twice in a second would otherwise fire two backfills at the
     same chart, and the second one's setData can land before the first one's. */
  if (resuming) return;
  resuming = true;
  /* The gap has to be filled BEFORE the stream resumes: series.update() with a time that is
     not strictly after the last one throws, and a chart that silently stops updating is
     worse than one that says it stopped. */
  try {
    bars = await fetchKlines();
    if (candles) candles.setData(bars.map(toBar));
    if (maLine) maLine.setData(maSeries(bars, 20));
    updateTape(bars[bars.length - 1], true);
    setLiveNote('');
  } catch (e) {
    setLiveNote('Thầy không hỏi lại được giá sau khi con quay lại — biểu đồ đang là nến cũ.');
  }
  attempt = 0;
  resuming = false;
  connect();
}

function watchVisibility() {
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      hideTimer = setTimeout(closeSocket, HIDDEN_GRACE_MS);
      return;
    }
    clearTimeout(hideTimer);
    if (!socket) resume();
  });
}

/* ============================ 00 · PHÁN NẾN ============================
 * The fortune-teller. He names a shape, gives a reading, and leaves himself an exit. He is
 * never allowed to say which way the price goes - that sentence belongs to the people this
 * page is about.
 */

const OPENERS = [
  'Con ngồi xuống. Thầy nhìn cây nến là thầy biết.',
  'Đừng bấm vội. Thầy đọc xong cái này đã.',
  'Thầy xem ba mươi năm rồi, nến nào thầy cũng gặp.',
  'Con đưa cái biểu đồ đây. Thầy soi.',
];

const READINGS = [
  'Cây nến cuối là <b>{pattern}</b>. Sách nào cũng vẽ nó, và vẽ rất đẹp.',
  'Thầy thấy <b>{pattern}</b> nằm ngay đó. Người ta phải học một khoá mới nhìn ra.',
  '<b>{pattern}</b>. Thầy nói thế thôi, con tự ngẫm.',
  'Hình này gọi là <b>{pattern}</b>. Nghe tên đã thấy có chuyện.',
];

const CLOSERS = [
  'Lên là con giỏi. Xuống là con vào sai giờ, thầy đã bảo rồi.',
  'Thầy chỉ đọc hình. Còn tay con bấm thì thầy không giữ được.',
  'Thầy không giải thích thêm. Giải thích là mất thiêng.',
  'Con nhớ: thầy đọc nến, chứ thầy không đọc hộ cái ví của con.',
];

const NO_PATTERN = 'không hình gì cả';

function factGrid(pairs, cls) {
  const grid = el('div', 'facts');
  for (const [k, v] of pairs) {
    const cell = el('div', 'fact');
    cell.appendChild(el('div', 'fact__k', k));
    cell.appendChild(el('div', cls || 'fact__v', v));
    grid.appendChild(cell);
  }
  return grid;
}

/** The most recent bar that fired anything, so thầy has something to name. */
function latestPattern(list) {
  for (let i = list.length - 1; i >= 0; i--) {
    const hit = patternsAt(list, i);
    if (hit.length) return { key: hit[0], index: i, age: list.length - 1 - i };
  }
  return null;
}

function stagePhanNen(d) {
  const section = stage('00', tw('1f52e', '🔮') + ' Phán nến',
    'Thầy đọc cây nến vừa xong. Giá trị dự báo: không.');
  const block = el('div', 'block block--torn');

  if (!d.ok) {
    const row = el('div', 'thay-row');
    row.innerHTML = THAY.flip('idle', 'blink')
      + '<div><p class="thay__say">Thầy không thấy cây nến nào, nên thầy không phán.</p></div>';
    block.appendChild(row);
    block.appendChild(el('p', 'note',
      'Không có nến thì không có quẻ. Trang này không dựng một cái biểu đồ cũ lên để thầy '
      + 'có cái mà nói.'));
    section.appendChild(block);
    return section;
  }

  const found = latestPattern(d.bars);
  const rand = seededRandom(canonical(d.bars));
  const pick = (arr) => arr[Math.floor(rand() * arr.length)];
  const name = found ? PATTERNS[found.key].label : NO_PATTERN;
  const last = d.bars[d.bars.length - 1];

  const row = el('div', 'thay-row');
  row.innerHTML = THAY.flip('idle', 'blink')
    + '<div>'
    + '<p class="thay__say">' + pick(OPENERS) + '</p>'
    + '<p class="thay__say">' + pick(READINGS).replace('{pattern}', name) + '</p>'
    + '<p class="thay__say">' + pick(CLOSERS) + '</p>'
    + '</div>';
  block.appendChild(row);

  block.appendChild(factGrid([
    ['Hình thầy gọi tên', name],
    ['Cách đây', found ? (found.age === 0 ? 'cây nến đang chạy' : found.age + ' cây nến') : '—'],
    ['Giá lúc thầy nhìn', usd(last.c) + ' USD'],
  ], 'fact__v'));

  block.appendChild(el('p', 'note',
    'Quẻ trên sinh ra từ chính mấy cây nến ở dưới, bằng một phép cộng chữ số. Cùng bộ nến '
    + 'thì cùng lời phán — nó ổn định, chứ không đúng. Chặng 02 đo xem cái hình thầy vừa '
    + 'gọi tên nói được gì về cây nến kế tiếp.'));
  section.appendChild(block);
  return section;
}

/* ============================ 01 · BẢNG NẾN ============================ */

const GLOSSARY = [
  ['Nến, và bốn con số của nó',
    'Một cây nến là một khoảng thời gian — ở đây là một phút. Thân nến nối giá <b>mở</b> với '
    + 'giá <b>đóng</b>; xanh là đóng cao hơn mở, đỏ là ngược lại. Hai cái bóng thò ra là giá '
    + '<b>cao nhất</b> và <b>thấp nhất</b> trong phút đó. Bốn số, viết tắt là OHLC.'],
  ['Bóng nến',
    'Bóng dài nghĩa là giá đã đi tới đó rồi bị kéo về. Nó cho biết trong phút ấy có giằng co, '
    + 'và không cho biết gì thêm.'],
  ['Khối lượng',
    'Bao nhiêu BTC đã đổi chủ trong cây nến đó. Cùng một biên độ giá, khối lượng lớn nghĩa là '
    + 'nhiều người tham gia hơn — không nghĩa là hướng đi đáng tin hơn.'],
  ['Khung thời gian',
    'Cùng một thị trường, đổi khung là đổi hình. Một cây nến 1 ngày gộp 1.440 cây nến 1 phút '
    + 'lại, và mọi mẫu hình con thấy ở khung này sẽ biến mất ở khung khác.'],
  ['Spread',
    'Khoảng cách giữa giá người mua sẵn sàng trả và giá người bán sẵn sàng nhận. Con mua ở '
    + 'mức cao, bán ở mức thấp, nên vừa vào lệnh là đã lỗ đúng bằng cái khoảng đó.'],
  ['Lệnh thị trường và lệnh giới hạn',
    '<b>Thị trường</b>: khớp ngay ở giá đang có, và trả phí taker. <b>Giới hạn</b>: đặt giá '
    + 'của mình rồi chờ, phí thấp hơn, đổi lại có thể không khớp bao giờ.'],
  ['Cắt lỗ',
    'Một lệnh tự đóng vị thế khi giá chạm ngưỡng con đặt trước. Nó giới hạn khoản lỗ của một '
    + 'lần vào lệnh. Nó không làm kỳ vọng của cả chuỗi lệnh dương lên.'],
  ['Đòn bẩy và giá thanh lý',
    'Đòn bẩy <b>L</b> nghĩa là một biến động ngược <b>1/L</b> đủ xoá sạch phần vốn của con. '
    + 'L = 20 thì con số đó là <b>5%</b> — và 5% trong một ngày của BTC không phải chuyện lạ. '
    + 'Sàn đóng vị thế giúp con, ở mức giá thị trường lúc ấy, không phải mức con muốn.'],
];

function chartBlock(d) {
  const box = el('div', 'block');
  box.appendChild(el('h3', 'block__head', tw('1f4ca', '📊') + ' BTC/USDT · nến 1 phút'));

  if (!d.ok) {
    box.appendChild(el('p', 'err',
      'Thầy không gọi được ' + SOURCE.label + ' — ' + d.error + '.'));
    box.appendChild(el('p', 'note',
      'Trang này không giữ bản sao nào, nên nguồn im là ô này trống. Không có cây nến cũ nào '
      + 'được dựng lên thay thế.'));
    return box;
  }

  const chartBox = el('div', 'chart');
  chartBox.id = 'chart';
  chartBox.setAttribute('role', 'img');
  chartBox.setAttribute('aria-label',
    'Biểu đồ nến BTC/USDT khung 1 phút, ' + d.bars.length + ' cây gần nhất. '
    + 'Giá đóng mới nhất ' + usd(d.bars[d.bars.length - 1].c) + ' đô la Mỹ.');
  box.appendChild(chartBox);

  const note = el('p', 'note err');
  note.id = 'live-note';
  note.hidden = true;
  box.appendChild(note);

  /* The numeric block does four jobs with one component: the screen-reader equivalent of a
     canvas, the keyboard-reachable equivalent, the only surface here whose contrast the DOM
     can measure, and the fallback when the CDN or the socket dies. It updates on bar close
     only - a live region firing several times a second is a denial of service aimed at a
     screen reader. */
  const tape = el('div', 'facts');
  tape.setAttribute('aria-live', 'polite');
  const cells = [['Mở', 'o'], ['Cao', 'h'], ['Thấp', 'l'], ['Đóng', 'c'], ['Khối lượng', 'v']];
  for (const [label, key] of cells) {
    const cell = el('div', 'fact');
    cell.appendChild(el('div', 'fact__k', label));
    const v = el('div', 'fact__v fact__v--num', '—');
    v.id = 'tape-' + key;
    cell.appendChild(v);
    if (key === 'c') {
      const delta = el('span', 'delta', '—');
      delta.id = 'tape-d';
      cell.appendChild(delta);
    }
    tape.appendChild(cell);
  }
  box.appendChild(tape);

  const foot = el('div', 'chart__foot');
  const stamp = el('p', 'note');
  stamp.id = 'tape-t';
  stamp.textContent = '—';
  foot.appendChild(stamp);
  const src = el('p', 'note src');
  src.innerHTML = 'Nguồn: <a href="' + SOURCE.site + '" target="_blank" rel="noopener">'
    + SOURCE.label + '</a> · trục thời gian là giờ VN';
  foot.appendChild(src);
  box.appendChild(foot);

  /* Lightweight Charts has no keyboard interaction, so the wrapper gets no tabindex. Saying
     so is more honest than a tabindex="0" that focuses a box nothing can be done with. */
  box.appendChild(el('p', 'note',
    'Biểu đồ chỉ đọc được bằng chuột hoặc chạm. Số của cây nến mới nhất nằm ngay trên, '
    + 'dạng chữ, và cập nhật mỗi khi một cây nến đóng.'));
  return box;
}

function glossaryBlock() {
  const box = el('div', 'block');
  box.appendChild(el('h3', 'block__head', 'Đọc cái biểu đồ đó'));
  const dl = el('dl', 'gloss');
  for (const [term, text] of GLOSSARY) {
    dl.appendChild(el('dt', null, term));
    dl.appendChild(el('dd', null, text));
  }
  box.appendChild(dl);
  return box;
}

function analysisBlock(d) {
  const box = el('div', 'block');
  box.appendChild(el('h3', 'block__head', 'Phân tích kỹ thuật — phần thầy dạy'));

  const dl = el('dl', 'gloss');
  dl.appendChild(el('dt', null, 'MA20 — đường trung bình 20 cây'));
  dl.appendChild(el('dd', null,
    'Trung bình cộng giá đóng của 20 cây gần nhất, vẽ đè lên biểu đồ. Người ta bảo giá cắt '
    + 'lên là tín hiệu tốt, cắt xuống là tín hiệu xấu.'
    + (d.ok && d.ma !== null ? ' Hiện tại: <span class="gloss__rule">' + usd(d.ma)
      + '</span>, giá đang ' + (d.bars[d.bars.length - 1].c >= d.ma ? 'nằm trên' : 'nằm dưới')
      + '.' : '')));
  dl.appendChild(el('dt', null, 'RSI14 — chỉ số sức mạnh tương đối'));
  dl.appendChild(el('dd', null,
    'Một con số từ 0 đến 100, đo tỉ lệ giữa phần tăng và phần giảm của 14 cây gần nhất. Trên '
    + '70 gọi là "quá mua", dưới 30 gọi là "quá bán".'
    + (d.ok && d.rsi !== null ? ' Hiện tại: <span class="gloss__rule">' + num(d.rsi, 1)
      + '</span>.' : '')));

  for (const key of PATTERN_KEYS) {
    dl.appendChild(el('dt', null, PATTERNS[key].label));
    dl.appendChild(el('dd', null,
      'Trang này nhận ra nó bằng đúng một điều kiện, viết ra đây chứ không giấu: '
      + '<span class="gloss__rule">' + PATTERNS[key].rule + '</span>.'));
  }
  box.appendChild(dl);

  box.appendChild(el('p', 'note',
    'Ngưỡng ở trên là do trang tự đặt. Đổi ngưỡng thì đổi số đếm — nên chúng được in ra, và '
    + 'chặng 02 chấm đúng bộ ngưỡng này chứ không phải một bộ khác. Nến búa ở đây không kèm '
    + 'điều kiện "phải có xu hướng giảm trước" mà sách hay đòi: một bộ lọc xu hướng là thêm '
    + 'một tham số tự do nữa, và hai chặng phải chạy đúng cùng một hàm.'));
  return box;
}

function stageBangNen(d) {
  const section = stage('01', tw('1f4ca', '📊') + ' Bảng nến',
    'Giá thật, chạy thật. Và đủ từ vựng để nhìn vào đó mà hiểu.');
  section.appendChild(chartBlock(d));
  section.appendChild(glossaryBlock());
  section.appendChild(analysisBlock(d));
  return section;
}

/* ============================ 02 · SỰ THẬT ============================
 * The fortune-teller is not allowed in this section.
 */

function cell(text, label, cls) {
  const td = el('td', cls || null, text);
  if (label) td.setAttribute('data-label', label);
  return td;
}

function forwardTable(stats) {
  const table = el('table', 'stack-sm stack-sm--matrix');
  const head = el('thead');
  const hr = el('tr');
  for (const h of ['Mẫu hình', 'Số lần nổ', 'Lợi suất nến kế tiếp', 'Lệch nền', 'p']) {
    hr.appendChild(el('th', null, h));
  }
  head.appendChild(hr);
  table.appendChild(head);

  const tbody = el('tbody');
  for (const row of stats.rows) {
    const tr = el('tr');
    tr.appendChild(cell(PATTERNS[row.key].label, 'Mẫu hình'));
    tr.appendChild(cell(String(row.n), 'Số lần nổ'));
    if (row.p === null) {
      tr.appendChild(cell('—', 'Lợi suất nến kế tiếp'));
      tr.appendChild(cell('—', 'Lệch nền'));
      tr.appendChild(cell('quá ít lần để nói', 'p', 'cmp__flat'));
    } else {
      tr.appendChild(cell(signed(row.mean, 5), 'Lợi suất nến kế tiếp'));
      tr.appendChild(cell(signed(row.edge, 5), 'Lệch nền'));
      tr.appendChild(cell(num(row.p, 3) + (row.p < stats.alpha ? '' : ' · trong nhiễu'),
        'p', row.p < stats.alpha ? null : 'cmp__flat'));
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  return table;
}

function shuffleTable(cmp) {
  const table = el('table', 'stack-sm stack-sm--matrix');
  const head = el('thead');
  const hr = el('tr');
  for (const h of ['Mẫu hình', 'Nến thật', 'Nến đã xáo', 'Chênh']) {
    hr.appendChild(el('th', null, h));
  }
  head.appendChild(hr);
  table.appendChild(head);

  const tbody = el('tbody');
  for (const key of PATTERN_KEYS) {
    const real = cmp.real[key];
    const fake = cmp.random[key];
    const tr = el('tr');
    tr.appendChild(cell(PATTERNS[key].label, 'Mẫu hình'));
    tr.appendChild(cell(String(real), 'Nến thật'));
    tr.appendChild(cell(num(fake, 1), 'Nến đã xáo'));
    tr.appendChild(cell(real === fake ? '0 · bất biến' : signed(fake ? (real - fake) / fake : 0, 1),
      'Chênh', real === fake ? 'cmp__flat' : null));
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  return table;
}

function measuredBlock(d) {
  const box = el('div', 'block');
  box.appendChild(el('h3', 'block__head',
    'Mấy hình đó nói được gì về cây nến kế tiếp?'));

  if (!d.ok) {
    box.appendChild(el('p', 'err',
      'Không lấy được cây nến nào, nên phần này không chạy được — nó cần dữ liệu thật để '
      + 'xáo, và trang không giữ bản sao nào.'));
    return box;
  }

  const stats = d.stats;
  box.appendChild(el('p', null,
    'Với mỗi lần một mẫu hình nổ, lấy lợi suất mở-đến-đóng của <b>cây nến ngay sau đó</b>, '
    + 'rồi so trung bình của chúng với trung bình của toàn bộ ' + stats.samples + ' cây. '
    + 'p-value tính bằng cách dán nhãn lại ngẫu nhiên ' + PERMUTATIONS + ' lần — không giả '
    + 'định phân phối nào cả.'));
  box.appendChild(forwardTable(stats));
  box.appendChild(el('p', 'note',
    'Nền chung: ' + signed(stats.base, 5) + ' mỗi cây nến. Ngưỡng ý nghĩa sau hiệu chỉnh '
    + 'Bonferroni cho ' + PATTERN_COUNT + ' phép thử song song: <b>p &lt; '
    + num(stats.alpha, 4) + '</b>. Thử năm thứ cùng lúc thì thỉnh thoảng một cái ra số đẹp '
    + 'là chuyện bình thường, không phải phát hiện.'));

  if (stats.bestEdge !== null) {
    box.appendChild(el('p', null,
      'Lợi thế lớn nhất đo được ở trên là <b>' + pctAt(stats.bestEdge, 5) + '</b> mỗi lệnh. '
      + 'Phí taker của chính sàn này, vào rồi ra, là <b>' + pctAt(stats.roundTripFee, 3)
      + '</b> — gấp <b>' + num(stats.roundTripFee / stats.bestEdge, 1) + ' lần</b>. Kể cả '
      + 'khi con số kia là thật, nó chưa đủ trả phí.'));
  }

  box.appendChild(el('h3', 'block__head', 'Thử cách khác: xáo thứ tự nến'));
  box.appendChild(el('p', null,
    'Lấy đúng ' + d.bars.length + ' cây nến đó, xáo thứ tự bằng xúc xắc ' + SHUFFLES + ' lần, '
    + 'nối lại thành một chuỗi giá mới, rồi đếm lại. Mọi cây nến trong chuỗi giả <b>đều là '
    + 'một cây nến thật</b> — chỉ thứ tự là ngẫu nhiên.'));
  box.appendChild(shuffleTable(d.cmp));
  box.appendChild(el('p', 'note',
    'Nến búa và doji là tính chất của <b>một</b> cây nến đứng riêng. Thầy xáo toàn bộ thứ tự '
    + 'bằng xúc xắc, và chúng xuất hiện <b>đúng bằng số cũ</b> — không phải gần bằng, mà '
    + 'bằng. Một hình dạng không hề biết cây kế tiếp là gì. Hai mẫu nhiều cây thì có chênh, '
    + 'nhưng cái chênh đó nói rằng thị trường có những đoạn biến động dồn cục — nó không nói '
    + 'rằng mẫu hình báo trước được điều gì. Bảng ở trên mới là bảng trả lời câu đó.'));
  box.appendChild(el('p', 'note',
    'Cửa sổ dữ liệu: ' + d.bars.length + ' cây nến ' + INTERVAL + ', lấy lúc ' + d.takenAt
    + ' giờ VN. Số ở hai bảng này tính một lần lúc tải trang và không đổi theo tick — một '
    + 'phép tính trung thực mà âm thầm chạy dưới mắt người đọc thì tệ hơn một con số cũ.'));
  return box;
}

function citationsBlock() {
  const box = el('div', 'block');
  box.appendChild(el('h3', 'block__head', 'Hai con số trang này không tự đo được'));
  const dl = el('dl', 'gloss');

  dl.appendChild(el('dt', null, '74–89% tài khoản bán lẻ CFD lỗ'));
  dl.appendChild(el('dd', null,
    'Phân tích của các cơ quan quản lý thành viên EU, trích trong quyết định can thiệp sản '
    + 'phẩm của <b>ESMA</b> (ESMA35-43-1135). Lỗ bình quân mỗi khách từ 1.600 đến 29.000 '
    + 'EUR. Đó là lý do mọi sàn CFD ở châu Âu bị buộc phải in tỉ lệ thua lỗ của chính họ lên '
    + 'quảng cáo.'));

  dl.appendChild(el('dt', null, '97% người trụ lại vẫn lỗ'));
  dl.appendChild(el('dd', null,
    'Chague, De-Losso &amp; Giovannetti, <i>"Day trading for a living?"</i> '
    + '(<a href="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101" target="_blank" '
    + 'rel="noopener">SSRN 3423101</a>). Toàn bộ cá nhân bắt đầu day trade 2013–2015 trên thị '
    + 'trường hợp đồng tương lai cổ phiếu Brazil và <b>trụ được ít nhất 300 ngày</b>: '
    + '<b>97% lỗ</b>, chỉ <b>0,4%</b> kiếm hơn một giao dịch viên ngân hàng (54 USD/ngày), '
    + 'người giỏi nhất được 310 USD/ngày với độ lệch chuẩn 2.560 USD. Và các tác giả '
    + '<b>không tìm thấy bằng chứng nào</b> cho thấy người ta khá lên theo thời gian.'));

  box.appendChild(dl);
  box.appendChild(el('p', 'note',
    'Hai con số này là của thị trường khác, không phải Việt Nam. Trang để nguyên như vậy: '
    + 'không có nguồn công khai nào đo cùng thứ đó cho nhà đầu tư cá nhân trong nước, và '
    + 'dựng một con số Việt Nam ra cho hợp cảnh là đúng thứ trang này bóc.'));
  return box;
}

function honestyBlock(d) {
  const box = el('div', 'block');
  box.appendChild(el('h3', 'block__head', 'Trang này tự khai'));
  const dl = el('dl', 'gloss');

  dl.appendChild(el('dt', null, 'Đây là Binance spot, không phải HOSE'));
  dl.appendChild(el('dd', null,
    'Biểu đồ trên realtime thật, và có được điều đó chỉ vì crypto chạy 24/7 và Binance mở '
    + 'API miễn phí. Giá cổ phiếu Việt Nam theo thời gian thực đi qua websocket của sở, bán '
    + 'theo hợp đồng cho vendor — nên trang tài chính bên cạnh in số <b>cuối phiên</b> và '
    + 'nói thẳng ra như vậy.'));

  dl.appendChild(el('dt', null, 'Mẫu hình là do trang tự định nghĩa'));
  dl.appendChild(el('dd', null,
    'Năm ngưỡng ở chặng 01 do trang đặt ra, và đổi ngưỡng thì đổi số đếm. Chúng được in ra '
    + 'để con kiểm được, và cùng một hàm chạy ở cả chặng 00 lẫn chặng này — nếu không, bảng '
    + 'trên chấm một thứ khác với thứ thầy vừa nói.'));

  dl.appendChild(el('dt', null, 'Mẫu nhỏ chế ra ý nghĩa'));
  dl.appendChild(el('dd', null,
    'Trong lúc dựng trang này, chạy thử trên 1000 cây nến 1 giờ, "nhấn chìm" ra p = 0,038 — '
    + 'trông như một phát hiện. Kéo lên 6000 cây thì nó tan thành p = 0,651. Bảng ở trên '
    + 'chạy trên ' + (d.ok ? d.bars.length : LIMIT) + ' cây; con số của nó cũng phải đọc với '
    + 'đúng sự dè dặt đó.'));

  dl.appendChild(el('dt', null, 'Một script bên thứ ba'));
  dl.appendChild(el('dd', null,
    'Biểu đồ được vẽ bằng TradingView Lightweight Charts™ (Apache-2.0), tải từ CDN và ghim '
    + 'theo cả phiên bản lẫn hash. Đó là thứ duy nhất trên cả site này gọi ra ngoài lúc chạy '
    + 'ngoài font, và nếu nó không tải được thì bảng số ở chặng 01 vẫn mang đủ dữ liệu.'));

  box.appendChild(dl);
  return box;
}

function stageSuThat(d) {
  const section = stage('02', tw('1f4c9', '📉') + ' Sự thật',
    'Phần này không có thầy. Chỉ có số của chính mấy cây nến ở trên.');
  section.appendChild(measuredBlock(d));
  section.appendChild(citationsBlock());
  section.appendChild(honestyBlock(d));
  return section;
}

/* ============================ boot ============================ */

function render(d) {
  const app = document.getElementById('app');
  app.innerHTML = '';
  app.appendChild(stagePhanNen(d));
  app.appendChild(stageBangNen(d));
  app.appendChild(stageSuThat(d));
  window.TienTriVuTruDom.observeReveals();
  window.TienTriVuTruDom.observeFlips();
}

async function boot() {
  let d;
  try {
    bars = await fetchKlines();
    const flags = patternFlags(bars);
    const rsi = rsi14(bars);
    d = {
      ok: true,
      bars,
      stats: forwardReturnStats(bars, flags),
      cmp: compareToRandom(bars),
      ma: sma(bars, bars.length - 1, 20),
      rsi: rsi[bars.length - 1],
      takenAt: vnStamp.format(new Date()),
    };
  } catch (e) {
    d = { ok: false, error: (e && e.message) || 'không rõ lý do' };
  }

  render(d);
  if (!d.ok) return;

  updateTape(bars[bars.length - 1], true);
  buildChart();
  new MutationObserver(retheme).observe(document.documentElement,
    { attributes: true, attributeFilter: ['data-theme'] });
  watchVisibility();
  connect();
}

window.TienTriVuTruTrader = {
  parseKlines, parseKlineEvent,
  PATTERNS, PATTERN_KEYS, patternsAt, detectPatterns, patternFlags,
  shuffledBars, canonical, compareToRandom, forwardReturnStats,
  sma, rsi14, backoffDelay,
  LIMIT, SHUFFLES, PERMUTATIONS, PATTERN_COUNT, TAKER_FEE,
  SOURCE, SYMBOL, INTERVAL,
};

if (typeof document !== 'undefined' && document.getElementById('app')) {
  T.initThemeControls();
  boot();
}
})();
