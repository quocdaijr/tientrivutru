/*
 * Renders the five stages. A fortune-telling session is an ordered thing, so the
 * page is too: KHAI -> TƯỚNG -> PHÁN -> SỔ NỢ -> SỰ THẬT.
 *
 * Stage 4 is deliberately written in a different voice from stages 0-3. The joke
 * only works if the statistics stay cold while the fortune-teller shouts.
 */
'use strict';

const P = window.TienTriVuTruPersonal;
const T = window.TienTriVuTruTheme;
const THAY = window.TienTriVuTruThay;

const {
  tw, vnd, billionsNum, billions, pct, pad, el, stage, observeReveals, observeFlips,
} = window.TienTriVuTruDom;

/**
 * What the fortune-teller says about a real hit count. The number drives the line, so
 * the joke can never contradict the data — and line 3 quotes the actual prize maths.
 */
const HIT_LINES = {
  0: 'Mong Tôn Hoa Sen thấy.',
  1: 'Một số. Thầy gọi đó là khởi đầu.',
  2: 'Hai số. Đại đại đi.',
  3: 'Ba số — giải ba! Được 30 nghìn trên 9,24 triệu đã đốt.',
  4: 'Bốn số. Thầy đã nói rồi mà!',
  5: 'Năm số. Thầy cũng sốc.',
  6: 'Sáu số. Con còn ngồi đây đọc cái này làm gì nữa?',
};
const hitLine = (h) => HIT_LINES[Math.min(h, 6)] ?? HIT_LINES[0];

const GENDERS = [['', 'không muốn nói'], ['nam', 'Nam'], ['nữ', 'Nữ']];
const CAN_PHUOC_ROI = -0.8;

/**
 * Six numbers, for the ticket most people actually buy.
 *
 * "Cách chơi: Cơ bản" in the Vietlott app is one row of six at 10,000d. Bao 12 is a real
 * product - Vietlott sells eleven bao sizes - but the page was handing over twelve numbers
 * for a six-number slip and leaving the reader to guess which six, which is not an answer.
 *
 * The split is the honest part. A typical field boosts three of the twelve and leaves the
 * other nine at exactly the same weight, so only the first `basic_reasoned` of these six
 * were chosen for a reason; the rest come out of a tie. Saying so is the point - a page
 * that presented all six as conviction would be inventing a ranking that does not exist.
 */
function basicPick(p) {
  if (!p.basic_pick || !p.basic_pick.length) return null;

  const block = el('div', 'basic');
  block.appendChild(el('p', 'basic__head', 'Chỉ mua một vé Cơ bản? Sáu số này.'));
  block.appendChild(ballRow(p.basic_pick, null));

  const reasoned = p.basic_reasoned || 0;
  const rest = p.basic_pick.length - reasoned;
  const ordered = (p.ranked || []).slice(0, p.basic_pick.length);
  const withReason = ordered.slice(0, reasoned).map(pad).join(' ');

  let text;
  if (reasoned === 0) {
    text = 'Kỳ này không số nào có lý do riêng. Cả sáu thầy bốc — thầy nói thẳng.';
  } else if (rest === 0) {
    text = 'Cả sáu số đều có lý do riêng. Hiếm lắm.';
  } else {
    text = `Có lý do riêng: <b>${withReason}</b>. `
      + `${rest} số còn lại cùng một mức, thầy bốc cho đủ sáu — thầy nói thẳng.`;
  }
  block.appendChild(el('p', 'basic__note', text));
  block.appendChild(el('p', 'note',
    `Vé Cơ bản = 6 số = <b>${vnd(10000)}</b>. Bao 12 ở trên = 924 tổ hợp = `
    + `<b>${vnd(9240000)}</b>. Cùng một bộ số, hai cách mua.`));
  return block;
}

/**
 * The jackpot, and the two numbers that stop it reading like an advert.
 *
 * This replaced a seven-row payout table. The table was correct and is still in
 * data.json, but for a joke about a jackpot a ledger of small prizes is noise, and it
 * buried the one figure anybody came for.
 *
 * What could not go: a pot with only its odds beside it is precisely how a lottery
 * markets itself. So the block keeps the counterweight - how often the wheel pays nothing
 * at all, and how rarely it clears its own stake - and it keeps the take-home rather than
 * the announced figure, because the announced figure is not what a winner receives.
 */
