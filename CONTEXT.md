# CONTEXT — Glossary

Từ vựng chuẩn của project. Đây **chỉ** là glossary — không chứa chi tiết triển khai,
không phải spec, không phải scratch pad.

## Thuật ngữ

**Kỳ quay** (Draw) — Một lượt quay số đã hoàn tất. Danh tính là cặp `(game, draw_id)`.
`draw_id` luôn là chuỗi 5 chữ số zero-pad (`01386`), không bao giờ là số nguyên trần.

**Bộ số chính** (Main) — 6 số được quay ra. Luôn sắp xếp tăng dần.

**Số phụ** (Bonus) — Số thứ 7, **chỉ** Power 6/55 có. Không thuộc bộ số chính và không
bao giờ trùng với số chính. Chỉ dùng để xác định Jackpot 2.

**Vé Cơ bản** — Một vé Vietlott thường: **6 số, 10.000đ**. Đây là "Cách chơi: Cơ bản"
trong app, và là cách phần lớn người chơi mua. Trang **phải** phục vụ chế độ này, không chỉ
bao 12 — thiếu nó thì trang đưa 12 số cho một tờ vé 6 ô rồi bỏ người đọc tự đoán.

**Sáu số cơ bản** (`basic_pick`) — 6 trong 12 số, xếp theo weight của chính oracle. Kèm
`basic_reasoned`: **bao nhiêu số trong đó thật sự có lý do**. Con số này bắt buộc phải hiện,
vì một kỳ điển hình chỉ boost 1–3 số trong 12, phần còn lại đứng đúng cùng một mức. Trình
bày cả sáu như thể đều có căn là bịa ra thứ tự không tồn tại.

Hoà thì **phá bằng seed**, không phải theo số tăng dần. Đo ra chứ không phải chọn cho đẹp:
xếp hoà tăng dần làm 6 số cơ bản có trung bình 20,79 so với 28,52 của bộ 12 — **lệch 7,7 về
số nhỏ**, sinh ra hoàn toàn bởi cách phá hoà. Ship một quy luật giả là đúng thứ project này
dựng ra để bóc.

**Bao 12** (Wheel-12) — Cách chơi chọn 12 số rồi đánh toàn bộ `C(12,6) = 924` tổ hợp.
Một kỳ bao 12 cho một game = 9.240.000đ. Đây là **sản phẩm thật**: trang giới thiệu sản phẩm
của Vietlott liệt kê 11 mức bao — 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18 — và giá một bộ số
là 10.000đ. Mấy trang tổng hợp ngoài thường ghi thiếu (liệt kê 7 mức rồi lại nói "11 loại"),
nên nguồn duy nhất được tin là trang gốc.

**Lời tiên tri** (Prophecy) — 12 số mà oracle cam kết cho một kỳ **chưa quay**, được ghi
lại **trước** thời điểm quay. Sinh deterministic từ seed. Append-only, không sửa được.

**Tầng Thật** (Honest layer) — Thống kê trung thực: tần suất, khoảng cách, chi-square.
Kết luận thường là "không có gì cả", và nó được in ra đúng như vậy.

**Tầng Tà Đạo** (Cursed layer) — Oracle sinh 12 số từ tín hiệu vũ trụ. Giá trị dự báo
bằng không. Đây là phát biểu về sự thật, không phải sự khiêm tốn.

**Tín hiệu vũ trụ** (Cosmic signal) — Một đại lượng có thật (giá BTC, nhiệt độ Hà Nội,
ngày âm lịch, con giáp) được oracle dùng làm cớ. `None` nghĩa là tín hiệu im lặng —
không lấy được — và oracle vẫn phải chạy bình thường.

**Nghiệp báo** (Karma) — Quy tắc tà đạo: số vừa làm số phụ kỳ trước bị giảm trọng số.

**Bảng Phong Thần** (Scoreboard) — Đối chiếu lời tiên tri với kết quả thật: tỉ lệ trúng
so với mức ngẫu nhiên, tiền đốt, tiền thắng, ROI.

