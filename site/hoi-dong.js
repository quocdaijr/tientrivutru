/*
 * The Council - TradingAgents' twelve LLM agents - scored in the reader's browser.
 *
 * The repo commits only what is its own: a rating per asset per day and the moment it was
 * written (site/data.json -> council). Prices are fetched here, in this tab, and forgotten when
 * it closes: Yahoo's terms forbid automated collection, and neither Binance nor VNDIRECT
 * licenses republishing what is derived from their data. That is the money page's rule, reused.
 *
 * Three rules carry the scoreboard, and tests/test_hoi_dong_js.py pins each one:
 *
 * - The window opens at the first bar AFTER the verdict was written. A verdict cannot be
 *   re-derived from a seed the way a prophecy can, so being written first is the only thing
 *   that makes it honest - and defining the window from the write time means a late write can
 *   only move the window, never choose it.
 * - A bar the source has no price for is a hole. Sliding past it would trade on a day the rule
 *   never named, so the verdict is left unscored and counted as such.
 * - Each verdict is one independent round trip, net of fees on both legs and of the sale tax.
 *   Overlapping Vietnamese windows are not netted: that would be a portfolio nobody proposed.
 *
 * An IIFE for the same reason as every other script here: classic scripts share one top-level
 * scope. Only window.TienTriVuTruHoiDong escapes.
 */