function jackpotFocus(game) {
  const p = game.prizes;
  const s = game.payout_summary;
  if (!p || !s) return null;

  const block = el('div', 'pot');
  const net = p.top_jackpot_take_home_vnd || p.top_jackpot_vnd;

  /* Three states, and the wording has to differ. The pot rolls over when nobody won, so
     the next draw's is that plus new ticket sales - "ít nhất" is the only true word. If
     somebody won, it has reset and this figure describes a pot that is gone. And if the
     prize fetch failed, the figure belongs to an older draw and must say so rather than
     pass itself off as current. */
  const label = !p.matches_latest_draw
    ? `Kỳ #${p.draw_id} về tay` : p.rolled_over
    ? 'Trúng cả 6 thì về tay ít nhất' : `Kỳ #${p.draw_id} có người lấy rồi — về tay`;
  block.appendChild(el('p', 'pot__label', label));
  /* Digits and unit are separate elements so only the digits have to fit on one line.
     "108,13 tỷ" broke across two lines at 280px as one string - and a 108 billion pot has
     actually happened, it is in Vietlott's own winners table. Six digits fit; nine
     characters did not. */
  block.appendChild(el('p', 'pot__figure',
    `<span class="pot__num">${billionsNum(net)}</span><span class="pot__unit">tỷ</span>`));
  block.appendChild(el('p', 'pot__sub',
    `công bố ${billions(p.top_jackpot_vnd)}, thuế giữ lại `
    + `${billions(p.top_jackpot_tax_vnd || 0)}`
    + (p.matches_latest_draw
        ? ` · kỳ #${p.draw_id}`
        : ` · kỳ #${p.latest_draw_id} thầy chưa đọc được`)));

  const facts = el('dl', 'pot__facts');
  const rows = [
    ['bao 12 mỗi kỳ', vnd(game.wheel.cost_vnd)],
    ['trúng cả 6', s.jackpot_one_in ? `1 phần ${s.jackpot_one_in.toLocaleString('vi-VN')}` : '—'],
    ['không được gì', pct(s.nothing_probability) + ' số kỳ'],
    ['có lãi', s.profit_one_in ? `1 phần ${s.profit_one_in.toLocaleString('vi-VN')} kỳ` : '—'],
  ];
  facts.innerHTML = rows.map(([k, v]) =>
    `<dt>${k}</dt><dd class="num">${v}</dd>`).join('');
  block.appendChild(facts);
  return block;
}

/** C(pool, pick), computed rather than shipped, so it cannot disagree with the game spec. */
function totalCombos(game) {
  let n = 1;
  for (let i = 0; i < game.pick; i++) n = n * (game.pool - i) / (i + 1);
  return Math.round(n);
}
function ballRow(numbers, bonus) {
  const box = el('div', 'balls');
  (numbers || []).forEach((n, i) => {
    const ball = el('div', 'ball ball--pick ball--in', pad(n));
    ball.style.animationDelay = i * 40 + 'ms';
    box.appendChild(ball);
  });
  if (bonus != null) box.appendChild(el('div', 'ball ball--bonus', pad(bonus)));
  return box;
}

function sermonList(numbers, sermon) {
  const list = el('ul', 'sermon');
  numbers.forEach((n) => {
    const line = sermon[n] ?? sermon[String(n)];
    if (line) list.appendChild(el('li', null, `<b>${pad(n)}</b> — ${line}`));
  });
  return list;
}

/* ============================ 00 · KHAI ============================ */