**Đốt giấy** (Paper burn) — Tiền **giả định** đã tiêu. Toàn bộ project là paper-trading;
không có dòng nào liên quan tới tiền thật.

**ROI bỏ jackpot** (Jackpot-free ROI) — ROI tính khi loại các giải jackpot. Chỉ số hạng
nhất, không phải phụ lục: một kỳ trúng jackpot trong ~1350 kỳ đủ để đẩy ROI từ −86% lên
dương, trong khi tỉ lệ trúng vẫn đúng bằng mức ngẫu nhiên.

**Backtest** — Chạy lại oracle trên lịch sử. **Phản thực** (counterfactual): không phải
tiên tri đã cam kết, và không bao giờ được ghi vào `predictions.jsonl`.

**Game đánh được bao 12** (wheel-playable) — Game có cơ cấu giải và giá vé để định giá bao
12, tức là Vietlott. Chỉ những game này mới có tiên tri, bao 12 và Bảng Phong Thần.

**Game chỉ thống kê** (stats-only) — Powerball và Mega Millions. Mang vào **chỉ** để Tầng
Thật chỉ ra rằng xổ số Mỹ cũng ngẫu nhiên y như Vietlott. Không tiên tri, không bao 12.

**Pool phụ riêng** (separate bonus pool) — Số phụ được quay từ dải số riêng, nên **được
phép trùng** số chính. Powerball (đỏ 1–26) và Mega Millions (vàng 1–25) là vậy: có 99 và 68
kỳ thật trùng như thế. Khác hẳn số phụ Power 6/55, quay cùng dải và không được trùng.

**Bảng giải** (Board) — Một đài xổ số kiến thiết, một ngày, **toàn bộ số in trên bảng**,
giữ nguyên dạng chuỗi và nguyên bề rộng chữ số. 18 giải cho Miền Nam / Miền Trung, 27 cho
Miền Bắc. Định danh là cặp `(ngày, đài)`. Không dùng `Draw` vì bảng giải không phải pick-N;
không dùng `XsmbDraw` vì kiểu đó vứt hết chỉ giữ hai chữ số cuối, nên **không chấm được vé**.

**Đuôi** (tail) — Hai chữ số cuối của một số trên bảng. `Board.tails` suy ra khi cần và cho
ra đúng không gian 00–99 mà Tầng Thật vẫn dùng — nên heatmap 10×10 của trang không phải sửa
một dòng nào khi thêm kiến thiết.

**XSMB** — Xổ số kiến thiết Miền Bắc. Từ nay là **view suy ra** từ `data/boards/mb.jsonl`
qua `Board.tails`; `data/xsmb.jsonl` ở lại làm **nhân chứng đối chiếu** độc lập chứ không
còn là nguồn. Kiểu `XsmbDraw` giữ nguyên chữ ký nên mọi nơi dùng nó không phải sửa: 27 giải
mỗi ngày, không gian 00–99 (**có số 0**), **cho phép trùng lặp** trong cùng một kỳ. Miền Bắc
không bao giờ sinh tiên tri và **không được phán vé** — vé có ký hiệu, cơ cấu giải đổi 2017
rồi đổi tiếp 01/04/2025, không có ROI trung thực nào trải được 21 năm.

**Vé** (VeProphecy) — Một tấm 6 chữ số, cho một đài, cho một kỳ, ghi vào `data/ve.jsonl`
**trước** khi đài quay. Có `KIENTHIET_ORACLE_VERSION` **riêng** và **không** đụng vào
`CosmicSignals` hay `ORACLE_VERSION`: thêm một tín hiệu vào oracle chung sẽ đổi mọi tiên tri
tương lai của mega645 và power655 để đổi lấy một tính năng không liên quan tới chúng.

**Ngày đài không quay** (NoDraw) — Ngày Tết, minhngoc in chữ `Tết` vào ô giải đặc biệt và
số `0` vào **mọi** ô còn lại. Parser bắt buộc phải bỏ nguyên ngày đó: nuốt 27 số `0` vào
bảng tần suất là lỗi tệ hơn một lỗ hổng, vì nó im lặng.