(function () {
'use strict';

const seededRandom = window.TienTriVuTruPersonal.seededRandom;

const DAY = 86400;
const RATINGS = ['Buy', 'Overweight', 'Hold', 'Underweight', 'Sell'];
const POSITION = { Buy: 1, Overweight: 0.5, Hold: 0, Underweight: -0.5, Sell: -1 };
const MIN_SCORED_FOR_P = 30;
/* Ten a half: below that, "better later" is the order two short runs of luck happened in. */
const MIN_SCORED_FOR_TREND = 20;
const PERMUTATIONS = 10000;
/* The code the Council runs, mirrored from hoi_dong.UPSTREAM for a bundle that predates it. */
const UPSTREAM = 'TauricResearch/TradingAgents@2d17df8da1536c121e4d7395ac5a5dcec9e96d6f';
/* A bundle built before the Council existed has no `council` key. That is "has not sat yet",
   not an error - only a bundle that cannot be fetched or read is. */
const NOT_YET = { upstream: UPSTREAM, month: null, spent_usd: 0, cap_usd: null,
                  stopped: false, verdicts: [] };

/* ---------------- assets and costs ----------------
 * Every number below was read from its primary source on 2026-09-23 (research/phi-thue-t2):
 * - BTC taker fee 0.10% per side: Binance and OKX regular-user spot taker.
 * - VN broker fee 0.15% per side: SSI online, and VPS after its promotion (VNDIRECT 0.10%,
 *   TCBS 0.03% - the default is the typical rate, not the cheapest one findable).
 * - VN sale tax 0.1% of the sale value: Personal Income Tax Law 109/2025/QH15 Art. 13, in force
 *   since 2026-07-01; Decree 253/2026 Art. 10.
 * - Exit at the close of session T+2: shares bought in session T arrive around noon on T+2
 *   and can be sold from that afternoon (HOSE investor guide 02/2026; VSDC, 2022-08-29).
 * - No retail shorting of HOSE shares: Circular 120/2020 Art. 7(3), Art. 11(5).
 * None of it includes spread or slippage, so a real round trip only ever costs more.
 */
const VN = { kind: 'vn_stock', canShort: false, fee: 0.0015, tax: 0.001, exitOffset: 2,
             source: 'vndirect' };
const ASSETS = {
  'BTC-USD': { key: 'BTC-USD', label: 'BTC', kind: 'crypto', canShort: true, fee: 0.001,
               tax: 0, exitOffset: 0, source: 'binance', symbol: 'BTCUSDT' },
  'FPT.VN': Object.assign({ key: 'FPT.VN', label: 'FPT', code: 'FPT' }, VN),
  'VNM.VN': Object.assign({ key: 'VNM.VN', label: 'VNM', code: 'VNM' }, VN),
  'VCB.VN': Object.assign({ key: 'VCB.VN', label: 'VCB', code: 'VCB' }, VN),
};

const SOURCES = {
  binance: { label: 'Binance', site: 'https://www.binance.com/',
             url: (a) => `https://api.binance.com/api/v3/klines?symbol=${a.symbol}&interval=1d&limit=1000` },
  vndirect: { label: 'VNDIRECT', site: 'https://dstock.vndirect.com.vn/',
              url: (a, since) => 'https://api-finfo.vndirect.com.vn/v4/stock_prices?sort=date'
                + `&q=code:${a.code}~date:gte:${since}&size=1000&page=1` },
};

/* ============================ rating -> money ============================ */

/** null for REVIEW or anything unrecognised: not a trade. Clamped to flat where shorting
    is not something the asset's retail holder can do. */
function position(rating, asset) {
  if (!Object.prototype.hasOwnProperty.call(POSITION, rating)) return null;
  const p = POSITION[rating];
  return asset.canShort ? p : Math.max(p, 0);
}

/**
 * Net return of one round trip on a notional of 1. The fee is charged on each leg's own
 * notional - entry at 1, exit at 1 + ret - and the sale tax on the exit of a long. A short
 * sells first and buys back: the same two fees, no sale tax on the buy-back.
 */
function net(pos, ret, asset) {
  if (pos === 0) return 0;
  let cost = Math.abs(pos) * asset.fee * (2 + ret);
  if (pos > 0) cost += pos * asset.tax * (1 + ret);
  return pos * ret - cost;
}

/* ============================ the window ============================ */

const nextMidnight = (t) => (Math.floor(t / DAY) + 1) * DAY;

/**
 * The bars a verdict is judged on, or null while they do not exist yet. Bars are
 * { t: epoch seconds of the open, o, c } and o/c may be null for a bar the source listed
 * without a price. For an asset that trades every day the entry bar's time is known in
 * advance, so a day the feed dropped entirely shows up as a hole - but only once a later bar
 * proves the feed has moved past it.
 */
function windowFor(bars, committedAt, asset, now) {
  const after = bars.filter((b) => b.t > committedAt).sort((a, b) => a.t - b.t);
  if (!after.length) return null;
  if (asset.kind === 'crypto' && after[0].t !== nextMidnight(committedAt)) {
    const hole = { t: nextMidnight(committedAt), o: null, c: null };
    return { entry: hole, exit: hole, gap: true };
  }
  if (after.length <= asset.exitOffset) return null;
  const entry = after[0];
  const exit = after[asset.exitOffset];
  if (exit.t + DAY > now) return null;
  return { entry, exit, gap: entry.o == null || exit.c == null };
}

/* ============================ baselines ============================ */

/** A fair five-sided coin, reproducible from (asset, day) alone, on the site's tested PRNG. */
function coinRating(assetKey, tradeDate) {
  const r = seededRandom(`coin|${assetKey}|${tradeDate}`)();
  return RATINGS[Math.min(RATINGS.length - 1, Math.floor(r * RATINGS.length))];
}

/**
 * Every verdict for one asset, sorted into what could be scored and why the rest could not.
 * Verdicts are the bundle's rows: { asset, trade_date, committed_at, status, rating }.
 */
function scoreAsset(verdicts, bars, asset, now) {
  const counts = { scored: 0, pending: 0, gap: 0, review: 0, skipped_budget: 0, failed: 0 };
  const rows = [];
  const mine = verdicts.filter((v) => v.asset === asset.key)
    .sort((a, b) => (a.trade_date < b.trade_date ? -1 : 1));
  for (const v of mine) {
    if (v.status !== 'ok') {
      if (Object.prototype.hasOwnProperty.call(counts, v.status)) counts[v.status]++;
      continue;
    }
    const pos = position(v.rating, asset);
    if (pos === null) { counts.review++; continue; }
    const w = windowFor(bars, Date.parse(v.committed_at) / 1000, asset, now);
    if (!w) { counts.pending++; continue; }
    if (w.gap) { counts.gap++; continue; }
    const ret = w.exit.c / w.entry.o - 1;
    const coinPos = position(coinRating(asset.key, v.trade_date), asset) || 0;
    counts.scored++;
    rows.push({ trade_date: v.trade_date, rating: v.rating, position: pos, ret,
                council: net(pos, ret, asset), alwaysBuy: net(1, ret, asset),
                coin: net(coinPos, ret, asset) });
  }
  return { rows, counts };
}

/* ============================ is it better than chance? ============================ */

/**
 * Null hypothesis: the Council's positions have nothing to do with what followed them.
 * Shuffle the positions across the windows it was scored on, recompute the mean net return,
 * and count how often a shuffle does at least as well. One-sided, because the claim on trial is
 * "beats chance". (k + 1) / (rounds + 1), so p is never exactly zero.
 */
function permutationP(rows, asset, seed, rounds = PERMUTATIONS) {
  const rets = rows.map((r) => r.ret);
  const meanNet = (ps) => ps.reduce((s, p, i) => s + net(p, rets[i], asset), 0) / ps.length;
  const observed = meanNet(rows.map((r) => r.position));
  const shuffled = rows.map((r) => r.position);
  const rand = seededRandom(seed);
  let k = 0;
  for (let round = 0; round < rounds; round++) {
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(rand() * (i + 1));
      const tmp = shuffled[i]; shuffled[i] = shuffled[j]; shuffled[j] = tmp;
    }
    // The tolerance only absorbs float noise from summing the same values in another order.
    if (meanNet(shuffled) >= observed - 1e-12) k++;
  }
  return (k + 1) / (rounds + 1);
}

function stats(values, positions) {
  const traded = values.filter((_, i) => positions[i] !== 0);
  return {
    mean: values.length ? values.reduce((a, b) => a + b, 0) / values.length : null,
    sum: values.reduce((a, b) => a + b, 0),
    hitRate: traded.length ? traded.filter((v) => v > 0).length / traded.length : null,
  };
}

/** The Council next to always-Buy and the coin, plus p once there is enough to say anything. */
function summarize(rows, asset, seed) {
  const coinPos = rows.map((r) => position(coinRating(asset.key, r.trade_date), asset) || 0);
  return {
    n: rows.length,
    council: stats(rows.map((r) => r.council), rows.map((r) => r.position)),
    alwaysBuy: stats(rows.map((r) => r.alwaysBuy), rows.map(() => 1)),
    coin: stats(rows.map((r) => r.coin), coinPos),
    p: rows.length >= MIN_SCORED_FOR_P ? permutationP(rows, asset, seed) : null,
  };
}

/* ============================ does it get better? ============================ */

/**
 * Ticket 09: the Council remembers its past verdicts and how they turned out. Whether that
 * makes it any better is the question the Brazil study answered for people - no evidence they
 * improve. Rows are scoreAsset's, in trade-date order. The edge is the Council net of always-Buy
 * on the same window, so a market that rose later does not pass for a Council that learned.
 * The middle row of an odd count is dropped, so both halves are the same size.
 */
function trend(rows) {
  if (rows.length < MIN_SCORED_FOR_TREND) return null;
  const half = Math.floor(rows.length / 2);
  const edge = (xs) => xs.reduce((s, r) => s + r.council - r.alwaysBuy, 0) / xs.length;
  return { half, early: edge(rows.slice(0, half)), late: edge(rows.slice(rows.length - half)) };
}

/* ============================ parsers ============================ */

/**
 * VNDIRECT daily bars, as the session open in Vietnam (09:00 = 02:00 UTC). The ADJUSTED open
 * and close, on purpose: FPT on 2026-09-18 traded 74.5 -> 71.7 and the next session opened at
 * 66.5 - a corporate action, not a crash. A holder across it received new shares, so the
 * traded series would book a loss they never had. The adjusted series is their P&L.
 */
function parseVndirect(payload) {
  const rows = payload && payload.data;
  if (!Array.isArray(rows)) throw new Error('VNDIRECT: không có data');
  return rows.map((r) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(r && r.date);
    if (!m) throw new Error('VNDIRECT: ngày không hợp lệ');
    const o = r.adOpen == null ? null : Number(r.adOpen);
    const c = r.adClose == null ? null : Number(r.adClose);
    if ((o !== null && !(o > 0)) || (c !== null && !(c > 0))) {
      throw new Error('VNDIRECT: giá không hợp lệ');
    }
    if (o === null && c === null && !('adOpen' in r)) throw new Error('VNDIRECT: thiếu giá');
    return { t: Date.UTC(+m[1], +m[2] - 1, +m[3], 2, 0, 0) / 1000, o, c };
  }).sort((a, b) => a.t - b.t);
}

