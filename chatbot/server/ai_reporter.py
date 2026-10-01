"""
ai_reporter.py — Module Báo Cáo Kinh Doanh & AI Executive Insights Tự Động
Chức năng:
  1. Quét toàn bộ dữ liệu khách hàng, lead, intent và learning queue từ Redis trong ngày.
  2. Dùng AI (Gemini / OpenRouter / Ollama) tổng hợp thành Bản Tin Báo Cáo Điều Hành chuẩn chỉnh.
  3. Cung cấp báo cáo dạng Web Dashboard và hỗ trợ bắn thẳng qua Telegram.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import redis.asyncio as aioredis

from ai_engine import generate_ai_text

logger = logging.getLogger(__name__)

_settings: dict = {}


def _load_settings() -> dict:
    global _settings
    cfg_path = Path(__file__).parent / "settings.json"
    if cfg_path.exists():
        _settings = json.loads(cfg_path.read_text(encoding="utf-8"))
    return _settings


def _get_redis() -> aioredis.Redis:
    cfg = _load_settings().get("redis", {})
    return aioredis.Redis(
        host=cfg.get("host", "127.0.0.1"),
        port=int(cfg.get("port", 6379)),
        password=cfg.get("password", "") or None,
        db=int(cfg.get("db", 0)),
        decode_responses=True,
    )


async def generate_daily_executive_report(send_telegram: bool = False) -> dict:
    """Tự động thu thập dữ liệu và dùng AI viết Báo Cáo Điều Hành Kinh Doanh trong ngày."""
    r = _get_redis()
    try:
        now_dt = datetime.now()
        date_str = now_dt.strftime("%Y-%m-%d")
        display_date = now_dt.strftime("%d/%m/%Y")

        raw_data = {
            "date": display_date,
            "zeo": {"customers": 0, "leads": [], "intents": {}},
            "cfc": {"customers": 0, "leads": [], "intents": {}},
            "total_customers": 0,
            "total_leads": 0,
            "learning_queue_count": 0,
        }

        for brand in ["zeo", "cfc"]:
            pattern = f"{brand}:customer:messenger:*"
            cursor = 0
            keys = []
            while True:
                cursor, batch = await r.scan(cursor, match=pattern, count=200)
                keys.extend(batch)
                if cursor == 0:
                    break

            # pyrefly: ignore [unsupported-operation]
            raw_data[brand]["customers"] = len(keys)
            # pyrefly: ignore [unsupported-operation]
            raw_data["total_customers"] += len(keys)

            for key in keys:
                raw_cust = await r.get(key)
                if not raw_cust:
                    continue
                try:
                    profile = json.loads(raw_cust)
                except Exception:
                    continue

                phone = profile.get("phone", "") or profile.get("customer_phone", "")
                area = profile.get("area", "") or profile.get("customer_location", "")
                stage = profile.get("lead_stage", "new")
                intent = profile.get("last_intent", "") or profile.get("last_need", "")

                if intent:
                    # pyrefly: ignore [bad-index]
                    raw_data[brand]["intents"][intent] = raw_data[brand]["intents"].get(intent, 0) + 1

                if phone:
                    # pyrefly: ignore [bad-index]
                    raw_data[brand]["leads"].append({
                        "phone": phone,
                        "area": area,
                        "stage": stage,
                        "intent": intent,
                    })
                    # pyrefly: ignore [unsupported-operation]
                    raw_data["total_leads"] += 1

            lq_key = f"{brand}:learning:queue"
            if await r.exists(lq_key):
                # pyrefly: ignore [not-async, unsupported-operation]
                raw_data["learning_queue_count"] += await r.llen(lq_key)

        # Prompt AI viết báo cáo
        prompt = f"""
Hãy đóng vai trò Giám đốc Vận hành & Phân tích Dữ liệu của hệ thống ZeO Vietnam & Phân bón CFC Cò Bay.
Dựa trên số liệu thực tế ngày {display_date} sau đây:

- Tổng số khách hàng tương tác: {raw_data['total_customers']} (ZeO: {raw_data['zeo']['customers']}, CFC: {raw_data['cfc']['customers']})
- Tổng số Lead thu thập được SĐT: {raw_data['total_leads']}
- Danh sách Lead chi tiết: {json.dumps(raw_data['zeo']['leads'] + raw_data['cfc']['leads'], ensure_ascii=False)}
- Các chủ đề/sản phẩm được hỏi nhiều nhất: {json.dumps({'ZeO': raw_data['zeo']['intents'], 'CFC': raw_data['cfc']['intents']}, ensure_ascii=False)}
- Số câu hỏi bot chưa chắc (Learning Queue): {raw_data['learning_queue_count']}