function stageKhai(data, onSubmit) {
  const section = stage('00', `${tw('1fa84','🪄')} Khai báo`, 'Thầy cần ngày sinh. Chỉ ngày sinh thôi.');
  const block = el('div', 'block');
  const profile = P.loadProfile();

  block.appendChild(el('div', 'privacy', `<b>🔒 Riêng tư:</b> ${data.privacy}`));

  const form = el('form', 'khai');
  form.innerHTML = `
    <label>Ngày sinh (bắt buộc)
      <input type="date" name="birthDate" required min="1930-01-01" max="2035-12-31"
             value="${profile?.birthDate ?? ''}"></label>
    <label>Họ tên (tuỳ chọn — để tính số tên)
      <input type="text" name="name" placeholder="bỏ trống cũng được"
             value="${profile?.name ? profile.name.replace(/"/g, '&quot;') : ''}"></label>
    <label>Giới tính (tuỳ chọn — để tính sao chiếu mệnh)
      <select name="gender">${GENDERS.map(([v, t]) =>
        `<option value="${v}"${(profile?.gender ?? '') === v ? ' selected' : ''}>${t}</option>`
      ).join('')}</select></label>
    <button class="btn" type="submit">Thầy xem cho</button>
    <button class="btn btn--ghost" type="button" data-forget>Xoá sạch</button>`;
  block.appendChild(form);

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const fd = new FormData(form);
    const birthDate = fd.get('birthDate');
    if (!birthDate) return;
    P.saveProfile({
      birthDate,
      name: (fd.get('name') || '').trim(),
      gender: fd.get('gender') || null,
    });
    onSubmit();
  });
  form.querySelector('[data-forget]').addEventListener('click', () => {
    P.clearAll();
    onSubmit();
  });

  if (!profile?.birthDate) {
    block.appendChild(el('p', 'hand',
      'Con điền ngày sinh vào đây. Thầy không hỏi số điện thoại — hỏi làm gì, thầy có bán số đâu.'));
  }
  section.appendChild(block);
  return section;
}

/* ============================ 01 · TƯỚNG ============================ */

function stageTuong(fortune, error) {
  const section = stage('01', `${tw('262f','☯')} Xem tướng`, 'Lá số dựng từ ngày sinh, tính ngay trong máy con.');
  const block = el('div', 'block');

  if (error) {
    block.appendChild(el('p', 'err', error));
    section.appendChild(block);
    return section;
  }
  if (!fortune) {
    block.appendChild(el('p', 'hand', 'Thầy không phải thần. Thầy cần ngày sinh — con quay lên trên đi.'));
    section.appendChild(block);
    return section;
  }

  const facts = [
    ['Năm âm lịch', `${fortune.canChi} (${fortune.lunarYear})`],
    ['Con giáp', fortune.animal],
    ['Mệnh', `${fortune.napAm} — ${fortune.element}`],
    ['Cung hoàng đạo', fortune.westernSign],
    ['Số chủ đạo', fortune.lifePath],
  ];
  if (fortune.nameNumber) facts.push(['Số tên', fortune.nameNumber]);
  if (fortune.guardianStar) facts.push(['Sao chiếu mệnh', fortune.guardianStar]);
  if (fortune.tamHop.length) facts.push(['Tam hợp', fortune.tamHop.join(', ')]);
  if (fortune.tuHanhXung.length) facts.push(['Tứ hành xung', fortune.tuHanhXung.join(', ')]);

  const grid = el('div', 'facts');
  facts.forEach(([k, v]) => grid.appendChild(
    el('div', 'fact', `<div class="fact__k">${k}</div><div class="fact__v">${v}</div>`)));
  block.appendChild(grid);
  block.appendChild(el('p', 'note',
    'Can chi, nạp âm và ngày Tết lấy từ bảng tra do Python sinh sẵn — trình duyệt không tự '
    + 'tính lại thuật toán âm lịch, nên hai bên không thể lệch nhau.'));
  section.appendChild(block);
  return section;
}

/* ============================ 02 · PHÁN ============================ */

