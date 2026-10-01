# Báo Cáo Đối Chiếu Dữ Liệu Khách Hàng (Excel vs CRM)
**Tổng số đại lý từ file Excel:** 263
**Tổng số đại lý đẩy lên Redis (thỏa mãn quy tắc CRM):** 196

## Chi Tiết Trạng Thái 263 Đại Lý Excel Trên AMIS CRM

## Bảng Tổng Hợp
- **Số đại lý có mặt trên CRM:** 263/263
- **Số đại lý (có trên CRM) nhưng THIẾU địa chỉ:** 85
- **Số đại lý (có trên CRM) nhưng KHÔNG có đơn hàng hợp lệ (Doanh số nằm ở Base/MISA):** 128
- **Số đại lý xuất hiện trên bản đồ (Redis):** 123
- **Số đại lý bị hệ thống chặn lại:** 140

| STT | Tên Đại Lý (Excel) | Số Điện Thoại (CRM) | Tồn Tại Trên CRM? | Có Địa Chỉ CRM? | Lịch Sử Mua Hàng | Lên Được Redis? | Nguyên Nhân Bị Loại |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | HỘ KINH DOANH PHONG PHÚ | 0981 332 667 - 0794 260 117 | ✅ CÓ | ✅ CÓ | ✅ 14 Đơn | ✅ CÓ | - |
| 2 | HỘ KINH DOANH TỐ - RANG | 0908 149 209 | ✅ CÓ | ✅ CÓ | ✅ 6 Đơn | ✅ CÓ | - |
| 3 | CÔNG TY TNHH NÔNG DƯỢC HOÀNG ÚT MÊKÔNG | 0908 082 077 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 4 | HỘ KINH DOANH KHA - DỮNG | 0939 661 457 | ✅ CÓ | ✅ CÓ | ✅ 15 Đơn | ✅ CÓ | - |
| 5 | CÔNG TY TNHH PHÂN BÓN HIẾU VÂN | 0932 938 887 | ✅ CÓ | ✅ CÓ | ✅ 24 Đơn | ✅ CÓ | - |
| 6 | HỘ KINH DOANH ĐÌNH HÙNG | 0942 411 606 | ✅ CÓ | ✅ CÓ | ✅ 9 Đơn | ✅ CÓ | - |
| 7 | CÔNG TY TNHH VẬT TƯ NÔNG NGHIỆP TÂN BÌNH MINH | 0919 084 584 | ✅ CÓ | ✅ CÓ | ❌ 4 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 8 | HỘ KINH DOANH CHÍN DỰ | 0919 127 955 | ✅ CÓ | ✅ CÓ | ✅ 15 Đơn | ✅ CÓ | - |
| 9 | CÔNG TY TNHH VẬT TƯ NÔNG NGHIỆP THÀNH PHÁT | 0703330499 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 10 | HỘ KINH DOANH TRẦN HOÀNG TUẤN | 0918 177 444 | ✅ CÓ | ✅ CÓ | ✅ 20 Đơn | ✅ CÓ | - |
| 11 | HỘ KINH DOANH LÝ ĐỨC | 0703 781 098 | ✅ CÓ | ✅ CÓ | ❌ 11 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 12 | CÔNG TY TNHH PLANT GROWTH | 0786 888 247 | ✅ CÓ | ✅ CÓ | ✅ 6 Đơn | ✅ CÓ | - |
| 13 | CÔNG TY TNHH NÔNG NGHIỆP NĂM BÉ | 0774 859 037 | ✅ CÓ | ✅ CÓ | ✅ 10 Đơn | ✅ CÓ | - |
| 14 | CÔNG TY TNHH SX TM XNK LSD | 0919 978 935 | ✅ CÓ | ✅ CÓ | ✅ 4 Đơn | ✅ CÓ | - |
| 15 | CÔNG TY TRÁCH NHIỆM HỮU HẠN MỘT THÀNH VIÊN THƯƠNG MẠI DỊCH VỤ ÚT NGÒ | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 35 Đơn | ✅ CÓ | - |
| 16 | HỘ KINH DOANH TRẦN TIẾT CHINH | 0909 323 071 - 0935 704 120 | ✅ CÓ | ✅ CÓ | ✅ 7 Đơn | ✅ CÓ | - |
| 17 | HỘ KINH DOANH CÁ THỂ HỒ NHƯ THỦY | 0909 014 432 - 0982 618 479 | ✅ CÓ | ✅ CÓ | ✅ 11 Đơn | ✅ CÓ | - |
| 18 | CÔNG TY TNHH THƯƠNG MẠI THỨC ĂN THANH DŨNG | 0966882991 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 19 | CÔNG TY TNHH TM - SẢN XUẤT NHẬT QUANG | 079.3836292 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 20 | HỘ KINH DOANH ĐẠI LÝ VÉ SỐ KIẾN THIẾT TÁM TUÔI (CỬA HÀNG VẬT TƯ NÔNG NGHIỆP TÁM TUÔI) | 0946 836 191 | ✅ CÓ | ✅ CÓ | ✅ 8 Đơn | ✅ CÓ | - |
| 21 | HỘ KINH DOANH BẢY THIỂU | 0949 534 481 | ✅ CÓ | ✅ CÓ | ✅ 1 Đơn | ✅ CÓ | - |
| 22 | CÔNG TY TNHH PHÂN BÓN BA MỸ | 0913 192 009 | ✅ CÓ | ✅ CÓ | ✅ 1 Đơn | ✅ CÓ | - |
| 23 | CÔNG TY TNHH NN&TS TRÚC ANH ĐÀO | 0916314679 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 24 | CÔNG TY TNHH BẮC TAM NÔNG | 0789 905 577 | ✅ CÓ | ✅ CÓ | ✅ 13 Đơn | ✅ CÓ | - |
| 25 | HỘ KINH DOANH  ÚT TỶ | 0916 753 334 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 26 | CỬA HÀNG VẬT TƯ NÔNG NGHIỆP PHƯƠNG LENL | 0277 3977 447 | ✅ CÓ | ✅ CÓ | ✅ 4 Đơn | ✅ CÓ | - |
| 27 | HỘ KINH DOANH TẤN DANH (MƯỜI TƯỜNG) | 0939 663 313 | ✅ CÓ | ✅ CÓ | ✅ 3 Đơn | ✅ CÓ | - |
| 28 | HỘ KINH DOANH CỦA HÀNG VẬT TƯ NÔNG NGHIỆP CHÍN TẤN | 0911 303 307 | ✅ CÓ | ✅ CÓ | ❌ 9 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 29 | HỘ KINH DOANH QUỲNH NHƯ | 0901 041 117 | ✅ CÓ | ✅ CÓ | ✅ 4 Đơn | ❌ KHÔNG | Không được approve / Thiếu Alias |
| 30 | HỘ KINH DOANH NĂM KINH. | *(Không có)* | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 31 | HỘ KINH DOANH THẦY TUẤN | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 7 Đơn | ✅ CÓ | - |
| 32 | HỘ KINH DOANH CỬA HÀNG VẬT TƯ NÔNG NGHIỆP THIỆN PHÁT | 0972658141 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 33 | CÔNG TY TNHH MTV BẢY BINH | 0917 939 474 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 34 | HỘ KINH DOANH BẢY MINH | 0919 582 649 | ✅ CÓ | ✅ CÓ | ✅ 26 Đơn | ✅ CÓ | - |
| 35 | HỘ KINH DOANH BA LIẾU 2 | 0919 574 340 | ✅ CÓ | ✅ CÓ | ✅ 4 Đơn | ✅ CÓ | - |
| 36 | CÔNG TY TNHH VẬT TƯ NÔNG NGHIỆP MINH TRUNG LẤP VÒ | 0972658141 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 37 | HỘ KINH DOANH CỬA HÀNG VẬT TƯ NÔNG NGHIỆP ĐỨC HẠNH | *(Không có)* | ✅ CÓ | ❌ THIẾU | ✅ 7 Đơn | ❌ KHÔNG | Thiếu địa chỉ |
| 38 | CÔNG TY TNHH NÔNG NGHIỆP TIẾN HƯNG | 0939 472 454 | ✅ CÓ | ✅ CÓ | ✅ 8 Đơn | ✅ CÓ | - |
| 39 | CÔNG TY TNHH VẬT TƯ NÔNG NGHIỆP PHƯƠNG HUỆ | 0937 966 766 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 40 | HỘ KINH DOANH THIỆN TÍNH | 0944 094 441 | ✅ CÓ | ✅ CÓ | ✅ 12 Đơn | ✅ CÓ | - |
| 41 | HỘ KINH DOANH CỬA HÀNG VẬT TƯ NÔNG NGHIỆP VŨ LINH | 0983 900 024 | ✅ CÓ | ✅ CÓ | ✅ 4 Đơn | ✅ CÓ | - |
| 42 | HỘ KINH DOANH VẬT TƯ NÔNG NGHIỆP KHOA NAM | 0799 832 589 | ✅ CÓ | ✅ CÓ | ✅ 12 Đơn | ✅ CÓ | - |
| 43 | HỘ KINH DOANH TƯ HỒNG | 0987 117 944 | ✅ CÓ | ✅ CÓ | ❌ 5 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 44 | HỘ KINH DOANH TRUNG TÍN 1 | 0939 123 159 | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 45 | HỘ KINH DOANH DƯƠNG HUNG | 0763 781 567 | ✅ CÓ | ✅ CÓ | ✅ 34 Đơn | ✅ CÓ | - |
| 46 | HỘ KINH DOANH  VĂN QUÍ | 0977 460 065 | ✅ CÓ | ✅ CÓ | ❌ 2 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 47 | HỘ KINH DOANH  HÙNG CƯỜNG | 0932 246 739 | ✅ CÓ | ✅ CÓ | ❌ 3 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 48 | CÔNG TY TNHH HƯƠNG NGỌC VÂN GIỒNG RIỀNG | 0917 693 777 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 49 | DOANH NGHIỆP TƯ NHÂN THANH TOÀN | 0913 131 590 | ✅ CÓ | ✅ CÓ | ✅ 3 Đơn | ✅ CÓ | - |
| 50 | HỘ KINH DOANH  CỬA HÀNG VTNN MINH LOAN KG | 0379402989 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 51 | CÔNG TY TNHH PT MINH SANG | 0781.3629014 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 52 | HỘ KINH DOANH  ĐỊNH HẰNG | 0919 649 447 | ✅ CÓ | ✅ CÓ | ✅ 15 Đơn | ✅ CÓ | - |
| 53 | HỘ KINH DOANH  NGUYỄN VĂN CÔNG | 0917708862 | ✅ CÓ | ✅ CÓ | ✅ 1 Đơn | ✅ CÓ | - |
| 54 | CÔNG TY TNHH HẠT NGỌC VÀNG TG | 0913 161 105 | ✅ CÓ | ✅ CÓ | ✅ 3 Đơn | ✅ CÓ | - |
| 55 | CÔNG TY TRÁCH NHIỆM HỮU HẠN TẤN LỢI | 0299 3816 567 | ✅ CÓ | ✅ CÓ | ✅ 12 Đơn | ✅ CÓ | - |
| 56 | HỘ KINH DOANH TRÂU VÀNG | 0917 869 898 | ✅ CÓ | ✅ CÓ | ✅ 10 Đơn | ✅ CÓ | - |
| 57 | CÔNG TY TNHH HỮU THÀNH 1 | 0966882991 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 58 | CÔNG TY TNHH SX PB HỮU THÀNH | 0966882991 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 59 | HỘ KINH DOANH  VẬT TƯ NÔNG NGHIỆP THANH PHONG | 0703330499 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 60 | HỘ KINH DOANH CỬA HÀNG VẬT TƯ NÔNG NGHIỆP KIM HUÊ | 0984 408 690 | ✅ CÓ | ✅ CÓ | ❌ 8 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 61 | HỢP TÁC XÃ DVNN KINH DỚN | 079.3218578 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 62 | HỢP TÁC XÃ DVNN HỒNG PHÁT | 0903406657 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 63 | HỢP TÁC XÃ DVNN BÌNH LỄ | 0967580152 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 64 | HỘ KINH DOANH  PHÚ NÔNG | 0902 721 227 | ✅ CÓ | ✅ CÓ | ✅ 9 Đơn | ✅ CÓ | - |
| 65 | HỘ KINH DOANH SIÊU THỊ NÔNG NGHIỆP | 0985 607 107 | ✅ CÓ | ✅ CÓ | ✅ 4 Đơn | ✅ CÓ | - |
| 66 | HỘ KINH DOANH  NGUYỄN MỸ Á | 079.3813101 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 67 | CÔNG TY TNHH NGUYỄN VĂN ẨN | 0988.377.939 - 0918.056.605 - 02733.827.327 | ✅ CÓ | ✅ CÓ | ❌ 4 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 68 | HỘ KINH DOANH  CỬA HÀNG VẬT TƯ NÔNG NGHIỆP NĂM LỮ | 0373 882 619 | ✅ CÓ | ✅ CÓ | ✅ 1 Đơn | ✅ CÓ | - |
| 69 | CÔNG TY TNHH PHÂN BÓN THÀNH VINH | 0949 939 747 | ✅ CÓ | ✅ CÓ | ✅ 3 Đơn | ✅ CÓ | - |
| 70 | CÔNG TY TNHH VẬT TƯ NÔNG NGHIỆP TÂN TIẾN | 0972658141 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 71 | CÔNG TY TNHH THƯƠNG MẠI HUỲNH GIA AGRI | 0982 372 472 | ✅ CÓ | ✅ CÓ | ✅ 4 Đơn | ✅ CÓ | - |
| 72 | HỘ KINH DOANH  HỒ VĂN LIÊM | 0972 238 259 | ✅ CÓ | ✅ CÓ | ✅ 3 Đơn | ✅ CÓ | - |
| 73 | CÔNG TY TNHH PHƯỚC QUANG LONG | 0913 962 360 | ✅ CÓ | ✅ CÓ | ❌ 4 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 74 | HỘ KINH DOANH  LÊ HOÀNG VŨ | 0919 185 346 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 75 | HỘ KINH DOANH  PHẠM VĂN CAM | 0984 372 979 | ✅ CÓ | ✅ CÓ | ❌ 5 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 76 | HỘ KINH DOANH  HUỲNH THỊ THANH TÂN | 0347 471 928 | ✅ CÓ | ✅ CÓ | ✅ 1 Đơn | ✅ CÓ | - |
| 77 | CÔNG TY TNHH VTNN QUỐC HỒNG | 0903406657 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 78 | HỘ KINH DOANH  HUỲNH THỊ TUYỀN | 0917 725 727 | ✅ CÓ | ✅ CÓ | ❌ 1 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 79 | CÔNG TY TNHH HIẾU CHẤN HƯNG | 0867788766 | ✅ CÓ | ✅ CÓ | ✅ 7 Đơn | ✅ CÓ | - |
| 80 | HỘ KINH DOANH CỬA HÀNG VẬT TƯ NÔNG NGHIỆP THÀNH LONG | 0703330499 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 81 | HỘ KINH DOANH  VÕ THÀNH NHÂN | 0272 3877 905 | ✅ CÓ | ✅ CÓ | ❌ 2 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 82 | HỘ KINH DOANH  NGỌC DUNG | 0936 012 697 | ✅ CÓ | ✅ CÓ | ❌ 3 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 83 | HỘ KINH DOANH  HAI HIẾU 9 | 0825 444 618 | ✅ CÓ | ✅ CÓ | ✅ 8 Đơn | ✅ CÓ | - |
| 84 | HỘ KINH DOANH  VẬT TƯ NÔNG NGHIỆP MINH SANG | 0972658141 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 85 | HỘ KINH DOANH  CH VẬT TƯ NÔNG NGHIỆP HÙNG GIANG | Ô969 838 374 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 86 | CÔNG TY TNHH NÔNG ĐIỀN PHÁT | 0909 327 668 | ✅ CÓ | ✅ CÓ | ✅ 24 Đơn | ✅ CÓ | - |
| 87 | CÔNG TY TNHH MỘT THÀNH VIÊN NÔNG NGHIỆP TRÍ TÍNH | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 54 Đơn | ✅ CÓ | - |
| 88 | HỘ KINH DOANH VẬT TƯ NÔNG NGHIỆP NGUYÊN LỘC | 0918 705 617 | ✅ CÓ | ✅ CÓ | ✅ 29 Đơn | ✅ CÓ | - |
| 89 | CỬA HÀNG VẬT TƯ NÔNG NGHIỆP LUẬT THƯ | *(Không có)* | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 90 | CÔNG TY TNHH VẬT TƯ NÔNG NGHIỆP TRANG HÒA | 0378901947 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 91 | HỘ KINH DOANH CỬA HÀNG VẬT TƯ NÔNG NGHIỆP NGHĨA THOA | 0919 133 113 | ✅ CÓ | ✅ CÓ | ❌ 8 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 92 | HỘ KINH DOANH THÁI MẬP | 0367 615 108 | ✅ CÓ | ✅ CÓ | ✅ 25 Đơn | ✅ CÓ | - |
| 93 | HỘ KINH DOANH KỈNH NGA | *(Không có)* | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 94 | HỢP TÁC XÃ KHIẾT TÂM | 0934 633 758 | ✅ CÓ | ✅ CÓ | ✅ 8 Đơn | ✅ CÓ | - |
| 95 | CÔNG TY TNHH THƯƠNG MẠI VÀ DỊCH VỤ NGUYÊN PHÚ PHÁT | 0939 474 202 | ✅ CÓ | ✅ CÓ | ✅ 26 Đơn | ✅ CÓ | - |
| 96 | HỘ KINH DOANH CHVTNN  TRUNG PHƯỢNG | 0703874406 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 97 | HỘ KINH DOANH NGUYỄN THỊ MỸ | 0397 640 543 | ✅ CÓ | ✅ CÓ | ✅ 14 Đơn | ✅ CÓ | - |
| 98 | HỘ KINH DOANH ĐỒNG VĂN TUẦN | 0356 861 582 | ✅ CÓ | ✅ CÓ | ✅ 19 Đơn | ✅ CÓ | - |
| 99 | CÔNG TY TNHH MTV CÀ PHÊ ANH PHƯƠNG | 0703874406 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 100 | HỘ KINH DOANH  PHẠM NGỌC KHÔI | 974775564 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 101 | CÔNG TY TNHH TM VÂN HỌC | 079.3218578 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 102 | CÔNG TY TNHH MTV MINH PHÚC ANH | 0975 013 014 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 103 | HỘ KINH DOANH TUẤN THANH | 0976883244 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 104 | HỘ KINH DOANH  TRẦN THỊ KIM LAN | 0355 417 022 | ✅ CÓ | ✅ CÓ | ✅ 17 Đơn | ✅ CÓ | - |
| 105 | CÔNG TY TNHH THANH BẰNG LỘC AN | 0966882991 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 106 | CÔNG TY TNHH CÀ PHÊ KHÁNH HƯƠNG | 0328 205 666 | ✅ CÓ | ✅ CÓ | ✅ 18 Đơn | ✅ CÓ | - |
| 107 | HỘ KINH DOANH  PHẠM UY QUYỀN | 0908 377 545 | ✅ CÓ | ✅ CÓ | ✅ 4 Đơn | ✅ CÓ | - |
| 108 | HỘ KINH DOANH  CH VTNN BÌNH AN | 0967580152 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 109 | CÔNG TY TNHH DUY THẮNG MƯỜI | 347744405 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 110 | CÔNG TY TNHH TIẾN PHÁT BM | 079.3868130 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 111 | HỘ KINH DOANH  CAO HUỆ | 0972 311 830 | ✅ CÓ | ✅ CÓ | ✅ 9 Đơn | ❌ KHÔNG | Không được approve / Thiếu Alias |
| 112 | CÔNG TY TNHH PHÚ THỊNH AGRICARE | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 13 Đơn | ✅ CÓ | - |
| 113 | HỘ KINH DOANH  ĐẠI LÝ HÀ CHƯƠNG | 0976 826 219 | ✅ CÓ | ✅ CÓ | ✅ 18 Đơn | ✅ CÓ | - |
| 114 | CÔNG TY TNHH CÀ PHÊ MINH ANH PHÁT | 079.3868130 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 115 | DNTN PHONG VŨ LONG | 079.3871292 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 116 | CÔNG TY TNHH CAN | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 74 Đơn | ✅ CÓ | - |
| 117 | CÔNG TY TNHH PHÚC ĐÔNG HẢI | 0 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 118 | HỘ KINH DOANH  KHIÊM TÌNH | *(Không có)* | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 119 | CÔNG TY TNHH TRUNG THANH HỘI | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 12 Đơn | ✅ CÓ | - |
| 120 | CÔNG TY TNHH DŨNG QUỐC AN | 0983 682 029 | ✅ CÓ | ✅ CÓ | ✅ 5 Đơn | ✅ CÓ | - |
| 121 | CÔNG TY TNHH TM & DV SONG PHÚC | 079.3894028 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 122 | CÔNG TY TNHH MTV VQN AGRITECH | 079.3868130 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 123 | CÔNG TY TNHH THÙY TRANG-LH | 0378901947 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 124 | CÔNG TY TNHH MTV VIỆT HOÀNG PHÁT | *(Không có)* | ✅ CÓ | ❌ THIẾU | ✅ 17 Đơn | ✅ CÓ | - |
| 125 | CÔNG TY TNHH THẢO NA TRANG | 0378901947 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 126 | HỘ KINH DOANH  PHÚC NỞ | 02632.218.523 - 0983.959.816 | ✅ CÓ | ✅ CÓ | ✅ 18 Đơn | ✅ CÓ | - |
| 127 | CÔNG TY TNHH MTV THÀNH TOÀN PHÁT LÂM HÀ | 0939847426 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 128 | HỘ KINH DOANH  MINH TUẤN | 0909 388 119 | ✅ CÓ | ✅ CÓ | ✅ 25 Đơn | ✅ CÓ | - |
| 129 | HỘ KINH DOANH  NGUYỄN ĐỨC VĂN | 0399 847 789 | ✅ CÓ | ✅ CÓ | ✅ 25 Đơn | ✅ CÓ | - |
| 130 | HỘ KINH DOANH  NGUYỄN THỊ KIM LOAN | 0385 986 086 | ✅ CÓ | ✅ CÓ | ✅ 14 Đơn | ✅ CÓ | - |
| 131 | CTY TNHH DV & TM NỮ CÔNG | 079.3868130 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 132 | CÔNG TY TNHH HƯNG THỊNH THANH BÌNH | *(Không có)* | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 133 | HỘ KINH DOANH  HÀ THỊ CÔNG LÝ | 0989 054 880 | ✅ CÓ | ✅ CÓ | ✅ 14 Đơn | ✅ CÓ | - |
| 134 | HỘ KINH DOANH  ĐOÀN THỊ LỆ HUYỀN | 0976 824 139 | ✅ CÓ | ✅ CÓ | ✅ 23 Đơn | ✅ CÓ | - |
| 135 | HỘ KINH DOANH  ĐẶNG THỊ HOÀI PHƯƠNG | 0986 776 335 | ✅ CÓ | ✅ CÓ | ✅ 4 Đơn | ✅ CÓ | - |
| 136 | HỘ KINH DOANH  NGUYỄN TRỌNG TRUNG | 0987 195 495 | ✅ CÓ | ✅ CÓ | ❌ 2 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 137 | CÔNG TY TNHH TM & DV ĐOÀN THÀNH | 0966882991 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 138 | HỘ KINH DOANH  NGUYỄN THỊ MỸ DUNG | *(Không có)* | ✅ CÓ | ❌ THIẾU | ✅ 18 Đơn | ❌ KHÔNG | Thiếu địa chỉ |
| 139 | DOANH NGHIỆP TƯ NHÂN XĂNG DẦU MẠNH HOÀNG | 0909084943 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 140 | CÔNG TY TNHH MTV TUẤN HƯƠNG | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 50 Đơn | ✅ CÓ | - |
| 141 | CỬA HÀNG VẶT TƯ NÔNG NGHIỆP THÀNH NHÂN | 0945 156 567 | ✅ CÓ | ✅ CÓ | ✅ 6 Đơn | ✅ CÓ | - |
| 142 | CÔNG TY TNHH MTV THÀNH TÍN LÂM ĐỒNG | 0388311828 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 143 | HỘ KINH DOANH PHẠM THỊ HOÀI | 0385 867 409 | ✅ CÓ | ✅ CÓ | ❌ 7 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 144 | HỘ KINH DOANH LOAN THỦY | 0979 128 818 | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 145 | HỘ KINH DOANH NGUYỄN HỮU TÀI | 0977 574 774 | ✅ CÓ | ✅ CÓ | ✅ 5 Đơn | ✅ CÓ | - |
| 146 | CÔNG TY TNHH MTV DŨNG HƯƠNG COFFEE | *(Không có)* | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 147 | HỘ KINH DOANH BÙI THANH HẢI | 0834849107 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 148 | HỘ KINH DOANH HÀ XUÂN THÀNH | 0978 292 988 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 149 | HỘ KINH DOANH NGHIỆP XUÂN | 0937454886 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 150 | HỘ KINH DOANH MINH TÚ | 0988053001 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 151 | CÔNG TY TNHH MTV ĐỒNG THỦY ĐAK NÔNG | *(Không có)* | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 152 | HỘ KINH DOANH LÊ ĐÌNH DŨNG | 0972 669 456 | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 153 | CÔNG TY TNHH TM VÀ DV THIẾT KẾ XD THÀNH VINH | 0392.706.588 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 154 | CÔNG TY TNHH MTV SƠN HẢO COFFEE | *(Không có)* | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 155 | CÔNG TY TNHH MTV PHÚ HẰNG LÂM ĐỒNG | *(Không có)* | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 156 | CÔNG TY TNHH MTV LONG HOÀI | 0976767678 | ✅ CÓ | ✅ CÓ | ✅ 14 Đơn | ✅ CÓ | - |
| 157 | CÔNG TY TNHH MTV DỊCH VỤ NÔNG SẢN THẢO ĐÔNG | *(Không có)* | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 158 | HỘ KINH DOANH LÊ HOÀI NGUYÊN | 0354053505 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 159 | CÔNG TY TNHH HAI THÀNH VIÊN LIÊM THÊM | 0982 576 527 | ✅ CÓ | ✅ CÓ | ✅ 14 Đơn | ✅ CÓ | - |
| 160 | CÔNG TY TNHH TM VÀ DV HOÀNG THÔNG | 0914 067 010 - 02623.872.349 | ✅ CÓ | ✅ CÓ | ✅ 7 Đơn | ✅ CÓ | - |
| 161 | CÔNG TY TNHH TM VÀ NÔNG SẢN GIAO NGA | *(Không có)* | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 162 | HỘ KINH DOANH  CƠ SỞ PHÂN BÓN XUÂN TRƯỜNG | 0961 222 227 | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 163 | CÔNG TY TNHH THƯƠNG MẠI THÀNH ĐẠT ĐẮK LẮK | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 164 | HỘ KINH DOANH VŨ THỊ QUYÊN | 0982 437 785 | ✅ CÓ | ✅ CÓ | ❌ 2 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 165 | CÔNG TY TNHH THAO NỤ | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 166 | HỘ KINH DOANH  LƯƠNG NGỌC ANH | 0976 940 027 | ✅ CÓ | ✅ CÓ | ✅ 5 Đơn | ✅ CÓ | - |
| 167 | HỘ KINH DOANH  TRẦN XANH | 0905 739 798 | ✅ CÓ | ✅ CÓ | ✅ 6 Đơn | ✅ CÓ | - |
| 168 | CÔNG TY TNHH THƯƠNG MẠI KHÔI LỘC | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 13 Đơn | ✅ CÓ | - |
| 169 | CÔNG TY TNHH MTV TM VÀ NÔNG SẢN HUY HỒNG ĐẮK LẮK | 0903406657 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 170 | CÔNG TY TNHH THƯƠNG MẠI NỘI PHƯƠNG | *(Không có)* | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 171 | CÔNG TY TNHH CÀ PHÊ QUANG ANH | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 10 Đơn | ✅ CÓ | - |
| 172 | CÔNG TY TNHH TƯ MAY | 0919 652 450 - 0914 420 402 | ✅ CÓ | ✅ CÓ | ✅ 36 Đơn | ✅ CÓ | - |
| 173 | HỘ KINH DOANH HẬU HÀ | 0919 525 547 | ✅ CÓ | ✅ CÓ | ✅ 4 Đơn | ✅ CÓ | - |
| 174 | HỘ KINH DOANH KIM MAI | 0933 944 864 | ✅ CÓ | ✅ CÓ | ✅ 8 Đơn | ✅ CÓ | - |
| 175 | HỘ KINH DOANH TOÀN THẮM | 0919 415 848 | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 176 | HỘ KINH DOANH KHỔNG THỊ HUYỀN | 0946 774 133 | ✅ CÓ | ✅ CÓ | ✅ 10 Đơn | ✅ CÓ | - |
| 177 | HỘ KINH DOANH PHÙ THỊ NGỌC LAN | 0972 646099 | ✅ CÓ | ✅ CÓ | ❌ 4 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 178 | HỘ KINH DOANH HẢI HUÊ | 0786 479 199 | ✅ CÓ | ✅ CÓ | ❌ 2 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 179 | HỘ KINH DOANH LÊ VĂN HOÀNG | 0355 039 009 | ✅ CÓ | ✅ CÓ | ✅ 3 Đơn | ✅ CÓ | - |
| 180 | HỘ KINH DOANH THUẬN TÀI | 0984 300 841 | ✅ CÓ | ✅ CÓ | ✅ 10 Đơn | ✅ CÓ | - |
| 181 | HỘ KINH DOANH BÌNH OANH | 0949186794 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 182 | CỬA HÀNG THANH THANH | 0327 035 804 | ✅ CÓ | ✅ CÓ | ✅ 14 Đơn | ✅ CÓ | - |
| 183 | HỘ KINH DOANH MAI TRANG | 0394 547 296 | ✅ CÓ | ✅ CÓ | ❌ 3 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 184 | HỘ KINH DOANH THANH DUY | 0328773639 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 185 | HỘ KINH DOANH NGÔ THANH TẠO | 0927 043 680 | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 186 | HỘ KINH DOANH VŨ CHẤN CƯỜNG | 0397 700 010 | ✅ CÓ | ✅ CÓ | ❌ 4 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 187 | HỘ KINH DOANH CHINH | 0942 777 248 | ✅ CÓ | ✅ CÓ | ❌ 3 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 188 | HỘ KINH DOANH DŨNG TÂM | 763891767 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 189 | HỘ KINH DOANH KIM OANH 1 | 0908 766 735 | ✅ CÓ | ✅ CÓ | ✅ 5 Đơn | ✅ CÓ | - |
| 190 | HỘ KINH DOANH DŨNG THẢO | 0949034592 | ✅ CÓ | ✅ CÓ | ✅ 5 Đơn | ✅ CÓ | - |
| 191 | HỘ KINH DOANH VẬT TƯ NÔNG NGHIỆP THÀNH NAM | 0946 840 924 | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 192 | CÔNG TY TNHH MTV PHẠM THANH HOA | 0913 739 920 | ✅ CÓ | ✅ CÓ | ✅ 11 Đơn | ✅ CÓ | - |
| 193 | HỘ KINH DOANH  CH VTNN DANH LINH | 0938184378 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 194 | CÔNG TY TNHH VTNN ĐÌNH CẢNH | 098 299 7415 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 195 | CÔNG TY TNHH HTP AGRI | 0916 971 071 | ✅ CÓ | ✅ CÓ | ✅ 26 Đơn | ✅ CÓ | - |
| 196 | HỘ KINH DOANH TRƯƠNG PHẠM DUY | 0919 988 167 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 197 | DOANH NGHIỆP TƯ NHÂN ÁNH - BÌNH PHƯỚC | 0915 318 257 | ✅ CÓ | ✅ CÓ | ✅ 16 Đơn | ✅ CÓ | - |
| 198 | HỘ KINH DOANH ĐẠI LÝ PHÂN BÓN TUẤN KIỆT | 0907 584 477 | ✅ CÓ | ✅ CÓ | ✅ 7 Đơn | ✅ CÓ | - |
| 199 | CÔNG TY TNHH MTV BẢO QUỐC TN | *(Không có)* | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 200 | HỘ KINH DOANH  CHVẬT TƯ NÔNG NGHIỆP TÍN PHONG | 0903406657 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 201 | CÔNG TY TNHH DỊCH VỤ VÀ THƯƠNG MẠI VN79 | 0258 3760 079 | ✅ CÓ | ✅ CÓ | ✅ 22 Đơn | ✅ CÓ | - |
| 202 | HỘ KINH DOANH LÊ VĂN PHƯỢNG | 0373 574 465 | ✅ CÓ | ✅ CÓ | ✅ 5 Đơn | ✅ CÓ | - |
| 203 | CÔNG TY TNHH THƯƠNG MẠI VÀ DỊCH VỤ TÁM TRUNG | 0256 3835 953 | ✅ CÓ | ✅ CÓ | ❌ 1 Đơn (Quá hạn/0đ) | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 204 | CÔNG TY TNHH VẬT TƯ NÔNG NGHIỆP NHÂN TUẤN | 0912 151 719 | ✅ CÓ | ✅ CÓ | ✅ 5 Đơn | ✅ CÓ | - |
| 205 | CÔNG TY TNHH TM-DV-TH VẬT TƯ NÔNG NGHIỆP MINH PHA | 0972658141 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 206 | HỘ KINH DOANH NÔNG DƯỢC XANH | *(Không có)* | ✅ CÓ | ❌ THIẾU | ✅ 8 Đơn | ❌ KHÔNG | Thiếu địa chỉ |
| 207 | CÔNG TY TNHH MTV HỮU PHÁP | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 208 | HỘ KINH DOANH HÒA PHÁT (TỪ THỊ THANH TÂM) | 0909084943 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 209 | HỘ KINH DOANH NGUYỄN TRỌNG HỨA | 0939 438 768 | ✅ CÓ | ✅ CÓ | ✅ 16 Đơn | ✅ CÓ | - |
| 210 | CÔNG TY CP THUỐC SÁT TRÙNG VIỆT NAM | 0982393833 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 211 | HỘ KINH DOANH NGUYỄN LINH | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 6 Đơn | ✅ CÓ | - |
| 212 | CÔNG TY TNHH NÔNG NGHIỆP LAKFARM | *(Không có)* | ✅ CÓ | ❌ THIẾU | ✅ 2 Đơn | ❌ KHÔNG | Thiếu địa chỉ |
| 213 | CÔNG TY TNHH VTNN THẢO NGUYÊN | 353766462 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 214 | CÔNG TY TNHH TM HUỲNH GIA AGRI | 079.3868130 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 215 | CÔNG TY TNHH TM DV MAI HINH | 079.3868130 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 216 | CÔNG TY TNHH NÔNG NGHIỆP ANH NGUYÊN | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 6 Đơn | ✅ CÓ | - |
| 217 | CÔNG TY TNHH THƯƠNG MẠI MINH QUÂN AGRI | 079.3615951 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 218 | CÔNG TY TNHH AGRI SÀI CÒN BAN MÊ | 079.3868130 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 219 | HỘ KINH DOANH LÊ HIỀN | 0366630497 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 220 | CÔNG TY TRÁCH NHIỆM HỮU HẠN MỘT THÀNH VIÊN PHÂN BÓN ÚT NGÒ III | *(Không có)* | ✅ CÓ | ❌ THIẾU | ✅ 9 Đơn | ❌ KHÔNG | Thiếu địa chỉ |
| 221 | HỘ KINH DOANH TRẦN HOÀNG TUẤN 1 | *(Không có)* | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 222 | HỘ KINH DOANH ĐỨC HƯNG PHÁT | 0383463427 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 223 | CÔNG TY TNHH THƯƠNG MẠI SÀI GÒN AN PHÚ | *(Không có)* | ✅ CÓ | ❌ THIẾU | ✅ 40 Đơn | ❌ KHÔNG | Thiếu địa chỉ |
| 224 | HỘ KINH DOANH HUỲNH NHƯ THIỆN | *(Không có)* | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 225 | CÔNG TY TNHH ĐÔNG ĐỨC THƯ | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 39 Đơn | ❌ KHÔNG | Không được approve / Thiếu Alias |
| 226 | CÔNG TY TNHH BRICS AGRO | 0906929292 | ✅ CÓ | ✅ CÓ | ✅ 21 Đơn | ❌ KHÔNG | Không được approve / Thiếu Alias |
| 227 | NGUYỄN THỊ KIM TIẾNG | *(Không có)* | ✅ CÓ | ❌ THIẾU | ✅ 3 Đơn | ❌ KHÔNG | Thiếu địa chỉ |
| 228 | HỘ KINH DOANH KHÁNH BĂNG | *(Không có)* | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 229 | CÔNG TY TNHH NÔNG NGHIỆP NĂM NGÀNH | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 7 Đơn | ✅ CÓ | - |
| 230 | HỘ KINH DOANH HÙNG CƯỜNG 2 | 0917 462 739 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 231 | HỘ KINH DOANH NGỌC BÍCH | *(Không có)* | ✅ CÓ | ❌ THIẾU | ✅ 2 Đơn | ❌ KHÔNG | Thiếu địa chỉ |
| 232 | HỘ KINH DOANH VẬT TƯ CÂY CẢNH-HẠT GIỐNG CÂY TRỒNG | 098 299 7415 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 233 | HỢP TÁC XÃ NÔNG NGHIỆP VÀ DỊCH VỤ TIẾN THUẬN | 0909851875 | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 234 | HỘ KINH DOANH CỬA HÀNG VẬT TƯ NÔNG NGHIỆP TUẤN THỊNH | 0769363629 | ✅ CÓ | ✅ CÓ | ✅ 7 Đơn | ✅ CÓ | - |
| 235 | HỘ KINH DOANH QUỐC THỊNH | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 4 Đơn | ✅ CÓ | - |
| 236 | HỘ KINH DOANH NGUYỄN VĂN THIỀNG | 0946 872 448 | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 237 | HỘ KINH DOANH PHÙNG HOÀNG SANG | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 1 Đơn | ✅ CÓ | - |
| 238 | HỘ KINH DOANH THANH HUY | 0328773639 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 239 | HỘ KINH DOANH TRẦN VĂN ÁNH | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 240 | CÔNG TY CỔ PHẦN NÔNG TRẠI ĐẠI PHÁT MEKONG | 0932261116 | ✅ CÓ | ✅ CÓ | ✅ 7 Đơn | ✅ CÓ | - |
| 241 | CÔNG TY TNHH TÀI HƯƠNG VIỆT | 079.3615951 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 242 | HỘ KINH DOANH ĐẠI LÝ PHÂN BÓN HƯNG HỒNG | 0903406657 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 243 | HỘ KINH DOANH VẬT TƯ NÔNG NGHIỆP CÔ LINH | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 4 Đơn | ✅ CÓ | - |
| 244 | HỘ KINH DOANH AN KHANG | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 1 Đơn | ✅ CÓ | - |
| 245 | HỘ KINH DOANH XUÂN TIỆN | 079.3218578 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 246 | CÔNG TY TNHH SƠN THU LÂM ĐỒNG | 0903001010 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 247 | CÔNG TY TNHH BẮC ĐÁNG | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 248 | HỘ KINH DOANH VẬT TƯ NÔNG NGHIỆP THANH VÂN C1 | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 1 Đơn | ✅ CÓ | - |
| 249 | HỘ KINH DOANH VĂN LUÂN | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 250 | HỘ KINH DOANH NGUYỄN THỊ TUYẾT TRANG | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 4 Đơn | ✅ CÓ | - |
| 251 | DOANH NGHIỆP TN DƯƠNG ANH DŨNG | *(Không có)* | ✅ CÓ | ✅ CÓ | ❌ 0 Đơn Hàng | ❌ KHÔNG | Không có doanh số (Trên MISA/Base) |
| 252 | CÔNG TY TNHH VẬT TƯ NÔNG NGHIỆP HẬU LOAN | 0939235166 | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 253 | CÔNG TY TNHH DUNG DŨNG PHÚ SƠN LÂM HÀ | 0822772528 | ✅ CÓ | ✅ CÓ | ✅ 4 Đơn | ✅ CÓ | - |
| 254 | CÔNG TY TNHH MINH PHÚ KHOA | *(Không có)* | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 255 | HỘ KINH DOANH VẬT TƯ NÔNG NGHIỆP TRỌNG MY | 0972658141 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 256 | HỘ KINH DOANH NGỌC QUYÊN | 079.3868223 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 257 | CÔNG TY TNHH SONG PHÁT AGRI | 0704724555 | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 258 | CÔNG TY TNHH TRƯƠNG GIA AGRI | 2773670314 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 259 | CÔNG TY TNHH VTNN &VLXD HUỲNH NHƯ | 079.3868130 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 260 | CÔNG TY TNHH MỘT THÀNH VIÊN THƯƠNG MẠI VÀ NÔNG SẢN KHOA QUYÊN | 0982993555 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 261 | HỘ KINH DOANH CỬA HÀNG VẬT TƯ NÔNG NGHIỆP NGỌC YẾN | 0917725727 | ✅ CÓ | ✅ CÓ | ✅ 2 Đơn | ✅ CÓ | - |
| 262 | HỘ KINH DOANH TRƯƠNG CÔNG DŨNG | 079.3882404 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |
| 263 | HỘ KINH DOANH CỬA HÀNG PB & VTNN YÊN ĐAN | 0379402989 | ✅ CÓ | ❌ THIẾU | ❌ 0 Đơn Hàng | ❌ KHÔNG | Thiếu địa chỉ, Không có doanh số (Trên MISA/Base) |