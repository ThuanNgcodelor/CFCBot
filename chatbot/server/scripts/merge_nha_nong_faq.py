# -*- coding: utf-8 -*-
"""
Script trích xuất 50 câu hỏi từ 'Nhung cau hoi thuong gap o nha nong.docx'
và chuẩn hóa, ghép vào file cfc_faq_google_sheet_from_CfcCoBayN8n_2026_08_13.csv
để cập nhật lên Google Sheets.
"""

import csv
import os
import re

CSV_PATH = "google_upload/cfc_faq_google_sheet_from_CfcCoBayN8n_2026_08_13.csv"
OUTPUT_FULL_CSV = "google_upload/cfc_faq_google_sheet_FULL_STANDARDIZED.csv"

# 50 câu hỏi chuẩn hóa từ Cẩm nang 50 câu hỏi nhà nông
NEW_FAQ_ENTRIES = [
    # ── NHÓM 1: TÌNH TRẠNG CÂY TRỒNG & GIAI ĐOẠN SINH TRƯỞNG (CÂU 1 - 10) ──
    {
        "category": "agronomy",
        "intent": "cfc_agronomy_shoot_development",
        "question_examples": (
            "Cây sầu riêng đang nhú mũi giáo rải dòng nào để mập đọt mà không rụng trái non?; "
            "Sầu riêng đang nhú đọt bón phân gì; cay sau rieng dang nhu mui giao rai phan nao; "
            "Bón phân gì cho đọt sầu riêng mập khỏe không rụng trái; sầu riêng đi đọt kèm trái non bón gì"
        ),
        "answer": (
            "Dạ chào bạn! Khi sầu riêng đang nhú 'mũi giáo' đồng thời đang mang trái non, "
            "bạn nên ưu tiên bón dòng Hữu cơ sinh học Cobanic kết hợp NPK cân bằng hàm lượng đạm vừa phải (như NPK Cò Bay 20-20-15 TE hoặc 16-16-16) "
            "với liều nhẹ, chia làm nhiều lần bón. Tránh rải đạm đơn hoặc NPK đạm cao vì sẽ gây phóng đọt mạnh, "
            "cạnh tranh dinh dưỡng làm rụng trái non. Bạn để lại SĐT và tuổi cây/số lượng trái để kỹ sư Cò Bay tư vấn công thức chuẩn xác nhất nhé ạ!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "medium",
        "learning_tags": "agronomy|durian|shoot_development|fruit_retention",
        "profile_slots": "crop|crop_stage|phone|area",
        "escalation_policy": "if_profile_has_phone_and_area_route_review_lead_contact_ready",
    },
    {
        "category": "agronomy",
        "intent": "cfc_agronomy_flowering_fruit_retention",
        "question_examples": (
            "Cây đang ra bông dùng loại phân nào để dai cuống chống rụng sinh lý?; "
            "Phân bón dai cuống cho cây đang ra hoa; bón gì chống rụng bông sầu riêng mít bưởi; "
            "cay dang ra bong dung phan nao de dai cuong; chong rung hoa sinh ly dung phan gi co bay"
        ),
        "answer": (
            "Dạ trong giai đoạn cây đang ra bông, để dai cuống và chống rụng hoa sinh lý, "
            "bạn nên bổ sung phân bón giàu Canxi, Bo và Kẽm kết hợp NPK Cò Bay hàm lượng Lân và Kali cao (như NPK Cò Bay 15-15-15 hoặc phân bón lá vi lượng chuyên hoa). "
            "Tuyệt đối hạn chế bón phân có hàm lượng Đạm cao lúc này để tránh cây xả bông non. "
            "Bạn nhắn lại loại cây trồng và thời tiết vườn đang mưa hay nắng để kỹ sư hướng dẫn liều phun/bón phù hợp nha!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "medium",
        "learning_tags": "agronomy|flowering|calcium_boron|fruit_drop_prevention",
        "profile_slots": "crop|crop_stage|phone|area",
        "escalation_policy": "if_profile_has_phone_and_area_route_review_lead_contact_ready",
    },
    {
        "category": "agronomy",
        "intent": "cfc_agronomy_petal_fall_fruit_set",
        "question_examples": (
            "Giai đoạn xả nhụy nên bón gì để đậu trái đều mà hãm được đọt không cho phóng tược?; "
            "Sau xả nhụy bón phân gì cho đậu trái; cach ham dot sau rieng giai doan xa nhuy; "
            "phan bon giai doan xa nhuy dau trai deu; xa nhuy xong bon phan gi"
        ),
        "answer": (
            "Dạ giai đoạn xả nhụy là thời điểm cực kỳ nhạy cảm! Để giúp đậu trái đều và chặn cây phóng đọt non, "
            "bạn nên giữ ẩm vừa phải, ngưng rải phân gốc đạm cao, ưu tiên phun qua lá các dòng Bo, Canxi hữu cơ "
            "kết hợp Kali trắng để dằn đọt. Khi trái đã chạy gai xanh ổn định mới bắt đầu nhử nhẹ NPK Cò Bay cân đối. "
            "Bạn gửi SĐT và hình ảnh đọt/bông qua tin nhắn, kỹ sư Cò Bay sẽ hỗ trợ kiểm tra trực tiếp cho vườn mình nhé ạ!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "medium",
        "learning_tags": "agronomy|petal_fall|fruit_set|shoot_suppression",
        "profile_slots": "crop|crop_stage|phone|area",
        "escalation_policy": "if_profile_has_phone_and_area_route_review_lead_contact_ready",
    },
    {
        "category": "agronomy",
        "intent": "cfc_agronomy_young_fruit_sizing",
        "question_examples": (
            "Trái non mới đậu rải NPK dòng nào để trái lớn nhanh như thổi mà không bị méo trái?; "
            "Phân bón nuôi trái non chống méo; npk lon trai tron deu co bay; "
            "trai non moi dau rai npk nao lon nhanh khong meo; trai sau rieng bi meo bon phan gi"
        ),
        "answer": (
            "Dạ khi trái non đã định hình (bằng quả trứng gà), để trái lớn nhanh, tròn đều và không bị giật hộc/méo trái, "
            "bạn nên dùng dòng NPK Cò Bay 20-20-15 TE hoặc NPK Cò Bay Ba Số Đều (15-15-15 / 16-16-16 TE) "
            "kết hợp bổ sung Trung - Vi lượng (Canxi, Magie). Nên chia nhỏ lượng bón định kỳ 10-12 ngày/lần. "
            "Bạn cho mình biết vườn đang trồng cây gì (sầu riêng, mít hay bưởi) để bên mình lên quy trình bón chuẩn nhé!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "medium",
        "learning_tags": "agronomy|young_fruit|fruit_sizing|fruit_shape",
        "profile_slots": "crop|crop_stage|phone|area",
        "escalation_policy": "if_profile_has_phone_and_area_route_review_lead_contact_ready",
    },
    {
        "category": "agronomy",
        "intent": "cfc_agronomy_root_rot_recovery",
        "question_examples": (
            "Vườn đang bị vàng lá rễ đen thui không ra rễ tơ tưới kích rễ loại nào cho cây tỉnh lại nhanh?; "
            "Cây bị vàng lá thối rễ tưới phân gì; rễ bị nghẹn rễ thối phục hồi sao; "
            "kich re phuc hoi cay vang la thoi re co bay; phan tuoi phuc hoi re den"
        ),
        "answer": (
            "Dạ tình trạng rễ đen thui, không ra rễ tơ thường do đất bị chua (pH thấp) kết hợp nấm rễ tấn công. "
            "Quy trình cứu rễ chuẩn của Cò Bay gồm 3 bước: "
            "1. Rải Lân nung chảy hoặc vôi để nâng pH đất lên > 5.5. "
            "2. Xử lý nấm bệnh bằng hoạt chất trừ nấm hoặc vi sinh đối kháng Trichoderma/Bacillus. "
            "3. Sau 5-7 ngày tưới Axit Humic/Fulvic hoặc Hữu cơ lỏng Cobanic để kích rễ tơ bung mới. "
            "Tuyệt đối KHÔNG rải phân hóa học NPK nồng độ cao lúc này vì sẽ làm cháy rễ non. Bạn để lại SĐT kỹ sư Cò Bay sẽ gọi hỗ trợ phác đồ trị bệnh nhé!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "high",
        "learning_tags": "agronomy|root_rot|yellow_leaf|humic_recovery",
        "profile_slots": "crop|symptom|phone|area",
        "escalation_policy": "if_profile_has_phone_and_area_route_review_lead_contact_ready",
    },
    {
        "category": "agronomy",
        "intent": "cfc_agronomy_pre_harvest_potassium",
        "question_examples": (
            "Sắp thu hoạch rồi đánh dòng Kali nào cho lên màu đẹp nặng ký nặng zem chắc hạt mà không cháy múi?; "
            "Bón phân gì trước thu hoạch cho ngọt trái đẹp màu; kali vao chac hat nang ky co bay; "
            "sap thu hoach danh dong kali nao cho dep mau nang ky; phan bon tao mau va do ngot"
        ),
        "answer": (
            "Dạ trước khi thu hoạch 20-30 ngày, để trái lên màu cơm vàng đẹp, đậm vị, ngọt nước, chắc hạt (nặng zem) mà không gây cháy múi, "
            "bạn nên dùng dòng NPK Cò Bay chuyên nuôi trái chín có hàm lượng Kali Sunphat (Kali trắng) cao như NPK Cò Bay 15-5-20 TE, 16-6-18 TE hoặc Kali hữu cơ. "
            "Dòng Kali Sunphat giúp tinh bột chuyển hóa thành đường nhanh, không làm tích nước hay nhạt cơm. "
            "Bạn gửi loại nông sản đang canh tác để chuyên viên Cò Bay gửi định mức bón chuẩn nha!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "medium",
        "learning_tags": "agronomy|harvest|potassium_sulfate|sweetness_color",
        "profile_slots": "crop|acreage|phone|area",
        "escalation_policy": "if_profile_has_phone_and_area_route_review_lead_contact_ready",
    },
    {
        "category": "agronomy",
        "intent": "cfc_agronomy_prevent_wet_core_souring",
        "question_examples": (
            "Làm sao để bón phân mà trái sầu riêng không bị sượng cơm cháy múi hay tích nước lúc mưa dầm?; "
            "Chống sượng cơm cháy múi sầu riêng mùa mưa; bon phan chong suong trai sau rieng; "
            "sau rieng bi chay mui phan nao chua; ky thuat bon phan khong bi tich nuoc suong com"
        ),
        "answer": (
            "Dạ hiện tượng sượng cơm, cháy múi và tích nước mùa mưa dầm thường do 3 nguyên nhân: thừa Đạm, thiếu Canxi - Bo - Magie và dư nước làm cây đi đọt non. "
            "Cách khắc phục: "
            "1. Cắt giảm hoàn toàn Đạm từ 30 ngày trước cắt trái. "
            "2. Bón NPK Cò Bay giàu Kali Sunphat (K2SO4) và bổ sung Canxi Bo định kỳ. "
            "3. Làm rãnh thoát nước gốc thật tốt, không để đọng vũng. "
            "Bạn để lại SĐT và khu vực vườn, kỹ sư Cò Bay sẽ gửi cẩm nang phòng ngừa sượng cơm chi tiết cho bạn nhé!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "medium",
        "learning_tags": "agronomy|durian|wet_core_prevention|calcium_potassium",
        "profile_slots": "crop|phone|area",
        "escalation_policy": "if_profile_has_phone_and_area_route_review_lead_contact_ready",
    },
    {
        "category": "agronomy",
        "intent": "cfc_agronomy_post_harvest_rejuvenation",
        "question_examples": (
            "Cây mới thu hoạch xong xơ xác quá rải hữu cơ nào kết hợp với đạm để bung đọt nhanh phục hồi lẹ cho vụ sau?; "
            "Phân bón phục hồi cây sau thu hoạch; phan huu co bung dot phuc hoi vuon sau cat trai; "
            "cay moi thu hoach xong xo xac qua rai phan gi; phuc hoi cay sau thu hoach co bay"
        ),
        "answer": (
            "Dạ sau thu hoạch cây bị kiệt sức, bạn cần tiến hành tỉa cành rửa vườn và phục hồi theo công thức: "
            "Bón gốc Hữu cơ Cobanic 30% (từ 3 - 5 kg/gốc tùy tuổi cây) kết hợp tưới kích rễ Humic, "
            "sau đó bón nhử NPK Cò Bay 20-20-15 TE hoặc 16-16-8 TE để kích đọt bung đồng loạt, lá dày bóng. "
            "Bộ đôi Hữu cơ Cobanic + NPK Cò Bay sẽ giúp đất tơi xốp và cây tích lũy dinh dưỡng dồi dào cho mùa hoa tới. "
            "Bạn cho mình biết diện tích vườn để tính toán số bao phân cần dùng nha!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "medium",
        "learning_tags": "agronomy|post_harvest|cobanic_organic|rejuvenation",
        "profile_slots": "crop|acreage|phone|area",
        "escalation_policy": "if_profile_has_phone_and_area_route_review_lead_contact_ready",
    },
    {
        "category": "agronomy",
        "intent": "cfc_agronomy_flower_induction_pk",
        "question_examples": (
            "Sắp tới làm bông giờ bón Lân và Kali loại nào để ép cây phân hóa mầm hoa mạnh nhất?; "
            "Phân bón làm bông tạo mầm hoa; bon lan va kali loai nao de ep phan hoa mam hoa; "
            "tao mam hoa dung phan gi co bay; phan bon lam bong sau rieng mit xoai"
        ),
        "answer": (
            "Dạ để ép cây tạo mầm hoa khỏe và ra hoa đồng loạt, công thức chuẩn là: "
            "1. Dưới gốc: Bón Lân nung chảy kết hợp Kali Sunphat hoặc NPK Cò Bay công thức Lân cao (như NPK 10-50-10 hoặc 9-25-17). "
            "2. Trên lá: Phun hoạt chất chặn đọt kết hợp MKP (Lân + Kali cao) để lá nhanh già lụa và hình thành mầm hoa. "
            "3. Siết nước tạo khô hạn cho đến khi mầm hoa nhú rõ. "
            "Bạn gửi SĐT và loại cây đang làm bông, kỹ sư nông nghiệp Cò Bay sẽ lên lịch trình cắt nước và bón phân cụ thể theo ngày cho bạn nhé!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "medium",
        "learning_tags": "agronomy|flower_induction|phosphorus_potassium|mkp",
        "profile_slots": "crop|phone|area",
        "escalation_policy": "if_profile_has_phone_and_area_route_review_lead_contact_ready",
    },
    {
        "category": "agronomy",
        "intent": "cfc_agronomy_potassium_sulfate_vs_chloride",
        "question_examples": (
            "Cây đang nuôi trái lớn bón Kali trắng Kali Sunphat hay Kali đỏ thì êm hơn cho chất lượng trái xuất khẩu?; "
            "Nên bón kali trắng hay kali đỏ nuôi trái; so sanh kali sunphat va kali clorua; "
            "kali trang hay kali do tot hon cho sau rieng; cay nuoi trai lon nen bon kali nao"
        ),
        "answer": (
            "Dạ với các dòng cây ăn trái nhạy cảm với gốc Clo (như sầu riêng, bưởi da xanh, mãng cầu, thuốc lá, tiêu) "
            "hoặc nông sản định hướng xuất khẩu, bạn **nên ưu tiên dùng Kali trắng (Kali Sunphat - K2SO4)**. "
            "Ưu điểm của Kali trắng: Không chứa gốc Clo gây sượng múi/cháy mép lá, giúp múi dẻo quánh, vỏ mỏng, ngọt thanh tự nhiên. "
            "Kali đỏ (KCl) chỉ phù hợp cho cây trồng chịu mặn tốt như lúa, ngô, mía hoặc dùng vào đầu giai đoạn nuôi trái với chi phí tiết kiệm hơn. "
            "Cò Bay có đầy đủ cả dòng NPK nền Kali trắng cao cấp, bạn nhắn lại nhu cầu để bên mình báo điểm đại lý gần nhất nha!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "low",
        "learning_tags": "agronomy|potassium_sulfate|kali_trang|export_quality",
        "profile_slots": "crop|phone|area",
        "escalation_policy": "",
    },

    # ── NHÓM 2: BÀI TOÁN KINH TẾ, BIẾN ĐỘNG GIÁ VÀ CÔNG NỢ (CÂU 11 - 18) ──
    {
        "category": "sales",
        "intent": "cfc_market_price_trend",
        "question_examples": (
            "Bao DAP Urê hôm nay giá bao nhiêu rồi tuần tới có nhích lên hay tuột xuống không?; "
            "Giá phân bón tuần này tăng hay giảm; xu huong gia phan bon sap toi; "
            "bao dap ure hom nay gia bao nhieu; gia phan ure dap co bay hom nay"
        ),
        "answer": (
            "Dạ giá phân bón (DAP, Urê, NPK) biến động theo ngày theo giá nguyên liệu thế giới và chính sách vận chuyển từng khu vực. "
            "Để nhận thông báo bảng giá cập nhật sớm nhất hôm nay và dự báo xu hướng tuần tới từ Cò Bay, "
            "bạn vui lòng để lại số điện thoại và tỉnh/huyện đang canh tác. Chuyên viên kinh doanh Cò Bay khu vực sẽ liên hệ gửi báo giá đại lý/nhà vườn chi tiết cho bạn nha!"
        ),
        "priority": 90,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "medium",
        "learning_tags": "sales|price_trend|dap_urea|lead_capture",
        "profile_slots": "product|phone|area",
        "escalation_policy": "if_profile_has_phone_and_area_route_review_lead_contact_ready",
    },
    {
        "category": "quality",
        "intent": "cfc_quality_vs_imported",
        "question_examples": (
            "Loại phân Cò Bay này xài có êm bằng hàng ngoại cũ tui hay dùng không giá rẻ hơn nhiều không?; "
            "Phân Cò Bay chất lượng so với phân nhập khẩu thế nào; phan noi dia cfc co bang hang ngoai; "
            "xai phan co bay co hieu qua nhu phan nhap khau khong; gia phan co bay re hon hang ngoai khong"
        ),
        "answer": (
            "Dạ phân bón CFC Cò Bay được sản xuất trên dây chuyền công nghệ Tháp Cao hiện đại, "
            "với nguồn nguyên liệu chọn lọc tương đương chuẩn quốc tế nhưng giá thành tiết kiệm hơn 15 - 25% do không phải chịu thuế nhập khẩu và chi phí vận chuyển biển cao. "
            "Đặc biệt, công thức phân Cò Bay được nghiên cứu chuyên biệt cho đất và khí hậu Việt Nam (chống chua đất, giữ dinh dưỡng mùa mưa dầm), "
            "giúp cây xanh bền, rễ mập mà không bị bốc nhanh rồi sụp cây. Bạn có thể bón thử nghiệm trên một liếp vườn để đối chứng hiệu quả thực tế nhé!"
        ),
        "priority": 90,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "low",
        "learning_tags": "quality|cfc_vs_imported|cost_effective|tower_tech",
        "profile_slots": "crop|phone|area",
        "escalation_policy": "",
    },
    {
        "category": "agronomy",
        "intent": "cfc_organic_dosage_cost_saving",
        "question_examples": (
            "Mua dòng hữu cơ vi sinh này tốn kém quá một gốc rải mấy ký là vừa túi tiền?; "
            "Định mức rải phân hữu cơ tiết kiệm chi phí; mot goc sau rieng rai may kg huu co; "
            "cach bon huu co tiet kiem tien ma van tot cay; dinh muc bon huu co cobanic"
        ),
        "answer": (
            "Dạ để bón phân Hữu cơ Cobanic vừa khỏe cây vừa tiết kiệm chi phí tối đa, "
            "bạn nên áp dụng nguyên tắc: "
            "- Cây kiến thiết cơ bản (1-3 năm): 1 - 2 kg/gốc/đợt (mỗi năm 3-4 đợt). "
            "- Cây kinh doanh (nuôi trái): 3 - 5 kg/gốc sau khi thu hoạch để phục hồi bộ rễ. "
            "Mẹo tiết kiệm: Rải phân kết hợp cuốc xới nhẹ quanh tán và lấp lớp đất mỏng/lá khô để tránh nắng gắt làm bay hơi chất hữu cơ. "
            "Bạn nhắn loại cây và số lượng gốc trong vườn, bên mình sẽ tính toán số bao phân tối ưu ngân sách nhất cho bạn nha!"
        ),
        "priority": 90,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "low",
        "learning_tags": "agronomy|organic_dosage|cost_optimization|cobanic",
        "profile_slots": "crop|acreage|phone|area",
        "escalation_policy": "",
    },
    {
        "category": "sales",
        "intent": "cfc_credit_payment_policy",
        "question_examples": (
            "Có cho ghi sổ không tới cuối vụ bán trái xong tui ra thanh toán một lượt nhé?; "
            "Chính sách mua phân bón nợ cuối vụ; co cho mua phan tra sau khong; "
            "mua phan co bay thanh toan cuoi vu duoc khong; chinh sach cong no dai ly co bay"
        ),
        "answer": (
            "Dạ chính sách công nợ (ghi sổ cuối vụ) sẽ do các Đại lý và Nhà phân phối Cò Bay tại địa phương trực tiếp xem xét và hỗ trợ cho bà con thân thiết. "
            "Công ty Cổ phần Phân bón & Hóa chất Cần Thơ (CFC) luôn có các chương trình trợ giá và liên kết đại lý để tạo điều kiện thuận lợi nhất cho nhà nông. "
            "Bạn để lại số điện thoại và địa bàn xã/huyện, admin sẽ kết nối bạn với đại lý Cò Bay gần nhất để trao đổi chính sách thanh toán linh hoạt nhé ạ!"
        ),
        "priority": 90,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "medium",
        "learning_tags": "sales|credit_policy|dealer_payment|lead_capture",
        "profile_slots": "phone|area",
        "escalation_policy": "if_profile_has_phone_and_area_route_review_lead_contact_ready",
    },

    # ── NHÓM 3: CHẤT LƯỢNG PHÂN BÓN VÀ MẸO THỬ THẬT - GIẢ TẠI NHÀ (CÂU 19 - 26) ──
    {
        "category": "quality",
        "intent": "cfc_tower_npk_vs_bulk_blend",
        "question_examples": (
            "NPK này là hàng tháp cao phức hợp hay hàng trộn thủ công rải xuống có tan hết không?; "
            "Phân bón tháp cao Cò Bay là gì; phan bon phuc hop khac phan tron the nao; "
            "npk co bay la thap cao hay tron; phan npk co bay rai xuong co tan het khong"
        ),
        "answer": (
            "Dạ các dòng NPK chủ lực của Cò Bay được sản xuất bằng **Công nghệ Tháp Cao (Phức hợp)** tiên tiến nhất hiện nay! "
            "Khác biệt hoàn toàn với phân trộn 3 màu thủ công: "
            "1. Từng hạt phân đều chứa đầy đủ N-P-K và vi lượng đồng nhất từ vỏ đến lõi, không bị phân lớp khi vận chuyển. "
            "2. Hạt phân tròn bóng, độ tan cực kỳ nhanh và tan hoàn toàn 100% khi gặp ẩm, giúp rễ cây hấp thụ trọn vẹn không để lại cặn bã chai đất. "
            "Bạn có thể lấy vài hạt phân Cò Bay hòa vào ly nước sẽ thấy phân tan nhanh trong 1-2 phút nhé ạ!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "low",
        "learning_tags": "quality|tower_technology|homogeneous_grain|solubility",
        "profile_slots": "product|phone|area",
        "escalation_policy": "",
    },
    {
        "category": "quality",
        "intent": "cfc_test_fake_fertilizer_guide",
        "question_examples": (
            "Cách thử phân bón thật giả tại nhà; mẹo thử urê kali npk thật giả; "
            "thử hòa tan urê vào nước có lạnh tay không; dot hat phan tren lua mui khai amoniac; "
            "kali do that khi khuay co de lai can bot gach khong; lam sao biet phan bon gia"
        ),
        "answer": (
            "Dạ Cò Bay chia sẻ với bạn 3 mẹo kiểm tra phân bón thật - giả cực chuẩn ngay tại nhà: "
            "1. **Thử Nước (Urê & Kali):** Urê thật tan rất nhanh và làm nước **lạnh buốt tay**. Kali đỏ thật tan hoàn toàn trong nước, nước có màu hồng/đỏ nhạt nhưng **không để lại lớp cặn bột gạch dày** ở đáy ly. "
            "2. **Thử Lửa (Đạm & NPK):** Đặt hạt phân lên miếng sắt nung nóng, phân thật sẽ nóng chảy, sủi bọt và bốc mùi khai nồng (Amoniac). Phân giả pha bột đá sẽ không tan, cháy đen hoặc nổ lách tách. "
            "3. **Cảm Quan Hạt Tháp Cao:** Hạt phân Cò Bay bẻ đôi ra có màu sắc và cấu trúc đồng nhất từ trong ra ngoài, hạt cứng, không bị nhuộm màu bên ngoài. "
            "Bà con nên mua tại đại lý ủy quyền của Cò Bay để đảm bảo 100% hàng chính hãng nha!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "low",
        "learning_tags": "quality|fake_fertilizer_detection|urea_test|potassium_test",
        "profile_slots": "",
        "escalation_policy": "",
    },
    {
        "category": "quality",
        "intent": "cfc_fertilizer_caking_storage",
        "question_examples": (
            "Sao bao phân này mở ra thấy chảy nước bết dính vậy có bị rút ruột hàm lượng không?; "
            "Phân bón bị vón cục chảy nước có xài được không; cach bao quan phan bon khong bi chay nuoc; "
            "phan bi bet dinh co giam chat luong khong co bay; bao quan phan bon dung cach"
        ),
        "answer": (
            "Dạ hiện tượng phân bón bị ẩm hoặc bết dính nhẹ thường do đặc tính hút ẩm tự nhiên của Đạm (Urê) và Kali khi tiếp xúc với không khí ẩm, "
            "hoàn toàn **không bị rút ruột hay giảm hàm lượng dinh dưỡng**. "
            "Cách bảo quản chuẩn: "
            "- Để bao phân trên pallet gỗ cách mặt đất 15-20cm, cách tường 20cm. "
            "- Bao đã mở miệng nên buộc thật kín bằng dây sau khi lấy phân. "
            "- Tránh để phân tiếp xúc trực tiếp với ánh nắng gắt hoặc nơi ẩm ướt. "
            "Nếu hạt phân bị vón cục, bạn chỉ cần bóp nhẹ là phân tơi ra và rải bình thường nhé ạ!"
        ),
        "priority": 85,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "low",
        "learning_tags": "quality|storage|caking_prevention|moisture_absorption",
        "profile_slots": "",
        "escalation_policy": "",
    },

    # ── NHÓM 4: THÍCH ỨNG THỜI TIẾT BẤT LỢI VÀ THỔ NHƯỠNG (CÂU 27 - 34) ──
    {
        "category": "soil_weather",
        "intent": "cfc_saline_alum_soil_treatment",
        "question_examples": (
            "Đất vườn đang bị phèn mặn rải Lân nung chảy hay Canxi để hạ phèn trước khi bón NPK?; "
            "Cách hạ phèn rửa mặn cho đất vườn; dat bi nhiem man bon phan gi; "
            "dat vuon bi phen man xu ly sao; phan bon ha phen giai doc dat cfc"
        ),
        "answer": (
            "Dạ khi đất bị nhiễm phèn hoặc hạn mặn, rễ cây bị bó và ngộ độc kim loại, bón NPK ngay sẽ làm rễ cháy nhanh hơn! "
            "Quy trình xử lý đất phèn mặn chuẩn: "
            "1. **Hạ phèn:** Rải **Lân nung chảy** kết hợp Vôi/Canxi (từ 300 - 500 kg/ha) để cố định độc chất nhôm sắt, nâng pH đất lên mức an toàn (5.5 - 6.5). "
            "2. **Rửa mặn & Dưỡng rễ:** Tưới Axit Humic hoặc bón Hữu cơ Cobanic để tạo phức chelate đẩy muối mặn ra khỏi vùng rễ và kích rễ tơ tái sinh. "
            "3. Khi cây nhú rễ tơ mới bắt đầu bón lại NPK Cò Bay với lượng nhẹ. "
            "Bạn để lại SĐT và đo giúp mình độ mặn/độ pH hiện tại, kỹ sư Cò Bay sẽ hỗ trợ hướng dẫn chi tiết nhé!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "medium",
        "learning_tags": "soil_weather|saline_alum|fused_magnesium_phosphate|ph_remedy",
        "profile_slots": "crop|symptom|phone|area",
        "escalation_policy": "if_profile_has_phone_and_area_route_review_lead_contact_ready",
    },
    {
        "category": "soil_weather",
        "intent": "cfc_rainy_season_leaching_prevention",
        "question_examples": (
            "Trời đang mưa dầm rải phân có sợ bị rửa trôi hết không có loại nào chậm tan không?; "
            "Bón phân mùa mưa dầm chống rửa trôi; mua dam rai phan gi khong bi troi; "
            "cach bon phan mua mua hieu qua khong bi that thoat; phan bon mua mua cfc co bay"
        ),
        "answer": (
            "Dạ mùa mưa dầm nguy cơ thất thoát phân bón do rửa trôi và xói mòn rất lớn (lên tới 40 - 50%)! "
            "Bí quyết bón phân mùa mưa của Cò Bay: "
            "1. **Chia nhỏ cữ bón:** Thay vì bón 1 lần nhiều phân, hãy chia làm 2-3 đợt bón cách nhau 10 ngày. "
            "2. **Dùng Hữu cơ lót nền:** Rải Hữu cơ Cobanic giúp tăng dung tích hấp thu của đất, giữ hạt phân NPK lại quanh vùng rễ không bị trôi tuột xuống mương. "
            "3. **Công nghệ Tháp cao Cò Bay:** Tan đều và ngấm sâu vào đất theo rễ, không bị bốc hơi. "
            "Bạn nhắn diện tích vườn để bên mình tính toán lịch rải phân đón mưa an toàn nhé!"
        ),
        "priority": 90,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "low",
        "learning_tags": "soil_weather|rainy_season|leaching_prevention|split_application",
        "profile_slots": "crop|acreage|phone|area",
        "escalation_policy": "",
    },
    {
        "category": "soil_weather",
        "intent": "cfc_basalt_soil_compaction_remedy",
        "question_examples": (
            "Đất đỏ bazan xài lâu năm bị chai cứng bón phân gì cho đất tơi xốp giữ nước tốt mùa khô?; "
            "Cải tạo đất chai cứng đất bạc màu; dat do bazan bi chai cung bon gi cho xop; "
            "phan cai tao dat chai cung giu am mua kho; lam sao cho dat toi xop tro lai"
        ),
        "answer": (
            "Dạ đất đỏ bazan hoặc đất vườn canh tác lâu năm bị chai cứng là do mất đi lớp mùn hữu cơ và vi sinh vật bản địa. "
            "Giải pháp cải tạo đất bền vững của Cò Bay: "
            "1. Bổ sung **Hữu cơ vi sinh Cobanic** định kỳ (3 - 5 tấn/ha/năm) để tái tạo kết cấu xốp như bọt biển cho đất, giúp giữ ẩm cực tốt qua 6 tháng mùa khô Tây Nguyên. "
            "2. Tưới bổ sung Humic Acid để giải phóng các hạt sét bị nén chặt và mở rộng đường cho rễ cây thở. "
            "3. Giữ thảm cỏ vườn (cắt cỏ để lại thân mục) thay vì xịt thuốc diệt cỏ làm trơ trọi đất. "
            "Bạn nhắn lại vị trí vườn (Tây Nguyên hay Miền Đông/Miền Tây) để kỹ sư Cò Bay tư vấn định mức cải tạo đất nhé!"
        ),
        "priority": 90,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "low",
        "learning_tags": "soil_weather|soil_compaction|basalt_soil|cobanic_humic",
        "profile_slots": "crop|acreage|phone|area",
        "escalation_policy": "",
    },
    {
        "category": "soil_weather",
        "intent": "cfc_micronutrient_te_deficiency",
        "question_examples": (
            "Cây bị vàng lá gân xanh có phải do thiếu vi lượng TE không?; "
            "Dấu hiệu cây thiếu vi lượng TE; cay vang la gan xanh bo sung phan gi; "
            "vi luong te trong phan bon co tac dung gi; cfc co dong phan bo sung te khong"
        ),
        "answer": (
            "Dạ hiện tượng 'vàng lá gân xanh' (thịt lá chuyển vàng nhưng gân lá vẫn giữ màu xanh) "
            "là dấu hiệu điển hình của việc cây bị **thiếu Trung - Vi lượng (Magiê, Kẽm, Sắt, Mangan, Bo)**. "
            "Cách xử lý nhanh: "
            "1. Phun qua lá dung dịch vi lượng Chelate tổng hợp để lá hấp thụ tức thì sau 3-5 ngày. "
            "2. Dưới gốc: Chuyển sang dùng các dòng **NPK Cò Bay có ký hiệu TE** (như NPK Cò Bay 20-20-15 TE, 16-16-8 TE) "
            "được tích hợp sẵn vi lượng dạng khoáng dễ tiêu, giúp cây quang hợp mạnh mẽ và lá xanh dày trở lại. "
            "Bạn chụp ảnh lá gửi qua tin nhắn để chuyên viên Cò Bay chẩn đoán chính xác loại vi lượng đang thiếu nha!"
        ),
        "priority": 90,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "low",
        "learning_tags": "soil_weather|micronutrients|te|yellow_vein_deficiency",
        "profile_slots": "crop|symptom|phone|area",
        "escalation_policy": "",
    },

    # ── NHÓM 5: KỸ THUẬT SỬ DỤNG VÀ THÓI QUEN PHỐI TRỘN (CÂU 35 - 42) ──
    {
        "category": "agronomy",
        "intent": "cfc_foliar_mix_pesticide_safety",
        "question_examples": (
            "Pha phân bón lá chung với thuốc sâu thuốc rầy xịt một lần có bị kết tủa đục nước không?; "
            "Trộn phân bón lá với thuốc bảo vệ thực vật được không; pha chung phan va thuoc sau co bi ket tua khong; "
            "cach pha chung phan bon la va thuoc tru sau; tai sao pha chung phan thuoc bi dong can"
        ),
        "answer": (
            "Dạ bạn hoàn toàn có thể phối trộn phân bón lá với thuốc trừ sâu rầy để tiết kiệm công phun xịt, "
            "nhưng cần tuân thủ **Quy tắc thử nghiệm 3 phút**: "
            "1. Múc 1 ca nước nhỏ, cho thuốc và phân bón lá vào khuấy đều. Nếu nước đồng nhất, không sủi bọt lạ, không kết tủa hay vón cục đóng cặn đáy ca thì phối trộn an toàn. "
            "2. **Thứ tự pha phuy 200L:** Thuốc dạng bột (WP) -> Thuốc dạng sữa/nhũ dầu (EC/SC) -> Phân bón lá hòa tan cuối cùng. "
            "3. **Lưu ý:** Không pha chung phân bón giàu Canxi, Đồng (Gốc đồng) với các loại thuốc gốc Lân hoặc Lưu huỳnh vì sẽ tạo cặn làm cháy lá và nghẹt béc xịt. "
            "Bạn nhắn tên loại phân thuốc đang muốn pha để kỹ sư kiểm tra tính tương thích cho an toàn nhé!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "medium",
        "learning_tags": "agronomy|tank_mix|compatibility|pesticide_foliar",
        "profile_slots": "crop|product|phone|area",
        "escalation_policy": "",
    },
    {
        "category": "agronomy",
        "intent": "cfc_mix_npk_with_organic",
        "question_examples": (
            "Trộn NPK chung với phân hữu cơ rải một lượt luôn cho đỡ tốn công được không?; "
            "Có nên trộn phân hóa học với phân hữu cơ rải chung; tron npk chung voi huu co rai duoc khong; "
            "cach tron phan huu co va npk rai mot lan; tron phan bon tiet kiem cong lao dong"
        ),
        "answer": (
            "Dạ bạn **HOÀN TOÀN CÓ THỂ** trộn NPK Cò Bay chung với Hữu cơ Cobanic để rải cùng một lần giúp tiết kiệm công lao động! "
            "Lợi ích: Chất hữu cơ sẽ bao bọc các hạt NPK, giảm thất thoát do bốc hơi và giữ phân tan từ từ quanh vùng rễ. "
            "**Nguyên tắc quan trọng:** "
            "- Trộn xong nên mang đi rải ngay trong ngày, không để phân đã trộn qua đêm vì phân sẽ hút ẩm và vón cục. "
            "- Nếu là dòng **Hữu cơ vi sinh vật sống** (chứa nấm đối kháng Trichoderma), không nên trộn với lượng NPK quá đậm đặc vì nồng độ muối khoáng cao có thể làm giảm mật độ vi sinh. "
            "Bạn cho mình biết công thức phân dự kiến trộn để kỹ sư Cò Bay góp ý tỷ lệ chuẩn nha!"
        ),
        "priority": 90,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "low",
        "learning_tags": "agronomy|mix_npk_organic|labor_saving|cobanic",
        "profile_slots": "crop|acreage|phone|area",
        "escalation_policy": "",
    },
    {
        "category": "agronomy",
        "intent": "cfc_drip_irrigation_solubility",
        "question_examples": (
            "Phân Cò Bay có hòa tan 100% để tưới qua hệ thống nhỏ giọt mà không nghẹt béc không?; "
            "Phân bón tưới hệ thống nhỏ giọt tưới béc cfc; phan bon hoa tan hoan toan tuoi nho giot; "
            "npk co bay co tuoi he thong nho giot duoc khong; phan tuoi nho giot chong nghet bec"
        ),
        "answer": (
            "Dạ Cò Bay có các dòng sản phẩm NPK Tháp Cao hòa tan nhanh và dòng phân bón tưới nhỏ giọt chuyên dụng (Fertigation)! "
            "Đặc điểm: Độ tinh khiết cực cao, tan 100% trong nước, không chứa tạp chất không tan hoặc cặn bã, "
            "giúp nước phân lưu thông mượt mà qua hệ thống dây nhỏ giọt và đầu béc bù áp mà không sợ nghẹt béc. "
            "Bạn để lại SĐT và loại cây/quy mô hệ thống tưới tự động, bên mình sẽ gửi danh mục các dòng phân tưới nhỏ giọt phù hợp nhất nhé!"
        ),
        "priority": 90,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "low",
        "learning_tags": "agronomy|drip_irrigation|solubility|fertigation",
        "profile_slots": "crop|acreage|phone|area",
        "escalation_policy": "if_profile_has_phone_and_area_route_review_lead_contact_ready",
    },

    # ── NHÓM 6: ĐỐI THOẠI VÔ CƠ & HỮU CƠ VI SINH (CÂU 43 - 50) ──
    {
        "category": "agronomy",
        "intent": "cfc_organic_before_chemical_rule",
        "question_examples": (
            "Hữu cơ đi trước Hóa học theo sau là sao cách nhau bao nhiêu ngày là chuẩn?; "
            "Quy tắc bón hữu cơ trước hóa học sau; cach nhau bao nhieu ngay giua huu co va npk; "
            "huu co di truoc hoa hoc theo sau la gi; khoang cach ngay giua bon huu co va hoa hoc"
        ),
        "answer": (
            "Dạ 'Hữu cơ đi trước, Hóa học theo sau' là quy tắc vàng trong canh tác nông nghiệp thông minh: "
            "1. **Bón Hữu cơ trước (Ngày 1):** Bón Hữu cơ Cobanic để 'nuôi đất', kích hoạt hệ vi sinh vật và kích thích rễ non bung ra tạo mạng lưới rễ cám dày đặc. "
            "2. **Bón NPK theo sau (Cách 7 - 10 ngày):** Khi rễ tơ đã sẵn sàng, bạn bón NPK Cò Bay vào. Lúc này rễ cây sẽ hấp thụ phân hóa học đạt hiệu suất tối đa (80-90%), "
            "tránh tình trạng rải NPK trên nền đất trơ làm cháy rễ và thất thoát phân bón. "
            "Bạn nhắn loại cây và giai đoạn để Cò Bay lên bảng lịch bón phân chuẩn từng tuần nha!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "low",
        "learning_tags": "agronomy|organic_before_chemical|fertilizer_timing|root_priming",
        "profile_slots": "crop|phone|area",
        "escalation_policy": "",
    },
    {
        "category": "agronomy",
        "intent": "cfc_5_signs_beneficial_microbes",
        "question_examples": (
            "Làm sao biết mấy con vi sinh đang hoạt động dưới gốc có dấu hiệu gì nhìn thấy được không?; "
            "5 dấu hiệu vi sinh hoạt động tốt trong đất; cach nhan biet vi sinh phat trien quanh goc; "
            "dau hieu dat tot nho vi sinh huu co; to nam trang quanh goc cay la gi"
        ),
        "answer": (
            "Dạ Cò Bay chia sẻ với bạn **5 dấu hiệu nhận biết mắt thường** cho thấy vi sinh vật đang hoạt động cực tốt quanh gốc sau khi bón Hữu cơ Cobanic: "
            "1. **Tơ nấm trắng:** Xuất hiện các mảng tơ nấm trắng mỏng chằng chịt như mạng nhện dưới lớp lá mục/phân hữu cơ (đây là nấm có lợi phân hủy xenlulozo). "
            "2. **Đùn phân trùn:** Đất xuất hiện nhiều ụ phân trùn đất đùn lên, đất tơi xốp rõ rệt. "
            "3. **Mùi đất ngọt thơm:** Đất có mùi mùn ngai ngái dễ chịu sau mưa, không còn mùi chua nồng hay hôi thối. "
            "4. **Kết cấu xốp mềm:** Đất chuyển màu nâu sẫm, xốp như miếng bọt biển, bóp nhẹ là vỡ vụn không đóng váng. "
            "5. **Rễ tơ trắng muốt:** Lớp rễ cám mập mạp mọc trồi lên tầng mặt để ăn dinh dưỡng. "
            "Vườn bạn đã có những dấu hiệu nào trong 5 dấu hiệu trên chưa ạ?"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "low",
        "learning_tags": "agronomy|microbes_signs|soil_health|white_hyphae|earthworms",
        "profile_slots": "",
        "escalation_policy": "",
    },
    {
        "category": "agronomy",
        "intent": "cfc_raw_manure_vs_composted",
        "question_examples": (
            "Phân bò phân gà tươi bón trực tiếp có được không hay bắt buộc phải ủ hoai?; "
            "Bón phân chuồng tươi có hại cây không; tai sao phan chuong phai u hoai moi duoc bon; "
            "phan ga phan bo tuoi bon truc tiep co sao khong; nguy co khi bon phan chuong chua u"
        ),
        "answer": (
            "Dạ bạn **TUYỆT ĐỐI KHÔNG NÊN** bón phân chuồng tươi (phân bò, phân gà tươi) trực tiếp vào gốc cây! "
            "Tác hại nghiêm trọng của phân tươi: "
            "1. Sinh nhiệt độ cao (quá trình tự ủ dưới gốc) làm **cháy rễ non**. "
            "2. Mang theo mầm bệnh tuyến trùng, nấm Phytophthora gây vàng lá thối rễ và hạt cỏ dại. "
            "3. Tạo môi trường cho ấu trùng sùng đất và ruồi đục rễ phát triển. "
            "**Khuyến nghị:** Hãy ủ hoai bằng nấm Trichoderma từ 45-60 ngày hoặc sử dụng trực tiếp dòng **Hữu cơ sinh học Cobanic 30%** của Cò Bay đã được xử lý thanh trùng, khử mùi và bổ sung vi sinh có lợi sẵn, rải vừa an toàn vừa tiện lợi nhé ạ!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "medium",
        "learning_tags": "agronomy|raw_manure_danger|composting|cobanic_alternative",
        "profile_slots": "crop|phone|area",
        "escalation_policy": "",
    },
    {
        "category": "agronomy",
        "intent": "cfc_microbe_fungicide_interval",
        "question_examples": (
            "Vừa bón vi sinh xong mà đổ thuốc nấm hóa học xuống thì có phí tiền không?; "
            "Khoảng cách giữa bón vi sinh và tưới thuốc trị nấm; thuoc nam co lam chet vi sinh khong; "
            "vua bon huu co vi sinh co duoc xit thuoc nam hoa hoc khong; khoang cach an toan giua vi sinh va thuoc benh"
        ),
        "answer": (
            "Dạ nếu vừa bón phân vi sinh xong mà tưới ngay thuốc trừ nấm hóa học (như Mancozeb, Ridomil, Hexaconazole...) thì thuốc sẽ **tiêu diệt toàn bộ vi sinh vật có lợi**, làm lãng phí 100% tiền mua phân vi sinh! "
            "**Quy tắc chuẩn:** "
            "- Nếu cây đang bị bệnh rễ nặng: Xử lý thuốc nấm hóa học trước để chặn đứng mầm bệnh. "
            "- Sau **7 - 10 ngày** khi thuốc hóa học đã phân hủy hết độc lực, mới tiến hành tưới bổ sung vi sinh đối kháng và Hữu cơ Cobanic để phục hồi đất. "
            "Bạn để lại SĐT và tình trạng bệnh của vườn, kỹ sư Cò Bay sẽ hỗ trợ hướng dẫn quy trình luân phiên an toàn nha!"
        ),
        "priority": 95,
        "source_id": "cfc_handbook_50_nha_nong_v1",
        "risk_level": "medium",
        "learning_tags": "agronomy|fungicide_microbe_safety|interval_timing|disease_management",
        "profile_slots": "crop|symptom|phone|area",
        "escalation_policy": "if_profile_has_phone_and_area_route_review_lead_contact_ready",
    },
]


def clean_text(s: str) -> str:
    if not s:
        return ""
    # Chuẩn hóa khoảng trắng
    return re.sub(r"\s+", " ", str(s)).strip()


def run_merge():
    print("Reading existing CSV from:", CSV_PATH)
    existing_rows = []
    fieldnames = [
        "active",
        "brand",
        "category",
        "intent",
        "question_examples",
        "answer",
        "priority",
        "source_id",
        "updated_at",
        "audience",
        "answer_mode",
        "risk_level",
        "learning_tags",
        "profile_slots",
        "escalation_policy",
    ]

    existing_intents = set()
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                intent = row.get("intent", "").strip()
                if intent:
                    existing_intents.add(intent)
                existing_rows.append(row)
        print(f"Loaded {len(existing_rows)} existing rows from CSV.")

    # Thêm các row mới nếu chưa tồn tại intent
    added_count = 0
    for entry in NEW_FAQ_ENTRIES:
        intent = entry["intent"]
        if intent in existing_intents:
            print(f"Skipping duplicate intent: {intent}")
            continue

        new_row = {
            "active": "TRUE",
            "brand": "CFC",
            "category": entry.get("category", "agronomy"),
            "intent": intent,
            "question_examples": clean_text(entry.get("question_examples", "")),
            "answer": clean_text(entry.get("answer", "")),
            "priority": str(entry.get("priority", 90)),
            "source_id": entry.get("source_id", "cfc_handbook_50_nha_nong_v1"),
            "updated_at": "2026-08-28",
            "audience": "customer",
            "answer_mode": "direct",
            "risk_level": entry.get("risk_level", "low"),
            "learning_tags": entry.get("learning_tags", "agronomy|faq"),
            "profile_slots": entry.get("profile_slots", ""),
            "escalation_policy": entry.get("escalation_policy", ""),
        }
        existing_rows.append(new_row)
        existing_intents.add(intent)
        added_count += 1

    print(f"Added {added_count} new FAQ rows from 50 questions handbook.")
    print(f"Total rows now: {len(existing_rows)}")

    # Ghi đè file CSV chính
    with open(CSV_PATH, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)
    print(f"Successfully updated main CSV: {CSV_PATH}")

    # Ghi file copy STANDARDIZED
    with open(OUTPUT_FULL_CSV, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)
    print(f"Successfully created standardized CSV: {OUTPUT_FULL_CSV}")


if __name__ == "__main__":
    run_merge()