function stagePhan(data, profile, fortune) {
  const section = stage('02', `${tw('1f52e','🔮')} Thầy phán`,
    'Mười hai số cho bao 12, sáu số cho vé Cơ bản. Ghi trước giờ quay, không sửa được.');

  const intro = el('div', 'thay-row');
  intro.innerHTML = THAY.flip('idle', 'blink')
    + '<p class="thay__say">Cảm ơn vũ trụ đã cho con công việc. Nhưng thầy thấy con thích '
    + 'trúng số hơn.<br>Vũ trụ ơi, cho con trúng số đi. Thầy xin hộ nó một câu.</p>';
  section.appendChild(intro);

  data.games.forEach((game) => {
    const row = el('div', 'row');

    /* --- the house oracle --- */
    const house = el('div', 'block block--torn');
    house.appendChild(el('h3', 'block__head', `${game.display} · oracle nhà cái`));
    if (game.pending_prophecy) {
      const p = game.pending_prophecy;
      house.appendChild(el('div', 'note',
        `Kỳ #${p.draw_id} · quay ${p.draw_date} lúc 18h00 · oracle v${p.oracle_version}`));
      house.appendChild(ballRow(p.numbers, null));
      house.appendChild(el('p', 'note',
        `bao 12 = ${game.wheel.combinations} tổ hợp = <b>${vnd(game.wheel.cost_vnd)}</b>`));
      const basic = basicPick(p);
      if (basic) house.appendChild(basic);
      const pot = jackpotFocus(game);
      if (pot) {
        house.appendChild(pot);
        const six = game.payout_if_hit[game.payout_if_hit.length - 1];
        if (!six.uses_live_jackpot) {
          house.appendChild(el('p', 'note',
            'Con số này theo mức sàn — kỳ này thầy chưa đọc được nồi.'));
        }
      }
      house.appendChild(sermonList(p.numbers, p.sermon));
    } else {
      house.appendChild(el('p', 'hand', 'Kỳ này thầy chưa phán. Con chờ.'));
    }
    row.appendChild(house);

    /* --- the personal oracle --- */
    const mine = el('div', 'block block--torn');
    mine.appendChild(el('h3', 'block__head', `${game.display} · số riêng của con`));
    if (!fortune) {
      mine.appendChild(el('p', 'hand', 'Chưa khai ngày sinh thì thầy lấy gì mà xem.'));
    } else if (!game.pending_prophecy) {
      mine.appendChild(el('p', 'hand', 'Chưa tới kỳ.'));
    } else {
      try {
        const pending = game.pending_prophecy;
        const pick = P.personalProphecy(profile, fortune, game, pending.draw_id, pending.draw_date);
        P.savePick(pick);
        mine.appendChild(el('div', 'note', `Kỳ #${pending.draw_id} · quay ${pending.draw_date}`));
        mine.appendChild(ballRow(pick.numbers, null));
        mine.appendChild(sermonList(pick.numbers, pick.sermon));
      } catch (e) {
        mine.appendChild(el('p', 'err', e.message));
      }
    }
    row.appendChild(mine);
    section.appendChild(row);
  });

  return section;
}

/* ============================ 03 · SỔ NỢ ============================ */

