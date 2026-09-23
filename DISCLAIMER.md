# ⚠️ Miễn trừ trách nhiệm · Disclaimer

*🇻🇳 Tiếng Việt bên dưới · 🇬🇧 [English below](#english)*

---

## 🇻🇳 Tiếng Việt

> **Trang này không dự đoán được xổ số. Không phần mềm nào làm được.**
> Đây là một thí nghiệm đốt token AI. Mọi con số ở đây là ngẫu nhiên, và trang tự công khai
> chứng minh điều đó.

### 1. Không dự đoán được, và không thể dự đoán được

Xổ số là **biến cố độc lập**: mỗi kỳ quay reset về 0. Không có "số nóng", không có "số lạnh",
không có momentum, không có cầu để soi. Kỳ vọng toán học **luôn âm**.

Đây không phải ý kiến — repo này tự đo và tự công bố bằng chứng chống lại chính nó. Kiểm định
chi-square trên **12.578 kỳ quay · 231.201 lượt số**, 5 xổ số, 2 quốc gia:

| Nguồn | p-value | Bác bỏ tính ngẫu nhiên? |
|---|---:|---|
| Power 6/55 | 0,5343 | không |
| Mega 6/45 | 0,8982 | không |
| Powerball (US) | 0,1731 | không |
| Mega Millions (US) | 0,7671 | không |
| XSMB Miền Bắc | 0,3391 | không |

**Không một nguồn nào** bác bỏ được giả thuyết "mọi số đồng xác suất". ROI kỳ vọng của lối
chơi bao 12: **−71,6%** (jackpot ở mức sàn) tới **−86,3%** (bỏ jackpot).

### 2. Không phải tư vấn tài chính hay đầu tư

Không có gì trong repo hay trên trang là lời khuyên tài chính, đầu tư, pháp lý hay bất kỳ
dạng tư vấn chuyên môn nào.

Điều này áp dụng **đặc biệt** cho trang tài chính (`/tai-chinh.html`), nơi hiển thị giá
vàng, chỉ số chứng khoán và giá crypto:

- **Không khuyến nghị mua bán.** "Quẻ" của thầy ở chặng 00 sinh ra từ một phép cộng chữ số
  trên chính mấy con số phía dưới. Giá trị dự báo của nó bằng **không**, đúng như oracle xổ số.
- **Dữ liệu từ API công khai của bên thứ ba, không có tài liệu và không có cam kết.** Nguồn
  đang dùng là PNJ, gold-api.com, VNDIRECT và CoinGecko. Không nguồn nào trong đó là API có
  hợp đồng — tất cả đều là endpoint nội bộ phục vụ web của chính chủ, nên chúng có thể đổi
  schema, bật xác thực, hoặc ngừng hoạt động bất cứ lúc nào mà không báo trước.
- **Chứng khoán Việt là số cuối phiên (EOD), không phải realtime.** Feed realtime chính thức
  của HOSE và HNX đi qua websocket và phân phối theo hợp đồng vendor; trang này không có nó.
- **Giá crypto quy đổi sang VND là quy đổi qua tỷ giá của CoinGecko**, không phải giá khớp
  lệnh trên một sàn Việt Nam.
- **Trang không lưu lại số liệu tài chính nào.** Mọi con số do trình duyệt của bạn gọi thẳng
  tới nguồn, mỗi lần tải lại. Nguồn chết thì ô đó trống — trang không dựng lại số cũ.

Cần số chính xác để giao dịch thì tra thẳng nguồn gốc, đừng dùng trang này.

Và cho trang trader (`/trader.html`):

- **Mẫu hình nến và lời phán là trò đùa.** Chặng cuối của trang tự đo chúng trên chính dữ liệu
  đó và cho thấy chúng không nói gì về cây nến kế tiếp.
- **Hội đồng là một hệ thống AI, và bậc nó ra (Buy, Overweight, Hold, Underweight, Sell) do AI
  tạo, có thể sai hoặc thiếu sót, chỉ để tham khảo.** Nó không phải khuyến nghị mua bán của
  bất kỳ ai. Hội đồng là TradingAgents (TauricResearch, Apache-2.0) chạy nguyên bản; để ra bậc
  nó tự đọc dữ liệu Yahoo Finance bằng máy, điều mà điều khoản của Yahoo không cho phép. Repo
  chỉ ghi lại bậc và giờ ghi — không một con số nào Hội đồng đọc được đưa lên trang.
- **Điểm của Hội đồng được chấm ngay trong trình duyệt của bạn**, bằng giá lấy từ Binance và
  VNDIRECT lúc bạn mở trang, và không được lưu lại ở đâu. Phí và thuế trong phép chấm là mức
  phổ biến, không phải mức của tài khoản bạn; spread và trượt giá không được tính.

### 3. Không bán gì

Không thu tiền. Không tài khoản. Không thanh toán. Không quảng cáo. Không affiliate. Không
thu thập dữ liệu cá nhân — ngày sinh nhập vào chỉ nằm trong trình duyệt của bạn.

### 4. Không tổ chức, không môi giới, không tiếp thị cờ bạc

Repo này **không** bán số, **không** nhận cược, **không** liên kết với bất kỳ nhà cái hay
đại lý nào, và **không** khuyến khích ai đặt cược. Bảng Phong Thần mặc định là *paper-trading*
— tiền trên giấy, không phải tiền thật.

### 5. Không liên quan tới Vietlott

Dự án này **không liên kết, không được tài trợ, không được uỷ quyền** bởi Công ty Xổ số Điện
toán Việt Nam (Vietlott) hay bất kỳ đơn vị xổ số nào khác. Tên sản phẩm ("Power 6/55",
"Mega 6/45", "Vietlott") chỉ được nhắc tới để **tham chiếu**, và thuộc về chủ sở hữu của chúng.

### 6. Dữ liệu từ bên thứ ba, có thể sai

Kết quả lấy từ các mirror cộng đồng trên GitHub, không phải nguồn chính thức. Chúng có thể
**sai, thiếu, hoặc chậm** — repo này đã từng ghi nhận mirror bỏ sót nguyên một kỳ quay
(Mega 6/45 kỳ #01550, Chủ nhật 16/08/2026).

**Cần số chính xác thì tra [vietlott.vn](https://vietlott.vn).** Không dùng trang này để đối
chiếu vé.

### 7. 18+

Vietlott yêu cầu người chơi đủ **18 tuổi**. Trang này không dành cho người dưới 18.

### 8. Tự chịu rủi ro

Phần mềm được cung cấp **NGUYÊN TRẠNG (AS IS)**, không bảo đảm dưới bất kỳ hình thức nào —
xem [LICENSE](LICENSE). Mọi quyết định và mọi tổn thất tài chính là **của riêng bạn**. Tác giả
không chịu trách nhiệm với bất kỳ thiệt hại nào phát sinh từ việc dùng hay không dùng phần
mềm này.

### 9. Nếu cờ bạc đang là vấn đề của bạn

Phải nói thật: **Việt Nam hiện không có đường dây nóng riêng cho nghiện cờ bạc.**

Nguồn miễn phí có thật gần nhất là [**Đường dây nóng Ngày Mai**](https://duongdaynongngaymai.vn/hotline/)
— **096.306.1414**, 13:00–20:30 các ngày Thứ 4 đến Chủ nhật. Nhưng cần rõ: đây là dịch vụ
**sơ cứu và hỗ trợ tâm lý** cho người khủng hoảng tinh thần, đặc biệt là trầm cảm — trang của
họ **không đề cập tới cờ bạc**. Gọi khi bạn cần một người lắng nghe, không phán xét.

Quốc tế: [Gamblers Anonymous](https://www.gamblersanonymous.org/) có danh sách nhóm hỗ trợ
theo quốc gia.

Nếu bạn đang nghĩ tới việc tự làm hại mình, hãy tìm hỗ trợ y tế khẩn cấp ngay.

---

<a name="english"></a>

## 🇬🇧 English

> **This site cannot predict lottery numbers. No software can.**
> It is an AI-token-burning experiment. Every number here is random, and the site publishes
> the proof against itself.

### 1. It cannot predict, and it never could

Lottery draws are **independent events**: every draw resets to zero. There are no "hot"
numbers, no "cold" numbers, no momentum, no patterns to read. Expected value is **always
negative**.

This is not an opinion — the repo measures itself and publishes the evidence against itself.
Chi-square tests across **12,578 draws · 231,201 number observations**, five lotteries, two
countries:

| Source | p-value | Rejects randomness? |
|---|---:|---|
| Power 6/55 | 0.5343 | no |
| Mega 6/45 | 0.8982 | no |
| Powerball (US) | 0.1731 | no |
| Mega Millions (US) | 0.7671 | no |
| XSMB (Northern Vietnam) | 0.3391 | no |

**Not one source** rejects the hypothesis that every number is equally likely. Expected ROI
for the wheel-12 bet: **−71.6%** (jackpot at its published floor) to **−86.3%** (jackpot
excluded).

### 2. Not financial or investment advice

Nothing in this repository or on the site is financial, investment, legal, or any other kind
of professional advice.

This applies **especially** to the finance page (`/tai-chinh.html`), which displays gold
prices, stock indices, and crypto prices:

- **No buy or sell recommendation.** The fortune-teller's "reading" in stage 00 is a digit
  sum over the very numbers printed below it. Its predictive value is **zero**, exactly like
  the lottery oracle's.
- **Data comes from undocumented third-party public APIs with no guarantees.** The sources
  in use are PNJ, gold-api.com, VNDIRECT, and CoinGecko. None of them is a contracted API —
  each is an internal endpoint serving its owner's own front end, so any of them may change
  shape, require authentication, or disappear without notice.
- **Vietnamese equities here are end-of-session (EOD), not realtime.** The official realtime
  feeds from HOSE and HNX run over websockets and are distributed under vendor contracts;
  this page does not have them.
- **Crypto prices in VND are a currency conversion done by CoinGecko**, not a trade price on
  any Vietnamese exchange.
- **No financial data is stored.** Every figure is fetched by your browser directly from the
  source on each page load. When a source is down, that block is empty — no stale number is
  substituted.

If you need accurate figures to trade on, go to the source. Do not use this page.

And to the trader page (`/trader.html`):

- **The candlestick patterns and the fortune-teller's reading are a joke.** The page's last
  stage measures them on the same data and shows they say nothing about the next candle.
- **The Council is an AI system, and its ratings (Buy, Overweight, Hold, Underweight, Sell) are
  AI-generated, may contain errors or omissions, and are for reference only.** They are no one's
  buy or sell recommendation. The Council is TradingAgents (TauricResearch, Apache-2.0), run
  unmodified; to reach a rating it reads Yahoo Finance data automatically, which Yahoo's terms
  do not permit. The repository records only the rating and the time it was written — no
  figure the Council read is published.
- **The Council is scored in your own browser**, on prices fetched from Binance and VNDIRECT
  when you open the page, and stored nowhere. The fees and taxes in that scoring are typical
  rates, not your account's; spread and slippage are not counted.

### 3. Nothing is for sale

No payments. No accounts. No checkout. No ads. No affiliate links. No personal data
collection — a birth date entered on the site never leaves your browser.

### 4. Does not organise, broker, or promote gambling

This project does **not** sell numbers, does **not** accept bets, is **not** affiliated with
any bookmaker or agent, and does **not** encourage anyone to gamble. The scoreboard is
*paper-trading* by default — imaginary money, not real stakes.

### 5. Not affiliated with Vietlott

This project is **not affiliated with, sponsored by, or endorsed by** Vietlott (Vietnam
Lottery Company) or any other lottery operator. Product names ("Power 6/55", "Mega 6/45",
"Vietlott") are used **for reference only** and belong to their respective owners.

### 6. Third-party data, which can be wrong

Results come from community-maintained GitHub mirrors, not official feeds. They can be
**wrong, incomplete, or stale** — this repo has already caught a mirror silently missing an
entire draw (Mega 6/45 draw #01550, Sunday 2026-08-16).

**For authoritative results, check [vietlott.vn](https://vietlott.vn).** Do not use this site
to verify a ticket.

### 7. 18+

Vietlott requires players to be **18 or older**. This site is not intended for minors.

### 8. Use at your own risk

The software is provided **AS IS**, without warranty of any kind — see [LICENSE](LICENSE).
Every decision and every financial loss is **yours alone**. The author accepts no liability
for any damages arising from the use, or inability to use, this software.

### 9. If gambling has become a problem

An honest note: **Vietnam currently has no dedicated gambling-addiction helpline.**

The nearest real free resource is the [**Ngày Mai hotline**](https://duongdaynongngaymai.vn/hotline/)
— **+84 96 306 1414**, 13:00–20:30 Wednesday to Sunday (Vietnam time). To be precise: it is a
**psychological first-aid** service for people in emotional crisis, particularly depression —
their site **does not mention gambling**. Call it when you need someone to listen without
judgement.

International: [Gamblers Anonymous](https://www.gamblersanonymous.org/) lists support groups
by country.

If you are having thoughts of harming yourself, please seek emergency medical help
immediately.
