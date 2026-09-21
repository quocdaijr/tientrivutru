/*
 * Oracle Tử Vi — personal prophecy, computed entirely in the browser.
 *
 * PRIVACY, and it is the whole design: the birth date, name and gender never leave
 * this device. There is no account, no server, no request carrying them anywhere.
 * They live in localStorage and can be deleted with one button.
 *
 * The browser does NOT reimplement the lunar algorithm. Every table it needs -
 * Tết dates per year, the sexagenary cycle, nạp âm, zodiac bounds, the nine stars -
 * is computed in Python and shipped inside data.json, so the two sides cannot drift.
 */
'use strict';

const STORAGE_KEY = 'tientrivutru.personal.v1';
const PICKS_KEY = 'tientrivutru.personal.picks.v1';
const WHEEL_SIZE = 12;
const MASTER_FALLBACK = 9;

/* ---------- deterministic PRNG (xmur3 + sfc32, public-domain constructions) ---------- */

function xmur3(str) {
  let h = 1779033703 ^ str.length;
  for (let i = 0; i < str.length; i++) {
    h = Math.imul(h ^ str.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return function () {
    h = Math.imul(h ^ (h >>> 16), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    h ^= h >>> 16;
    return h >>> 0;
  };
}

function sfc32(a, b, c, d) {
  return function () {
    a >>>= 0; b >>>= 0; c >>>= 0; d >>>= 0;
    let t = (a + b) | 0;
    a = b ^ (b >>> 9);
    b = (c + (c << 3)) | 0;
    c = (c << 21) | (c >>> 11);
    d = (d + 1) | 0;
    t = (t + d) | 0;
    c = (c + t) | 0;
    return (t >>> 0) / 4294967296;
  };
}

function seededRandom(seedText) {
  const h = xmur3(seedText);
  return sfc32(h(), h(), h(), h());
}

/* ---------- fortune, read from the Python-generated tables ---------- */

function stripDiacritics(text) {
  return text
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');
}

function reduceToRoot(value, masterNumbers) {
  while (value > 9) {
    if (masterNumbers.includes(value)) return value;
    value = String(value).split('').reduce((sum, ch) => sum + Number(ch), 0);
  }
  return value || MASTER_FALLBACK;
}

function digitRoot(value) {
  return reduceToRoot(Math.abs(value), []);
}

function lifePathNumber(iso, masterNumbers) {
  const digits = iso.replace(/-/g, '').split('').reduce((s, ch) => s + Number(ch), 0);
  return reduceToRoot(digits, masterNumbers);
}

function nameNumber(name, rows, masterNumbers) {
  const letters = stripDiacritics(name).toUpperCase().replace(/[^A-Z]/g, '');
  if (!letters) return null;
  let total = 0;
  for (const ch of letters) {
    for (const row of rows) {
      const at = row.indexOf(ch);
      if (at >= 0) { total += at + 1; break; }
    }
  }
  return reduceToRoot(total, masterNumbers);
}

function westernSign(iso, bounds) {
  const [, m, d] = iso.split('-').map(Number);
  for (let i = bounds.length - 1; i >= 0; i--) {
    const b = bounds[i];
    if (m > b.month || (m === b.month && d >= b.day)) return b.name;
  }
  return 'Ma Kết'; // before 20 January, still the sign that began in December
}

/**
 * The lunar year a birth date belongs to: the solar year, unless the date falls
 * before that year's Tết, in which case it belongs to the year before.
 */
function lunarYearOf(iso, table) {
  const year = Number(iso.slice(0, 4));
  const entry = table[String(year)];
  if (!entry) return null;
  return iso < entry.tet ? year - 1 : year;
}

function guardianStar(lunarYear, currentLunarYear, gender, astro) {
  if (gender !== 'nam' && gender !== 'nữ') return null;
  const list = gender === 'nam' ? astro.stars_male : astro.stars_female;
  const age = Math.max(currentLunarYear - lunarYear + 1, astro.star_base_age);
  return list[(age - astro.star_base_age) % list.length];
}

function groupMates(animal, groups) {
  for (const group of groups) {
    if (group.includes(animal)) return group.filter((x) => x !== animal);
  }
  return [];
}

function readFortune(profile, astro, todayIso) {
  const table = astro.lunar_years;
  const lunarYear = lunarYearOf(profile.birthDate, table);
  // A birth date in January before Tết belongs to the previous lunar year, so the
  // table must carry that year too. Out of range is reported, never returned as null
  // for the caller to trip over.
  if (lunarYear === null || !table[String(lunarYear)]) {
    const years = Object.keys(table).map(Number);
    throw new RangeError(
      `Ngày sinh ngoài phạm vi bảng tra (${Math.min(...years)}–${Math.max(...years)}).`
    );
  }
  const entry = table[String(lunarYear)];

  const currentLunarYear = lunarYearOf(todayIso, table) ?? Number(todayIso.slice(0, 4));

  return {
    lunarYear,
    canChi: entry.can_chi,
    animal: entry.animal,
    napAm: entry.nap_am,
    element: entry.element,
    westernSign: westernSign(profile.birthDate, astro.zodiac_bounds),
    lifePath: lifePathNumber(profile.birthDate, astro.master_numbers),
    nameNumber: profile.name ? nameNumber(profile.name, astro.pythagorean_rows, astro.master_numbers) : null,
    guardianStar: guardianStar(lunarYear, currentLunarYear, profile.gender, astro),
    tamHop: groupMates(entry.animal, astro.tam_hop),
    tuHanhXung: groupMates(entry.animal, astro.tu_hanh_xung),
  };
}

/* ---------- the personal oracle ---------- */

const ANIMAL_ORDER = ['Tý','Sửu','Dần','Mão','Thìn','Tỵ','Ngọ','Mùi','Thân','Dậu','Tuất','Hợi'];
const ELEMENT_ORDER = ['Kim','Mộc','Thủy','Hỏa','Thổ'];

const BOOST = {
  lifePath: 1.9,
  nameNumber: 1.6,
  animal: 1.7,
  element: 1.5,
  sign: 1.4,
  star: 1.5,
  tamHop: 1.35,
};
const PENALTY_XUNG = 0.55;

/**
 * Personal weights. Every rule folds a fortune value into the game's pool with a
 * modulo, so it always lands on a real number, and no weight ever reaches zero.
 */
function personalWeights(fortune, pool) {
  const weights = new Map();
  const reasons = new Map();
  for (let n = 1; n <= pool; n++) { weights.set(n, 1); reasons.set(n, []); }

  const boost = (n, factor, why) => {
    if (!weights.has(n)) return;
    weights.set(n, weights.get(n) * factor);
    reasons.get(n).push(why);
  };
  const fold = (value) => ((value % pool) + pool) % pool + 1;

  // Digit-root equality, NOT divisibility: life path 1 divides every number in the
  // pool, which would boost all of them and give every number the same sermon.
  // Master numbers reduce for this comparison, since no number 1..70 has root 11.
  const rootTarget = fortune.lifePath > 9
    ? reduceToRoot(fortune.lifePath, [])
    : fortune.lifePath;
  for (let n = 1; n <= pool; n++) {
    if (digitRoot(n) === rootTarget) {
      boost(n, BOOST.lifePath, `Số gốc ${rootTarget} — trùng số chủ đạo của con. Thầy không bịa ra được.`);
    }
  }
  if (fortune.nameNumber) {
    boost(fold(fortune.nameNumber * 7), BOOST.nameNumber,
      `Tên con ra số ${fortune.nameNumber}, nhân bảy vía thành nó.`);
  }

  const animalIndex = ANIMAL_ORDER.indexOf(fortune.animal);
  if (animalIndex >= 0) {
    boost(fold(animalIndex * 5), BOOST.animal, `Tuổi ${fortune.animal} đứng thứ ${animalIndex + 1} trong mười hai con giáp. Số này của con.`);
    for (const mate of fortune.tamHop) {
      const mateIndex = ANIMAL_ORDER.indexOf(mate);
      if (mateIndex >= 0) boost(fold(mateIndex * 5), BOOST.tamHop, `Tam hợp với tuổi ${mate}. Hợp thì cứ đánh, thầy nói vậy.`);
    }
    for (const foe of fortune.tuHanhXung) {
      const foeIndex = ANIMAL_ORDER.indexOf(foe);
      if (foeIndex >= 0) {
        const n = fold(foeIndex * 5);
        if (weights.has(n)) {
          weights.set(n, weights.get(n) * PENALTY_XUNG);
          reasons.get(n).push(`Tứ hành xung với tuổi ${foe}. Thầy để đấy, nhưng con né ra thì hơn.`);
        }
      }
    }
  }

  const elementIndex = ELEMENT_ORDER.indexOf(fortune.element);
  if (elementIndex >= 0) {
    boost(fold(elementIndex * 11 + 3), BOOST.element, `Mệnh ${fortune.napAm}. ${fortune.element} nó dẫn về số này, thầy không cãi được.`);
  }

  const signIndex = ['Bạch Dương','Kim Ngưu','Song Tử','Cự Giải','Sư Tử','Xử Nữ',
    'Thiên Bình','Bọ Cạp','Nhân Mã','Ma Kết','Bảo Bình','Song Ngư'].indexOf(fortune.westernSign);
  if (signIndex >= 0) {
    boost(fold(signIndex * 3 + 1), BOOST.sign, `Cung ${fortune.westernSign} chiếu đúng ô này. Tây với ta gặp nhau ở đây.`);
  }

  if (fortune.guardianStar) {
    boost(fold(fortune.guardianStar.length * 13), BOOST.star,
      `Năm nay sao ${fortune.guardianStar} chiếu mệnh con. Số theo sao mà ra.`);
  }

  return { weights, reasons };
}

function weightedSample(rng, weights, count) {
  const remaining = new Map(weights);
  const chosen = [];
  for (let i = 0; i < count; i++) {
    let total = 0;
    for (const w of remaining.values()) total += w;
    let target = rng() * total;
    let picked = null;
    for (const n of [...remaining.keys()].sort((x, y) => x - y)) {
      target -= remaining.get(n);
      if (target <= 0) { picked = n; break; }
    }
    if (picked === null) picked = Math.max(...remaining.keys());
    chosen.push(picked);
    remaining.delete(picked);
  }
  return chosen.sort((a, b) => a - b);
}

const GENERIC = [
  'Con đừng hỏi. Thầy nhìn lá số là biết.',
  'Số này nằm trong lá số con, thầy chỉ đọc lại.',
  'Vía con đẩy nó lên, thầy chỉ ghi.',
  'Thầy không giải thích. Giải thích là mất thiêng.',
  'Cái này là lộc của con, thầy không tranh.',
  'Con cứ ghi đi. Thầy đi ba mươi năm rồi.',
];

/**
 * The seed binds the person to a specific draw, so the numbers are stable: reload the
 * page and you get the same twelve, exactly like the house oracle.
 */
function personalProphecy(profile, fortune, game, drawId, drawDate) {
  const seedText = [
    'tientrivutru-personal-v1', game.key, drawId, drawDate,
    profile.birthDate, profile.name || '-', profile.gender || '-',
  ].join('|');
  const rng = seededRandom(seedText);
  const { weights, reasons } = personalWeights(fortune, game.pool);
  const numbers = weightedSample(rng, weights, WHEEL_SIZE);

  const sermonRng = seededRandom(seedText + '|sermon');
  const sermon = {};
  for (const n of numbers) {
    const why = reasons.get(n);
    sermon[n] = why && why.length ? why[0] : GENERIC[Math.floor(sermonRng() * GENERIC.length)];
  }
  return { numbers, sermon, drawId, drawDate, game: game.key };
}

/* ---------- storage: profile + committed picks, all local ---------- */

function loadProfile() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null'); }
  catch { return null; }
}
function saveProfile(profile) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
}
function clearAll() {
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(PICKS_KEY);
}
function loadPicks() {
  try { return JSON.parse(localStorage.getItem(PICKS_KEY) || '{}'); }
  catch { return {}; }
}
function savePick(pick) {
  const picks = loadPicks();
  const key = `${pick.game}:${pick.drawId}`;
  if (!picks[key]) {            // append-only, same rule as the house oracle
    picks[key] = { numbers: pick.numbers, drawDate: pick.drawDate };
    localStorage.setItem(PICKS_KEY, JSON.stringify(picks));
  }
  return picks[key];
}

/* ---------- personal scoreboard ---------- */

function scorePicks(picks, game, draws) {
  const byId = new Map(draws.map((d) => [d.draw_id, d]));
  const rows = [];
  for (const [key, pick] of Object.entries(picks)) {
    const [gameKey, drawId] = key.split(':');
    if (gameKey !== game.key) continue;
    const draw = byId.get(drawId);
    if (!draw) continue;        // not drawn yet -> not scorable, same as the house rule
    const hits = pick.numbers.filter((n) => draw.main.includes(n)).length;
    rows.push({ drawId, hits, drawDate: draw.date });
  }
  rows.sort((a, b) => a.drawId.localeCompare(b.drawId));
  const scored = rows.length;
  const hitsTotal = rows.reduce((s, r) => s + r.hits, 0);
  return {
    scored,
    hitsTotal,
    hitsPerDraw: scored ? hitsTotal / scored : 0,
    expected: (game.pick * WHEEL_SIZE) / game.pool,
    rows,
  };
}

window.TienTriVuTruPersonal = {
  readFortune, personalProphecy, loadProfile, saveProfile, clearAll,
  loadPicks, savePick, scorePicks, seededRandom, stripDiacritics,
  lifePathNumber, nameNumber, westernSign, lunarYearOf, digitRoot, personalWeights,
  WHEEL_SIZE,
};