function stageSoNo(data, fortune) {
  const section = stage('03', `${tw('1f4c9','📉')} Sổ nợ`,
    'Thầy phán xong thì phải chịu chấm điểm. Tiền ở đây là tiền giấy.');

  data.games.forEach((game) => {
    const score = game.score;
    const block = el('div', 'block');
    block.appendChild(el('h3', 'block__head', game.display));

    if (!score.draws_scored) {
      block.appendChild(el('p', 'hand',
        'Chưa kỳ nào chấm được. Thầy tạm thời vô tội.'));
    } else {
      const delta = score.hits_per_draw_actual - score.hits_per_draw_expected;
      block.appendChild(el('div', 'kpi ' + (score.roi > 0 ? 'kpi--good' : 'kpi--bad'), pct(score.roi)));
      block.appendChild(el('div', 'note', 'ROI cộng dồn'));

      const table = el('table', 'stack-sm');
      table.innerHTML = `<tbody>
        <tr><th>kỳ đã chấm</th><td class="num">${score.draws_scored}</td></tr>
        <tr><th>trúng / kỳ</th><td class="num">${score.hits_per_draw_actual}</td></tr>
        <tr><th>ngẫu nhiên / kỳ</th><td class="num">${score.hits_per_draw_expected}</td></tr>
        <tr><th>chênh lệch</th><td class="num">${delta >= 0 ? '+' : ''}${delta.toFixed(3)}</td></tr>
        <tr><th>đã đốt (giấy)</th><td class="num">${vnd(score.paper_burned_vnd)}</td></tr>
        <tr><th>thắng (giấy)</th><td class="num">${vnd(score.paper_won_vnd)}</td></tr>
        <tr><th>ROI bỏ jackpot</th><td class="num">${pct(score.roi_excluding_jackpot)}</td></tr>
      </tbody>`;
      block.appendChild(table);

      /* The drawing is chosen by the real hit count, so it can never flatter the data. */
      if (score.best_draw) {
        const hits = score.best_draw.hits;
        const row = el('div', 'thay-row');
        row.innerHTML = THAY.still(THAY.poseForHits(hits))
          + `<div><p class="thay__say">Kỳ đỉnh nhất #${score.best_draw.draw_id}: `
          + `trúng ${hits}/12 số.<br>${hitLine(hits)}</p>`
          + (hits >= 5
            ? '<figure class="print"><img src="./img/dong-ho-dai-cat.webp" alt="Tranh Đông Hồ Đại Cát" '
              + 'width="240" height="329" loading="lazy">'
              + '<figcaption>“Đại Cát” — vận may lớn. Tranh Đông Hồ, public domain.</figcaption></figure>'
            : '')
          + '</div>';
        block.appendChild(row);
      }

      if (score.roi_excluding_jackpot < CAN_PHUOC_ROI) {
        block.appendChild(el('div', 'verdict-stamp', 'CẠN PHƯỚC'));
        block.appendChild(el('p', 'hand',
          `ROI bỏ jackpot ${pct(score.roi_excluding_jackpot)}. Thầy nói thật đấy, lần này không đùa.`));
      }
      if (score.jackpot_hits && score.roi > 0) {
        block.appendChild(el('div', 'disclaim',
          `ROI dương chỉ nhờ ${score.jackpot_hits} kỳ trúng jackpot. Bỏ jackpot ra còn `
          + `${pct(score.roi_excluding_jackpot)}, và tỉ lệ trúng ${score.hits_per_draw_actual} `
          + `vẫn đúng bằng mức ngẫu nhiên ${score.hits_per_draw_expected}. `
          + `Một cú may che hết phần còn lại — đó là cách mọi "hệ thống" tự lừa mình.`));
      }
    }

    /* head-to-head, only meaningful once the visitor has picks of their own */
    if (fortune) {
      const mine = P.scorePicks(P.loadPicks(),
        { key: game.key, pool: game.pool, pick: game.pick }, game.recent);
      /* Two measures across three contenders, so this one is a real matrix. It cannot
         just stack like the label/value tables: drop the header row on a narrow screen
         and each row becomes two bare numbers with nothing saying what they measure.
         Every cell carries its own column name instead, which the mobile rule reveals. */
      const versus = el('table', 'stack-sm stack-sm--matrix');
      const KY = 'kỳ đã chấm', TR = 'trúng / kỳ';
      versus.innerHTML = `<thead><tr><th></th><th class="num">${KY}</th>
        <th class="num">${TR}</th></tr></thead><tbody>
        <tr><th>Số tử vi của con</th>
            <td class="num" data-label="${KY}">${mine.scored}</td>
            <td class="num" data-label="${TR}">${mine.scored ? mine.hitsPerDraw.toFixed(3) : '—'}</td></tr>
        <tr><th>Oracle nhà cái</th>
            <td class="num" data-label="${KY}">${score.draws_scored}</td>
            <td class="num" data-label="${TR}">${score.draws_scored ? score.hits_per_draw_actual : '—'}</td></tr>
        <tr><th>Ngẫu nhiên thuần</th>
            <td class="num" data-label="${KY}">∞</td>
            <td class="num" data-label="${TR}">${mine.expected.toFixed(3)}</td></tr>
      </tbody>`;
      block.appendChild(el('p', 'note', 'So kè'));
      block.appendChild(versus);
    }

    block.appendChild(el('p', 'note',
      `ROI kỳ vọng lý thuyết: ${pct(game.wheel.expected_roi)} · `
      + `bỏ jackpot: ${pct(game.wheel.expected_roi_excluding_jackpot)}`));
    section.appendChild(block);
  });

  return section;
}

/* ============================ 04 · SỰ THẬT ============================
 * From here down the fortune-teller is not allowed to speak. */

function chiSquareTable(chi, label) {
  const block = el('div', 'block');
  block.appendChild(el('h3', 'block__head', label));
  const table = el('table', 'stack-sm');
  table.innerHTML = `<tbody>
    <tr><th>lượt số quan sát</th><td class="num">${chi.observations.toLocaleString('vi-VN')}</td></tr>
    <tr><th>chi-square</th><td class="num">${chi.statistic}</td></tr>
    <tr><th>bậc tự do</th><td class="num">${chi.degrees_of_freedom}</td></tr>
    <tr><th>p-value</th><td class="num">${chi.p_value}</td></tr>
  </tbody>`;
  block.appendChild(table);
  block.appendChild(el('p', 'note', chi.verdict));
  return block;
}

/**
 * One đài, one vé, 10.000đ. The prize table pays back exactly half of what a đài takes,
 * so the theoretical ROI is −50% — not an estimate, arithmetic. It is printed next to the
 * realised figure precisely because the two will not match for a very long time: giải đặc
 * biệt is 40% of the pool and lands about once per million tickets.
 */
