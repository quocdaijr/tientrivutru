# 🔮 Tiên Tri Vũ Trụ

*Thầy phán số cho con. Rồi toán học phán thầy.*

[![Oracle](https://github.com/quocdaijr/tientrivutru/actions/workflows/oracle.yml/badge.svg)](https://github.com/quocdaijr/tientrivutru/actions/workflows/oracle.yml)
[![CI](https://github.com/quocdaijr/tientrivutru/actions/workflows/ci.yml/badge.svg)](https://github.com/quocdaijr/tientrivutru/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)
[![Ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://docs.astral.sh/ruff/)
[![tests](https://img.shields.io/badge/tests-1019%20passing-brightgreen.svg)](tests/)
[![draws analysed](https://img.shields.io/badge/draws%20analysed-31%2C470-informational.svg)](#kết-quả-tầng-thật-trên-dữ-liệu-thật)
[![chi-square](https://img.shields.io/badge/chi²%20p--value-0.10%20→%20random-informational.svg)](#kết-quả-tầng-thật-trên-dữ-liệu-thật)
[![prediction accuracy](https://img.shields.io/badge/prediction%20accuracy-0%25-critical.svg)](DISCLAIMER.md)
[![expected ROI](https://img.shields.io/badge/expected%20ROI-−86%25-critical.svg)](DISCLAIMER.md)
[![kien thiet ROI](https://img.shields.io/badge/vé%20kiến%20thiết%20ROI-−50%25%20(chính%20xác)-critical.svg)](#vé-số-kiến-thiết--con-số-duy-nhất-không-phải-ước-lượng)
[![status](https://img.shields.io/badge/status-satire-ff69b4.svg)](DISCLAIMER.md)

**🇬🇧 English → [README.en.md](README.en.md)**

---

> ## ⚠️ ĐỌC CÂU NÀY TRƯỚC
>
> ### Trang này không dự đoán được xổ số. Không phần mềm nào làm được.
>
> Đây là một **thí nghiệm đốt token AI**. Mọi con số ở đây là ngẫu nhiên, và trang tự công
> khai chứng minh điều đó bằng chi-square trên 31.470 kỳ quay.
>
> - **Không bán gì** — không thu tiền, không tài khoản, không quảng cáo
> - **Không liên quan Vietlott** — không liên kết, không tài trợ, không uỷ quyền
> - **Dữ liệu từ mirror bên thứ ba**, có thể sai hoặc thiếu — cần chính xác thì tra [vietlott.vn](https://vietlott.vn)
> - **18+**
> - **Tự chịu rủi ro** — phần mềm cung cấp NGUYÊN TRẠNG, mọi tổn thất là của riêng bạn
>
> 📄 Đầy đủ: [**DISCLAIMER.md**](DISCLAIMER.md)

---

## Vì sao repo này tồn tại

Nói thật: **để số token AI đã đốt không đi đâu mất.**

Đây là sản phẩm phụ của một cuộc thí nghiệm code bằng AI. Thay vì để hàng triệu token trôi
vào hư không, chúng biến thành một thứ chạy được, có test, và tự giễu chính nó.

Giá trị thật duy nhất của repo nằm ở **Tầng Thật** — phần thống kê chứng minh xổ số là ngẫu
nhiên, trên dữ liệu thật của 7 nguồn xổ số, 36 đài và 2 quốc gia. Phần còn lại là một ông
thầy bói vỉa hè bằng code.

Con vào đây tìm số để đánh thì thầy nói luôn: số ở đây ngẫu nhiên **đúng bằng** số con tự
bốc. Khác biệt duy nhất là trang này **thừa nhận điều đó**.

## Hai tầng

**Tầng Thật** — thống kê tử tế: tần suất, khoảng cách (gap), kiểm định chi-square so với
phân phối đều. Kết quả dự kiến: `p >> 0.05`, tức là *chả có gì cả*. Và nó in ra đúng như thế.

**Tầng Tà Đạo** — oracle sinh 12 số Vietlott, và **một tấm vé 6 chữ số cho mỗi đài kiến
thiết**, từ "tín hiệu vũ trụ": thần số học ngày quay, giá BTC, nhiệt độ Hà Nội, ngày âm
lịch, con giáp, và nghiệp báo của kỳ trước. Zero giá trị dự báo. 100% giá trị giải trí.

## Thứ làm project này trung thực

Mỗi lời tiên tri sinh **deterministic** từ `sha256(version|game|draw_id|date|signals)` và
được ghi vào `data/predictions.jsonl` **trước** khi kỳ đó quay. Chạy lại ra đúng số cũ.
Không thể sửa hồi tố. Nhờ vậy Bảng Phong Thần mới có ý nghĩa.

## Dùng

```bash
uv sync

uv run tientrivutru ingest --check-gaps      # tải kết quả; tự vá từ vietlott.vn khi mirror lag
uv run tientrivutru stats                    # Tầng Thật: chi-square + phán quyết (mọi nguồn)
uv run tientrivutru oracle                   # Tầng Tà Đạo: 12 số Vietlott + mỗi đài một vé
uv run tientrivutru score                    # dựng lại Bảng Phong Thần
uv run tientrivutru backtest --game mega645  # tiên tri lại toàn bộ lịch sử → ROI
uv run tientrivutru today                    # dashboard kỳ quay tới
uv run tientrivutru site                     # sinh site/data.json cho trang tĩnh
uv run tientrivutru notify --kind prophecy   # đẩy 12 số + vé lên Telegram
uv run tientrivutru pulse --plan             # giờ nào hôm nay sẽ có tin random
uv run tientrivutru pulse --force --dry-run  # xem thử một thẻ, không gửi gì
```

Xổ số kiến thiết đi chung mọi lệnh trên. `--region {mb,mn,mt}` thu hẹp về một miền, và
**chỉ** miền đó — không kéo theo bốn game bóng:

```bash
uv run tientrivutru ingest --region mn --since 2026-08-01   # kéo hẹp một khoảng
uv run tientrivutru ingest --backfill                       # toàn bộ lịch sử 3 miền, resume được
uv run tientrivutru stats --region mt                       # chi-square riêng miền Trung
uv run tientrivutru backtest --region mn                    # phán lại 10.654 vé → ROI
```

`--backfill` đi theo **trang tuần** của minhngoc: một request trả về cả tuần của một miền
(22 bảng cho miền Nam), rẻ hơn khoảng ba mươi lần so với hỏi từng đài từng ngày. Tuần nào
đã đủ dữ liệu thì bỏ qua, không gửi request — chạy lại giữa chừng là an toàn.

Xem trang tĩnh:

```bash
uv run tientrivutru site && python3 -m http.server -d site 8000
```

Telegram cần `TELEGRAM_BOT_TOKEN` và `TELEGRAM_CHAT_ID` (GitHub Secrets khi chạy CI).
Thiếu biến thì `notify` báo lỗi rõ ràng, còn pipeline dữ liệu **không bao giờ** bị ảnh hưởng.

### Tin random trong ngày — `tientrivutru pulse`

Ngoài hai mốc cố định (10h: 12 số, 18h45: kết quả), `pulse` gửi **2–3 tin/ngày vào giờ bất
kỳ trong 8h–22h VN**, mỗi tin một thẻ: nóng/lạnh, chi-square, số lâu chưa ra, lịch + jackpot +
giá bao 12, Bảng Phong Thần, một lời sấm, kiến thiết cả ba miền, vé thầy phán,
tín hiệu vũ trụ, **giá vàng**, **giá crypto**, và lá số cá nhân.

#### Giá vàng: đơn vị là chỗ dễ sai nhất

PNJ công bố **nghìn đồng mỗi chỉ**; người ta nói chuyện bằng **đồng mỗi lượng**; một lượng là
mười chỉ. Nghĩa là câu trả lời sai nằm đúng một số 0 cạnh câu trả lời đúng, mà 15 triệu/lượng
trông không kém hợp lý hơn 150 triệu với ai không cầm miếng vàng trong tay. Phép đổi nằm ở
đúng một chỗ (`sources/markets.py`), và `tests/test_markets.py` chốt nó từ **hai đầu**: khớp
với con số webgia.com công bố bằng đồng, và khớp bậc độ lớn với giá vàng thế giới quy đổi độc
lập.

Thẻ vàng nói thêm hai con số ít ai để ý: **chênh mua–bán** (~2%, mất ngay lúc mua) và
**premium nội địa** so với vàng thế giới quy đổi (~3%). Tỷ giá dùng để quy đổi là tỷ giá do
chính nguồn giá ngụ ý, không phải tỷ giá ngân hàng, và được ghi rõ như vậy — thiếu tỷ giá thì
**bỏ hẳn dòng premium** chứ không đoán.


Giờ gửi là random nhưng **không phải bất định**: kế hoạch của một ngày sinh ra từ seed
`sha256(ngày)`, nên `pulse.yml` chạy mỗi giờ mà không cần state file — 12 lần thức dậy còn lại
thoát 0 và không gửi gì. Một ngày không lặp lại cùng một *loại* thẻ. Bấm `workflow_dispatch`
là gửi ngay, không đợi tới giờ.

Khung giờ cắt thành `n` dải bằng nhau (2 tin → 8–14h và 15–22h; 3 tin → 8–12h, 13–17h, 18–22h),
mỗi dải bốc uniform một giờ. Cách này giữ phân bố giờ **phẳng** (lệch 1,14× trên 3650 ngày);
đổi lại, hai tin có thể rơi sát nhau qua ranh dải, khoảng 15% số ngày. Bản trước ép "cách nhau
≥ 3h" và **chính ràng buộc đó** làm 8h với 22h xuất hiện 1,55× nhiều hơn 20h — vì uniform trên
*tập kế hoạch hợp lệ* không phải uniform trên *giờ*.

Lá số cá nhân đọc từ `TIENTRIVUTRU_BIRTH_DATE` (kèm `TIENTRIVUTRU_GENDER`, `TIENTRIVUTRU_NAME` tuỳ chọn) và
chỉ ở dạng secret. Job `pulse` có `permissions: contents: read` — nó không commit gì cả, và
thông báo lỗi chỉ gọi tên biến chứ không in giá trị, vì log Actions là công khai. Nguyên tắc
[không thu thập PII](#cá-nhân-hoá--và-vì-sao-không-có-đăng-ký) vẫn nguyên: ngày sinh không nằm
ở đâu trong repo này.

## Bốn bộ da

Trang có bốn bộ da đổi được ngay trên nav, lưu ở `localStorage`:

| | giấy | chữ hiển thị | tinh thần |
|---|---|---|---|
| **Vé Số** (mặc định) | giấy ngả vàng | Bungee | vé số vỉa hè, mực riso đỏ |
| **Thần Tài** | đỏ sẫm | Playfair Display | bàn thờ, chữ nhũ vàng |
| **Vỉa Hè** | gần đen | Anton | brutalist, phosphor xanh |
| **Y2K** | tím | Bungee Shade | diễn đàn lô đề đầu 2000 |

Một cấu trúc, bốn bộ da. Mọi màu và font đều qua token trong `site/tokens.css` — không có
giá trị thô nào trong trang. Mọi bề mặt chữ đạt **AA 4.5:1 ở cả bốn bộ da** (thấp nhất 4.56),
đo bằng canvas chứ không ước lượng.

Font display đều đã kiểm có **glyph tiếng Việt** — nhiều font đẹp thì không, và dùng nhầm là
vỡ sạch dấu.

## Cá nhân hoá — và vì sao không có đăng ký

Trang có **Oracle Tử Vi**: nhập ngày sinh (tuỳ chọn thêm tên và giới tính), nhận 12 số riêng
tính từ can chi, nạp âm ngũ hành, cung hoàng đạo, thần số học, sao chiếu mệnh, tam hợp và
tứ hành xung — kèm bảng so kè giữa **số tử vi của bạn**, **oracle nhà cái** và **mức ngẫu
nhiên thuần**.

> **🔒 Không có đăng ký, không có tài khoản, không có server.** Ngày sinh, tên và giới tính
> chỉ nằm trong `localStorage` của trình duyệt. Không request nào mang chúng đi đâu. Nút
> "Xoá dữ liệu" xoá sạch.

Đây là quyết định kiến trúc, không phải sự lười: repo này **commit dữ liệu vào git public**
làm audit trail, nên dữ liệu cá nhân tuyệt đối không được chạm vào đường dữ liệu — git
history thì không xoá được. Mà toàn bộ phần vui đều suy ra được từ mỗi ngày sinh, nên chẳng
cần thu thập gì cả.

Trình duyệt **không** cài lại thuật toán âm lịch: Python sinh sẵn bảng tra (ngày Tết, can
chi, nạp âm mỗi năm 1929–2035) nhúng vào `site/data.json`. Có test đối chiếu chéo chạy
`site/personal.js` thật qua Node để đảm bảo JS và Python không bao giờ lệch nhau.

## Nguồn dữ liệu

| Nguồn | Dùng làm gì | Quy mô |
|---|---|---|
| [`thanhnhu/vietlott`](https://github.com/thanhnhu/vietlott) (MIT) | Nguồn chính — Power 6/55 & Mega 6/45 | 1386 + 1353 kỳ, từ 2017 |
| `vietlott.vn` | Dự phòng khi mirror lag (chỉ lấy được kỳ mới nhất) | — |
| `vietlott.vn` (cùng trang đó) | Giá trị nồi + các hạng giải theo từng kỳ | 2 game |
| [`minhngoc.net.vn`](https://www.minhngoc.net.vn) | Bảng giải xổ số kiến thiết cả 3 miền — Tầng Thật, phán vé, tín hiệu vũ trụ | 26.409 bảng, 36 đài, MB từ 2005 · MN/MT từ 2017 |
| [`khiemdoan/vietnam-lottery-xsmb-analysis`](https://github.com/khiemdoan/vietnam-lottery-xsmb-analysis) (MIT) | **Nhân chứng đối chiếu** cho XSMB — không còn là nguồn ingest | 7526 kỳ, từ 2005 |
| [`jbaranski/jeffs-lottery-utils`](https://github.com/jbaranski/jeffs-lottery-utils) (MIT) | Powerball & Mega Millions — chỉ để thống kê | 1395 + 918 kỳ |
| CoinGecko / Open-Meteo | Tín hiệu vũ trụ (BTC, thời tiết) | — |
| [Binance](https://www.binance.com/) | Nến BTC/USDT cho trang trader — REST + WebSocket, gọi tại trình duyệt, không commit | 1000 cây/lần tải |

`data.ny.gov` (nguồn "chính thống" hay được nhắc tới) **không dùng được**: cả domain trả
403 từ mạng này, kể cả trang HTML thường, có hay không có header browser.

Game Mỹ **chỉ để thống kê** — không tiên tri, không bao 12, không Bảng Phong Thần. Bao 12
là sản phẩm của Vietlott; mục đích duy nhất của data Mỹ là cho Tầng Thật chỉ ra rằng xổ số
Mỹ cũng ngẫu nhiên y như vậy.

### Con số nồi là gì, và không là gì

Trang kết quả ghi giá trị Jackpot **tại kỳ đã quay** — và đó là con số duy nhất một request
HTTP thuần lấy được: vietlott.vn phát ước tính cho kỳ **sắp tới** qua JavaScript, còn các
trang chủ/`choi-ngay` trả về một vỏ 18 KB không có dữ liệu nào.

Nên khi không ai trúng, trang ghi **"ít nhất X"**, vì nồi kỳ sau là X cộng thêm tiền vé bán
ra. Nó không bao giờ ghi "giải đang X". Nó cũng luôn nói rõ tiền đó của **kỳ nào**: nếu lượt
đọc giải thất bại, con số còn lưu thuộc về một kỳ cũ hơn — và một con số cũ mang nhãn hiện
tại đúng là thứ repo này dựng ra để không in.

Phép tính của Bảng Phong Thần **không đổi**. Các hạng cố định đúng là cố định — trang live
xác nhận 40.000.000 / 500.000 / 50.000 cho Power, khớp `games.py` — và nồi thì vốn đã bị loại
khỏi `roi_excluding_jackpot` chính vì nó biến động. Giờ có test bắt bảng tĩnh phải khớp bảng
live, nên upstream đổi giá là nó văng lỗi chứ không im.

### Sáu số hay mười hai? Cả hai — và giờ trang nói rõ số nào là số nào

Vé Vietlott thường — "Cách chơi: **Cơ bản**" trong app — là **6 số, 10.000đ**. Bao 12 là
lựa chọn thật, không phải em nghĩ ra: trang giới thiệu sản phẩm của Vietlott liệt kê **11 mức
bao** (5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18) và ghi giá một bộ số là 10.000đ, nên
`C(12,6) = 924` tổ hợp = 9.240.000đ là đúng. Các trang tổng hợp bên ngoài hay ghi sai — có bài
liệt kê 7 mức rồi lại nói "11 loại" ngay trong cùng bài — nên chỉ trang gốc được tin.

Trước đây trang chỉ đưa 12 số, tức là ai mua vé Cơ bản phải **tự đoán đánh 6 số nào**. Giờ có
cả hai, và có luôn **ranh giới**: một kỳ điển hình chỉ boost 1–3 số trong 12, phần còn lại
đứng đúng cùng một mức — nên chỉ đúng bấy nhiêu số là có lý do, số còn lại lấy từ thế hoà, và
trang nói thẳng ra.

Hoà thì phá bằng seed của lời tiên tri, **không** theo số tăng dần. Đo ra chứ không chọn cho
đẹp: xếp hoà tăng dần làm 6 số cơ bản có trung bình **20,79** so với **28,52** của bộ 12 —
lệch **7,7** về số nhỏ, sinh ra hoàn toàn bởi cách phá hoà. Ship một quy luật giả thì phá sạch
lý do tồn tại của repo này.

### Hôm nay trúng thì thực nhận bao nhiêu?

Con số ước tính nồi **kỳ tới** không có ở bất kỳ trang nào một request thuần lấy được.
Nhưng câu này thì có — và nó chính là câu mà con số jackpot làm người ta muốn hỏi, nên
trang trả lời bằng số học chứ không bằng một con số nó không có.

Mega 6/45, bao 12 tốn 9.240.000đ:

| trúng | 1 trên | thực nhận | lãi/lỗ |
|---|---|---|---|
| 3 | 7 | 2.520.000đ | −6.720.000đ |
| 4 | 31 | 15.120.000đ | **+5.880.000đ** |
| 5 | 312 | 112.000.000đ | **+102.760.000đ** |
| 6 | 8.815 | 24.946.610.500đ | **+24.937.370.500đ** |

Bảng buộc phải có **cả hai nửa**. Riêng cột tiền đọc ra thành lời khuyên nên chơi — trúng 4
số đã có lãi thật. Riêng cột xác suất đọc ra thành "giải bèo", mà giải không hề bèo. Chỉ khi
đứng cạnh nhau chúng mới nói đúng: tiền là thật, và xác suất là thứ lấy lại. Trúng 4 trở lên
xảy ra khoảng **1 trên 28 kỳ** — đó là chỗ −71,57% đi ra.

## Trang tài chính — `/tai-chinh.html`

Trang thứ hai, cùng hai tầng: thầy phán một quẻ về chợ, rồi trang tự nói quẻ đó đáng giá
bao nhiêu. Vàng (miếng SJC + nhẫn trơn), chỉ số ba sàn, giao dịch khối ngoại, và crypto.

Khác trang xổ số ở đúng một chỗ: **không có Python nào tham gia**. Không nguồn, không
store, không bundle, không cron. Trình duyệt gọi thẳng năm API, và **không con số nào được
commit vào repo**.

| Khối | Nguồn | Độ tươi thật |
|---|---|---|
| Vàng trong nước | PNJ | Giá niêm yết, đổi vài lần/ngày |
| Vàng thế giới | gold-api.com | Realtime |
| Chỉ số + khối ngoại | VNDIRECT | **Cuối phiên (EOD)** |
| Crypto | CoinGecko | Realtime, 24/7 |

Ba điều trang nói thẳng thay vì giấu:

**Không phải realtime.** Realtime thật của HOSE/HNX đi qua websocket SignalR và bán theo
hợp đồng vendor; nguồn duy nhất có tài liệu (SSI FastConnect) bắt ra quầy ký giấy. Nên số
chứng khoán ở đây là cuối phiên, và trang in dấu thời gian gốc của API chứ không phải giờ
tải trang. Cuối tuần nó ghi rõ *"phiên gần nhất"*.

**Không lưu gì cả.** Mọi endpoint giá dùng được đều là API nội bộ không kèm điều khoản nào.
Luật repo đã có sẵn: *không có licence xác minh được thì không vào repo*. Nên trang fetch
tại trình duyệt và không commit. Cái giá là thật: **nguồn chết là ô trống**, và trang không
dựng số cũ lên thay. Mỗi khối suy biến riêng — một API im không kéo đổ trang.

**Không có giá đất.** Định có, rồi bỏ, và lý do được in ra ngay trên trang: chỉ số giá bất
động sản của Việt Nam mới tồn tại ở dạng bản đặc tả chỉ tiêu **năm 2019 chưa từng công bố số
liệu**; cổng CSDL bất động sản quốc gia theo NĐ 94/2024 **không phân giải tên miền**; và
BIS, OECD, FRED, IMF Global Housing Watch đều **không có Việt Nam**. Bịa một con số thì dễ.
Nói rằng nó không tồn tại thì đúng.

> Trang này **không phải tư vấn đầu tư**. Quẻ ở chặng 00 là một phép cộng chữ số, giá trị
> dự báo bằng **không** — đúng như oracle xổ số. Xem [DISCLAIMER.md](DISCLAIMER.md) mục 2.

## Trang trader — `/trader.html`

Trang thứ ba, cùng hai tầng, nhưng có một thứ hai trang kia không có: **chặng im lặng chấm
điểm chặng ồn ào, trên đúng dữ liệu của chặng ồn ào, ngay trong lúc người đọc đang nhìn.**

Biểu đồ nến BTC/USDT chạy thật — REST của Binance cho 1000 cây lịch sử, WebSocket cho cây
đang chạy. Không khoá API, không proxy. Đây là chỗ duy nhất trên cả site có realtime thật,
và lý do rất tầm thường: crypto chạy 24/7 còn Binance mở API miễn phí, trong khi realtime
chứng khoán Việt đi qua SignalR bán theo hợp đồng vendor.

Thầy dạy con đọc nến, dạy MA20 và RSI14, gọi tên năm mẫu hình. Rồi chặng `02 · SỰ THẬT` đo
chính năm mẫu hình đó.

**Cách đo đúng, sau khi cách hiển nhiên hoá ra sai.** Ý đầu tiên là đếm mẫu hình trên nến
thật rồi so với nến ngẫu nhiên. Nó hỏng theo hai kiểu cùng lúc: doji và nến búa là tính chất
của **một** cây nến đứng riêng, nên xáo thứ tự cho ra **đúng** con số cũ — rỗng theo định
nghĩa; còn hai mẫu nhiều cây thì lệch thật, nhưng cái lệch đó nói rằng thị trường có những
đoạn biến động dồn cục, không nói rằng mẫu hình báo trước được gì.

Thứ trả lời đúng câu hỏi là **lợi suất cây nến kế tiếp**: sau mỗi lần một mẫu nổ, lấy lợi
suất mở-đến-đóng của cây ngay sau, so với nền chung, p-value bằng hoán vị 2000 lần. Trên
6000 cây nến 1 giờ, cả năm mẫu đều nằm trong nhiễu (p từ 0,21 đến 0,65), kể cả trước hiệu
chỉnh Bonferroni. Và lợi thế **lớn nhất đo được** nhỏ hơn phí taker vào-ra của chính sàn đó
**một bậc**.

Một chi tiết được giữ lại vì nó là bài học tự thân: ở mẫu 1000 cây, "nhấn chìm" từng ra
p = 0,038 — trông như một phát hiện. Kéo lên 6000 cây thì nó tan. Trang in cả ngưỡng
Bonferroni lẫn số phép thử, và nói thẳng điều đó.

Hai con số trang **không** tự đo được, nên đi mượn và ghi rõ của ai:

| Con số | Nguồn |
|---|---|
| **74–89%** tài khoản bán lẻ CFD lỗ, lỗ bình quân 1.600–29.000 EUR | ESMA35-43-1135, phân tích của các NCA thành viên EU |
| **97%** người trụ trên 300 phiên vẫn lỗ; chỉ **0,4%** kiếm hơn một giao dịch viên ngân hàng; **không** có bằng chứng học được gì | Chague, De-Losso & Giovannetti, *"Day trading for a living?"* ([SSRN 3423101](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101)) |

Cả hai là thị trường khác, không phải Việt Nam, và trang để nguyên như vậy.

Giống trang tài chính: **không một cây nến nào được commit**. Binance không kèm điều khoản
cho phép phát hành lại, nên trình duyệt fetch và tab quên. Nguồn chết là ô trống — đã thử
chặn từng đường một: mất CDN thì bảng số vẫn mang đủ dữ liệu, mất REST thì thầy **không
phán** và hai trích dẫn vẫn còn nguyên.

> Trang này **không phải tư vấn đầu tư, khuyến nghị mua bán, hay khoá học.** Giá là thật;
> mẫu hình và lời phán là trò đùa, và chặng cuối đo chính chúng để chứng minh.

### Hội đồng — TradingAgents bị chấm công khai

Chặng `02 · HỘI ĐỒNG` là một oracle nữa để bị chấm:
[TradingAgents](https://github.com/TauricResearch/TradingAgents) (Apache-2.0) — mười hai agent
LLM, bốn đọc số, hai tranh luận, một chốt, ba lo rủi ro, một duyệt — mỗi ngày ra một bậc năm mức
cho BTC, FPT, VNM, VCB. Nó chạy nguyên bản ở commit `2d17df8` (tag `v0.5.0`), cài thẳng từ git:
package `tradingagents` trên PyPI là **một dự án khác**, của người khác.

Repo chỉ ghi **bậc và giờ ghi**, append-only, vào `data/hoi_dong/verdicts.jsonl`. Không giá,
không lợi suất, không một câu tranh luận nào — tranh luận của nó trích tin Yahoo, StockTwits,
Reddit, FRED, và không nguồn nào cho phát lại. **Điểm được chấm ngay trong trình duyệt người
đọc**, bằng giá lấy từ Binance và VNDIRECT lúc mở trang: lệnh giấy trừ phí thật (BTC 0,10% mỗi
chiều; cổ phiếu 0,15% + thuế bán 0,1%), cửa sổ mở ở nến đầu tiên sau giờ ghi — nên ghi trễ chỉ
bị đẩy sang cửa sổ sau, không gian lận được. So với *luôn Buy* và *tung đồng xu* cùng cửa sổ;
p-value chỉ in khi đủ 30 phán quyết.

Hai điều trang nói thẳng: để ra bậc, Hội đồng tự đọc Yahoo Finance bằng máy, điều mà điều khoản
của Yahoo không cho phép; và chính sách LLM mỗi hãng khác nhau về chuyện tự động đăng output,
nên Hội đồng chạy trên Gemini API — hãng duy nhất trong bốn không đòi duyệt từng cái — gói miễn phí, mỗi ngày 19:10 giờ VN. Trên gói miễn phí, trần là hạn mức của Google (vượt thì bị chặn, không bị tính tiền); nếu
chuyển sang trả phí thì có trần đô cứng — chạm trần thì ngày đó ghi `skipped_budget` chứ không
im lặng.

## Kết quả Tầng Thật trên dữ liệu thật

Kiểm định chi-square, H₀ = "mọi số đồng xác suất":

| Nguồn | Kỳ / bảng | Lượt số | χ² | df | p-value | Bác bỏ H₀? |
|---|---:|---:|---:|---:|---:|---|
| Power 6/55 | 1.388 | 8.328 | 52,66 | 54 | **0,5263** | không |
| Mega 6/45 | 1.356 | 8.136 | 31,96 | 44 | **0,9115** | không |
| Powerball (US) | 1.397 | 6.985 | 78,93 | 68 | **0,1716** | không |
| Mega Millions (US) | 920 | 4.600 | 60,33 | 69 | **0,7625** | không |
| Kiến thiết Miền Nam (21 đài) | 10.654 | **191.772** | 117,39 | 99 | **0,1002** | không |
| Kiến thiết Miền Trung (14 đài) | 8.220 | **147.960** | 92,07 | 99 | **0,6760** | không |
| Kiến thiết Miền Bắc (1 đài) | 7.535 | **203.445** | 106,13 | 99 | **0,2938** | không |

Bảy nguồn độc lập, **36 đài**, hai quốc gia, **571.226 lượt số**, 21 năm dữ liệu — và
**không một nguồn nào** bác bỏ được giả thuyết ngẫu nhiên. Con số nào trông "nóng" cũng chỉ
là nhiễu.

Với kiến thiết, không gian số là **hai chữ số cuối của cả 18 (hoặc 27) giải trên bảng** —
đúng cái không gian 00–99 mà dân đánh lô soi hàng ngày.

## Vé số kiến thiết — con số duy nhất không phải ước lượng

Mọi con số khác trong repo này là một mẫu: một p-value dao động, một ROI paper-trading nhảy
theo may rủi. **Cơ cấu giải xổ số kiến thiết miền Nam / miền Trung thì không.**

Một đài phát hành **1.000.000 vé × 10.000đ = 10 tỷ doanh thu**. Bảng giải trả ra:

| Giải | Trùng | Số vé trúng / 1tr | Giá trị | Tổng |
|---|---|---:|---:|---:|
| Đặc biệt | 6 số | 1 | 2.000.000.000 | 2.000.000.000 |
| Phụ đặc biệt | sai chữ số **đầu** | 9 | 50.000.000 | 450.000.000 |
| Khuyến khích | sai 1 trong **5** số còn lại | 45 | 6.000.000 | 270.000.000 |
| Nhất | 5 số cuối | 10 | 30.000.000 | 300.000.000 |
| Nhì | 5 số cuối | 10 | 15.000.000 | 150.000.000 |
| Ba (×2) | 5 số cuối | 20 | 10.000.000 | 200.000.000 |
| Tư (×7) | 5 số cuối | 70 | 3.000.000 | 210.000.000 |
| Năm | 4 số cuối | 100 | 1.000.000 | 100.000.000 |
| Sáu (×3) | 4 số cuối | 300 | 400.000 | 120.000.000 |
| Bảy | 3 số cuối | 1.000 | 200.000 | 200.000.000 |
| Tám | 2 số cuối | 10.000 | 100.000 | 1.000.000.000 |
| | | | **Tổng** | **5.000.000.000** |

5 tỷ trên 10 tỷ. **ROI kỳ vọng của một tấm vé là −50,00%**, và đó không phải ước lượng —
đó là phép cộng. Test [`test_kienthiet_prizes.py`](tests/test_kienthiet_prizes.py) chấm cả
**1.000.000 vé** trên một bảng thật và bắt tổng chi trả phải bằng đúng 5 tỷ.

Thầy phán mỗi đài một vé, ghi vào `data/ve.jsonl` **trước** khi đài quay. Backtest lại toàn
bộ lịch sử:

| Miền | Vé đã chấm | Vé trúng gì đó | ROI thực tế | ROI lý thuyết |
|---|---:|---:|---:|---:|
| Miền Nam | 10.654 | 116 | **−86,77%** | −50,00% |
| Miền Trung | 8.015 | 97 | **−81,53%** | −50,00% |

Lệch khỏi −50% không phải lỗi: **giải đặc biệt chiếm 40% quỹ giải** và về một lần trên một
triệu vé, nên gần hai vạn vé vẫn chưa đủ để nó xuất hiện. Bỏ ĐB và phụ ĐB ra, mức hội tụ
đúng là **−74,50%** — và đó là con số repo in ra cạnh con số thực tế, thay vì giấu đi.

> Miền Bắc **không** được phán vé. Vé XSMB có ký hiệu, cơ cấu giải đổi năm 2017 rồi đổi
> tiếp 01/04/2025, và giải đặc biệt chia cho nhiều vé — không có một ROI trung thực nào
> trải được suốt 21 năm. Miền Bắc ở lại Tầng Thật, và repo nói thẳng ra điều đó.

## Lịch quay

- **Power 6/55** — 18h thứ 3, thứ 5, thứ 7
- **Mega 6/45** — 18h thứ 4, thứ 6, chủ nhật
- **XSMB** — 18h15 hàng ngày
- **Kiến thiết Miền Nam** — 16h15 hàng ngày, 3 đài (thứ Bảy 4 đài)
- **Kiến thiết Miền Trung** — 17h15 hàng ngày, 2–3 đài

Lịch từng đài **không hardcode**: `kienthiet.schedule_from()` suy ra từ 8 tuần gần nhất
trong chính kho dữ liệu, nên đài đổi ngày thì code tự theo.

## Tài nguyên hình ảnh

Toàn bộ **tự host trong repo** — trang không gọi một request nào ra ngoài để lấy ảnh hay emoji.

Ngoài font, cả site gọi ra ngoài đúng **một** script: thư viện vẽ nến trên `/trader.html`, tải
từ CDN, ghim theo cả phiên bản lẫn hash SRI, và ghi công ở footer trang đó vì NOTICE của
Apache-2.0 yêu cầu thế. Nếu nó không tải được thì bảng số của trang vẫn mang đủ dữ liệu.
Chi tiết từng file, kèm ngày tải và cả danh sách nguồn *đã cân nhắc rồi loại*, ở
[`site/img/CREDITS.md`](site/img/CREDITS.md).

| Thứ | Nguồn | Giấy phép |
|---|---|---|
| Tranh khắc gỗ Đông Hồ *Đại Cát* | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Dong_Ho_painting_-_Dai_cat.jpg) | Public domain |
| 13 emoji | [jdecked/twemoji](https://github.com/jdecked/twemoji) — © Twitter/X | đồ hoạ **CC-BY 4.0**, code MIT |
| Hình thầy bói (7 dáng) | vẽ tay trong repo này, `site/thay.js` | MIT, cùng repo |
| TradingView Lightweight Charts™ v5.2.1 | [tradingview/lightweight-charts](https://github.com/tradingview/lightweight-charts) — © TradingView, Inc. | **Apache-2.0, bắt buộc ghi công** |

Repo này là MIT, tức là ai clone cũng được cấp lại quyền phát hành. Nên nó **không thể** chứa
thứ nó không sở hữu: meme nhân vật có bản quyền, ảnh chụp phim, hay ảnh lấy từ mạng xã hội đều
bị loại — không phải vì khó tìm, mà vì không có giấy phép. Cũng đã loại **OpenMoji**: nó là
CC-BY-**SA**, copyleft, xung đột với MIT.

## Giấy phép & miễn trừ trách nhiệm

[MIT](LICENSE) — phần mềm cung cấp **NGUYÊN TRẠNG**, không bảo đảm dưới bất kỳ hình thức nào.
Giấy phép MIT áp cho **code**; tài nguyên bên thứ ba giữ giấy phép riêng, xem bảng trên.

Bản miễn trừ đầy đủ (song ngữ): [**DISCLAIMER.md**](DISCLAIMER.md)

Con dùng cái này để đánh xổ số rồi thua thì đó là quyết định của con, không phải của thầy,
và càng không phải của repo.

### Nếu cờ bạc đang là vấn đề

*Phần này thầy không nói. Đây là chuyện thật.*

Việt Nam **không có** đường dây nóng riêng cho nghiện cờ bạc. Nguồn miễn phí có thật gần nhất
là [Đường dây nóng Ngày Mai](https://duongdaynongngaymai.vn/hotline/) — **096.306.1414**,
13:00–20:30 T4–CN. Đó là hỗ trợ **khủng hoảng tâm lý**, không phải chuyên về cờ bạc, nhưng họ
lắng nghe và không phán xét.
