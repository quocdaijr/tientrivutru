/*
 * The money page. Same two layers as the lottery page, same rule about which one is
 * allowed to shout.
 *
 * Everything here is fetched in the browser and nothing is committed to the repo. That
 * is a licensing decision, not a technical one: every usable Vietnamese price endpoint
 * is an undocumented internal API with no terms attached, and this repo's own rule is
 * that what has no verifiable licence does not get checked in.
 *
 * The cost of that choice is real and is not hidden: with no baked copy to fall back on,
 * a dead upstream means a dead block. So every source degrades on its own - one silent
 * API must never take the page down with it. That contract is lifted straight from
 * sources/vibes.py, which says it best: a dead price API must never stop the pipeline,
 * and a None signal is honest about the fact that the moon was not consulted today.
 *
 * Wrapped in an IIFE for the same reason dom.js is: classic scripts share one top-level
 * lexical scope, and this page loads five of them. `boot`, `digitRoot` and `seededRandom`
 * all collide with warning.js and personal.js otherwise - measured, not guessed. Only
 * window.TienTriVuTruFinance escapes.
 */
(function () {
'use strict';

const T = window.TienTriVuTruTheme;
const THAY = window.TienTriVuTruThay;
/* The site already has one seeded PRNG and it is the tested one. */
const seededRandom = window.TienTriVuTruPersonal.seededRandom;
const { el, stage, tw, vnd } = window.TienTriVuTruDom;

/* ---------------- units ----------------
 *
 * Gold is where this page could most easily lie by a factor of ten, so the conversion is
 * spelled out rather than folded into a magic number.
 *
 * PNJ quotes in thousands of dong per CHỈ (3.75 g), not per lượng. Three independent
 * checks agree, measured 2026-08-22: world spot 4604.40 USD/oz at CoinGecko's own
 * USD/VND cross gives 14,501,916 d/chi; BTMC's silver rows - which carry explicit gram
 * weights, "1 KG 1000 GRAM" and "5 LƯỢNG" agreeing on 64,347 d/g - give 14,477,964 d/chi
 * at a gold:silver ratio of 60; PNJ's own 14,760 lands between them once multiplied by
 * a thousand. Reading it as per-lượng would put Vietnamese gold at a tenth of the world
 * price, which arbitrage does not permit.
 */
const DONG_PER_PNJ_UNIT = 1000;
const CHI_PER_LUONG = 10;
const GRAM_PER_LUONG = 37.5;
const GRAM_PER_OZT = 31.1034768;
const OZT_PER_LUONG = GRAM_PER_LUONG / GRAM_PER_OZT;

const HCM = 'Asia/Ho_Chi_Minh';

/* ---------------- sources ----------------
 * Every one of these is an internal endpoint that its owner published for their own
 * front end, not an API with a contract. Named here so the page can credit each number
 * on screen, and so the day one of them dies the obituary has an address.
 */
const SOURCES = {
  gold: {
    label: 'PNJ',
    site: 'https://giavang.pnj.com.vn/',
    url: 'https://edge-api.pnj.io/ecom-frontend/v1/get-gold-price',
  },
  xau: {
    label: 'gold-api.com',
    site: 'https://gold-api.com/',
    url: 'https://api.gold-api.com/price/XAU',
  },
  indices: {
    label: 'VNDIRECT',
    site: 'https://dstock.vndirect.com.vn/',
    url: 'https://api-finfo.vndirect.com.vn/v4/change_prices?q=code:VNINDEX,HNX,UPCOM~period:1D',
  },
  foreign: {
    label: 'VNDIRECT',
    site: 'https://dstock.vndirect.com.vn/',
    url: 'https://api-finfo.vndirect.com.vn/v4/foreigns'
       + '?q=code:FPT,VNM,HPG,VCB,SSI&sort=tradingDate:desc&size=40',
  },
  crypto: {
    label: 'CoinGecko',
    site: 'https://www.coingecko.com',
    url: 'https://api.coingecko.com/api/v3/simple/price'
       + '?ids=bitcoin,ethereum&vs_currencies=usd,vnd'
       + '&include_24hr_change=true&include_last_updated_at=true',
  },
};

/* ============================ parsing ============================
 *
 * Split from fetching on purpose. The repo has no HTTP mocking library and does not want
 * one; the convention everywhere else is that the parser takes a payload and is tested
 * offline against a real recorded one. Parsers throw on a shape they do not recognise -
 * the caller turns that into a dead block, which is the honest thing to render.
 */

const num = (v) => {
  const n = typeof v === 'number' ? v : Number(v);
  if (!Number.isFinite(n)) throw new Error('không phải số: ' + JSON.stringify(v));
  return n;
};

/** Gold quotes we care about. The rest of the PNJ list is jewellery alloys. */
const GOLD_WANTED = [
  ['SJC', 'Vàng miếng SJC 999.9'],
  ['N24K', 'Nhẫn trơn PNJ 999.9'],
];

function parseGold(payload) {
  const rows = payload && payload.data;
  if (!Array.isArray(rows)) throw new Error('PNJ không trả về mảng data');
  const out = [];
  for (const [code, label] of GOLD_WANTED) {
    const row = rows.find((r) => r && r.masp === code);
    if (!row) continue;
    const perChi = (v) => num(v) * DONG_PER_PNJ_UNIT;
    out.push({
      code,
      label,
      buyChi: perChi(row.giamua),
      sellChi: perChi(row.giaban),
      buyLuong: perChi(row.giamua) * CHI_PER_LUONG,
      sellLuong: perChi(row.giaban) * CHI_PER_LUONG,
    });
  }
  if (!out.length) throw new Error('PNJ không còn niêm yết SJC lẫn nhẫn trơn');
  return out;
}

function parseXau(payload) {
  if (!payload || payload.symbol !== 'XAU') throw new Error('không phải giá XAU');
  return { usdPerOzt: num(payload.price), updatedAt: payload.updatedAt || null };
}

const INDEX_ORDER = ['VNINDEX', 'HNX', 'UPCOM'];

function parseIndices(payload) {
  const rows = payload && payload.data;
  if (!Array.isArray(rows) || !rows.length) throw new Error('VNDIRECT trả về rỗng');
  const byCode = new Map(rows.map((r) => [r.code, r]));
  const out = [];
  for (const code of INDEX_ORDER) {
    const r = byCode.get(code);
    if (!r) continue;
    out.push({
      code,
      price: num(r.price),
      change: num(r.change),
      changePct: num(r.changePct) / 100,
      lastUpdated: r.lastUpdated || null,
    });
  }
  if (!out.length) throw new Error('không có chỉ số nào trong ' + INDEX_ORDER.join(', '));
  return out;
}

/**
 * Foreign net flow, newest session only.
 *
 * The endpoint returns several sessions per ticker; mixing two dates into one column
 * would be the sort of quiet error nobody catches, so this keeps the newest tradingDate
 * present in the payload and drops the rest.
 */
function parseForeign(payload) {
  const rows = payload && payload.data;
  if (!Array.isArray(rows) || !rows.length) throw new Error('VNDIRECT trả về rỗng');
  const dates = rows.map((r) => r.tradingDate).filter(Boolean).sort();
  const latest = dates[dates.length - 1];
  if (!latest) throw new Error('không có tradingDate');
  const seen = new Set();
  const out = [];
  for (const r of rows) {
    if (r.tradingDate !== latest || seen.has(r.code)) continue;
    seen.add(r.code);
    out.push({ code: r.code, netVal: num(r.netVal), floor: r.floor || null });
  }
  out.sort((a, b) => b.netVal - a.netVal);
  return { tradingDate: latest, rows: out };
}

const COINS = [['bitcoin', 'BTC'], ['ethereum', 'ETH']];

function parseCrypto(payload) {
  if (!payload || typeof payload !== 'object') throw new Error('CoinGecko trả về rỗng');
  const out = [];
  for (const [id, ticker] of COINS) {
    const r = payload[id];
    if (!r) continue;
    out.push({
      id,
      ticker,
      usd: num(r.usd),
      vnd: num(r.vnd),
      change24h: num(r.usd_24h_change) / 100,
      lastUpdatedAt: r.last_updated_at ?? null,
    });
  }
  if (!out.length) throw new Error('CoinGecko không trả về đồng nào');
  return out;
}

/**
 * The USD/VND rate CoinGecko itself used, recovered from the pair of quotes.
 *
 * This is not a bank rate and must never be labelled as one - Vietcombank's XML is the
 * number Vietnamese people actually transact at, and it locks CORS to its own origin, so
 * this page genuinely cannot have it. What this is: the cross-rate implied by one
 * provider quoting the same coin twice. Useful only to sanity-check gold against world
 * spot, which is the single place the page uses it.
 */
function impliedUsdVnd(coins) {
  const c = coins.find((x) => x.usd > 0);
  return c ? c.vnd / c.usd : null;
}

/* ============================ fetching ============================ */

async function pull(key, parse) {
  const src = SOURCES[key];
  const res = await fetch(src.url, { cache: 'no-store' });
  if (!res.ok) throw new Error('HTTP ' + res.status);
  return parse(await res.json());
}

/** Never rejects. One dead upstream must cost exactly one block. */
async function settle(key, parse) {
  try {
    return { ok: true, value: await pull(key, parse) };
  } catch (e) {
    return { ok: false, error: e.message || String(e) };
  }
}

/* ============================ formatting ============================ */

const trieu = (n) => (n / 1e6).toLocaleString('vi-VN', {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
}) + ' tr';

const usd = (n) => '$' + n.toLocaleString('en-US', {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
});

const points = (n) => n.toLocaleString('vi-VN', {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
});

/* The shared pct() prints "1.78%"; every other figure on this page is vi-VN, where the
   decimal mark is a comma. One page must not use both. */
const signedPct = (r) => (r >= 0 ? '+' : '−')
  + (Math.abs(r) * 100).toLocaleString('vi-VN', {
      minimumFractionDigits: 2, maximumFractionDigits: 2,
    }) + '%';

function deltaTag(ratio, text) {
  const cls = ratio > 0 ? 'delta delta--up' : ratio < 0 ? 'delta delta--down' : 'delta';
  const arrow = ratio > 0 ? '▲' : ratio < 0 ? '▼' : '·';
  return el('span', cls, `${arrow} ${text}`);
}

/** Today in Vietnam, as the API writes it. Comparing in UTC would flip the date at 07:00. */
function todayHcm() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: HCM }).format(new Date());
}

