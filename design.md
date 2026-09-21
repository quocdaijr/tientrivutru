# design.md — Tiên Tri Vũ Trụ

Locked design system. Written by Hallmark on 2026-08-19. Any later page in this project
follows this file rather than rotating to a new look.

## Voice

A street fortune-teller. Says **thầy**, calls the reader **con**. Overconfident, never
responsible, always leaves an exit ("trúng là phúc nhà con, trượt là do con đi ngang qua
đám ma"). He is **never** allowed to say the numbers will win — that sentence belongs to
the scam sites this project is mocking.

He is also **silent** in one place: stage `04 · SỰ THẬT`, the disclaimer, and every
statistical label. The joke is the gap between four stages of shouting and one stage of
cold arithmetic. Collapse that gap and the project loses both its punchline and its
honesty.

## Macrostructure — Narrative Workflow

A fortune-telling session is an ordered thing, so the page is too. There are **two pages**,
and both run the same shape: the fortune-teller shouts through the opening stages, then goes
silent for one stage of cold arithmetic. Same skins, same tokens, same stage frame.

`site/index.html` — the lottery session:

| stage | content |
|---|---|
| `00 · KHAI` | birth-date form, local-only, with the privacy block |
| `01 · TƯỚNG` | the fortune: can chi, nạp âm, cung, số chủ đạo, sao, tam hợp / tứ hành xung |
| `02 · PHÁN` | twelve numbers for the wheel and six for a plain ticket, house oracle and personal oracle side by side, then the pot |
| `03 · SỔ NỢ` | scoreboard, ROI, ROI-excluding-jackpot, head-to-head, "cạn phước" |
| `04 · SỰ THẬT` | chi-square across seven sources, heatmaps, recent draws, kiến thiết 3 miền |

`site/tai-chinh.html` — the money page. Three stages rather than five, because there is no
birth date to take and no scoreboard to keep; the reading is generated from the prices
themselves, so it has nothing to be scored against:

| stage | content |
|---|---|
| `00 · PHÁN TÀI` | the fortune-teller reads the market: a digit root over the fetched figures, an element, and how many sources were silent |
| `01 · SỔ GIÁ` | gold (SJC bars and plain rings, plus world spot), the three indices, foreign net flows, crypto — each with its source and the API's own timestamp |
| `02 · SỰ THẬT` | what is genuinely realtime and what is end-of-session, why there is no land price, and the page checking its own gold against world spot |

Stage numbers sit **above** their titles in the same column. Number-left / title-right is
the most reliable templated-editorial tell and is not used here.

The two pages are **not** interchangeable in voice. Stage `04 · SỰ THẬT` on the lottery page
and `02 · SỰ THẬT` on the money page are the silent stages; everything above them shouts.
A page that let the fortune-teller into its statistics stage would lose the joke and the
honesty in the same move.

Nav: **N7 brutal slab** — thick sticky bar, wordmark left, four rubber stamps right, and one
`.slab__to` text link between the wordmark and the stamps carrying the reader to the other
page. It is body face, not a fifth stamp: five stamps would read as five skins.

The wordmark became **Tiên Tri Vũ Trụ** on 2026-09-21 (was `trungso`), and that is a
measured change, not a cosmetic one: 214px unwrapped at the bar's 23.2px body face, up
from 119px. One row of the slab now needs `20 + 214 + 25 + 81 + 20 = 360px`, so **360px
is the exact floor** for wordmark and `.slab__to` sharing a row. At 375px there is 40px
of slack; below 360px the link wraps to its own row and the bar goes 130px → 174px. That
wrap is left in: it stays on one left axis, collides with nothing, and adds no horizontal
scroll — 320px is the only live width that sees it. A longer name would have to earn its
own breakpoint by being measured, not by inheriting this one.
Footer: **Ft2 credit columns** — three columns of the same `<h2> + <dl>` shape (thanks ·
assets · this page) over one full-width base strip. Every column head carries a hairline,
so three rules of equal length landing on one y is what makes the grid legible; below the
breakpoint the columns stack and the same rule becomes the section divider.

It was Ft5 statement until 2026-08-19, then Ft4 colophon until 2026-08-22;
`.hallmark/log.json` carries all three entries. A locked system file that disagrees with
what shipped is worse than no locked file, so it gets amended, not left behind.

Ft4's prose block is what forced the change, and the reason is worth keeping: it held a
`max-width: 70ch` while the credit columns above it filled the 1060px `.wrap`, so its top
rule stopped 440px short of the block it was supposed to close and its one sentence wrapped
mid-phrase with half the row empty. Together with a 12px `padding-left` on every `dd`, the
footer ran **four competing left axes** in one block. The fix was not to widen the prose —
it was to delete it and let a third column carry that content in the same shape as the other
two, leaving **one left axis, repeated three times**. Two rules follow from that:

- **No element in the footer gets a measure of its own.** A reading measure inside a block
  whose siblings are full-width is not typography, it is a second, invisible container.
- **Hierarchy inside a column is carried by colour, never by indentation.** `--color-ink-dim`
  already separates `dd` from `dt`; a 12px indent on top of it is too small to read as
  hierarchy and big enough to read as sloppiness.

The column ratio is `1.25fr 1fr 1fr` and the breakpoint is 980px. Both are measured, not
chosen: the longest credit is 329.5px unwrapped, three even columns give 318.66px, and the
old 900px breakpoint left the long name wrapped from 904px to 960px. A breakpoint inherited
across a change in column count is a breakpoint nobody has measured.

Section rhythm is **not** uniform: `02 · PHÁN` gets extra air because it is the loud stage,
and `04 · SỰ THẬT` comes in tighter because that is where the fortune-teller goes silent.
Equal padding on all five stages would flatten the one contrast the page is built on.

## Shape language

- `--radius: 0` everywhere. The only round thing on the page is a lottery ball (`--ball: 50%`).
- Blocks are divided by **uneven rules** — a `--rule-slab` on one edge, `--rule-hair` on the
  others. Never an even 1px box on four sides; that is the card look this redesign removed.
- Torn ticket edge via `repeating-linear-gradient`, no image asset.
- Full-page grain overlay, `mix-blend-mode` per skin. The page should feel printed.
- Stamps: display type, rotated `-4deg`, thick border. Used for the skin picker and for
  the "CẠN PHƯỚC" verdict.

## Four skins

One macrostructure, four skins, switchable at runtime and remembered in `localStorage`.

| key | paper | display | body | accent | axes |
|---|---|---|---|---|---|
| `veso` (default) | cream `#F2E8D5` | Bungee | Be Vietnam Pro | brick red | light · display-heavy · warm |
| `thantai` | lacquer red `#7A1414` | Playfair Display | Be Vietnam Pro | gilt gold | dark · high-contrast-serif · warm-gold |
| `viahe` | near-black `#0A0A0A` | Anton | JetBrains Mono | phosphor green | dark · display-condensed · chromatic-other |
| `y2k` | violet `#1A0B2E` | Bungee Shade | Grandstander | cyan + magenta | dark · display-3D · cool |

`Sriracha` (handwriting) runs across all four for the fortune-teller's own lines. It is the
thread that ties the skins together, and the clearest anti-AI-slop detail on the page.

## Two rules learned the hard way

**1. Every display face must carry Vietnamese glyphs.** Verified against the Google Fonts
API. These are safe: Bungee · Bungee Shade · Anton · Alfa Slab One · Playfair Display ·
Bricolage Grotesque · Be Vietnam Pro · JetBrains Mono · Baloo 2 · Oswald · Merriweather ·
Sriracha · Grandstander. These are **not**, and will shred every diacritic on the page:
Archivo Black · Bebas Neue · Instrument Serif · DM Serif Display · Lilita One · Fredoka ·
Passion One · Rubik Mono One.

**2. A 3D display face is illegible below ~20px.** Data values use `--font-body` at weight
800, never `--font-display`. "ĐẠI LÂM MỘC" in Bungee Shade at 16px is a smudge.

Size is not the only reason, and the fix is not `--font-body` either. Measured per-digit in
the DOM, at the same size and weight the page actually renders:

| face | role | digit-width spread |
|---|---|---|
| Bungee · Anton · Playfair Display | `--font-display` | 5.84 - 12.15px |
| Be Vietnam Pro | `--font-body` | **77.13px, and `tabular-nums` does not help** |
| Grandstander | `--font-body` (y2k) | 60.4px → 0 with `tabular-nums` |
| JetBrains Mono | `--font-num` | **0** |

Be Vietnam Pro as loaded ships **no tabular figure set**, so `font-variant-numeric` is a
no-op in `veso` and `thantai` - the two skins that use it as the body face. So **any column
of figures uses `--font-num`**, which is monospaced and cannot misalign. That is already what
`.ball`, `.cell`, `.num`, `.pot__num` and the tables do; `.kpi` was the one exception and is
no longer. `tabular-nums` stays on as belt-and-braces for any future non-mono face.

The money page is where this rule earns its keep, because it is nothing but columns of
figures. `.fact__v` stays on the body face - on the lottery page it holds words (can chi,
nạp âm) - and the money page opts its price cells into `.fact__v--num`. `.delta`, the
signed-change chip, is `--font-num` for the same reason. Both are weight **700**, not 800:
only 400 and 700 of JetBrains Mono are loaded, and 800 would be a synthesised bold.
Re-measured per-digit in the DOM across all four skins: spread **0**.

## Contrast floor — measured, not assumed

Every text surface clears **AA 4.5:1 in all four skins**, on **both pages**; the lowest
measured anywhere is 4.56 (`.note` on `veso`).
Two tokens exist purely to hold that line:

- `--color-on-accent-2` — the dark colour to place on a solid `--color-accent-2` fill.
  Accent-2 is a loud colour in every skin, so `--color-ink` on top fails (1.01:1 in `viahe`).
- `veso`'s `--color-accent` was deepened from `oklch(60.4%)` to `oklch(54%)`. Cream-on-red
  was 3.53:1, short of AA for the 14px bold UI text that uses it.

`.delta` is a chip on `--color-paper-2` rather than bare text on `--color-paper`, and that
is a contrast decision, not a decorative one: on `thantai` the paper **is** lacquer red, so
`--color-bad` on it measured **4.26:1** — under AA. The same colour on `paper-2` measures
5.32, which is where `.kpi--bad` already lives.

Measure with a canvas, not by parsing `getComputedStyle().color` — it returns `oklch(...)`
verbatim, and string-parsing that as RGB produces confident nonsense.

## Motion

Four primitives, all `transform` / `opacity`: `stamp-press`, `ball-in` (staggered),
`reveal` (on scroll), and `thay-idle`. Named easings only. `prefers-reduced-motion: reduce`
collapses everything to a 150ms opacity fade.

`thay-idle` is the one infinite loop on the page, and it was added on an explicit request
for a real looping animation rather than a one-shot. It cross-fades two frames of the
hand-drawn fortune-teller over 4s using `opacity` only, so it stays GPU-composited and
never touches layout. It exists in exactly one place - the head of stage 02 - and it ships
with two conditions that are part of the primitive, not options attached to it:

1. **It pauses when it is not on screen.** `render.js` observes the figure and toggles
   `.is-paused`, which sets `animation-play-state: paused`. An infinite animation running
   behind the fold is battery cost with nothing to show for it. Verified by reading
   `animation-play-state`, not by trusting the class.
2. **`prefers-reduced-motion: reduce` removes it entirely** - `animation: none`, second
   frame hidden. Not slowed, not shortened. Removed. This is an accessibility requirement,
   so it is not subject to taste.

A fifth primitive would need the same treatment, or it does not get added.

## Exports

`site/tokens.css` is the single source for every colour, face, space, and duration. No page
CSS declares a raw colour or a `font-family` string; everything references a token by name.

`site/page.css` holds the page styles and is **shared by both pages** — it was inline in
`index.html` until the money page needed the same stage frame, and two copies of a
stylesheet is how two pages start disagreeing. `site/dom.js` does the same job for the
handful of helpers that build a stage or format a number. A component that only one page
uses still lives in `page.css`; splitting per-page stylesheets would put the shared frame
back at risk of drifting.