/** Binance daily klines through the trader page's own tested parser. Called only at fetch time,
    long after trader.js has loaded, so the load order of the two files does not matter. */
function parseBinanceDaily(rows) {
  return window.TienTriVuTruTrader.parseKlines(rows).map((b) => ({ t: b.t, o: b.o, c: b.c }));
}

async function fetchBars(asset, since) {
  const src = SOURCES[asset.source];
  const res = await fetch(src.url(asset, since), { cache: 'no-store' });
  if (!res.ok) throw new Error('HTTP ' + res.status);
  const body = await res.json();
  return asset.source === 'binance' ? parseBinanceDaily(body) : parseVndirect(body);
}

/* ============================ the page ============================ */

const { el, tw } = window.TienTriVuTruDom || {};

const pctAt = (x, d) => (x * 100).toLocaleString('vi-VN', { minimumFractionDigits: d,
                                                            maximumFractionDigits: d }) + '%';
const signed = (x, d) => (x >= 0 ? '+' : '−') + pctAt(Math.abs(x), d);
const usd = (x) => '$' + x.toLocaleString('vi-VN', { minimumFractionDigits: 2,
                                                      maximumFractionDigits: 2 });

const STATUS_WORDS = {
  review: 'đọc không ra bậc (REVIEW)',
  skipped_budget: 'không họp — hết ngân sách tháng',
  failed: 'phiên họp hỏng',
};