/**
 * What to say about the timestamp VNDIRECT returned.
 *
 * Takes today as an argument rather than reading the clock, because the branch that
 * matters most is the one that only occurs on a trading day - and a test that can only
 * run Monday to Friday is a test that does not run.
 */
function sessionLabel(stamp, today) {
  if (!stamp) return null;
  if (stamp.slice(0, 10) !== today) {
    return `Đây là <b>phiên gần nhất</b> (${stamp}), không phải hôm nay. `
         + 'Sàn nghỉ thứ Bảy, Chủ nhật và ngày lễ.';
  }
  return `Cập nhật lúc ${stamp} (giờ VN).`;
}

/**
 * `numeric` picks the monospaced face for the value.
 *
 * design.md: any column of figures uses --font-num. The lottery page's fact grids hold
 * words (can chi, nạp âm), so they keep the body face; this page's hold prices, and in
 * Be Vietnam Pro those misalign by up to 77px with no tabular set to fall back on.
 */
function factGrid(pairs, { numeric = false } = {}) {
  const grid = el('div', 'facts');
  const cls = numeric ? 'fact__v fact__v--num' : 'fact__v';
  for (const [k, v, extra] of pairs) {
    const cell = el('div', 'fact');
    cell.appendChild(el('div', 'fact__k', k));
    cell.appendChild(el('div', cls, v));
    if (extra) cell.appendChild(extra);
    grid.appendChild(cell);
  }
  return grid;
}

