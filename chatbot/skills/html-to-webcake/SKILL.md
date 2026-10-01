---
name: HTML sang Webcake
description: Chuyển HTML sang file Webcake .pke để tải lên Webcake chỉnh sửa tiếp.
group: Marketing
---

# HTML sang Webcake (.pke)

## Khi nào dùng

Kích hoạt khi người dùng nói những câu như: "chuyển file html này sang webcake",
"đổi html thành pke", "tạo file webcake từ html", "làm landing này thành file sửa được
trên webcake", "html to webcake", "convert html sang webcake".

Việc skill làm: đọc HTML, tái dựng thành page_source đúng khuôn Webcake rồi xuất .pke.

Biến một trang HTML thành **file `.pke`** mở và sửa được trong trình dựng trang Webcake.

## Hiểu đúng bản chất trước khi làm

- File `.pke` = `base64( MessagePack( envelope ) )`, trong đó `envelope.source` chính là **page_source** của editor Webcake (`settings, popup, page, options, cartConfigs`).
- Webcake là **canvas định vị TUYỆT ĐỐI theo pixel**, mỗi phần tử ghi `top/left/width/height` RIÊNG cho 2 khổ: mobile rộng 420, desktop rộng 960. Không phải HTML trôi theo dòng.
- Vì vậy skill này **TÁI DỰNG** nội dung HTML thành các section Webcake xếp dọc, sạch và sửa được - KHÔNG phải bản sao pixel y hệt trang HTML gốc. Luôn nói rõ điều này với người dùng.
- HTML do Webcake publish (bản đã xuất để chạy) không chứa source biên tập; skill vẫn đọc được nội dung của nó để dựng lại.

## Công cụ (đi kèm skill, không cần cài gói)

Ở thư mục `tools/` cạnh file SKILL.md này:

- `webcake-build.js` - nhận **spec JSON** -> sinh page_source -> xuất `.pke`. Tự chạy lint sau khi build.
  `node tools/webcake-build.js spec.json out.pke [--check]` (`--check`: exit 1 nếu lint có lỗi)
- `webcake-lint.js` - kiểm tra layout: node chồng nhau, tràn đáy/mép section, khoảng chết > 140px.
  `node tools/webcake-lint.js out.pke`
- `webcake-preview.js` - render page_source thành HTML tĩnh mô phỏng đúng canvas để SOI TRƯỚC khi giao.
  `node tools/webcake-preview.js out.pke previewBase [--debug]` -> `previewBase.desktop.html` + `previewBase.mobile.html`
  (`--debug` vẽ khung đứt nét quanh text + hộp virtualHeight để đối chiếu chiều cao)
- `webcake-pke.js` - codec 2 chiều: `decode file.pke file.json` / `encode file.json file.pke`.

Ví dụ spec chuẩn: `examples/salepage-16-buoc-spec.json` (sales page dark 16 section, dùng đủ theme + element mới).

## Quy trình khi kích hoạt (BẮT BUỘC đủ 7 bước)

1. **Xác định HTML nguồn.** Người dùng đưa file `.html` hoặc dán HTML. Đọc bằng Read.
2. **Bóc nội dung theo thứ tự trên xuống** thành các section; trong mỗi section nhận diện heading / text / ảnh / nút / form / bảng giá / testimonial / cam kết... và ghi lại màu nền, màu chữ, canh lề.
3. **Viết `spec.json`** theo schema dưới: khai `theme` (bảng màu + default) TRƯỚC, rồi mới viết sections. Mỗi trang dùng >= 3 pattern bố cục khác nhau (xem Design pass).
4. **Build**: `node tools/webcake-build.js spec.json out.pke` - đọc kỹ output lint đi kèm.
5. **Lint phải 0 ERROR.** Còn lỗi chồng/tràn thì sửa spec (hoặc engine) rồi build lại - KHÔNG giao file đang lỗi.
6. **Soi bằng mắt / bằng đo đạc (không được bỏ qua):**
   - `node tools/webcake-preview.js out.pke preview` -> mở `preview.desktop.html` và `preview.mobile.html` bằng browser tool.
   - Nếu chụp được screenshot: tự chấm theo checklist Design pass bên dưới ở CẢ 2 khổ.
   - Nếu không chụp được: chạy đoạn đo DOM trong trang preview (so `offsetHeight` thật với `data-vh` trên từng `.tb`, quét chồng lấn/tràn giữa các node cùng section) - phần tử lệch quá 10% theo hướng THIẾU chỗ là phải sửa.
   - Lặp build -> lint -> preview đến khi sạch.
