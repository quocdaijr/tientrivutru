/*
 * First-visit warning gate.
 *
 * The site hands strangers lottery numbers. Before anyone sees one, they read the
 * sentence that matters: this cannot predict anything. The acknowledgement is stored
 * locally - there is no server to record it on, and recording it is not the point.
 *
 * The point is that nobody reaches the numbers without passing the sentence.
 *
 * Each page warns about its own hazard and remembers its own acknowledgement. A visitor
 * who landed on the money page has not been told anything about lotteries, and one who
 * dismissed the lottery gate has not been told that the share prices are end-of-session.
 * Sharing one key across both would silently skip whichever sentence they never read.
 */
'use strict';

/* The lottery page keeps the original key so nobody who already agreed is asked twice. */
const GATES = {
  xoso: {
    ackKey: 'tientrivutru.ack.v1',
    eyebrow: '⚠ Đọc trước khi xem số',
    title: 'Trang này không dự đoán được xổ số.<br>Không phần mềm nào làm được.',
    lede: 'Đây là một thí nghiệm đốt token AI. Mọi con số ở đây là ngẫu nhiên, và trang tự '
        + 'công khai chứng minh điều đó bằng chi-square trên 12.578 kỳ quay.',
    points: [
      'Không bán gì — không thu tiền, không tài khoản, không quảng cáo',
      'Không liên quan Vietlott — không liên kết, không tài trợ, không uỷ quyền',
      'Dữ liệu từ mirror bên thứ ba, có thể sai — cần chính xác thì tra vietlott.vn',
      '18+ · tự chịu rủi ro',
    ],
  },
  taichinh: {
    ackKey: 'tientrivutru.ack.taichinh.v1',
    eyebrow: '⚠ Đọc trước khi xem giá',
    title: 'Trang này không phải tư vấn đầu tư.<br>Và nó không biết giá ngày mai.',
    lede: 'Số liệu lấy thẳng từ API công khai của bên thứ ba — không tài liệu, không cam '
        + 'kết. Quẻ của thầy sinh ra từ một phép cộng chữ số, và giá trị dự báo của nó bằng không.',
    points: [
      'Không khuyến nghị mua bán — không bán gì, không quảng cáo, không affiliate',
      'Chứng khoán Việt ở đây là số <b>cuối phiên</b>, không phải realtime',
      'Nguồn có thể sai, thiếu hoặc chết — cần số chính xác thì tra thẳng nguồn gốc',
      'Tự chịu rủi ro — mọi quyết định tài chính là của riêng bạn',
    ],
  },
};

function gateCopy() {
  return GATES[document.body && document.body.dataset.page] || GATES.xoso;
}

function hasAcknowledged() {
  try {
    return localStorage.getItem(gateCopy().ackKey) === '1';
  } catch {
    // Private browsing refuses reads. Show the warning again rather than assume consent.
    return false;
  }
}

function remember() {
  try {
    localStorage.setItem(gateCopy().ackKey, '1');
  } catch {
    // Storage blocked. The modal still closes - see closeGate. Failing to remember a
    // dismissal must never leave the visitor locked out of the page.
  }
}

function buildGate() {
  const gate = document.createElement('div');
  gate.className = 'gate';
  gate.setAttribute('role', 'dialog');
  gate.setAttribute('aria-modal', 'true');
  gate.setAttribute('aria-labelledby', 'gate-title');
  const copy = gateCopy();
  gate.innerHTML = `
    <div class="gate__panel">
      <p class="gate__eyebrow">${copy.eyebrow}</p>
      <h2 class="gate__title" id="gate-title">${copy.title}</h2>
      <p class="gate__lede">${copy.lede}</p>
      <ul class="gate__list">${copy.points.map((t) => `<li>${t}</li>`).join('')}</ul>
      <div class="gate__actions">
        <button class="btn" type="button" id="gate-ok">TÔI HIỂU</button>
        <a class="gate__more" href="https://github.com/quocdaijr/tientrivutru/blob/main/DISCLAIMER.md"
           target="_blank" rel="noopener">Đọc bản đầy đủ →</a>
      </div>
    </div>`;
  return gate;
}

function closeGate(gate) {
  gate.remove();
  document.documentElement.classList.remove('is-gated');
  remember();
  const firstStamp = document.querySelector('.stamp');
  if (firstStamp) firstStamp.focus();
}

/** Keep Tab inside the dialog while it is open. */
function trapFocus(gate, event) {
  if (event.key !== 'Tab') return;
  const focusable = gate.querySelectorAll('button, a[href]');
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function openGate() {
  const gate = buildGate();
  document.documentElement.classList.add('is-gated');
  document.body.appendChild(gate);

  const ok = gate.querySelector('#gate-ok');
  ok.addEventListener('click', () => closeGate(gate));
  gate.addEventListener('keydown', (event) => {
    // Escape deliberately does nothing: the button must be pressed.
    if (event.key === 'Escape') event.preventDefault();
    trapFocus(gate, event);
  });
  ok.focus();
  return gate;
}

function initWarningGate() {
  if (hasAcknowledged()) return null;
  return openGate();
}

/* The warning strip and the nav share one sticky wrapper, so the wrapper's height is
   whatever the strip's text wraps to: 114px on a laptop, 131px at 375px, 204px once the
   strip needs three lines at 280px. Any hardcoded scroll-margin is therefore wrong at
   most widths, and it was - it said 96px. Measure it instead and let CSS read it. */
function trackTopbarHeight() {
  const bar = document.querySelector('.topbar');
  if (!bar) return;
  const publish = () => document.documentElement.style
    .setProperty('--topbar-h', Math.round(bar.getBoundingClientRect().height) + 'px');
  publish();
  if ('ResizeObserver' in window) new ResizeObserver(publish).observe(bar);
  else window.addEventListener('resize', publish);
}

window.TienTriVuTruWarning = {
  GATES, gateCopy, hasAcknowledged, initWarningGate, openGate, closeGate,
  trackTopbarHeight,
};

function boot() {
  initWarningGate();
  trackTopbarHeight();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