/** Provenance, on every number the page prints. */
function sourceLine(key, stamp) {
  const src = SOURCES[key];
  const line = el('p', 'note src');
  line.innerHTML = `Nguồn: <a href="${src.site}" target="_blank" rel="noopener">${src.label}</a>`
    + (stamp ? ` · ${stamp}` : '');
  return line;
}

/** Fills a block that has already got its heading, so a dead source keeps its place. */
function fillDead(box, key, error) {
  const src = SOURCES[key];
  box.appendChild(el('p', 'err', `Thầy không gọi được <b>${src.label}</b> — ${error}.`));
  box.appendChild(el('p', 'note',
    'Trang này không giữ bản sao nào, nên nguồn im là ô này trống. '
    + 'Không có số cũ nào được dựng lên thay thế.'));
  return box;
}

/* ============================ 01 · SỔ GIÁ ============================
 * From here down the fortune-teller does not speak.
 */

function goldBlock(gold, xau) {
  const box = el('div', 'block');
  box.appendChild(el('h3', 'block__head', `${tw('1fa84', '🪄')} Vàng`));

  if (!gold.ok) return fillDead(box, 'gold', gold.error);

  const pairs = [];
  for (const row of gold.value) {
    pairs.push([`${row.label} — mua vào`, trieu(row.buyLuong) + '/lượng']);
    pairs.push([`${row.label} — bán ra`, trieu(row.sellLuong) + '/lượng']);
  }
  box.appendChild(factGrid(pairs, { numeric: true }));
  box.appendChild(el('p', 'note',
    'PNJ niêm yết theo <b>chỉ</b> (3,75 g); trang quy ra <b>lượng</b> (10 chỉ, 37,5 g) '
    + 'vì đó là đơn vị người ta nói khi nói về vàng miếng.'));
  box.appendChild(sourceLine('gold'));

  if (xau.ok) {
    box.appendChild(el('p', 'note',
      `Vàng thế giới: <b>${usd(xau.value.usdPerOzt)}/oz</b>`
      + (xau.value.updatedAt ? ` · ${xau.value.updatedAt}` : '')));
    box.appendChild(sourceLine('xau'));
  } else {
    box.appendChild(el('p', 'note err', `Vàng thế giới im: ${xau.error}`));
  }
  return box;
}