/** The AI label every provider researched requires or recommends - in DeepSeek's words, the
    strictest of them: generated by AI, may contain errors or omissions, for reference only. */
const AI_LABEL = 'Bậc do AI tạo, có thể sai hoặc thiếu sót, chỉ để tham khảo — không phải '
  + 'khuyến nghị mua bán.';

/** Stage 02, loud. Thầy only introduces them; the Council is not thầy and does not speak as him. */
function stage(mark) {
  const section = window.TienTriVuTruDom.stage(mark, tw('1f3b2', '🎲') + ' Hội đồng',
    'Mười hai cái máy họp xong mới phán. Thầy chỉ dẫn vào.');
  section.id = 'stage-hoi-dong';
  const block = el('div', 'block block--torn');
  const row = el('div', 'thay-row');
  row.innerHTML = window.TienTriVuTruThay.still('point')
    + '<div>'
    + '<p class="thay__say">Thầy mời hội đồng mười hai người vào họp. Bốn người đọc số, hai '
    + 'người cãi nhau, một người chốt, ba người lo rủi ro, một người duyệt.</p>'
    + '<p class="thay__say">Hội đồng phán, không phải thầy. Đúng là hội đồng giỏi, sai thì '
    + 'hội đồng chịu.</p>'
    + '</div>';
  block.appendChild(row);
  const body = el('div', 'hoi-dong__body');
  body.appendChild(el('p', 'note', 'Hội đồng đang vào chỗ ngồi…'));
  block.appendChild(body);
  section.appendChild(block);
  return section;
}

/** The block that goes inside SỰ THẬT, silent. */
function truthBlock() {
  const box = el('div', 'block');
  box.id = 'hoi-dong-cham';
  box.appendChild(el('h3', 'block__head', 'Hội đồng bị chấm'));
  box.appendChild(el('p', 'note', 'Đang lấy giá để chấm…'));
  return box;
}

function latestOf(verdicts, key) {
  const mine = verdicts.filter((v) => v.asset === key);
  return mine.length ? mine.reduce((a, b) => (a.trade_date >= b.trade_date ? a : b)) : null;
}

/** On a project with no billing there is nothing to charge: past the limit the provider
    refuses, it does not bill. Google's free tier also says its input is "used to improve our
    products" - true here too, and harmless only because all that goes in is public prices. */
function freeLine(provider) {
  const google = provider === 'google';
  return 'Hội đồng chạy trên gói miễn phí' + (google ? ' của Gemini API' : '') + ': không tốn '
    + 'đồng nào, và vượt giới hạn thì nhà cung cấp chặn chứ không tính tiền.'
    + (google ? ' Đổi lại, Google được dùng dữ liệu gửi lên để cải thiện sản phẩm của họ — ở đây '
      + 'chỉ có dữ liệu thị trường công khai.' : '');
}