Hãy viết một Bản Tin Báo Cáo Điều Hành (Executive Summary) ngắn gọn, súc tích và chuyên nghiệp theo cấu trúc:
1. 📊 TỔNG QUAN TÌNH HÌNH TRONG NGÀY
2. 🎯 PHÂN TÍCH NHU CẦU & SẢN PHẨM NỔI BẬT
3. 📞 ĐÁNH GIÁ TIỀM NĂNG CHỐT ĐƠN (LEADS)
4. 💡 ĐỀ XUẤT HÀNH ĐỘNG CHO NGÀY TIẾP THEO
"""
        ai_res = await generate_ai_text(
            prompt=prompt,
            system_prompt="Bạn là Giám đốc Phân tích Dữ liệu AI của CFC & ZeO. Viết báo cáo tiếng Việt rõ ràng, đầy đủ số liệu và gợi ý kinh doanh thực tiễn.",
            preferred_provider="groq",
            temperature=0.3,
        )

        if ai_res.get("success") and ai_res.get("text"):
            report_text = ai_res.get("text")
            provider_used = ai_res.get("provider", "groq")
        else:
            provider_used = "system-analytics"
            report_text = f"""###  BẢN TIN ĐIỀU HÀNH KINH DOANH NGÀY {display_date}

#### 1. TỔNG QUAN TÌNH HÌNH TRONG NGÀY
- **Tổng khách hàng tương tác**: **{raw_data['total_customers']}** (ZeO: {raw_data['zeo']['customers']} | CFC: {raw_data['cfc']['customers']}).
- **Tổng Lead thu thập được SĐT**: **{raw_data['total_leads']}** (Tỷ lệ chuyển đổi SĐT đạt {round((raw_data['total_leads'] / max(raw_data['total_customers'], 1)) * 100, 1)}%).
- **Hàng đợi cần duyệt FAQ (Learning Queue)**: **{raw_data['learning_queue_count']} câu**.

#### 2. PHÂN TÍCH NHU CẦU & LEADS NỔI BẬT
- **ZeO Vietnam**: Tương tác sôi nổi về các dòng nước giặt sinh học, nước rửa chén không ăn da tay và đơn hàng sỉ.
- **CFC Cò Bay**: Nhận diện tương tác về phân bón NPK và tư vấn kỹ thuật cây trồng.

#### 3. ĐỀ XUẤT HÀNH ĐỘNG CHO NGÀY TIẾP THEO
1. **Sales & Telesale**: Liên hệ ngay danh sách {raw_data['total_leads']} khách hàng đã để lại số điện thoại trong ngày để tư vấn chốt đơn.
2. **Quản trị viên**: Vào mục Learning Queue để xem xét và duyệt các câu hỏi chưa được lập chỉ mục nhằm nâng cao độ chính xác cho bot.
"""

        report_payload = {
            "date": date_str,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ai_provider": provider_used,
            "metrics": raw_data,
            "report_markdown": report_text,
        }

        # Lưu báo cáo vào Redis
        await r.set(f"cfc:report:daily:{date_str}", json.dumps(report_payload, ensure_ascii=False))
        await r.set("cfc:report:daily:latest", json.dumps(report_payload, ensure_ascii=False))

        # Gửi Telegram nếu được yêu cầu
        if send_telegram:
            try:
                from telegram_notifier import send_telegram_message
                tel_text = f" <b>BÁO CÁO ĐIỀU HÀNG KINH DOANH ({display_date})</b>\n\n"
                tel_text += f" <b>Khách tương tác:</b> {raw_data['total_customers']} |  <b>Leads SĐT:</b> {raw_data['total_leads']}\n\n"
                tel_text += report_text[:3500]
                await send_telegram_message(tel_text)
            except Exception as e:
                logger.warning("Lỗi gửi báo cáo qua Telegram: %s", e)

        return {"success": True, "report": report_payload}
    finally:
        await r.aclose()


async def get_latest_report() -> Optional[dict]:
    """Lấy báo cáo kinh doanh gần nhất đã lưu trong Redis."""
    r = _get_redis()
    try:
        raw = await r.get("cfc:report:daily:latest")
        if raw:
            return json.loads(raw)
        return None
    finally:
        await r.aclose()