function stocksBlock(indices, foreign) {
  const box = el('div', 'block');
  box.appendChild(el('h3', 'block__head', `${tw('1f4ca', '📊')} Chứng khoán Việt`));

  if (!indices.ok) return fillDead(box, 'indices', indices.error);

  const grid = el('div', 'facts');
  for (const idx of indices.value) {
    const cell = el('div', 'fact');
    cell.appendChild(el('div', 'fact__k', idx.code));
    cell.appendChild(el('div', 'fact__v fact__v--num', points(idx.price)));
    cell.appendChild(deltaTag(idx.change,
      `${points(Math.abs(idx.change))} (${signedPct(idx.changePct)})`));
    grid.appendChild(cell);
  }
  box.appendChild(grid);

  const note = sessionLabel(indices.value[0].lastUpdated, todayHcm());
  if (note) box.appendChild(el('p', 'note', note));
  box.appendChild(sourceLine('indices'));

  if (foreign.ok) {
    box.appendChild(el('h4', 'block__head', 'Khối ngoại mua ròng'));
    const rows = foreign.value.rows.map((r) => {
      const cell = el('div', 'fact');
      cell.appendChild(el('div', 'fact__k', r.code));
      cell.appendChild(el('div', 'fact__v fact__v--num', vnd(Math.round(r.netVal))));
      cell.appendChild(deltaTag(r.netVal, r.netVal >= 0 ? 'mua ròng' : 'bán ròng'));
      return cell;
    });
    const grid2 = el('div', 'facts');
    rows.forEach((r) => grid2.appendChild(r));
    box.appendChild(grid2);
    box.appendChild(el('p', 'note', `Phiên ${foreign.value.tradingDate}.`));
    box.appendChild(sourceLine('foreign'));
  } else {
    box.appendChild(el('p', 'note err', `Khối ngoại im: ${foreign.error}`));
  }
  return box;
}

function cryptoBlock(crypto) {
  const box = el('div', 'block');
  box.appendChild(el('h3', 'block__head', `${tw('1f3b2', '🎲')} Crypto`));

  if (!crypto.ok) return fillDead(box, 'crypto', crypto.error);

  const grid = el('div', 'facts');
  for (const c of crypto.value) {
    const cell = el('div', 'fact');
    cell.appendChild(el('div', 'fact__k', c.ticker + ' / USD'));
    cell.appendChild(el('div', 'fact__v fact__v--num', usd(c.usd)));
    cell.appendChild(deltaTag(c.change24h, signedPct(c.change24h) + ' · 24h'));
    grid.appendChild(cell);

    const cellV = el('div', 'fact');
    cellV.appendChild(el('div', 'fact__k', c.ticker + ' / VND'));
    cellV.appendChild(el('div', 'fact__v fact__v--num', vnd(Math.round(c.vnd))));
    grid.appendChild(cellV);
  }
  box.appendChild(grid);
  box.appendChild(el('p', 'note',
    'Giá VND là <b>quy đổi qua tỷ giá</b> của CoinGecko, không phải giá khớp trên một '
    + 'sàn Việt Nam.'));

  /* CoinGecko's attribution guide asks for the credit next to the data, not in a footer. */
  const credit = el('p', 'note src');
  credit.innerHTML = 'Powered by '
    + '<a href="https://www.coingecko.com" target="_blank" rel="noopener">CoinGecko</a>';
  box.appendChild(credit);
  return box;
}