function fillStage(body, council) {
  body.innerHTML = '';
  if (!council.verdicts.length) {
    body.appendChild(el('p', 'note', 'Hội đồng chưa họp phiên nào. Khi họp, bậc của từng mã '
      + 'sẽ hiện ở đây, và bảng điểm ở chặng dưới.'));
  } else {
    const grid = el('div', 'facts');
    for (const asset of Object.values(ASSETS)) {
      const v = latestOf(council.verdicts, asset.key);
      const cell = el('div', 'fact');
      cell.appendChild(el('div', 'fact__k', asset.label + (v ? ' · ' + v.trade_date : '')));
      cell.appendChild(el('div', 'fact__v',
        !v ? 'chưa họp' : v.status === 'ok' ? v.rating : STATUS_WORDS[v.status] || v.status));
      grid.appendChild(cell);
    }
    body.appendChild(grid);
  }
  body.appendChild(el('p', 'note', AI_LABEL));
  const remembers = memoryLine(council.verdicts);
  if (remembers) body.appendChild(el('p', 'note', remembers));
  body.appendChild(el('p', 'note',
    'Hội đồng là <a href="https://github.com/TauricResearch/TradingAgents" target="_blank" '
    + 'rel="noopener">TradingAgents</a> (Apache-2.0), chạy nguyên bản ở commit '
    + '<code>' + council.upstream.split('@')[1].slice(0, 7) + '</code>. Để ra bậc, nó tự đọc '
    + 'dữ liệu Yahoo Finance bằng máy — điều khoản của Yahoo không cho phép việc đó, và trang '
    + 'này nói thẳng ra thay vì giấu. Không một con số nào Hội đồng đọc được đưa lên đây: chỉ có '
    + 'bậc, và giờ nó được ghi.'));
  if (!council.month) return;
  if (council.billing === 'free') {
    body.appendChild(el('p', 'note', freeLine(council.provider)));
    return;
  }
  const spent = 'Tháng ' + council.month + ' Hội đồng đã đốt ' + usd(council.spent_usd)
    + (council.cap_usd != null ? ' của trần ' + usd(council.cap_usd) : '') + '.';
  body.appendChild(el('p', council.stopped ? 'note err' : 'note',
    spent + (council.stopped ? ' Nó đã dừng họp vì chạm trần — ngày dừng vẫn được ghi.' : '')));
}