**Kỷ nguyên 6 chữ số** — Giải đặc biệt Miền Trung chỉ có 6 chữ số từ 01/04/2017 (Miền Nam
đã đổi trước đó). 205 bảng Miền Trung quý I/2017 vẫn nằm trong Tầng Thật nhưng **bị bỏ qua**
khi chấm vé — vé 6 số không chấm được với bảng 5 số, và đoán bừa là bịa ra một ROI.

**Upstream lag đã vá** (patched lag) — Kỳ mà mirror bỏ sót, được lấy bù từ `vietlott.vn`.
Trang chính thức **chỉ** cho kỳ mới nhất, nên chỉ vá được đúng ca lag phổ biến nhất.

**Upstream lag** — Trạng thái mirror không có gap `draw_id` nào nhưng vẫn thiếu kỳ so với
thực tế. Khác với **gap**, và cần cơ chế phát hiện riêng.

**Lá số** (Fortune) — Tập hợp suy ra được **chỉ từ ngày sinh**: can chi, con giáp, nạp âm,
mệnh ngũ hành, cung hoàng đạo, số chủ đạo, số tên, sao chiếu mệnh, tam hợp, tứ hành xung.
Là **dữ liệu dẫn xuất** — không chứa tên, không chứa ngày sinh.

**Oracle Tử Vi** (personal oracle) — Oracle riêng theo lá số, chạy **hoàn toàn trong trình
duyệt**. Khác với **oracle nhà cái** (Tầng Tà Đạo) vốn chạy trong CI và có Bảng Phong Thần
công khai.

**Chỉ-tại-máy** (local-only) — Nguyên tắc bất di bất dịch: ngày sinh, tên và giới tính nằm
trong `localStorage`, không có tài khoản, không có server, không request nào mang chúng đi.
Repo này commit dữ liệu vào git public, nên PII **không được phép** chạm vào đường dữ liệu.

**Bảng tra âm lịch** (lunar lookup table) — Bảng do Python sinh (ngày Tết + can chi + nạp âm
mỗi năm) nhúng trong `site/data.json`. Trình duyệt **không** cài lại thuật toán âm lịch; nó
tra bảng. Nhờ vậy hai bên không thể lệch nhau, và có test đối chiếu chéo qua Node.

**Trang tài chính** (`site/tai-chinh.html`) — Trang thứ hai của site. Cùng hai tầng như
trang xổ số: thầy phán một quẻ ở chặng 00, số liệu trung thực ở chặng 01, và chặng 02 nói
thẳng quẻ đó đáng giá bao nhiêu. Khác trang xổ số ở đúng một chỗ: **không có Python nào
tham gia**. Không nguồn, không store, không bundle, không cron.

**Fetch-tại-trình-duyệt** (client-only fetch) — Nguyên tắc của trang tài chính: mọi con số
do trình duyệt gọi thẳng tới nguồn, và **không con số nào được commit**. Đây là quyết định
**giấy phép**, không phải kỹ thuật — mọi endpoint giá dùng được đều là API nội bộ không có
điều khoản nào kèm theo, mà luật repo đã có sẵn là *"không có licence xác minh được thì không
vào repo"*. Cái giá phải trả là có thật và không được giấu: không có bản bake để rơi về, nên
**nguồn chết là ô trống**. Khác hẳn `Chỉ-tại-máy`, vốn nói về PII.

**Suy biến theo khối** (per-block degradation) — Một nguồn im **chỉ** được làm hỏng đúng ô
của nó, kèm tên nguồn và lý do. Không bao giờ để trang trắng, và không bao giờ dựng số cũ lên
thay. Cùng hợp đồng với `vibes.py`: tín hiệu chết trả `None`, không raise.