function stageSoGia(d) {
  const section = stage('01', `${tw('1f4ca', '📊')} Sổ giá`,
    'Số thật, nguồn thật, giờ thật. Thầy không có ý kiến ở chặng này.');
  const row = el('div', 'row');
  row.appendChild(goldBlock(d.gold, d.xau));
  row.appendChild(stocksBlock(d.indices, d.foreign));
  row.appendChild(cryptoBlock(d.crypto));
  section.appendChild(row);
  return section;
}

/* ============================ 00 · PHÁN TÀI ============================
 * The cursed layer. Deterministic from the numbers themselves, so the same market
 * produces the same sermon - a fortune-teller who contradicts himself on a refresh is
 * not even good satire.
 */

const ELEMENTS = ['Kim', 'Mộc', 'Thuỷ', 'Hoả', 'Thổ'];

const OPENERS = [
  'Thầy nhìn bảng giá mà thấy cả tam giới rung.',
  'Thầy vừa gieo quẻ trên bảng điện, khói hương chưa tan.',
  'Thầy xem giá xong, thầy im một lúc.',
  'Bảng giá hôm nay có tướng, mà tướng gì thì thầy chưa nói vội.',
];

const READINGS = [
  'Số gốc {root} rơi vào hành {element} — hành này kỵ người hay bấm F5.',
  'Hành {element} đang vượng, số gốc {root}. Vượng ở đâu thì thầy chưa đo được.',
  'Quẻ ra {root}, hành {element}. Sách thầy ghi vậy, sách ai thầy không biết.',
  '{element} gặp số {root}: cổ nhân gọi là “thị trường vẫn đang mở”.',
];

const CLOSERS = [
  'Con cứ nhìn, đừng hỏi thầy nên làm gì — thầy không biết, và thầy có nói cũng đừng nghe.',
  'Lên là phúc nhà con, xuống là do con đọc trang này.',
  'Thầy phán tới đây thôi. Phần còn lại là số học, mà số học thì không nể thầy.',
  'Thầy nói cho vui. Tiền thì không vui như thầy.',
];

/**
 * Digit root of the whole visible market, the same trick oracle.py plays on a draw date.
 * Silent sources contribute the string '-' exactly as vibes.py renders a None signal, so
 * a dead API changes the sermon instead of being quietly skipped.
 */
function canonical(d) {
  const part = (r, f) => (r.ok ? f(r.value) : '-');
  return [
    'gold=' + part(d.gold, (v) => v.map((x) => x.sellChi).join(',')),
    'xau=' + part(d.xau, (v) => String(Math.round(v.usdPerOzt))),
    'idx=' + part(d.indices, (v) => v.map((x) => x.price).join(',')),
    'fx=' + part(d.foreign, (v) => v.tradingDate),
    'coin=' + part(d.crypto, (v) => v.map((x) => Math.round(x.usd)).join(',')),
  ].join('|');
}

function digitRoot(n) {
  let v = Math.abs(Math.round(n));
  while (v > 9) v = String(v).split('').reduce((s, c) => s + Number(c), 0);
  return v || 9;
}

function marketRoot(d) {
  const seed = canonical(d);
  let sum = 0;
  for (let i = 0; i < seed.length; i++) {
    const c = seed.charCodeAt(i);
    if (c >= 48 && c <= 57) sum += c - 48;
  }
  return digitRoot(sum);
}