function veBlock(ve) {
  const block = el('div', 'block');
  block.appendChild(el('h3', 'block__head', 'Bảng Phong Thần vé số'));
  if (!ve.tickets) {
    block.appendChild(el('p', 'note', 'Chưa có vé nào được chấm.'));
    return block;
  }
  const pct = (v) => `${(v * 100).toFixed(2)}%`;
  const table = el('table', 'stack-sm');
  table.innerHTML = `<tbody>
    <tr><th>vé đã chấm</th><td class="num">${ve.tickets.toLocaleString('vi-VN')}</td></tr>
    <tr><th>vé trúng gì đó</th><td class="num">${ve.winning_tickets.toLocaleString('vi-VN')}</td></tr>
    <tr><th>tiền vé (giấy)</th><td class="num">${ve.paper_burned_vnd.toLocaleString('vi-VN')}đ</td></tr>
    <tr><th>tiền trúng (giấy)</th><td class="num">${ve.paper_won_vnd.toLocaleString('vi-VN')}đ</td></tr>
    <tr><th>ROI</th><td class="num">${pct(ve.roi)}</td></tr>
    <tr><th>ROI lý thuyết</th><td class="num">${pct(ve.theoretical_roi)}</td></tr>
    <tr><th>ROI bỏ ĐB &amp; phụ ĐB</th><td class="num">${pct(ve.roi_excluding_headline)}</td></tr>
    <tr><th>— lý thuyết</th><td class="num">${pct(ve.theoretical_roi_excluding_headline)}</td></tr>
  </tbody>`;
  block.appendChild(table);
  if (ve.best && ve.best.payout_vnd) {
    block.appendChild(el('p', 'note',
      `Vé đẹp nhất: ${ve.best.ve} · ${ve.best.display} ${ve.best.draw_date} · `
      + `ĐB ${ve.best.special} · ${ve.best.prizes} · ${ve.best.payout_vnd.toLocaleString('vi-VN')}đ`));
  }
  block.appendChild(el('p', 'note',
    'Cơ cấu giải trả về đúng 5 tỷ trên 10 tỷ doanh thu mỗi đài mỗi kỳ. '
    + 'Thầy phán hay con tự bốc thì con số vẫn thế.'));
  return block;
}

/**
 * Tappable heatmap. `title` tooltips do not exist on touch, so every cell is a button
 * that writes into a live readout — otherwise the frequency data is desktop-only.
 */
function heatmap(freq, pool, offset = 1) {
  const box = el('div');
  const matrix = pool === 100; // 00..99 is a natural 10x10 grid, easier to read than auto-fill
  const wrap = el('div', 'heat ' + (matrix ? 'heat--matrix' : 'heat--pool'));
  wrap.setAttribute('role', 'group');
  wrap.setAttribute('aria-label', 'Tần suất từng số, bấm để xem');

  const values = Object.values(freq).map(Number);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const readout = el('p', 'heat__readout', 'Bấm một số để xem tần suất.');
  readout.setAttribute('role', 'status');
  readout.setAttribute('aria-live', 'polite');

  for (let i = 0; i < pool; i++) {
    const n = i + offset;
    const count = Number(freq[String(n)] ?? freq[pad(n)] ?? 0);
    // Deliberately gentle: a strong gradient would imply the spread means something.
    const t = hi === lo ? 0.5 : (count - lo) / (hi - lo);
    const cell = el('button', 'cell', pad(n));
    cell.type = 'button';
    /* The heat used to be the cell's own opacity, which faded the LABEL along with it -
       the coldest number measured 2.78:1 on veso, well under AA, and no contrast check
       caught it because opacity never touches the computed `color`. The tint moved to the
       background; the label now always reads at full ink. Custom property rather than an
       inline background so the pressed-state rule can still win. */
    // Unitless 0..1. How far that goes is --heat-max, which is per skin because the
    // safe ceiling is: 60% on veso, 37% on thantai. CSS does the multiply, so switching
    // theme re-tints every cell with no JS involved.
    cell.style.setProperty('--heat', t.toFixed(3));
    cell.setAttribute('aria-label', `Số ${pad(n)}, ra ${count} lần`);
    cell.setAttribute('aria-pressed', 'false');
    cell.addEventListener('click', () => {
      wrap.querySelectorAll('[aria-pressed="true"]')
        .forEach((b) => b.setAttribute('aria-pressed', 'false'));
      cell.setAttribute('aria-pressed', 'true');
      readout.textContent = `Số ${pad(n)} đã ra ${count} lần.`;
    });
    wrap.appendChild(cell);
  }
  box.appendChild(wrap);
  box.appendChild(readout);
  return box;
}