**Nghìn đồng mỗi chỉ** (PNJ unit) — PNJ niêm yết theo **chỉ** (3,75 g) và tính bằng **nghìn
đồng**, nên `14760` là 14.760.000 đ/chỉ = **147.600.000 đ/lượng**. Đọc nhầm thành đồng/lượng
là sai **10 lần** mà vẫn trông hợp lý. Đã đối chiếu ba đường độc lập: XAU spot quy qua tỷ giá
CoinGecko, các dòng bạc của BTMC có ghi rõ khối lượng gram, và chính giá PNJ. Vàng Việt thấp
hơn giá thế giới 10 lần là điều arbitrage không cho phép.

**Cuối phiên** (EOD) — Trạng thái thật của số liệu chứng khoán trên trang. Realtime thật của
HOSE/HNX đi qua websocket SignalR và phân phối theo hợp đồng vendor; nguồn có tài liệu duy
nhất (SSI FastConnect) bắt ra quầy ký giấy. Trang **không bao giờ** được gán nhãn "realtime"
cho số chứng khoán — dán nhãn sai chính là thứ project này dựng lên để bóc.

**Thầy / con** — Ngôi xưng hô của **mọi văn bản hướng tới người đọc**: lời sấm, README,
tagline, và câu kết mục giấy phép. Thầy bói vỉa hè, không phải trợ lý. Thầy **không bao giờ**
nói "chắc chắn trúng" — đó là câu của trang lừa đảo, và là ranh giới cứng.

Thầy **im lặng** ở ba chỗ: khối miễn trừ trách nhiệm, mọi số liệu thống kê, và mục hỗ trợ tâm
lý. Độ vênh giữa bốn chặng gào thét và ba chỗ im lặng chính là cú hài — và cũng là thứ giữ cho
project trung thực. Xoá độ vênh đó là mất cả hai.

Cách gọi người đọc, theo vùng:

| Vùng | Gọi là | Ví dụ |
|---|---|---|
| Phần diễn — lời sấm, tagline, "vì sao repo tồn tại", câu kết mục giấy phép | **con** | *"Con cứ ghi đi, đúng sai tính sau."* |
| Ba vùng thầy im lặng — miễn trừ trách nhiệm, số liệu thống kê, hỗ trợ tâm lý | **bạn** (trung tính) | *"Mọi tổn thất tài chính là của riêng bạn."* |
| Khối cam kết riêng tư | **bạn** — đây là lời hứa người đọc tin vào, không phải chỗ diễn | *"chỉ nằm trong trình duyệt của bạn"* |

**"anh" / "chị"** thì không bao giờ — đó là giọng chat giữa người viết và chủ repo, đã từng
lọt vào README một lần và phải sửa. Nó không phải giọng của project.

**Bộ da** (skin) — Một trong bốn bảng token: `veso` · `thantai` · `viahe` · `y2k`. Đổi lúc
chạy, lưu `localStorage`. Cấu trúc trang không đổi theo bộ da; chỉ token đổi.

**Chặng** (stage) — Một trong năm bước có thứ tự của trang: KHAI → TƯỚNG → PHÁN → SỔ NỢ →
SỰ THẬT. Số chặng là **cấu trúc**, không phải trang trí.

**Cạn phước** — Tiếng lóng 2026, nghĩa là hết may. Con dấu bật ở Sổ Nợ khi ROI-bỏ-jackpot
xuống dưới −0,8. Là chỗ **duy nhất** giọng thầy được chạm vào khu số liệu.

**Bộ weight tà đạo** — Các hằng `BOOST_*` là **tuỳ ý có chủ đích**. Mọi bộ weight đều cho
cùng một EV, nên đây là lựa chọn thẩm mỹ chứ không phải tối ưu. Nói ngược lại là phá chính
tính trung thực mà project dựng lên.

**Luật trùng số gốc** (digit-root rule) — Boost số có **cùng số gốc** với mục tiêu, **không
phải** chia hết. Chia hết với số gốc 1 sẽ trúng toàn bộ dải số — một luật kích hoạt với mọi
số thì không còn là luật.

**Hình thầy** — Ông thầy bói vẽ bằng nét que, bảy dáng, sống trong repo này. Dáng được
chọn theo **số trúng thật** của kỳ chấm được cao nhất, nên nó là một cách đọc số liệu chứ
không phải đồ trang trí. Vẽ lệch có chủ ý: nét hoàn hảo là dấu hiệu máy làm.