function stagePhanTai(d) {
  const section = stage('00', `${tw('1f52e', '🔮')} Phán tài`,
    'Thầy xem giá cả rồi phán. Giá trị dự báo: không.');
  const seed = canonical(d);
  const rand = seededRandom(seed);
  const root = marketRoot(d);
  const element = ELEMENTS[root % ELEMENTS.length];
  const pick = (arr) => arr[Math.floor(rand() * arr.length)];

  const row = el('div', 'thay-row');
  row.innerHTML = THAY.flip('idle', 'blink')
    + '<div>'
    + `<p class="thay__say">${pick(OPENERS)}</p>`
    + `<p class="thay__say">${pick(READINGS)
        .replace('{root}', root).replace('{element}', element)}</p>`
    + `<p class="thay__say">${pick(CLOSERS)}</p>`
    + '</div>';

  const block = el('div', 'block block--torn');
  block.appendChild(row);
  block.appendChild(factGrid([
    ['Số của chợ hôm nay', String(root)],
    ['Hành', element],
    ['Nguồn im lặng', String(silentCount(d)) + '/5'],
  ]));
  block.appendChild(el('p', 'note',
    'Quẻ trên sinh ra từ chính mấy con số ở chặng dưới, bằng một phép cộng chữ số. '
    + 'Cùng bộ giá thì cùng lời phán — nó ổn định, chứ không đúng.'));
  section.appendChild(block);
  return section;
}

function silentCount(d) {
  return ['gold', 'xau', 'indices', 'foreign', 'crypto']
    .filter((k) => !d[k].ok).length;
}

/* ============================ 02 · SỰ THẬT ============================
 * The fortune-teller is not allowed in this section.
 */

