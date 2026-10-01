"""
build_exact_shopee_catalog.py — Chuẩn hóa 100% Top 10 Bán Chạy Nhất & Top 10 Mới Nhất theo ảnh thật Shopee
"""

import csv
import json
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

INPUT_DIR = Path(__file__).resolve().parents[2] / "google_upload"
OUTPUT_CSV = INPUT_DIR / "zeo_shopee_catalog_template.csv"

ALL_VERIFIED_ITEMS = [
    # ==========================================
    # 🔥 TOP 10 BÁN CHẠY NHẤT (THEO ẢNH SHOPEE "BÁN CHẠY")
    # ==========================================
    {
        "name": "Nước rửa chén Vitamin E Pano Hương chanh, Sạch dầu mỡ - khử mùi tanh - dịu da tay, Nhiều dung tích",
        "brand": "PANO", "category": "Nước rửa chén", "price": 12350, "original_price": 13140, "discount": "6%", "in_stock": True,
        "badge": "BEST_SELLER_TOP_1",
        "keywords": "nuoc rua chen; pano; vitamin e; chanh; diu da tay; rua bat; ban chay; top 1; best seller; 309 da ban",
        "specs": "Chai 400g / 800g / Can 3.8kg", "variants": "Chai 400g; Chai 800g; Can 3.8kg"
    },
    {
        "name": "[GIÁ RẺ] Bột giặt Pano Hương cam chanh & oải hương, Sạch quần áo - ít cặn - lưu hương lâu, Túi 300g/ 2.4kg/ 5.5kg",
        "brand": "PANO", "category": "Bột giặt", "price": 46350, "original_price": 51500, "discount": "10%", "in_stock": True,
        "badge": "BEST_SELLER_TOP_2",
        "keywords": "bot giat; pano; cam chanh; oai huong; gia re; giat tay; giat may; ban chay; top 2; 291 da ban",
        "specs": "Túi 300g / 2.4kg / 5.5kg", "variants": "Túi 300g; Túi 2.4kg; Túi 5.5kg"
    },
    {
        "name": "Bột giặt ZeO Nha Đam lưu hương kép 400g/720g hương nha đam the mát, giặt tay giặt máy dịu nhẹ sạch vết bẩn",
        "brand": "ZeO", "category": "Bột giặt", "price": 17550, "original_price": 27000, "discount": "35%", "in_stock": True,
        "badge": "BEST_SELLER_TOP_3",
        "keywords": "bot giat; zeo; nha dam; diu nhe; em be; giat tay; giat may; ban chay; top 3; 285 da ban",
        "specs": "Túi 400g / 720g", "variants": "Túi 400g; Túi 720g"
    },
    {
        "name": "Nước giặt Pano Hương táo - dứa - hoa nhài - đào, Làm sạch - khử mùi - lưu hương lâu, Túi 3.5kg",
        "brand": "PANO", "category": "Nước giặt", "price": 95058, "original_price": 202251, "discount": "53%", "in_stock": True,
        "badge": "BEST_SELLER_TOP_4",
        "keywords": "nuoc giat; pano; tao dua hoa nhai dao; tui 3.5kg; veilex; ban chay; top 4; 980 da ban",
        "specs": "Túi 3.5kg", "variants": "Túi 3.5kg"
    },
    {
        "name": "Nước tẩy toilet đậm đặc ZeO Hương trái cây, Tẩy cặn vôi - ố vàng - khử mùi hôi, Chai 650ml",
        "brand": "ZeO", "category": "Tẩy Toilet", "price": 23000, "original_price": 46000, "discount": "50%", "in_stock": True,
        "badge": "BEST_SELLER_TOP_5",
        "keywords": "tay toilet; bon cau; zeo; trai cay; tay can voi; o vang; ban chay; top 5; 206 da ban",
        "specs": "Chai 650ml", "variants": "Chai 650ml"
    },
    {
        "name": "Nước tẩy quần áo trắng ZeO Javel chai 500ml/1000ml không hương liệu, tẩy trắng mạnh - diệt khuẩn quần áo, bề mặt",
        "brand": "ZeO", "category": "Nước tẩy trắng Javen", "price": 10400, "original_price": 16000, "discount": "35%", "in_stock": True,
        "badge": "BEST_SELLER_TOP_6",
        "keywords": "javel; javen; nuoc tay; thuoc tay; tay trang; zeo; diet khuan; ban chay; top 6; 91 da ban",
        "specs": "Chai 500ml / 1000ml", "variants": "Chai 500ml; Chai 1000ml"
    },
    {
        "name": "Nước rửa chén Pano Hương chanh tự nhiên, Sạch dầu mỡ - khử mùi tanh - dịu da tay, 400g/800g/1.5kg",
        "brand": "PANO", "category": "Nước rửa chén", "price": 13000, "original_price": 22800, "discount": "43%", "in_stock": True,
        "badge": "BEST_SELLER_TOP_7",
        "keywords": "nuoc rua chen; pano; chanh tu nhien; sach dau mo; rua bat; ban chay; top 7; 106 da ban",
        "specs": "Chai 400g / 800g / 1.5kg", "variants": "Chai 400g; Chai 800g; Can 1.5kg"
    },
    {
        "name": "[COMBO 10 gói] Nước xả vải Nano Clean ZeO Hương hoa trắng & xạ hương, Mềm vải - giảm nhăn, 10 gói x 20g",
        "brand": "ZeO", "category": "Nước xả vải", "price": 17100, "original_price": 18000, "discount": "5%", "in_stock": True,
        "badge": "BEST_SELLER_TOP_8",
        "keywords": "nuoc xa vai; nano clean; zeo; combo 10 goi; hoa trang; xa huong; ban chay; top 8; 84 da ban",
        "specs": "10 gói x 20g", "variants": "Combo 10 gói"
    },
    {
        "name": "Nước giặt 2in1 Oplus Hương nước hoa Pháp, Sạch sâu - mềm vải - không cần nước xả, Can 1kg/3.5kg",
        "brand": "Oplus", "category": "Nước giặt", "price": 62100, "original_price": 69000, "discount": "10%", "in_stock": True,
        "badge": "BEST_SELLER_TOP_9",
        "keywords": "nuoc giat; oplus; 2in1; nuoc hoa phap; can 1kg; can 3.5kg; ban chay; top 9; 340 da ban",
        "specs": "Can 1kg / Can 3.5kg", "variants": "Can 1kg; Can 3.5kg"
    },
    {
        "name": "[SIÊU TIẾT KIỆM] Nước lau sàn Pano Hương Hoa Hạ & phấn em bé, Sạch sàn - khử mùi - thơm lâu, Chai/ Can 1kg/3.8kg",
        "brand": "PANO", "category": "Nước lau sàn", "price": 29450, "original_price": 52500, "discount": "44%", "in_stock": True,
        "badge": "BEST_SELLER_TOP_10",
        "keywords": "nuoc lau san; pano; hoa ha; phan em be; can 3.8kg; sieu tiet kiem; ban chay; top 10; 222 da ban",
        "specs": "Chai 1kg / Can 3.8kg", "variants": "Chai 1kg; Can 3.8kg"
    },

    # ==========================================
    # ✨ TOP 10 MỚI NHẤT (THEO ẢNH SHOPEE "MỚI NHẤT")
    # ==========================================
    {
        "name": "[COMBO 2 túi] Nước giặt xả 2in1 Oplus Hương nước hoa Pháp, Sạch sâu - mềm vải - thơm lâu, 2 túi tổng 3.6kg",
        "brand": "Oplus", "category": "Nước giặt", "price": 133479, "original_price": 290171, "discount": "54%", "in_stock": True,
        "badge": "NEW_ARRIVAL_TOP_1",
        "keywords": "nuoc giat; oplus; combo 2 tui; 3.6kg; nuoc hoa phap; moi nhat; top 1 moi",
        "specs": "Combo 2 túi (3.6kg)", "variants": "Combo 2 túi"
    },
    {
        "name": "Bột giặt Oplus túi 720g 5.5kg hương hoa trắng xạ hương giặt tay giặt máy sạch vết bẩn làm mới quần áo sỉn màu",
        "brand": "Oplus", "category": "Bột giặt", "price": 66000, "original_price": 110000, "discount": "40%", "in_stock": True,
        "badge": "NEW_ARRIVAL_TOP_4",
        "keywords": "bot giat; oplus; hoa trang; xa huong; tui 5.5kg; 720g; moi nhat; top 4 moi",
        "specs": "Túi 720g / 5.5kg", "variants": "Túi 720g; Túi 5.5kg"
    },
    {
        "name": "[MUA 1 TẶNG 1] Nước hoa treo xe ô tô Pano, Hương nước hoa Pháp, Khử mùi - tỏa hương thư giãn, COMBO 2 chai",
        "brand": "PANO", "category": "Tinh dầu & Nước hoa", "price": 36000, "original_price": 60000, "discount": "40%", "in_stock": True,
        "badge": "NEW_ARRIVAL_TOP_5",
        "keywords": "nuoc hoa; treo xe; pano; nuoc hoa phap; combo 2 chai; mua 1 tang 1; moi nhat; top 5 moi",
        "specs": "Combo 2 chai", "variants": "Combo 2 chai"
    },
    {
        "name": "Nước lau kính ZeO Hương trà xanh, Sáng bóng - khô nhanh - không để lại vệt, Chai 570ml",
        "brand": "ZeO", "category": "Nước lau kính", "price": 30100, "original_price": 43000, "discount": "30%", "in_stock": True,
        "badge": "NEW_ARRIVAL_TOP_6",
        "keywords": "nuoc lau kinh; zeo; tra xanh; sang bong; khong de lai vet; chai 570ml; moi nhat; top 6 moi",
        "specs": "Chai 570ml", "variants": "Chai 570ml"
    },
    {
        "name": "[CAN TO TIẾT KIỆM] Nước giặt Pano Hương nước hoa Pháp, Sạch sâu - khử mùi - lưu hương lâu, Can 3.8kg",
        "brand": "PANO", "category": "Nước giặt", "price": 123291, "original_price": 205485, "discount": "40%", "in_stock": True,
        "badge": "NEW_ARRIVAL_TOP_7",
        "keywords": "nuoc giat; pano; nuoc hoa phap; can 3.8kg; can to tiet kiem; moi nhat; top 7 moi",
        "specs": "Can 3.8kg", "variants": "Can 3.8kg"
    },
    {
        "name": "[GÓI TIẾT KIỆM] Bột giặt Nha Đam ZeO Hương Fresh Floral Green, Dịu nhẹ - sạch vết bẩn - lưu hương kép, Túi 2.7kg/ 4.1kg",
        "brand": "ZeO", "category": "Bột giặt", "price": 114855, "original_price": 185250, "discount": "38%", "in_stock": True,
        "badge": "NEW_ARRIVAL_TOP_9",
        "keywords": "bot giat; zeo; nha dam; fresh floral green; goi tiet kiem; tui 4.1kg; moi nhat; top 9 moi",
        "specs": "Túi 2.7kg / Túi 4.1kg", "variants": "Túi 2.7kg; Túi 4.1kg"
    },
    {
        "name": "[MỚI] Nước lau sàn Oplus Hương sả chanh, Khử mùi - sạch bóng sàn gỗ & gạch men, Can 1kg/3.6kg",
        "brand": "Oplus", "category": "Nước lau sàn", "price": 34450, "original_price": 53000, "discount": "35%", "in_stock": True,
        "badge": "NEW_ARRIVAL",
        "keywords": "nuoc lau san; oplus; sa chanh; sang bong; can 1kg; can 3.6kg; moi; moi ra; hang moi",
        "specs": "Can 1kg / Can 3.6kg", "variants": "Can 1kg; Can 3.6kg"
    },
    {
        "name": "[GIẶT NHANH] Nước giặt Bio Enzyme ZeO Hương tươi mát, Đánh bay vết bẩn protein - lưu hương, Can 2kg/9kg",
        "brand": "ZeO", "category": "Nước giặt", "price": 104357, "original_price": 168317, "discount": "38%", "in_stock": True,
        "badge": "NEW_ARRIVAL",
        "keywords": "nuoc giat; zeo; bio enzyme; giat nhanh; can 2kg; can 9kg; moi ra; cong nghe moi",
        "specs": "Can 2kg / Can 9kg", "variants": "Can 2kg; Can 9kg"
    },
    {
        "name": "Nước giặt Pano Active combo 2 túi 1.8kg, tặng nước rửa chén 200g, hương nước hoa Pháp giặt tay giặt máy sạch sâu",
        "brand": "PANO", "category": "Nước giặt", "price": 147582, "original_price": 238035, "discount": "38%", "in_stock": True,
        "badge": "NEW_ARRIVAL",
        "keywords": "nuoc giat; pano; active; combo 2 tui; 1.8kg; moi ra; the thao; nuoc hoa phap",
        "specs": "Combo 2 túi 1.8kg + Quà tặng", "variants": "Combo 2 túi 1.8kg"
    },
    {
        "name": "Nước giặt Pano Elegant 2 túi 1.8kg, tặng nước rửa chén 200g hương nước hoa Pháp giặt tay giặt máy sạch sâu thơm lâu",
        "brand": "PANO", "category": "Nước giặt", "price": 147582, "original_price": 238035, "discount": "38%", "in_stock": True,
        "badge": "NEW_ARRIVAL",
        "keywords": "nuoc giat; pano; elegant; combo 2 tui; 1.8kg; moi ra; thanh lich; nuoc hoa phap",
        "specs": "Combo 2 túi 1.8kg + Quà tặng", "variants": "Combo 2 túi 1.8kg"
    },

    # ==========================================
    # 📦 CÁC DÒNG SẢN PHẨM KHÁC
    # ==========================================
    {
        "name": "Bột giặt Nước hoa ZeO Hương hoa trắng & xạ hương, Sạch vết bẩn cứng đầu - lưu hương kép, Gói 720g/ 750g",
        "brand": "ZeO", "category": "Bột giặt", "price": 36400, "original_price": 45500, "discount": "20%", "in_stock": True,
        "badge": "STANDARD", "keywords": "bot giat; zeo; nuoc hoa; hoa trang; xa huong", "specs": "Gói 720g / 750g", "variants": "Gói 720g; Gói 750g"
    },
    {
        "name": "Nước rửa chén Oplus Hương chanh tự nhiên, Sạch dầu mỡ - khử mùi tanh - dịu da tay, Bao bì nhiều lựa chọn",
        "brand": "Oplus", "category": "Nước rửa chén", "price": 14300, "original_price": 22000, "discount": "35%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc rua chen; oplus; chanh tu nhien", "specs": "Can / Túi / Chai", "variants": "Chai 800g; Can 3.8kg"
    },
    {
        "name": "Nước lau sàn ZeO Hương Ylang Ylang & bạc hà, Sạch bóng sàn - khử mùi, Can 1kg/3.8kg",
        "brand": "ZeO", "category": "Nước lau sàn", "price": 33150, "original_price": 44200, "discount": "25%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc lau san; zeo; ylang ylang; bac ha", "specs": "Can 1kg / Can 3.8kg", "variants": "Can 1kg; Can 3.8kg"
    },
    {
        "name": "Bột giặt ZeO Bọt Biển Hương táo - dứa - hoa nhài, Sạch vết bẩn - lưu hương kép, Túi 720g/2.7kg",
        "brand": "ZeO", "category": "Bột giặt", "price": 35100, "original_price": 54000, "discount": "35%", "in_stock": True,
        "badge": "STANDARD", "keywords": "bot giat; zeo; bot bien; tao dua hoa nhai", "specs": "Túi 720g / 2.7kg", "variants": "Túi 720g; Túi 2.7kg"
    },
    {
        "name": "Nước rửa chén Enzyme ZeO Hương chanh tự nhiên, Sạch dầu mỡ - khử mùi tanh - dịu da tay, Can 400g/800g/1.5kg",
        "brand": "ZeO", "category": "Nước rửa chén", "price": 16900, "original_price": 26000, "discount": "35%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc rua chen; zeo; enzyme; chanh tu nhien", "specs": "400g / 800g / 1.5kg", "variants": "Chai 400g; Chai 800g; Can 1.5kg"
    },
    {
        "name": "Nước giặt 2in1 Oplus Hương nước hoa Pháp, Sạch vết bẩn - mềm vải - lưu hương kép, Túi 2.4kg",
        "brand": "Oplus", "category": "Nước giặt", "price": 91257, "original_price": 172183, "discount": "47%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; oplus; 2in1; nuoc hoa phap; tui 2.4kg", "specs": "Túi 2.4kg", "variants": "Túi 2.4kg"
    },
    {
        "name": "Nước rửa chén Pano can 3.8kg hương chanh tự nhiên cho nhà hàng quán ăn sạch dầu mỡ khử mùi tanh da tay",
        "brand": "PANO", "category": "Nước rửa chén", "price": 76050, "original_price": 117000, "discount": "35%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc rua chen; pano; can 3.8kg; quan an", "specs": "Can 3.8kg", "variants": "Can 3.8kg"
    },
    {
        "name": "[TẶNG KÈM 3 gói nước xả vải] Bột giặt Oplus Hương hoa trắng & xạ hương, Tiết kiệm nước - sạch vết bẩn - ít cặn, Túi 2kg",
        "brand": "Oplus", "category": "Bột giặt", "price": 72150, "original_price": 111000, "discount": "35%", "in_stock": True,
        "badge": "STANDARD", "keywords": "bot giat; oplus; tang kem 3 goi; tui 2kg", "specs": "Túi 2kg", "variants": "Túi 2kg"
    },
    {
        "name": "Nước giặt 2in1 Oplus Hương nước hoa Pháp, Sạch sâu - mềm vải - không cần nước xả, Can 1kg",
        "brand": "Oplus", "category": "Nước giặt", "price": 60720, "original_price": 69000, "discount": "12%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; oplus; 2in1; can 1kg", "specs": "Can 1kg", "variants": "Can 1kg"
    },
    {
        "name": "Combo 2 nước giặt Pano 1.8kg hương nước hoa Pháp giặt tay giặt máy sạch sâu vết bẩn an toàn da tay",
        "brand": "PANO", "category": "Nước giặt", "price": 122550, "original_price": 129000, "discount": "5%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; pano; combo 2 tui; 1.8kg", "specs": "Combo 2 túi 1.8kg", "variants": "Combo 2 túi 1.8kg"
    },
    {
        "name": "Chai xịt tẩy rửa đa năng Pano Hương trà xanh, Đánh bay dầu mỡ - vết bẩn - đa bề mặt, Chai 500ml",
        "brand": "PANO", "category": "Tẩy rửa đa năng", "price": 46620, "original_price": 74000, "discount": "37%", "in_stock": True,
        "badge": "STANDARD", "keywords": "tay da nang; xit da nang; pano; tra xanh", "specs": "Chai 500ml", "variants": "Chai 500ml"
    },
    {
        "name": "Nước giặt xả 2in1 Oplus Hương nước hoa Pháp, Sạch sâu - mềm vải - không cần nước xả, Túi 1.8kg",
        "brand": "Oplus", "category": "Nước giặt", "price": 77727, "original_price": 119580, "discount": "35%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; oplus; giat xa 2in1; tui 1.8kg", "specs": "Túi 1.8kg", "variants": "Túi 1.8kg"
    },
    {
        "name": "Nước xả vải Nano Clean ZeO Hương hoa trắng & xạ hương, Mềm vải - giảm nhăn - thơm lâu, Can 1kg/3.8kg",
        "brand": "ZeO", "category": "Nước xả vải", "price": 83200, "original_price": 128000, "discount": "35%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc xa vai; nano clean; zeo; can 3.8kg", "specs": "Can 1kg / Can 3.8kg", "variants": "Can 1kg; Can 3.8kg"
    },
    {
        "name": "[SẠCH SÂU - TIẾT KIỆM] Nước giặt xả 2in1 Oplus Hương nước hoa Pháp, Mềm vải - lưu hương lâu, Can 3.1kg/3.5kg",
        "brand": "Oplus", "category": "Nước giặt", "price": 129390, "original_price": 227000, "discount": "43%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; oplus; 2in1; can 3.5kg", "specs": "Can 3.1kg / Can 3.5kg", "variants": "Can 3.1kg; Can 3.5kg"
    },
    {
        "name": "Nước giặt Pano Hương nước hoa Pháp, Sạch vết bẩn - khử mùi - lưu hương lâu, Can 3.6kg",
        "brand": "PANO", "category": "Nước giặt", "price": 131100, "original_price": 234107, "discount": "44%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; pano; can 3.6kg", "specs": "Can 3.6kg", "variants": "Can 3.6kg"
    },
    {
        "name": "Nước giặt Pano combo 2 gói 1,8kg tặng nước rửa chén 400g, hương hoa tươi mát giặt tay, giặt máy sạch sâu vết bẩn",
        "brand": "PANO", "category": "Nước giặt", "price": 120640, "original_price": 251333, "discount": "52%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; pano; combo 2 goi; tang qua", "specs": "Combo 2 gói 1.8kg + Quà tặng", "variants": "Combo 2 gói 1.8kg"
    },
    {
        "name": "[COMBO 4 túi] Nước giặt xả 2in1 Oplus, Hương nước hoa Pháp, Sạch sâu - mềm vải - thơm lâu, 4 túi tổng 7.2kg",
        "brand": "Oplus", "category": "Nước giặt", "price": 257592, "original_price": 585436, "discount": "56%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; oplus; combo 4 tui; 7.2kg", "specs": "Combo 4 túi (7.2kg)", "variants": "Combo 4 túi"
    },
    {
        "name": "Combo 4 nước giặt Pano 1.8kg hương nước hoa Pháp giặt tay giặt máy sạch sâu vết bẩn an toàn cho da tay",
        "brand": "PANO", "category": "Nước giặt", "price": 239343, "original_price": 460275, "discount": "48%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; pano; combo 4 tui; 1.8kg", "specs": "Combo 4 túi 1.8kg", "variants": "Combo 4 túi 1.8kg"
    },
    {
        "name": "Thùng nước giặt Pano Active 6 túi hương nước hoa Pháp sang trọng giặt tay giặt máy sạch sâu an toàn da tay",
        "brand": "PANO", "category": "Nước giặt", "price": 681812, "original_price": 1311176, "discount": "48%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; pano; active; thung 6 tui; gia si", "specs": "Thùng 6 túi (10.8kg)", "variants": "Thùng 6 túi"
    },
    {
        "name": "Nước giặt Pano Fresh combo 2 gói 1,8kg tặng 1 nước rửa chén 200g, hương hoa trắng, giặt tay giặt máy sạch sâu vết bẩn",
        "brand": "PANO", "category": "Nước giặt", "price": 115795, "original_price": 241239, "discount": "52%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; pano; fresh; combo 2 goi; tang quà", "specs": "Combo 2 gói 1.8kg + Quà tặng", "variants": "Combo 2 gói 1.8kg"
    },
    {
        "name": "Nước giặt Pano Elegant túi 1.8kg combo mua 1 được 3 hương nước hoa Pháp cổ điển giặt tay giặt máy sạch sâu vết bẩn",
        "brand": "PANO", "category": "Nước giặt", "price": 130693, "original_price": 251332, "discount": "48%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; pano; elegant; tui 1.8kg", "specs": "Túi 1.8kg + Quà tặng", "variants": "Túi 1.8kg"
    },
    {
        "name": "Combo 2 túi Nước giặt Pano Warmish 1.8kg hương táo dứa hoa nhài sạch sâu vết bẩn tặng nước rửa chén 400g",
        "brand": "PANO", "category": "Nước giặt", "price": 147582, "original_price": 238035, "discount": "38%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; pano; warmish; combo 2 tui; 1.8kg", "specs": "Combo 2 túi 1.8kg + Quà tặng", "variants": "Combo 2 túi 1.8kg"
    },
    {
        "name": "Combo 2 túi Nước giặt Pano Warmish 1.8kg hương táo dứa hoa nhài sạch sâu vết bẩn tặng nước rửa chén 200g",
        "brand": "PANO", "category": "Nước giặt", "price": 130693, "original_price": 242024, "discount": "46%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; pano; warmish; combo 2 tui; 1.8kg", "specs": "Combo 2 túi 1.8kg + Quà tặng", "variants": "Combo 2 túi 1.8kg"
    },
    {
        "name": "Thùng nước giặt Pano Fresh 6 túi hương táo hoa trắng giặt tay giặt máy sạch sâu vết bẩn an toàn da tay bán sỉ",
        "brand": "PANO", "category": "Nước giặt", "price": 681812, "original_price": 1311176, "discount": "48%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; pano; fresh; thung 6 tui", "specs": "Thùng 6 túi (10.8kg)", "variants": "Thùng 6 túi"
    },
    {
        "name": "Nước giặt Pano Active combo 2 túi 1.8kg tặng nước rửa chén 400g hương nước hoa Pháp sang trọng sạch sâu vết bẩn",
        "brand": "PANO", "category": "Nước giặt", "price": 120640, "original_price": 251333, "discount": "52%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; pano; active; combo 2 tui", "specs": "Combo 2 túi 1.8kg + Quà tặng", "variants": "Combo 2 túi 1.8kg"
    },
    {
        "name": "Thùng nước giặt Pano Warmish 6 túi hương táo dứa hoa nhài giặt tay giặt máy sạch sâu an toàn da tay bán sỉ",
        "brand": "PANO", "category": "Nước giặt", "price": 552653, "original_price": 1151360, "discount": "52%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; pano; warmish; thung 6 tui", "specs": "Thùng 6 túi (10.8kg)", "variants": "Thùng 6 túi"
    },
    {
        "name": "Thùng nước giặt Pano Elegant 6 túi hương nước hoa Pháp cổ điển giặt tay giặt máy sạch sâu an toàn da tay",
        "brand": "PANO", "category": "Nước giặt", "price": 555939, "original_price": 1292881, "discount": "57%", "in_stock": True,
        "badge": "STANDARD", "keywords": "nuoc giat; pano; elegant; thung 6 tui", "specs": "Thùng 6 túi (10.8kg)", "variants": "Thùng 6 túi"
    },

    # --- HẾT HÀNG ---
    {
        "name": "Nước tẩy toilet đậm đặc Pano Hương trái cây, Tẩy cặn vôi - ố vàng - khử mùi hôi, Chai 960g",
        "brand": "PANO", "category": "Tẩy Toilet", "price": 30000, "original_price": 30000, "discount": "0%", "in_stock": False,
        "badge": "OUT_OF_STOCK", "keywords": "tay toilet; bon cau; pano; chai 960g", "specs": "Chai 960g", "variants": "Chai 960g"
    },
    {
        "name": "Nước tẩy quần áo màu Oxy Active ZeO Hương cam chanh & oải hương, Tẩy vết bẩn - giữ màu không phai, Chai 400ml",
        "brand": "ZeO", "category": "Nước tẩy quần áo màu", "price": 39000, "original_price": 39000, "discount": "0%", "in_stock": False,
        "badge": "OUT_OF_STOCK", "keywords": "tay mau; quan ao mau; zeo; oxy active", "specs": "Chai 400ml", "variants": "Chai 400ml"
    },
    {
        "name": "Bộ 4, Tinh dầu thơm phòng 4in1, ZeO, Hương SPA, bưởi biển, Midnight, Khử mùi - thư giãn, 4 chai kèm kẹp treo",
        "brand": "ZeO", "category": "Tinh dầu & Nước hoa", "price": 233367, "original_price": 288107, "discount": "19%", "in_stock": False,
        "badge": "OUT_OF_STOCK", "keywords": "tinh dau thom phong; zeo; 4 chai", "specs": "Bộ 4 chai kèm kẹp treo", "variants": "Bộ 4 chai"
    },

    # --- CFC CÒ BAY ---
    {
        "name": "Phân bón hữu cơ sinh học CFC Cò Bay Cần Thơ Bao 25kg",
        "brand": "CFC", "category": "Phân bón nông nghiệp", "price": 320000, "original_price": 350000, "discount": "9%", "in_stock": True,
        "badge": "BEST_SELLER_CFC", "keywords": "phan bon; co bay; huu co; sinh hoc; cfc", "specs": "Bao 25kg", "variants": "Bao 25kg; Bao 50kg"
    },
    {
        "name": "Phân bón NPK CFC Cò Bay Chuyên Cây Ăn Trái Bao 25kg",
        "brand": "CFC", "category": "Phân bón nông nghiệp", "price": 450000, "original_price": 490000, "discount": "8%", "in_stock": True,
        "badge": "BEST_SELLER_CFC", "keywords": "phan bon; npk; co bay; cfc; cay an trai", "specs": "Bao 25kg", "variants": "Bao 25kg"
    }
]


