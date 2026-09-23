# 🔮 Tiên Tri Vũ Trụ

*The fortune-teller calls the numbers for you. Then mathematics calls the fortune-teller.*

[![Oracle](https://github.com/quocdaijr/tientrivutru/actions/workflows/oracle.yml/badge.svg)](https://github.com/quocdaijr/tientrivutru/actions/workflows/oracle.yml)
[![CI](https://github.com/quocdaijr/tientrivutru/actions/workflows/ci.yml/badge.svg)](https://github.com/quocdaijr/tientrivutru/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)
[![Ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://docs.astral.sh/ruff/)
[![tests](https://img.shields.io/badge/tests-1015%20passing-brightgreen.svg)](tests/)
[![draws analysed](https://img.shields.io/badge/draws%20analysed-31%2C470-informational.svg)](#what-the-honest-layer-found)
[![chi-square](https://img.shields.io/badge/chi²%20p--value-0.10%20→%20random-informational.svg)](#what-the-honest-layer-found)
[![prediction accuracy](https://img.shields.io/badge/prediction%20accuracy-0%25-critical.svg)](DISCLAIMER.md)
[![expected ROI](https://img.shields.io/badge/expected%20ROI-−86%25-critical.svg)](DISCLAIMER.md)
[![kien thiet ROI](https://img.shields.io/badge/kiến%20thiết%20ticket%20ROI-−50%25%20(exact)-critical.svg)](#the-one-number-here-that-is-not-an-estimate)
[![status](https://img.shields.io/badge/status-satire-ff69b4.svg)](DISCLAIMER.md)

**🇻🇳 Tiếng Việt → [README.md](README.md)**

---

> ## ⚠️ READ THIS SENTENCE FIRST
>
> ### This site cannot predict lottery numbers. No software can.
>
> It is an **AI-token-burning experiment**. Every number here is random, and the site
> publishes the proof against itself — a chi-square test over 31,470 real draws.
>
> - **Nothing is for sale** — no payments, no accounts, no ads
> - **Not affiliated with Vietlott** — not sponsored, not endorsed, not authorised
> - **Third-party data** that can be wrong or incomplete — for authoritative results use [vietlott.vn](https://vietlott.vn)
> - **18+**
> - **Use at your own risk** — provided AS IS; every loss is yours alone
>
> 📄 Full text: [**DISCLAIMER.md**](DISCLAIMER.md)

---

## Why this repository exists

Honestly: **so the AI tokens already burned wouldn't go to waste.**

This is a by-product of an AI-coding experiment. Rather than let millions of tokens evaporate,
they turned into something that runs, has tests, and makes fun of itself.

The only genuine value here is **The Honest Layer** — the statistics showing that lotteries are
random, measured on real data from seven sources, 36 provincial đài, across two countries.
Everything else is a pavement fortune-teller implemented in code.

If you came looking for numbers to play, the fortune-teller will tell you straight: the numbers
here are **exactly** as random as numbers you pick yourself. The only difference is that this
site **admits it**.

### A note on voice

The Vietnamese original is written in the register of a pavement fortune-teller: he calls himself
**thầy** ("master", "teacher") and calls the reader **con** ("child"). It is deliberately
presumptuous — the register of someone who has decided he is the authority in the room.

English has no equivalent pronoun pair, so this translation uses plain "you". The hierarchy is
lost; the presumption survives in the phrasing.

He is silent in three places, in both languages: the disclaimer, the statistics, and the
gambling-support note. That gap is the joke, and it is also what keeps the project honest.

## Two layers

**The Honest Layer** — frequency, gap analysis, and a chi-square goodness-of-fit test against a
uniform distribution. The incomplete gamma function is hand-rolled so the project needs no
scipy. The expected result is `p >> 0.05`, meaning *nothing to see here* — and the site prints
exactly that.

**The Cursed Layer** — an oracle that produces twelve Vietlott numbers, and **one six-digit
ticket per kiến thiết đài**, from "cosmic signals": numerology of the draw date, the Bitcoin
price, the temperature in Hanoi, the lunar date and its zodiac animal, and the karma of the
previous draw. Predictive value: zero. Entertainment value: the entire point.

## What makes this project honest

Every prophecy is generated **deterministically** from
`sha256(version | game | draw_id | date | signals)` and written to `data/predictions.jsonl`
**before** that draw takes place. Run it again and you get the same twelve numbers. It cannot
be edited after the fact.

`ORACLE_VERSION` is part of the seed, so changing the algorithm cannot flatter the past — two
prophecies committed at v1.0.0 are still v1.0.0 even though the oracle is now at v1.3.0.

That is what makes the **Hall of Shame** (*Bảng Phong Thần* — literally "the register of
deified names", used here for a scoreboard of failure) mean anything.

## Usage

```bash
uv sync

uv run tientrivutru ingest --check-gaps      # fetch results; patches from vietlott.vn when the mirror lags
uv run tientrivutru stats                    # The Honest Layer: chi-square + verdict, every source
uv run tientrivutru oracle                   # The Cursed Layer: twelve numbers, plus one vé per đài
uv run tientrivutru score                    # rebuild the Hall of Shame
uv run tientrivutru backtest --game mega645  # replay the oracle over all of history → ROI
uv run tientrivutru today                    # dashboard for the next draw
uv run tientrivutru site                     # emit site/data.json for the static page
uv run tientrivutru notify --kind prophecy   # push the twelve numbers and the vé to Telegram
uv run tientrivutru pulse --plan             # which hours today get a random pulse
uv run tientrivutru pulse --force --dry-run  # preview one card without sending it
```

Xổ số kiến thiết rides along with every command above. `--region {mb,mn,mt}` narrows to one
region, and **only** that region — it does not drag the four ball games along with it:

```bash
uv run tientrivutru ingest --region mn --since 2026-08-01   # a narrow window
uv run tientrivutru ingest --backfill                       # all three regions, resumable
uv run tientrivutru stats --region mt                       # chi-square for the centre alone
uv run tientrivutru backtest --region mn                    # replay 10,654 vé → ROI
```

`--backfill` walks minhngoc's **weekly** pages: one request returns a whole week of a region
(22 boards for the south), roughly thirty times cheaper than asking each đài for each day.
A week already covered is skipped without a request, so an interrupted run just resumes.

View the static site:

```bash
uv run tientrivutru site && python3 -m http.server -d site 8000
```

Telegram needs `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (GitHub Secrets in CI). Without them
`notify` fails loudly, while the data pipeline is **never** affected.

### Random pulses through the day — `tientrivutru pulse`

Beyond the two fixed slots (10:00 for the numbers, 18:45 for the result), `pulse` sends
**two or three messages a day at arbitrary hours between 08:00 and 22:00 VN**, one card each:
hot and cold numbers, chi-square, longest absences, the next draw with the jackpot and the
price of a wheel, the Hall of Shame, one line of the pending prophecy, all three kiến
thiết regions, the committed vé, the cosmic signals, **gold prices**, **crypto prices**,
and a personal fortune.

#### Gold: the unit is where this goes wrong

PNJ publishes **thousands of dong per chỉ**; Vietnamese buyers talk in **dong per lượng**; a
lượng is ten chỉ. The wrong answer therefore sits exactly one zero away from the right one,
and 15 million a lượng looks no less plausible than 150 million to anyone not holding the bar.
The conversion lives in one place (`sources/markets.py`) and `tests/test_markets.py` pins it
from **both ends**: against the figure webgia.com publishes in plain dong, and against world
spot converted independently.

The card also reports two numbers people rarely look at: the **dealer spread** (~2%, lost the
instant you buy) and the **domestic premium** over converted world spot (~3%). The rate used
for that conversion is the one the price source itself implies, not a bank rate, and is
labelled as such — with no rate available the premium line is **dropped rather than guessed**.


The hours are random but not unpredictable-to-themselves: a day's plan comes from a
`sha256(date)` seed, so `pulse.yml` can run hourly with no state file to keep — the other
twelve wake-ups exit 0 having sent nothing. A day never repeats a *kind* of card, and a manual
`workflow_dispatch` run sends immediately rather than waiting for an hour on the plan.

The window is cut into `n` equal bands (two pulses → 08:00–14:00 and 15:00–22:00; three →
08:00–12:00, 13:00–17:00, 18:00–22:00) and each band contributes one uniformly-chosen hour.
That keeps the spread across hours **flat** — a 1.14× spread over 3650 days — at the price of
two pulses occasionally landing in adjacent hours across a band boundary, on roughly 15% of
days. An earlier version enforced "at least 3h apart", and **that constraint was itself** why
08:00 and 22:00 came up 1.55× as often as 20:00: sampling uniformly over valid *schedules* is
not sampling uniformly over *hours*.

The personal layer reads `TIENTRIVUTRU_BIRTH_DATE` (with optional `TIENTRIVUTRU_GENDER` and
`TIENTRIVUTRU_NAME`) and lives only as a secret. The `pulse` job runs with
`permissions: contents: read` — it commits nothing — and a malformed value is reported by
naming the variable and nothing else, because these logs are public. The
[no-PII rule](#personalisation--and-why-there-is-no-sign-up) holds: the birth date is nowhere
in this repository.

## Wheel-12 arithmetic

The site plays *bao 12* — pick twelve numbers, cover all `C(12,6) = 924` combinations. At
10,000₫ per line that is **9,240,000₫ per draw per game**.

With `k` = how many of your twelve appear among the six drawn:

```
N(j) = C(k, j) · C(12 − k, 6 − j)        Σ N(j) = 924   (Vandermonde; asserted in tests)
```

Power 6/55's Jackpot 2 needs five main numbers **plus** the bonus, so that combination has to be
separated out rather than counted as a first prize.

| | Expected ROI (jackpot at floor) | Excluding jackpot |
|---|---:|---:|
| Mega 6/45 | −71.57% | −86.30% |
| Power 6/55 | −76.20% | −86.55% |

A backtest over 1,353 Mega 6/45 draws hit the jackpot exactly **once**, and ROI jumped to
**+11.35%** — while the hit rate stayed at 1.624 against a chance expectation of 1.600. That is
why *ROI excluding jackpot* is a first-class figure here and not a footnote: one lucky draw
hides everything else, which is precisely how every "lottery system" fools itself.

## Four skins

The page ships four runtime-switchable skins, remembered in `localStorage`:

| | paper | display face | spirit |
|---|---|---|---|
| **Vé Số** (default) | yellowed newsprint | Bungee | street lottery ticket, red riso ink |
| **Thần Tài** | lacquer red | Playfair Display | household shrine, gilt lettering |
| **Vỉa Hè** | near-black | Anton | pavement brutalism, phosphor green |
| **Y2K** | violet | Bungee Shade | early-2000s Vietnamese forum |

One macrostructure, four skins. Every colour and face comes from a token in `site/tokens.css` —
no raw values in the page. Every text surface clears **WCAG AA 4.5:1 in all four skins**
(lowest is 4.56), measured with a canvas rather than estimated.

Every display face was verified to carry **Vietnamese glyphs**. Several attractive faces do not,
and using one shreds every diacritic on the page.

## Personalisation — and why there is no sign-up

Enter a birth date (optionally a name and gender) and the page derives a full *lá số*: sexagenary
year, five-element destiny, Western zodiac sign, life-path number, guardian star, and the
harmony/clash animal groups — then twelve numbers of your own, plus a head-to-head table against
the house oracle and against pure chance.

> **🔒 No sign-up, no accounts, no server.** The birth date, name and gender live only in your
> browser's `localStorage`. No request carries them anywhere. One button wipes them.

This is an architectural decision, not laziness: this repo **commits its data into public git**
as an audit trail, so personal data must never touch the data path — git history cannot be
un-published. And everything enjoyable here is derivable from a birth date alone, so there is
nothing worth collecting.

The browser does **not** reimplement the lunar algorithm. Python generates a lookup table
(Tết dates, sexagenary cycle, five-element names for 1929–2035) embedded in `site/data.json`, and
a parity test drives the real `site/personal.js` through Node to check every value against
Python.

## Data sources

| Source | Used for | Size |
|---|---|---|
| [`thanhnhu/vietlott`](https://github.com/thanhnhu/vietlott) (MIT) | primary — Power 6/55 & Mega 6/45 | 1,386 + 1,353 draws since 2017 |
| `vietlott.vn` | fallback when the mirror lags (latest draw only) | — |
| `vietlott.vn` (same page) | Jackpot value and prize tiers per draw | 2 games |
| [`minhngoc.net.vn`](https://www.minhngoc.net.vn) | full prize boards for all three kiến thiết regions — honest layer, vé, cosmic signal | 26,409 boards, 36 đài; north since 2005, south/centre since 2017 |
| [`khiemdoan/vietnam-lottery-xsmb-analysis`](https://github.com/khiemdoan/vietnam-lottery-xsmb-analysis) (MIT) | **cross-check witness** for XSMB — no longer the ingest source | 7,526 draws since 2005 |
| [`jbaranski/jeffs-lottery-utils`](https://github.com/jbaranski/jeffs-lottery-utils) (MIT) | Powerball & Mega Millions — statistics only | 1,395 + 918 draws |
| CoinGecko / Open-Meteo | cosmic signals (BTC, weather) | — |
| [Binance](https://www.binance.com/) | BTC/USDT candles for the trader page — REST + WebSocket, called in the browser, never committed | 1000 candles per load |

`data.ny.gov` — the "official" source usually recommended — is **unusable**: the entire domain
returns 403 from this network, including its plain HTML pages, with or without browser headers.

The US games are **statistics-only**: no prophecies, no wheel, no scoreboard. Wheel-12 is a
Vietlott product; the sole purpose of the US data is to let The Honest Layer show that American
lotteries are exactly as random.

### What the jackpot figure is, and is not

The results page states the jackpot **as at a completed draw**, and that is the only jackpot
figure a plain HTTP request can get: vietlott.vn serves its estimate for the *upcoming* draw
through JavaScript, and the landing pages return an 18 KB shell with no data in it at all.

So when nobody won, the site says **"ít nhất X"** — at least X — because the next draw's pot
is that figure plus whatever the new tickets add. It never says "the jackpot is X". It also
always names the draw the money belongs to, because if the prize fetch failed on the last
run the stored figure describes an older draw, and a stale number wearing a current label is
the one thing this repository is built not to print.

The scoreboard's arithmetic did not change. The fixed tiers really are fixed — the live page
confirms 40.000.000 / 500.000 / 50.000 for Power, matching `games.py` — and the jackpot was
already excluded from `roi_excluding_jackpot` precisely because it varies. A test now asserts
the static table still matches the live one, so a silent upstream change would fail loudly.

### Six numbers or twelve? Both, and the page now says which

A plain Vietlott ticket - "Cách chơi: Cơ bản" in the app - is **six numbers for 10,000d**.
Bao 12 is a real alternative, not an invention: Vietlott's own product pages list eleven bao
sizes (5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18) and price a single combination at 10,000d, so
`C(12,6) = 924` combinations for 9,240,000d is correct. Third-party summaries routinely get
this wrong - one lists seven sizes and then says "eleven types" in the same article - so the
official page is the only source used here.

The page used to show only the twelve, which meant anyone buying the basic ticket had to guess
which six. It now shows both, and shows the **split**: a typical draw boosts one to three of
the twelve and leaves the rest at exactly the same weight, so only that many of the six were
chosen for a reason. The rest come out of a tie, and the page says so.

Ties break on the prophecy's seed, not by ascending number. That was measured, not styled:
sorting ties ascending made the six-number pick average 20.79 against the wheel's 28.52 over
300 draws - a 7.7 skew toward low numbers created entirely by the tie-break. Shipping a
spurious pattern would defeat the whole point of the repository.

### If it comes in tonight, what do you actually get?

The estimated pot for the *next* draw is not published anywhere a plain request can reach.
This is, and it is the question the jackpot figure makes people ask anyway - so the page
answers it from arithmetic instead of from a number it does not have.

For Mega 6/45, a bao-12 ticket costs 9,240,000đ:

| hits | 1 in | pays | net |
|---|---|---|---|
| 3 | 7 | 2,520,000đ | −6,720,000đ |
| 4 | 31 | 15,120,000đ | **+5,880,000đ** |
| 5 | 312 | 112,000,000đ | **+102,760,000đ** |
| 6 | 8,815 | 24,946,610,500đ | **+24,937,370,500đ** |

The table has to carry both halves. The money column alone reads as an argument *for*
playing - four hits already clears the stake, and it does. The probability column alone
reads as though the prizes were stingy, and they are not. Only together do they say the
true thing: the payouts are real, and the odds are what take them back. Four-or-better
happens about once in 28 draws, which is where the −71.57% goes.

## The finance page — `/tai-chinh.html`

A second page with the same two layers: the fortune-teller reads the market, then the page
states what that reading is worth. Gold (SJC bars and plain rings), the three exchange
indices, foreign net flows, and crypto.

It differs from the lottery page in exactly one way: **no Python is involved**. No source
module, no store, no bundle, no cron. The browser calls five APIs directly, and **no figure
is committed to the repository**.

| Block | Source | Actual freshness |
|---|---|---|
| Domestic gold | PNJ | Quoted price, changes a few times a day |
| World gold | gold-api.com | Realtime |
| Indices + foreign flows | VNDIRECT | **End of session (EOD)** |
| Crypto | CoinGecko | Realtime, 24/7 |

Three things the page states rather than hides:

**It is not realtime.** The real HOSE/HNX realtime feeds run over SignalR websockets and are
sold under vendor contracts; the only documented source (SSI FastConnect) requires signing up
in person at a branch. So the equity figures are end-of-session, and the page prints the
API's own timestamp rather than the page load time. At weekends it says *"latest session"*.

**Nothing is stored.** Every usable price endpoint is an internal API with no terms attached.
The repo already has a rule: *what has no verifiable licence does not get checked in*. So the
page fetches in the browser and commits nothing. The cost is real: **a dead source is an
empty block**, and no stale number is substituted. Each block degrades on its own — one
silent API never takes the page down.

**There is no land price.** It was planned, then dropped, and the reason is printed on the
page: Vietnam's residential property price index exists only as a **2019 indicator
specification that has never published a figure**; the national real-estate database portal
mandated by Decree 94/2024 **does not resolve**; and BIS, OECD, FRED, and the IMF Global
Housing Watch all **exclude Vietnam**. Inventing a number would be easy. Saying it does not
exist is correct.

> This page is **not investment advice**. The reading in stage 00 is a digit sum; its
> predictive value is **zero**, exactly like the lottery oracle's. See
> [DISCLAIMER.md](DISCLAIMER.md) section 2.

## The trader page — `/trader.html`

The third page, same two layers, with one thing neither of the others has: **the silent
stage grades the loud stage, on the loud stage's own data, while the reader is looking at
it.**

A live BTC/USDT candlestick chart — Binance REST for 1000 historical candles, WebSocket for
the one still forming. No API key, no proxy. It is the only genuinely realtime thing on the
site, for a mundane reason: crypto trades 24/7 and Binance publishes an open API, whereas
realtime Vietnamese equities go through SignalR sold on a vendor contract.

Thầy teaches you to read candles, teaches MA20 and RSI14, and names five patterns. Then
stage `02 · SỰ THẬT` measures those same five.

**The right measurement, after the obvious one turned out to be wrong.** The first idea was
to count patterns on real candles and compare against random ones. It fails two ways at
once: a doji and a hammer are properties of **one** candle standing alone, so shuffling the
order returns the **identical** count — vacuous by construction; and the multi-bar patterns
do differ, but that difference says the market has bursts of clustered volatility, not that
the pattern foretells anything.

What answers the actual question is the **forward return**: after each firing, take the
open-to-close return of the very next candle, compare it to the baseline, and get the
p-value by relabelling 2000 times. Over 6000 hourly candles all five sit inside the noise
(p from 0.21 to 0.65), even before the Bonferroni correction. And the **largest edge
measured** is an order of magnitude smaller than the exchange's own round-trip taker fee.

One detail is kept because it teaches itself: at a sample of 1000 candles, "engulfing" once
came in at p = 0.038 — which looks like a finding. At 6000 it dissolves. The page prints
both the corrected threshold and the number of tests, and says so out loud.

Two figures the page **cannot** measure itself, so it borrows them and names the owner:

| Figure | Source |
|---|---|
| **74–89%** of retail CFD accounts lose money, average loss 1,600–29,000 EUR | ESMA35-43-1135, analyses by EU national competent authorities |
| **97%** of those who persisted past 300 sessions still lost; only **0.4%** earned more than a bank teller; **no** evidence of learning | Chague, De-Losso & Giovannetti, *"Day trading for a living?"* ([SSRN 3423101](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101)) |

Both are other markets, not Vietnam, and the page leaves it that way.

Like the money page: **not one candle is committed.** Binance attaches no terms that would
permit redistribution, so the browser fetches and the tab forgets. A dead source is an empty
block — each path was blocked in turn: without the CDN the numeric table still carries every
figure, without REST thầy **gives no reading** and both citations stay intact.

> This page is **not investment advice, not a recommendation, and not a course.** The prices
> are real; the patterns and the reading are a joke, and the last stage measures them to
> prove it.

### The Council — TradingAgents, scored in public

Stage `02 · HỘI ĐỒNG` is one more oracle to be graded:
[TradingAgents](https://github.com/TauricResearch/TradingAgents) (Apache-2.0) — twelve LLM
agents, four reading numbers, two arguing, one deciding, three on risk, one approving — issuing a
five-tier rating each day for BTC, FPT, VNM and VCB. It runs unmodified at commit `2d17df8`
(tag `v0.5.0`), installed straight from git: `tradingagents` on PyPI is **a different project**
by someone else.

The repository records only **the rating and when it was written**, append-only, in
`data/hoi_dong/verdicts.jsonl`. No prices, no returns, not one sentence of the debate — the debate
quotes Yahoo news, StockTwits, Reddit and FRED, none of which licenses republication. **The
scoring happens in the reader's browser**, on prices fetched from Binance and VNDIRECT when the
page opens: paper trades net of real costs (BTC 0.10% per side; stocks 0.15% plus the 0.1% sale
tax), with the window opening at the first bar after the write — so a late write only moves the
window, it cannot cheat. Graded against *always Buy* and *a coin flip* on the same windows; a
p-value appears once 30 verdicts are scored.

Two things the page says outright: to reach a rating, the Council reads Yahoo Finance
automatically, which Yahoo's terms do not permit; and LLM providers differ on whether their
output may be published unattended, so the `Hội đồng` workflow is manual-only for now. A hard
monthly cost cap applies — a day past the cap is written as `skipped_budget`, not silence.

## What the Honest Layer found

Chi-square test, H₀ = "every number is equally likely":

| Source | Draws / boards | Observations | χ² | df | p-value | Rejects H₀? |
|---|---:|---:|---:|---:|---:|---|
| Power 6/55 | 1,388 | 8,328 | 52.66 | 54 | **0.5263** | no |
| Mega 6/45 | 1,356 | 8,136 | 31.96 | 44 | **0.9115** | no |
| Powerball (US) | 1,397 | 6,985 | 78.93 | 68 | **0.1716** | no |
| Mega Millions (US) | 920 | 4,600 | 60.33 | 69 | **0.7625** | no |
| Kiến thiết South (21 đài) | 10,654 | **191,772** | 117.39 | 99 | **0.1002** | no |
| Kiến thiết Centre (14 đài) | 8,220 | **147,960** | 92.07 | 99 | **0.6760** | no |
| Kiến thiết North (1 đài) | 7,535 | **203,445** | 106.13 | 99 | **0.2938** | no |

Seven independent sources, **36 đài**, two countries, **571,226 number observations**, 21 years
of data — and **not one source** rejects the randomness hypothesis. Any number that looks
"hot" is noise.

For the kiến thiết boards the value space is **the last two digits of all 18 (or 27) prizes** —
the same 00–99 space Vietnamese lô players stare at every evening.

## The one number here that is not an estimate

Every other figure in this repository is a sample: a p-value that wobbles, a paper-trading ROI
that moves with luck. **The southern and central kiến thiết prize table is not.**

One đài issues **1,000,000 tickets × 10,000₫ = 10 billion in revenue**. The table pays out:

| Prize | Match | Winners per million | Value | Total |
|---|---|---:|---:|---:|
| Đặc biệt (special) | 6 digits | 1 | 2,000,000,000 | 2,000,000,000 |
| Phụ đặc biệt | wrong **first** digit | 9 | 50,000,000 | 450,000,000 |
| Khuyến khích | wrong 1 of the other **5** | 45 | 6,000,000 | 270,000,000 |
| 1st | last 5 | 10 | 30,000,000 | 300,000,000 |
| 2nd | last 5 | 10 | 15,000,000 | 150,000,000 |
| 3rd (×2) | last 5 | 20 | 10,000,000 | 200,000,000 |
| 4th (×7) | last 5 | 70 | 3,000,000 | 210,000,000 |
| 5th | last 4 | 100 | 1,000,000 | 100,000,000 |
| 6th (×3) | last 4 | 300 | 400,000 | 120,000,000 |
| 7th | last 3 | 1,000 | 200,000 | 200,000,000 |
| 8th | last 2 | 10,000 | 100,000 | 1,000,000,000 |
| | | | **Total** | **5,000,000,000** |

Five billion out of ten. **The expected ROI on one ticket is −50.00%**, and that is not an
estimate — it is addition. [`test_kienthiet_prizes.py`](tests/test_kienthiet_prizes.py) settles
all **1,000,000 tickets** against a real board and requires the payout to come to exactly five
billion.

The fortune-teller commits one ticket per đài to `data/ve.jsonl` **before** that đài draws.
Replayed over the whole archive:

| Region | Tickets settled | Tickets that won anything | Realised ROI | Theoretical ROI |
|---|---:|---:|---:|---:|
| South | 10,654 | 116 | **−86.77%** | −50.00% |
| Centre | 8,015 | 97 | **−81.53%** | −50.00% |

The gap is not a bug: **the special prize is 40% of the pool** and lands about once per million
tickets, so nineteen thousand tickets is nowhere near enough to see one. Excluding the special
and its runner-up, the figure a normal run converges to is **−74.50%** — which the repo prints
next to the realised number rather than hiding.

> The north gets **no ticket**. XSMB tickets carry a ký hiệu (series symbol), the prize table
> changed in 2017 and again on 2025-04-01, and the special prize splits across several winners
> — no single honest ROI spans twenty-one years of that. The north stays in the honest layer,
> and the repo says so out loud.

## Draw schedule

- **Power 6/55** — 18:00 Tue / Thu / Sat
- **Mega 6/45** — 18:00 Wed / Fri / Sun
- **XSMB** — 18:15 daily
- **Kiến thiết South** — 16:15 daily, 3 đài (4 on Saturdays)
- **Kiến thiết Centre** — 17:15 daily, 2–3 đài

The per-đài calendar is **not hardcoded**: `kienthiet.schedule_from()` derives it from the last
eight weeks of the archive, so a province that moves its day is followed automatically.

## Image assets

Everything is **self-hosted in the repository** — the page makes no outbound request for an
image or an emoji. Per-file provenance, download dates, and the list of sources that were
considered and rejected are in [`site/img/CREDITS.md`](site/img/CREDITS.md).

Beyond the fonts, the whole site makes exactly **one** outbound script request: the
candlestick library on `/trader.html`, loaded from a CDN, pinned by both version and SRI
hash, and credited in that page's footer because Apache-2.0's NOTICE asks for it. If it
fails to load, the page's numeric table still carries every figure.

| Asset | Source | Licence |
|---|---|---|
| Đông Hồ woodblock print *Đại Cát* | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Dong_Ho_painting_-_Dai_cat.jpg) | Public domain |
| 13 emoji | [jdecked/twemoji](https://github.com/jdecked/twemoji) — © Twitter/X | graphics **CC-BY 4.0**, code MIT |
| Fortune-teller figures (7 poses) | drawn by hand in this repo, `site/thay.js` | MIT, same repo |
| TradingView Lightweight Charts™ v5.2.1 | [tradingview/lightweight-charts](https://github.com/tradingview/lightweight-charts) — © TradingView, Inc. | **Apache-2.0, attribution required** |

This repository is MIT, which means anyone who clones it is granted the right to redistribute
it. So it cannot contain anything it does not own: copyrighted meme characters, film stills,
and images taken from social media were all ruled out — not because they were hard to find,
but because there was no licence. **OpenMoji** was ruled out too: it is CC-BY-**SA**, and
copyleft conflicts with MIT.

## Licence & disclaimer

[MIT](LICENSE) — the software is provided **AS IS**, without warranty of any kind. The MIT
grant covers the **code**; third-party assets keep their own licences, listed above.

Full disclaimer (bilingual): [**DISCLAIMER.md**](DISCLAIMER.md)

If you use this to gamble and lose, that was your decision — not the fortune-teller's, and
certainly not the repository's.

### If gambling has become a problem

*The fortune-teller does not speak here. This part is real.*

Vietnam has **no** dedicated gambling-addiction helpline. The nearest real free resource is the
[Ngày Mai hotline](https://duongdaynongngaymai.vn/hotline/) — **+84 96 306 1414**, 13:00–20:30
Wed–Sun. It is **psychological crisis support**, not gambling-specific, but they listen without
judgement. Internationally, [Gamblers Anonymous](https://www.gamblersanonymous.org/) lists groups
by country.