**Bản in Đại Cát** — Tranh khắc gỗ Đông Hồ, public domain, đặt cạnh ROI âm. *Đại Cát* nghĩa
là **vận may lớn**; đó là toàn bộ câu đùa. Hiện đúng **một chỗ** trên trang, và chỉ khi kỳ tốt
nhất đạt từ 5 số trở lên.

**Tự host** — Mọi ảnh và emoji nằm trong repo. Trang không gọi request ra ngoài để lấy tài
nguyên hình ảnh. Ngoại lệ duy nhất có từ trước là Google Fonts.

**Cấp lại quyền** (sublicense) — Repo MIT cấp cho người clone quyền phát hành lại. Nên repo
không được chứa thứ nó không sở hữu. Đây là lý do loại meme nhân vật có bản quyền, ảnh phim,
và ảnh lấy từ mạng xã hội — thiếu giấy phép, không phải thiếu chỗ tìm.

**Nồi** (jackpot) — Giá trị Jackpot **tại kỳ đã quay**, đọc từ trang kết quả vietlott.vn.
Không phải ước tính cho kỳ sắp tới: vietlott chỉ phát con số ước tính qua JavaScript, HTML
thuần không có. Vì vậy trang **không bao giờ** gọi nó là "giải đang", chỉ gọi là nồi của
kỳ nào.

**Cộng dồn** (rolled over) — Hạng cao nhất của kỳ đó không ai trúng, nên nồi chuyển sang kỳ
sau. Đây là lý do câu duy nhất đúng là **"ít nhất X"**: kỳ sau sẽ là X cộng thêm tiền vé
bán ra. Trúng rồi thì nồi về mức sàn, và trang phải nói ra chuyện đó chứ không im.

**Khớp kỳ mới nhất** (`matches_latest_draw`) — Cờ so `draw_id` của số liệu giải với kỳ mới
nhất đã lưu. Nếu lượt đọc giải thất bại, con số còn lại thuộc về một kỳ cũ hơn; giấu nó thì
mất thông tin, mà trưng nó như số hiện tại thì là nói dối. Cờ này để trang nói rõ tiền đó
của kỳ nào.

**Mức sàn** (`jackpot_floor`) — Giá trị nồi reset về sau khi có người trúng. Cũng là ngưỡng
để bắt lỗi bóc dữ liệu: một "jackpot" thấp hơn mức sàn không phải jackpot nhỏ, nó là regex
bắt sai dòng — parser phải văng lỗi thay vì công bố.

**Khối nồi** (`pot`) — Thứ trang **hiện**: số về tay nếu trúng cả 6, kèm ba con số đối
trọng — chi phí mỗi kỳ, tỷ lệ trúng cả 6, tỷ lệ không được gì, tỷ lệ có lãi. Thay cho bảng
7 hàng: với một trò đùa về jackpot thì sổ sách giải nhỏ là nhiễu, và nó chôn mất con số duy
nhất người ta vào xem.

Ba con số đối trọng **không được bỏ**. Một cái nồi kèm đúng tỷ lệ trúng của nó là chính xác
cách xổ số tự quảng cáo. Có chúng thì nó là số liệu; thiếu chúng thì nó là tờ rơi.

**Bảng thực nhận** (`payout_if_hit`) — Với mỗi số lượng trúng k = 0..6, bao 12 thực nhận
bao nhiêu. **Vẫn nằm trong `data.json`** dù trang không còn vẽ ra: bị cắt khỏi giao diện theo
yêu cầu, không phải bị xoá khỏi dữ liệu. Suy ra được hoàn toàn: `wheel.prize_counts` đã biết trong 924 vé có bao nhiêu vé
ăn hạng nào khi k trong 12 số về, còn giá mỗi hạng thì lấy từ trang thật.

