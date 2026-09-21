/*
 * Skin switcher. Four skins, one macrostructure.
 *
 * The choice lives in localStorage and nowhere else - same rule as the birth date.
 * A skin preference is not worth a server round-trip, and this project does not
 * have a server to send it to.
 */
'use strict';

const THEMES = ['veso', 'thantai', 'viahe', 'y2k'];
const THEME_KEY = 'tientrivutru.theme.v1';
const DEFAULT_THEME = 'veso';

const THEME_LABELS = {
  veso: { full: 'VÉ SỐ', short: 'V' },
  thantai: { full: 'THẦN TÀI', short: 'T' },
  viahe: { full: 'VỈA HÈ', short: 'H' },
  y2k: { full: 'Y2K', short: 'Y' },
};

function readTheme() {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    return THEMES.includes(stored) ? stored : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
}

/** Apply a skin and remember it. Returns the skin that actually took effect. */
function applyTheme(name) {
  const theme = THEMES.includes(name) ? name : DEFAULT_THEME;
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // Private browsing refuses writes. The skin still applies for this session -
    // failing to remember a preference is not a reason to fail to show the page.
  }
  document.querySelectorAll('[data-set-theme]').forEach((button) => {
    button.setAttribute('aria-checked', String(button.dataset.setTheme === theme));
  });
  return theme;
}

/** Wire the stamps in the nav slab. Arrow keys move within the radiogroup. */
function initThemeControls(root = document) {
  const buttons = [...root.querySelectorAll('[data-set-theme]')];
  buttons.forEach((button, index) => {
    button.addEventListener('click', () => applyTheme(button.dataset.setTheme));
    button.addEventListener('keydown', (event) => {
      const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
      if (!step) return;
      event.preventDefault();
      const next = buttons[(index + step + buttons.length) % buttons.length];
      next.focus();
      applyTheme(next.dataset.setTheme);
    });
  });
  applyTheme(readTheme());
  preloadDisplayFaces();
}

/**
 * Browsers only download a webfont when something actually renders in it, so the
 * first click on a skin would otherwise swap fonts mid-flight. Warm all four
 * display faces once, in the background, and switching becomes instant.
 */
function preloadDisplayFaces() {
  if (!document.fonts || !document.fonts.load) return Promise.resolve();
  const faces = ['Bungee', 'Playfair Display', 'Anton', 'Bungee Shade', 'Sriracha'];
  // Includes accented glyphs on purpose: the Vietnamese subset is a separate file.
  return Promise.all(
    faces.map((face) => document.fonts.load(`700 48px '${face}'`, 'SỰ THẬT'))
  ).catch(() => undefined);
}

window.TienTriVuTruTheme = {
  THEMES,
  THEME_KEY,
  THEME_LABELS,
  DEFAULT_THEME,
  readTheme,
  applyTheme,
  initThemeControls,
  preloadDisplayFaces,
};