7. **Giao file**: đặt `out.pke` cạnh HTML gốc hoặc trong vault, nhúng link markdown cho user tải, báo cáo NGẮN: bao nhiêu section, đã QA những gì, nhắc "upload lên Webcake để sửa" và các giới hạn (mục cuối).

## Schema của spec.json

```json
{
  "name": "Tên trang", "title": "Tiêu đề SEO", "description": "Mô tả SEO",
  "font": "Montserrat", "favicon": "https://... (tùy chọn)",
  "extraScript": "JS chạy khi publish/preview (vd đếm ngược)",
  "extraCss": "CSS phụ trợ khi publish",
  "theme": {
    "colors": { "ink": "rgba(242,240,232,1)", "amber": "rgba(232,168,92,1)", "cta": "linear-gradient(...)" },
    "text":    { "color": "$soft", "size": 16 },
    "heading": { "color": "$ink" },
    "badge":   { "color": "$amber", "bg": "rgba(232,168,92,0.08)", "borderColor": "rgba(232,168,92,0.35)" },
    "card":    { "bg": "$cardBg", "borderColor": "$line", "radius": 16, "titleColor": "$ink", "textColor": "$soft" },
    "button":  { "bg": "$cta", "color": "$bg0", "radius": 99, "size": 17 },
    "textMaxWidth": 700, "headingMaxWidth": 800, "cardMaxWidth": 800
  },
  "sections": [ { "name": "hero", "background": "$bg0 hoặc chuỗi CSS gradient", "padTop": 56, "gap": 18, "padBottom": 56,
    "elements": [ ] } ]
}
```

**Token màu**: `"$ten"` (nguyên chuỗi) hoặc `${ten}` (nhúng trong html dài) -> tự thay bằng `theme.colors.ten`. Tên không tồn tại thì giữ nguyên chuỗi (an toàn với chuỗi kiểu "$50").
Mỗi mục `theme.text/heading/badge/card/button/testimonial/priceTable/guarantee/progress/divider/ctaBlock` là **default cho kind tương ứng** - element chỉ ghi field khác default.

### Element LÁ

| kind | field chính | ghi chú |
|---|---|---|
| `heading` | `text` (HTML inline OK), `size`, `tag` h1/h2/h3, `align`, `kicker` | `kicker: "01"` tự sinh pill nhỏ phía trên (thay badge rời) |
| `text` | `html`, `size`, `color`, `align`, `maxWidth` | mặc định tự bó về `textMaxWidth` (~700) và căn giữa khối |
| `image` | `src`, `ratio` (w/h), `width` 0..1, `widthMobile`, `radius`, `boxShadow` | |
| `button` | `text`, `href` hoặc `scrollTo`, `width`, `bg`, `color`, `radius`, `boxShadow`, `animation` | glow tự suy từ màu bg; text dài tự tăng height |
| `badge` | `text`, `align`, `bg`, `color`, `borderColor` | text dài tự HẠ cỡ chữ; vẫn dài nữa thì tự wrap và pill cao lên |
| `card` | `icon`, `iconTop` true/false, `title`, `text`, `accent` (sọc màu cạnh trái), `pad`, `align`, `maxWidth` | hộp nền bo góc + tiêu đề + mô tả |
| `divider` | `width` 0..1, `color`, `thickness` | đường kẻ mảnh căn giữa |
| `progress` | `value` 0..1, `width`, `label`, `fillColor`, `trackColor`, `glow` | thanh tiến trình (vd "47/100 suất") |
| `priceTable` | `title`, `rows: [{label, price}]`, `total: {label, price}`, `strike`, `today` | bảng giá trị: label trái, giá phải, kẻ hairline, hàng tổng, dòng gạch giá |
| `testimonial` | `quote`, `author`, `stars` 1..5 | tự bọc card: sao + quote nghiêng + tên tác giả |
| `guarantee` | `icon`, `title`, `text` | icon lớn bên trái, nội dung bên phải, viền xanh |
| `ctaBlock` | `text`, `href`, `sub`, `arrow` true/false + mọi field button | mũi tên + nút + dòng phụ thành 1 khối |
| `spacer` | `height` | |
| `window` | `title`, `lines: [{who: "you|bot", text}]` | khung cửa sổ chat |
| `form` | `fields`, `submitText`, `submitBg`, `redirect` | input + nút gửi |

### Element BỐ CỤC (chống trang 1 cột đơn điệu)