Bảng **phải có cả hai nửa** — tiền và xác suất. Riêng cột tiền đọc ra thành lời khuyên nên
chơi (trúng 4 số đã có lãi). Riêng cột xác suất đọc ra thành "giải bèo", mà không hề bèo.
Chỉ khi đứng cạnh nhau chúng mới nói đúng sự thật: tiền là thật, và xác suất là thứ lấy lại.

Con số thật, đã tính bằng code chứ không nhẩm: bao 12 Mega 6/45 trúng 4 số lãi **+5,88 tr**,
trúng 5 số lãi **+102,76 tr**. Chỗ ROI −71,57% đến từ việc trúng 4 trở lên chỉ khoảng
**1 trên 28 kỳ**.

**Về tay** (take-home) — Tiền thật đến tay người trúng, sau khi trừ 10% thuế trúng thưởng
trên **phần vượt** 10 triệu. Công bố 34,9 tỷ → về tay 31,41 tỷ. Trang **bắt buộc** in cả hai:
nêu con số gộp rồi im về phần bị trừ đúng là cách mấy trang lừa đảo làm.

**Nhận trọn** — Giải ≤ 10 triệu, thuế bằng 0. Giải Nhất của Mega đúng 10.000.000đ nên là giải
**nhận trọn cao nhất**, dù Giải Nhất của Power to gấp 4 lần. Khác hoàn toàn với "về tay nhiều
nhất", vốn luôn là jackpot.

**Chưa mô hình hoá** (`tax.py` ghi rõ) — Vé bao tính là 1 vé hay 924 vé cho luật thuế-theo-vé,
và jackpot chia cho nhiều người trúng. Không biết thì phải nói không biết, không được đoán.

**Cây nến** (Candle) — Một khoảng thời gian trên biểu đồ giá, mang đúng bốn số: mở, cao,
thấp, đóng. Danh tính là cặp `(mã, mốc mở)`. Mốc luôn là **giây UTC**, không bao giờ là
mili-giây: thư viện vẽ nhận giây, và đưa nhầm mili-giây thì biểu đồ vẽ ở năm 50000 mà không
báo lỗi gì.

**Nến đã đóng** (Closed candle) — Cây nến mà khoảng thời gian của nó đã hết. Binance đánh
dấu bằng cờ `k.x` trong khung WebSocket. Cây **chưa** đóng vẫn đổi số từng giây, nên nó
không bao giờ được cộng vào chuỗi dùng để thống kê.

**Mẫu hình nến** (Candlestick pattern) — Một điều kiện hình học trên một tới ba cây nến, ví
dụ doji hay nhấn chìm. Trong project này mọi ngưỡng là **tỉ lệ so với biên độ cây nến**,
không bao giờ là giá tuyệt đối — nếu không, chuỗi nến xáo thứ tự (nối lại ở mức giá khác) bị
so sánh không công bằng và cả chặng `SỰ THẬT` của trang trader sụp.

**Lợi suất nến kế tiếp** (Forward return) — Lợi suất mở-đến-đóng của cây nến **ngay sau**
lần một mẫu hình nổ. Đây là con số trả lời được câu "mẫu hình có báo trước gì không", và nó
thay cho phép so tần suất, vốn rỗng theo định nghĩa với mẫu một cây: doji là tính chất của
một cây nến đứng riêng, nên xáo thứ tự cho ra **đúng** con số cũ.

**Hiệu chỉnh Bonferroni** — Thử `k` mẫu hình cùng lúc thì ngưỡng ý nghĩa là `0,05 / k`, chứ
không phải 0,05. Trang in cả ngưỡng đã chia lẫn số phép thử, vì năm phép thử song song thì
thỉnh thoảng một cái ra số đẹp là chuyện bình thường, không phải phát hiện.

## Từ tránh dùng

- **"số nóng" / "số lạnh" / "cầu" / "soi cầu"** — chỉ dùng khi đang trích dẫn để bóc phốt,
  không bao giờ dùng như khái niệm của project.
- **"power645"** — tên file của upstream đặt sai. Game đó tên là **Mega 6/45** (`mega645`).
  Tên sai chỉ được phép tồn tại ở đúng một chỗ: `GameSpec.mirror_filename`.
