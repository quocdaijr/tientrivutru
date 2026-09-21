/*
 * The handful of helpers every page on this site needs: build a node, open a stage,
 * format a number the way Vietnamese reads it, reveal on scroll.
 *
 * These lived in render.js while there was only one page. The finance page needs the
 * same stage frame and the same number formatting, and two copies of a formatter is
 * exactly how two pages start disagreeing about what 14.760.000 looks like.
 *
 * Wrapped in an IIFE on purpose: classic scripts share one top-level lexical scope, so a
 * bare `const tw` here collides with render.js destructuring the same name back off
 * TienTriVuTruDom. Only the namespace escapes.
 */
(function () {
'use strict';

/** Self-hosted Twemoji. Explicit beats a runtime DOM walk: no reflow, no library. */
const tw = (cp, alt) =>
  `<img class="tw" src="./img/emoji/${cp}.svg" alt="${alt}" width="20" height="20" loading="lazy">`;

const vnd = (n) => (n || 0).toLocaleString('vi-VN') + 'đ';
/** Billions, because 34.897.731.150 is a number nobody reads and "34,90 tỷ" is one they do. */
const billionsNum = (n) => (n / 1e9).toLocaleString('vi-VN', {maximumFractionDigits: 2});
const billions = (n) => billionsNum(n) + ' tỷ';

const pct = (n) => (n * 100).toFixed(2) + '%';
const pad = (n) => String(n).padStart(2, '0');

function el(tag, cls, html) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (html != null) node.innerHTML = html;
  return node;
}

function stage(mark, title, lede) {
  const section = el('section', 'stage reveal');
  section.id = 'stage-' + mark;
  section.appendChild(el('div', 'stage__mark', mark));
  section.appendChild(el('h2', 'stage__title', title));
  if (lede) section.appendChild(el('p', 'stage__lede', lede));
  return section;
}

function observeReveals() {
  const targets = document.querySelectorAll('.reveal');
  if (!('IntersectionObserver' in window)) {
    targets.forEach((t) => t.classList.add('is-in'));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-in');
        io.unobserve(entry.target);
      }
    });
  }, { rootMargin: '0px 0px -8% 0px' });
  targets.forEach((t) => io.observe(t));
}

/**
 * Pause the looping figure whenever it scrolls out of view.
 *
 * This is the condition attached to having a looping animation at all: one that only
 * runs while somebody is looking costs almost nothing, one that never stops costs
 * battery on the phones this page was just tuned for.
 */
function observeFlips() {
  const flips = document.querySelectorAll('.thay--flip');
  if (!('IntersectionObserver' in window)) return;
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => e.target.classList.toggle('is-paused', !e.isIntersecting));
  }, { threshold: 0 });
  flips.forEach((f) => { f.classList.add('is-paused'); io.observe(f); });
}

window.TienTriVuTruDom = {
  tw, vnd, billionsNum, billions, pct, pad, el, stage, observeReveals, observeFlips,
};
})();