function scoreTable(summary) {
  const table = el('table', 'stack-sm stack-sm--matrix');
  const head = el('thead');
  const hr = el('tr');
  for (const h of ['', 'Lợi suất ròng TB / lệnh', 'Cộng dồn', 'Tỉ lệ lệnh thắng']) {
    hr.appendChild(el('th', null, h));
  }
  head.appendChild(hr);
  table.appendChild(head);
  const tbody = el('tbody');
  const rows = [['Hội đồng', summary.council], ['Luôn Buy', summary.alwaysBuy],
                ['Tung đồng xu', summary.coin]];
  for (const [who, s] of rows) {
    const tr = el('tr');
    tr.appendChild(el('td', null, who));
    for (const [label, text] of [
      ['Lợi suất ròng TB / lệnh', s.mean == null ? '—' : signed(s.mean, 3)],
      ['Cộng dồn', signed(s.sum, 2)],
      ['Tỉ lệ lệnh thắng', s.hitRate == null ? '—' : pctAt(s.hitRate, 0)],
    ]) {
      const td = el('td', 'fact__v--num', text);
      td.setAttribute('data-label', label);
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  return table;
}

/** Two numbers and no verdict on them: nothing here tests whether the gap is more than luck. */
function trendLine(t, n) {
  const q = 'Có khá lên theo thời gian không? ';
  if (!t) {
    return q + 'Chưa đủ ' + MIN_SCORED_FOR_TREND + ' phán quyết đã chấm để so nửa đầu với nửa '
      + 'sau — mới có ' + n + '.';
  }
  return q + t.half + ' lệnh đầu hơn Luôn Buy ' + signed(t.early, 3) + ' mỗi lệnh; '
    + t.half + ' lệnh gần nhất ' + signed(t.late, 3) + '. Chưa kiểm định gì: đó chỉ là hai '
    + 'con số. Với người thật, nghiên cứu Brazil trên trang này không tìm thấy bằng chứng nào '
    + 'cho thấy họ khá lên.';
}

/** Since when the Council has read its own past verdicts before sitting, if it ever has. */
function memoryLine(verdicts) {
  const since = verdicts.filter((v) => v.memory).map((v) => v.trade_date).sort()[0];
  if (!since) return null;
  return 'Từ phiên ' + since + ', trước mỗi phiên Hội đồng đọc lại các phán quyết cũ của chính '
    + 'nó và chúng đã lời lỗ ra sao — trí nhớ có sẵn của TradingAgents. Trí nhớ đó không nằm '
    + 'trong repo: nó là văn xuôi của model và lợi suất tính từ giá Yahoo, không thứ nào được '
    + 'phép đăng lại.';
}

function countsLine(c) {
  const parts = [c.scored + ' đã chấm'];
  if (c.pending) parts.push(c.pending + ' đang chờ cửa sổ đóng');
  if (c.gap) parts.push(c.gap + ' rơi vào lỗ dữ liệu, không chấm');
  if (c.review) parts.push(c.review + ' REVIEW');
  if (c.skipped_budget) parts.push(c.skipped_budget + ' bỏ vì ngân sách');
  if (c.failed) parts.push(c.failed + ' phiên hỏng');
  return parts.join(' · ');
}

async function fillTruth(box, council, now) {
  box.querySelectorAll('.note').forEach((n) => n.remove());
  if (!council.verdicts.length) {
    box.appendChild(el('p', 'note', 'Chưa có phán quyết nào để chấm.'));
    return;
  }
  for (const asset of Object.values(ASSETS)) {
    const mine = council.verdicts.filter((v) => v.asset === asset.key);
    if (!mine.length) continue;
    box.appendChild(el('h3', 'block__head', asset.label));
    const since = mine.map((v) => v.trade_date).sort()[0];
    let bars;
    try {
      bars = await fetchBars(asset, since);
    } catch (e) {
      box.appendChild(el('p', 'err', 'Không lấy được giá ' + asset.label + ' từ '
        + SOURCES[asset.source].label + ' — ' + ((e && e.message) || 'không rõ lý do')
        + '. Phán quyết vẫn được ghi; chỉ là lúc này không chấm được.'));
      continue;
    }
    const { rows, counts } = scoreAsset(council.verdicts, bars, asset, now);
    if (rows.length) {
      const s = summarize(rows, asset, 'hoi-dong|' + asset.key + '|' + rows.length);
      box.appendChild(scoreTable(s));
      box.appendChild(el('p', 'note', s.p == null
        ? 'Chưa đủ ' + MIN_SCORED_FOR_P + ' phán quyết đã chấm để kết luận gì — mới có '
          + s.n + '. Vài lệnh thắng liền nhau là chuyện đồng xu cũng làm được.'
        : 'p = ' + s.p.toLocaleString('vi-VN', { maximumFractionDigits: 3 })
          + ' (hoán vị ' + PERMUTATIONS.toLocaleString('vi-VN') + ' lần): xác suất một hội đồng '
          + 'phán bừa mà vẫn đạt được mức này hoặc hơn.'));
      box.appendChild(el('p', 'note', trendLine(trend(rows), rows.length)));
    }
    box.appendChild(el('p', 'note', countsLine(counts)));
  }
  box.appendChild(el('p', 'note src',
    'Giá: <a href="' + SOURCES.binance.site + '" target="_blank" rel="noopener">Binance</a> '
    + '(nến ngày) · <a href="' + SOURCES.vndirect.site + '" target="_blank" rel="noopener">'
    + 'VNDIRECT</a> (giá điều chỉnh theo quyền), lấy ngay trong trình duyệt này và không lưu lại. '
    + 'Phí mỗi chiều: BTC 0,10% · cổ phiếu 0,15% + thuế bán 0,1%. Chưa tính spread. Cửa sổ mở '
    + 'ở nến đầu tiên sau giờ ghi phán quyết: BTC giữ một nến ngày, cổ phiếu ra ở phiên T+2. '
    + 'Mã Việt Nam không bán khống được, nên bậc bán của chúng là đứng ngoài.'));
}

/** Fill both blocks. Each degrades on its own: a dead price source only blanks its asset. */
async function load(stageEl, truthEl) {
  const body = stageEl.querySelector('.hoi-dong__body');
  let council;
  try {
    const res = await fetch('./data.json', { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    council = (await res.json()).council || NOT_YET;
    if (!Array.isArray(council.verdicts)) throw new Error('sổ của Hội đồng không đúng dạng');
  } catch (e) {
    const msg = 'Không đọc được sổ của Hội đồng — ' + ((e && e.message) || 'không rõ lý do') + '.';
    body.innerHTML = '';
    body.appendChild(el('p', 'err', msg));
    truthEl.querySelectorAll('.note').forEach((n) => n.remove());
    truthEl.appendChild(el('p', 'err', msg));
    return;
  }
  fillStage(body, council);
  await fillTruth(truthEl, council, Date.now() / 1000);
}

window.TienTriVuTruHoiDong = {
  RATINGS, POSITION, MIN_SCORED_FOR_P, MIN_SCORED_FOR_TREND, PERMUTATIONS, ASSETS, UPSTREAM,
  position, net, windowFor, coinRating, scoreAsset, permutationP, summarize, trend,
  parseVndirect, parseBinanceDaily,
  freeLine, stage, truthBlock, load,
};
})();