- **"dự đoán"** hiểu theo nghĩa thật — oracle **không** dự đoán. Nó *tiên tri*, và đó là
  từ được chọn có chủ ý.
- **"data.ny.gov"** như một nguồn khả dụng — cả domain trả 403 từ mạng này. Nguồn Mỹ đang
  dùng là `jbaranski/jeffs-lottery-utils`.
- **`sjc.com.vn`** như nguồn giá vàng — cả ba endpoint trả **403 Cloudflare**, kể cả khi kèm
  User-Agent browser và `Referer`. Kinh nghiệm `vietlott.vn` **không** chuyển giao được sang
  đây; cách đúng là **đổi nguồn (PNJ, có luôn giá SJC)**, không phải leo thang công cụ.
- **`apipubaws.tcbs.com.vn`** — từng dùng rộng rãi, nay **403 Cloudflare**.
- **`giavang.doji.vn`** — **503**, site hỏng. **`api.phuquygroup.vn`** — **500**, còn rò cả
  tên user database trong thông báo lỗi.
- **`vnstock`** như một dependency — `LICENSE.md` **cấm phân phối lại**, mà repo này là public
  MIT. Ngoài ra nó fingerprint máy, gửi telemetry, và có cổng chấp nhận điều khoản khi chạy
  lần đầu. Nó cũng chỉ là lớp bọc quanh chính những endpoint gọi thẳng được.
- **"realtime"** cho số liệu chứng khoán Việt — xem `Cuối phiên`.
- **"giá đất trung bình"** như một con số lấy được — không tồn tại nguồn nào. Chỉ số giá bất
  động sản của VN mới ở dạng bản đặc tả 2019 chưa từng công bố; cổng CSDL quốc gia theo
  NĐ 94/2024 không phân giải tên miền; BIS, OECD, FRED và IMF đều không có Việt Nam.
- **"cloudscraper"** như thứ bắt buộc để crawl `vietlott.vn` — đã kiểm chứng là **không
  cần**: `requests` kèm User-Agent browser trả về 200.
- **"đăng ký" / "tài khoản" / "thu thập dữ liệu người dùng"** — không tồn tại trong project
  này và sẽ không tồn tại. Cá nhân hoá đạt được **không cần** lưu gì của ai.
- **"chắc chắn trúng" / "số chuẩn" / "cam kết"** — thầy bựa tới đâu cũng dừng trước câu này.
- **"giải X tỷ"** đứng một mình — nêu số công bố thì phải nêu số về tay. Thiếu một nửa
  là quảng cáo, không phải số liệu.
- **"giải đang X tỷ"** — trang không biết con số đó. Nó biết nồi của kỳ đã quay,
  nên chỉ được nói **"ít nhất X"** khi cộng dồn, và phải kèm số kỳ.
- **"em"** khi oracle nói — oracle xưng **thầy**, gọi **con**. Không phải trợ lý.
- **"thấy trên Facebook"** như một nguồn tài nguyên — mạng xã hội không phải giấy
  phép. Ảnh không có nguồn và licence xác minh được thì không vào repo.
- **"kèo" / "lệnh chắc thắng" / "gồng lãi"** như lời khuyên — trang trader dạy đọc biểu đồ,
  không đưa ra lệnh nào. Chỉ được dùng khi đang trích để bóc.
- **"học phí"** như cách gọi khoản lỗ — đó là uyển ngữ của người bán khoá học, và nó ngụ ý
  có thứ gì đó được học. Nghiên cứu Brazil trong `trader.html` nói thẳng là không có bằng
  chứng người ta khá lên theo thời gian.
- **"tín hiệu mua" / "tín hiệu bán"** cho một mẫu hình — trang đo rồi: lợi suất cây nến kế
  tiếp sau mỗi mẫu đều nằm trong nhiễu, và lợi thế lớn nhất đo được nhỏ hơn phí vào-ra một
  bậc. Gọi nó là tín hiệu là phát biểu một điều trang vừa tự bác bỏ.
