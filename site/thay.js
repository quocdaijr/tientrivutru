/*
 * The fortune-teller, drawn by hand.
 *
 * Inline SVG, not <img>: `currentColor` only inherits through inline SVG, so this is
 * what lets one drawing take the ink colour of all four skins for free.
 *
 * The strokes are deliberately uneven — varying widths, slightly lopsided head, no
 * mirror symmetry. Perfect geometry is the tell; a wobble is the hand. Nothing here
 * is traced from an existing character: a crude-stick-figure *style* is not anyone's
 * property, but a specific character is, so this one is ours.
 */
'use strict';

/*
 * Geometry, measured rather than guessed. Three failed passes taught this:
 *   - The head bbox is y 8..62, x 30..90. Legs must start AT y 60, not above it,
 *     or they sprout out of the face.
 *   - A raised arm cannot rise through the head. The head is 60 wide in a 120 box,
 *     which leaves 30 units of clear air each side — raised arms live there.
 *   - Arms drawn inside the leg span read as clothing: a sash, a collar, a seam.
 * Lopsided on purpose. Perfect geometry is the tell; a wobble is the hand.
 */
const HEAD = '<path d="M60 8c21 0 31 15 30 28-1 15-14 26-30 26-18 0-31-10-30-27C31 22 41 8 60 8Z" stroke-width="4.4"/>';

/** Legs hang off the bottom of the head, sock-puppet style. Uneven widths on purpose. */
const LEGS = '<path d="M49 60c-4 20-5 38-3 55" stroke-width="3.8"/>'
           + '<path d="M72 61c5 21 6 39 3 54" stroke-width="4.2"/>';

const EYES = {
  open:   '<circle cx="51" cy="30" r="3.2" fill="currentColor" stroke="none"/>'
        + '<circle cx="70" cy="31" r="2.9" fill="currentColor" stroke="none"/>',
  shut:   '<path d="M47 30c3 3 7 3 9 0" stroke-width="3.1"/>'
        + '<path d="M66 31c3 3 7 3 9 0" stroke-width="2.9"/>',
  wide:   '<circle cx="51" cy="29" r="4.6" stroke-width="3"/>'
        + '<circle cx="70" cy="30" r="4.1" stroke-width="3"/>',
  weary:  '<circle cx="51" cy="33" r="3" fill="currentColor" stroke="none"/>'
        + '<circle cx="70" cy="34" r="2.8" fill="currentColor" stroke="none"/>'
        + '<path d="M45 24c4-4 9-4 12 0" stroke-width="2.8"/>'
        + '<path d="M64 25c4-4 9-4 12 0" stroke-width="2.8"/>',
};

const MOUTH = {
  smile: '<path d="M49 42c5 8 16 7 22-1" stroke-width="3.8"/>',
  flat:  '<path d="M50 45c7 2 14 2 21-1" stroke-width="3.5"/>',
  frown: '<path d="M49 49c5-8 16-7 22 1" stroke-width="3.6"/>',
  gasp:  '<ellipse cx="60" cy="45" rx="5.4" ry="6.8" stroke-width="3.2"/>',
};

const ARMS = {
  /** Hands together in the middle, elbows out — the default sitting pose. */
  pray:  '<path d="M47 70 55 86 60 79 66 86 74 70" stroke-width="4"/>',
  /** One hand up in the clear air beside the head, hailing someone. */
  wave:  '<path d="M47 70 41 92" stroke-width="3.8"/>'
       + '<path d="M74 66 108 30" stroke-width="4.2"/>'
       + '<path d="M108 30 114 25M108 30 102 26" stroke-width="3"/>',
  /** Palms up, elbows bent out past the legs. Nothing to explain. */
  shrug: '<path d="M47 70 28 80 34 64" stroke-width="3.8"/>'
       + '<path d="M74 70 93 80 87 64" stroke-width="3.6"/>',
  /** Pointing straight out at a number nobody else can see. */
  point: '<path d="M47 70 41 92" stroke-width="3.6"/>'
       + '<path d="M74 73 114 68" stroke-width="4.2"/>',
  /** Both arms up through the clear air, well past the head. Rare. */
  cheer: '<path d="M48 66 14 32" stroke-width="4.2"/>'
       + '<path d="M73 66 106 28" stroke-width="4"/>',
  /** Hands in the lap, defeated. */
  limp:  '<path d="M49 70c6 13 22 13 26 0" stroke-width="3.6"/>',
};

/** name -> [eyes, mouth, arms] */
const POSES = {
  idle:  ['open',  'smile', 'pray'],
  blink: ['shut',  'smile', 'pray'],
  wave:  ['open',  'smile', 'wave'],
  sad:   ['weary', 'frown', 'limp'],
  shrug: ['open',  'flat',  'shrug'],
  point: ['open',  'smile', 'point'],
  cheer: ['wide',  'gasp',  'cheer'],
};

/** Alt text per pose, so the drawing is not information the screen reader loses. */
const POSE_ALT = {
  idle:  'Thầy bói ngồi, hai tay chắp',
  blink: 'Thầy bói nhắm mắt',
  wave:  'Thầy bói giơ tay',
  sad:   'Thầy bói mặt buồn, tay bỏ xuống',
  shrug: 'Thầy bói xoè hai tay',
  point: 'Thầy bói chỉ tay ra ngoài',
  cheer: 'Thầy bói giơ hai tay, miệng há',
};

function svg(pose) {
  const [eyes, mouth, arms] = POSES[pose] || POSES.idle;
  return '<svg viewBox="0 0 120 120" fill="none" stroke="currentColor"'
    + ' stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
    + HEAD + LEGS + EYES[eyes] + MOUTH[mouth] + ARMS[arms] + '</svg>';
}

/**
 * A single still pose.
 * `extraClass` lets a caller size it without reaching into this module's CSS.
 */
function still(pose, extraClass = '') {
  return `<div class="thay ${extraClass}">${svg(pose)}`
    + `<span class="sr-only">${POSE_ALT[pose] || POSE_ALT.idle}</span></div>`;
}

/**
 * Two poses stacked, frame B cross-fading over frame A on a loop.
 *
 * The loop is paused whenever it scrolls out of view (see render.js), and disabled
 * outright under prefers-reduced-motion. An animation that only runs while somebody
 * is looking at it costs almost nothing; one that never stops costs battery.
 */
function flip(poseA, poseB, extraClass = '') {
  return `<div class="thay thay--flip ${extraClass}">`
    + `<div class="thay__a">${svg(poseA)}</div>`
    + `<div class="thay__b">${svg(poseB)}</div>`
    + `<span class="sr-only">${POSE_ALT[poseA] || POSE_ALT.idle}</span></div>`;
}

/** Pose keyed to how many numbers actually landed. Data drives the drawing. */
function poseForHits(hits) {
  if (hits >= 5) return 'cheer';
  if (hits >= 3) return 'point';
  if (hits >= 1) return 'shrug';
  return 'sad';
}

window.TienTriVuTruThay = { POSES, POSE_ALT, svg, still, flip, poseForHits };