function stageSuThat(d) {
  const section = stage('02', `${tw('1f4c9', '📉')} Sự thật`,
    'Phần này không có thầy. Chỉ có nguồn, độ trễ, và những thứ không đo được.');

  const delay = el('div', 'block');
  delay.appendChild(el('h3', 'block__head', 'Cái gì thật sự là realtime'));
  const table = el('div', 'facts');
  [
    ['Crypto', 'Realtime', 'Chạy 24/7, CoinGecko cập nhật trong 1–2 phút.'],
    ['Vàng thế giới', 'Realtime', 'Spot XAU/USD, nghỉ theo phiên cuối tuần.'],
    ['Vàng trong nước', 'Giá niêm yết', 'Doanh nghiệp công bố, đổi vài lần mỗi ngày.'],
    ['Chứng khoán VN', 'Cuối phiên (EOD)', 'Không phải realtime. Xem đoạn dưới.'],
  ].forEach(([k, v, note]) => {
    const cell = el('div', 'fact');
    cell.appendChild(el('div', 'fact__k', k));
    cell.appendChild(el('div', 'fact__v', v));
    cell.appendChild(el('div', 'note', note));
    table.appendChild(cell);
  });
  delay.appendChild(table);
  delay.appendChild(el('p', 'note',
    'Bảng giá realtime chính thức của HOSE và HNX đều đẩy qua websocket (SignalR) và '
    + 'phân phối theo hợp đồng vendor; nguồn có tài liệu duy nhất, SSI FastConnect, bắt '
    + 'ra quầy ký giấy mới cấp tài khoản. Trang này không có cái nào trong số đó, nên nó '
    + 'không gọi số liệu chứng khoán là realtime.'));
  section.appendChild(delay);

  const land = el('div', 'block');
  land.appendChild(el('h3', 'block__head', 'Giá đất: không có số để in'));
  land.appendChild(el('p', null,
    'Trang này định có mục giá đất trung bình. Nó không có, và lý do đáng in ra hơn '
    + 'là một con số bịa:'));
  const lands = el('ul', 'sermon');
  [
    'Chỉ số giá bất động sản của Việt Nam mới tồn tại ở dạng bản đặc tả chỉ tiêu năm 2019 — chưa từng công bố số liệu.',
    'Cổng cơ sở dữ liệu bất động sản quốc gia theo Nghị định 94/2024 hiện không phân giải tên miền.',
    'BIS, OECD, FRED và IMF Global Housing Watch đều không có Việt Nam trong bộ chỉ số giá nhà.',
    'Các trang rao vặt có dữ liệu, nhưng điều khoản của họ cấm sao chép và phân phối lại.',
  ].forEach((t) => lands.appendChild(el('li', null, t)));
  land.appendChild(lands);
  land.appendChild(el('p', 'note',
    'Một trang tài chính bịa ra “giá đất trung bình toàn quốc” thì dễ. '
    + 'Nói rằng con số đó không tồn tại thì đúng.'));
  section.appendChild(land);

  const zero = el('div', 'block');
  zero.appendChild(el('h3', 'block__head', 'Về quẻ ở chặng 00'));
  zero.appendChild(el('p', null,
    'Quẻ đó có giá trị dự báo bằng <b>không</b>. Nó là một phép cộng chữ số trên giá '
    + 'đóng cửa, và một phép cộng chữ số không biết gì về thị trường. '
    + 'Trang này không phải tư vấn đầu tư, không khuyến nghị mua bán, và không có gì để bán.'));

  if (d.crypto.ok && d.gold.ok && d.xau.ok) {
    const rate = impliedUsdVnd(d.crypto.value);
    if (rate) {
      const worldLuong = d.xau.value.usdPerOzt * OZT_PER_LUONG * rate;
      const sjc = d.gold.value.find((g) => g.code === 'SJC');
      if (sjc) {
        const premium = sjc.sellLuong / worldLuong - 1;
        zero.appendChild(el('h3', 'block__head', 'Trang tự đối chiếu số của chính nó'));
        zero.appendChild(factGrid([
          ['Vàng thế giới quy ra lượng', trieu(worldLuong) + '/lượng'],
          ['SJC bán ra', trieu(sjc.sellLuong) + '/lượng'],
          ['Chênh lệch', signedPct(premium)],
        ], { numeric: true }));
        zero.appendChild(el('p', 'note',
          `Tỷ giá dùng để quy đổi là <b>${Math.round(rate).toLocaleString('vi-VN')} ₫/$</b>, `
          + 'suy ra từ chính CoinGecko (cùng một đồng được niêm yết bằng cả USD lẫn VND). '
          + 'Đây <b>không</b> phải tỷ giá ngân hàng — tỷ giá Vietcombank khoá CORS theo '
          + 'origin nên trình duyệt không lấy được. Con số này chỉ dùng để kiểm tra chéo '
          + 'giá vàng, không dùng để đổi tiền.'));
      }
    }
  }
  section.appendChild(zero);

  const src = el('div', 'block');
  src.appendChild(el('h3', 'block__head', 'Nguồn, và vì sao không có nguồn nào được lưu'));
  src.appendChild(el('p', null,
    'Mọi con số trên trang được trình duyệt của bạn gọi thẳng tới nguồn, mỗi lần tải lại. '
    + 'Repo không commit dữ liệu tài chính nào.'));
  src.appendChild(el('p', 'note',
    'Lý do là giấy phép: VNDIRECT, PNJ và gold-api đều là endpoint nội bộ không có điều '
    + 'khoản API nào kèm theo, mà luật của repo này là thứ không có licence xác minh được '
    + 'thì không vào repo. Đổi lại, nguồn chết là ô trống — trang không có bản sao để dựng lại.'));
  section.appendChild(src);
  return section;
}

/* ============================ boot ============================ */

function render(d) {
  const app = document.getElementById('app');
  app.innerHTML = '';
  app.appendChild(stagePhanTai(d));
  app.appendChild(stageSoGia(d));
  app.appendChild(stageSuThat(d));
  window.TienTriVuTruDom.observeReveals();
  window.TienTriVuTruDom.observeFlips();
}

async function boot() {
  const [gold, xau, indices, foreign, crypto] = await Promise.all([
    settle('gold', parseGold),
    settle('xau', parseXau),
    settle('indices', parseIndices),
    settle('foreign', parseForeign),
    settle('crypto', parseCrypto),
  ]);
  render({ gold, xau, indices, foreign, crypto });
}

window.TienTriVuTruFinance = {
  parseGold, parseXau, parseIndices, parseForeign, parseCrypto,
  impliedUsdVnd, canonical, marketRoot, digitRoot, silentCount, todayHcm, sessionLabel,
  DONG_PER_PNJ_UNIT, CHI_PER_LUONG, OZT_PER_LUONG,
};

if (typeof document !== 'undefined' && document.getElementById('app')) {
  T.initThemeControls();
  boot();
}
})();