- `row` `{ "gap": 44, "valign": "center", "cols": [ {"w": 0.55, "items": []}, {"w": 0.45, "items": []} ] }` - desktop xếp cột cạnh nhau (valign center = căn giữa dọc), mobile tự xếp dọc.
- `hero` `{ "side": "right|left", "mediaW": 0.4, "media": {element ảnh/window}, "items": [] }` - đường tắt "chữ 1 bên, hình 1 bên" căn giữa dọc.
- `cardsRow` `{ "gap": 18, "cards": [ {icon,title,text} ] }` - 1 hàng card đều nhau (mọi khối "3 ý cạnh nhau").
- `testimonialRow` `{ "items": [ {quote,author} ] }` - hàng testimonial ngang.
- `iconRow` `{ "items": [ {icon, text} ] }` - hàng icon + chú thích ngắn.

## Design pass (checklist thẩm mỹ - chấm TRƯỚC khi giao)

1. **Nhịp nền**: luân phiên nền section đậm / nhạt; tối đa 1 radial-gradient nhấn cho hero + 1 cho khối giá.
2. **>= 3 pattern bố cục** mỗi trang (hero 2 cột, cardsRow, priceTable, testimonial...). Cấm 100% một cột.
3. **Khổ chữ đọc được**: đoạn văn <= ~90 ký tự/dòng (textMaxWidth lo việc này - đừng tắt nếu không có lý do).
4. **Heading scale nhất quán**: vd h1 42 / h2 31 / h3 19 desktop (mobile tự nhân ~0.84). Kicker dùng cùng 1 kiểu pill xuyên suốt.
5. **Spacing bội số 8** cho padTop/padBottom/gap; gộp nội dung liền mạch vào một section, đừng cắt vụn mỗi dòng một section.
6. **CTA lặp 2-3 lần**, cùng màu cùng radius; nút chính nổi bật nhất trang.
7. **Lint 0 ERROR + preview 2 khổ**: không chồng chữ, không hụt nền, không khoảng chết > 140px.

## Nguyên tắc chuyển đổi

- **Chữ nhấn mạnh**: thẻ inline trong html - `<span style='font-weight:700;color:${ink};'>...</span>`, gạch giá `<span style='text-decoration:line-through;'>...</span>`. Xuống dòng `<br>`, KHÔNG lồng `<p>`.
- **Màu**: dạng `rgba(r,g,b,a)` hoặc token `$ten`. Nút nổi bật dùng gradient.
- **Ảnh**: Webcake tải theo URL public. Ảnh local/base64 -> CẢNH BÁO user cần upload ảnh lên host rồi thay `src`, nếu không ảnh sẽ trống.
- **Đo chữ**: engine dùng bảng độ rộng TỪNG ký tự Montserrat đo từ Chrome thật (chuẩn cả tiếng Việt, CHỮ HOA, emoji, số) + biên an toàn 1.5%; span `font-size`/`font-weight` inline cũng được tính vào chiều cao. Sai số thực tế ~0-1%. Font khác Montserrat sẽ kém chính xác hơn một chút - cứ chạy preview để soi.
- **Script/CSS động**: `extraScript` / `extraCss` map vào Cài đặt > HTML/JavaScript của Webcake; CHỈ chạy khi Xem trước / Xuất bản, KHÔNG chạy trong editor - dặn user bấm Preview mới thấy (vd đồng hồ đếm ngược).
- **KHÔNG dùng ký tự em dash** ở bất cứ đâu (text, spec, báo cáo) - dùng "-".

## Cách nâng cao (tự dựng page_source rồi encode)

Nếu cần kiểm soát sâu (group lồng nhau, popup, radio/checkbox sản phẩm), tự dựng nguyên object `source`
(`{settings, popup, page, options, cartConfigs}`) đúng schema node Webcake, ghi ra JSON rồi:
`node tools/webcake-pke.js encode source.json out.pke` (file chỉ chứa `source` sẽ được tự bọc envelope; thêm `--name` `--owner` nếu cần).

## Giới hạn cần nói thẳng với người dùng

Skill tái dựng bố cục sạch theo lưới dọc + các hàng nhiều cột, không sao chép y hệt vị trí pixel của HTML gốc.
Hiệu ứng nền động (canvas, orb blur...) không mang sang editor được - chỉ nhúng lại qua `extraScript` và chỉ chạy khi publish.
Radio/checkbox chọn sản phẩm (gắn `product_id`/`variation` của Pancake) không tự sinh được - user thêm trong Webcake sau khi upload.
Khuyến khích upload thử file `.pke` trước, lệch đâu chỉnh spec rồi build lại.