function stageSuThat(data) {
  const section = stage('04', `${tw('1f4ca','📊')} Sự thật`,
    'Phần này thầy không được nói. Đây là số liệu, và số liệu không nể ai.');

  data.games.forEach((game) => {
    const row = el('div', 'row');
    if (game.chi_square) {
      row.appendChild(chiSquareTable(game.chi_square, `${game.display} · ${game.draw_count} kỳ`));
    }
    const heat = el('div', 'block');
    heat.appendChild(el('h3', 'block__head', `Tần suất · ${game.display}`));
    heat.appendChild(heatmap(game.frequency, game.pool));
    heat.appendChild(el('p', 'note',
      'Đậm hơn = ra nhiều hơn. Trông như có quy luật, nhưng chi-square bên cạnh nói đó là nhiễu thuần.'));
    row.appendChild(heat);
    section.appendChild(row);

    const recent = el('div', 'block');
    recent.appendChild(el('h3', 'block__head', `Các kỳ gần đây · ${game.display}`));
    const scroll = el('div', 'scroll');
    const table = el('table');
    table.innerHTML = '<thead><tr><th>kỳ</th><th>ngày</th><th>số</th>'
      + (game.has_bonus ? '<th>phụ</th>' : '') + '<th>nguồn</th></tr></thead>';
    const body = el('tbody');
    [...game.recent].reverse().forEach((d) => {
      body.innerHTML += `<tr><td>#${d.draw_id}</td><td>${d.date}</td>`
        + `<td>${d.main.map(pad).join(' ')}</td>`
        + (game.has_bonus ? `<td>${d.bonus != null ? pad(d.bonus) : '—'}</td>` : '')
        + `<td>${d.source}</td></tr>`;
    });
    table.appendChild(body);
    scroll.appendChild(table);
    recent.appendChild(scroll);
    section.appendChild(recent);
  });

  // Xổ số kiến thiết: three regions, same 00–99 tail space, same 10×10 heatmap the
  // Miền Bắc block used to have to itself.
  (data.kienthiet || []).forEach((k) => {
    const row = el('div', 'row');
    row.appendChild(chiSquareTable(k.chi_square,
      `${k.display} · ${k.draw_count.toLocaleString('vi-VN')} bảng · ${k.provinces} đài · ${k.first_date} → ${k.last_date}`));
    // block--heat, not plain block: a 10x10 grid needs its width stated, or a third block
    // in the row squeezes the cells past the point where they overlap each other.
    const heat = el('div', 'block block--heat');
    heat.appendChild(el('h3', 'block__head', 'Tần suất 00–99 (hai số cuối mỗi giải)'));
    heat.appendChild(heatmap(k.frequency, 100, 0));
    heat.appendChild(el('p', 'note',
      `${k.chi_square.observations.toLocaleString('vi-VN')} lượt số. Vẫn đều tăm tắp.`));
    row.appendChild(heat);
    if (k.ve) row.appendChild(veBlock(k.ve));
    section.appendChild(row);
  });

  section.appendChild(el('div', 'disclaim', data.disclaimer));
  return section;
}

/* ============================ boot ============================ */

function render(data) {
  const app = document.getElementById('app');
  app.innerHTML = '';

  const profile = P.loadProfile();
  let fortune = null;
  let fortuneError = null;
  if (profile?.birthDate) {
    try {
      fortune = P.readFortune(profile, data.astrology, new Date().toISOString().slice(0, 10));
    } catch (e) {
      fortuneError = e.message;
    }
  }

  app.appendChild(stageKhai(data, () => render(data)));
  app.appendChild(stageTuong(fortune, fortuneError));
  app.appendChild(stagePhan(data, profile, fortune));
  app.appendChild(stageSoNo(data, fortune));
  app.appendChild(stageSuThat(data));

  observeReveals();
  observeFlips();
}

T.initThemeControls();

fetch('./data.json', { cache: 'no-store' })
  .then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
  .then(render)
  .catch((e) => {
    document.getElementById('app').innerHTML =
      `<div class="block"><p class="err">Không tải được <code>data.json</code> (${e.message}). `
      + 'Chạy <code>uv run tientrivutru site</code> rồi serve thư mục này.</p></div>';
  });