def load_crawled_urls() -> dict[str, str]:
    url_map = {}
    csv_files = [
        INPUT_DIR / "zeo_shopee_crawled_37_products.csv",
        INPUT_DIR / "zeo_shopee_crawled_37_products (1).csv",
    ]
    for p in csv_files:
        if p.exists():
            with open(p, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    link = r.get("link_shopee", "").strip()
                    item_id = r.get("item_id", "").strip()
                    if link and item_id:
                        unq = urllib.parse.unquote(link).lower()
                        url_map[item_id] = link
                        url_map[unq] = link
    return url_map


def generate_slug_url(name: str, item_id: str, shop_id: str = "20523065") -> str:
    slug = name.lower()
    slug = re.sub(r"[àáạảãâầấậẩẫăằắặẳẵ]", "a", slug)
    slug = re.sub(r"[èéẹẻẽêềếệểễ]", "e", slug)
    slug = re.sub(r"[ìíịỉĩ]", "i", slug)
    slug = re.sub(r"[òóọỏõôồốộổỗơờớợởỡ]", "o", slug)
    slug = re.sub(r"[ùúụủũưừứựửữ]", "u", slug)
    slug = re.sub(r"[ỳýỵỷỹ]", "y", slug)
    slug = re.sub(r"[đ]", "d", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return f"https://shopee.vn/{slug}-i.{shop_id}.{item_id}"


def build_catalog():
    urls_by_id = load_crawled_urls()
    final_rows = []

    for idx, item in enumerate(ALL_VERIFIED_ITEMS, start=1):
        item_id = f"item_{idx:02d}"
        if item["brand"] == "CFC":
            item_id = f"cfc-{idx:02d}"
            link = f"https://shopee.vn/cfccobay/{item_id}"
        else:
            matched_link = None
            for raw_unq, real_link in urls_by_id.items():
                first_few_words = " ".join(item["name"].lower().split()[:3])
                if first_few_words in raw_unq:
                    matched_link = real_link
                    m = re.search(r"-i\.\d+\.(\d+)", real_link)
                    if m:
                        item_id = m.group(1)
                    break
            link = matched_link or generate_slug_url(item["name"], item_id)

        final_rows.append({
            "active": "TRUE",
            "item_id": item_id,
            "name": item["name"],
            "brand": item["brand"],
            "category": item["category"],
            "price": item["price"],
            "original_price": item["original_price"],
            "discount": item["discount"],
            "badge": item.get("badge", "STANDARD"),
            "specs": item["specs"],
            "keywords": item["keywords"],
            "variants": item["variants"],
            "link_shopee": link,
            "in_stock": "TRUE" if item["in_stock"] else "FALSE",
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        })

    fieldnames = [
        "active", "item_id", "name", "brand", "category",
        "price", "original_price", "discount", "badge", "specs",
        "keywords", "variants", "link_shopee", "in_stock", "updated_at"
    ]

    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(final_rows)

    print(f"✓ ĐÃ XUẤT THÀNH CÔNG {len(final_rows)} SẢN PHẨM (ĐẦY ĐỦ TOP BÁN CHẠY & MỚI NHẤT) VÀO: {OUTPUT_CSV.name}")


if __name__ == "__main__":
    build_catalog()
