import json
import logging
from typing import List, Dict, Any, Optional
from ai_engine import generate_ai_text

logger = logging.getLogger("cfc_semantic_planner")

_PLANNER_SYSTEM_PROMPT = """Bạn là trợ lý điều phối ngữ nghĩa (Semantic Planner) cho chatbot CFC - Phân bón Cò Bay.
Nhiệm vụ của bạn là nhận câu của người dùng, phân tích ý định (intent), và đưa ra Kế Hoạch (Plan) dạng JSON.

Hỗ trợ các ý định (intent) sau:
- "purchase": Mua hàng, hỏi giá sỉ/lẻ, đặt hàng, hỏi mua.
- "dealer_location": Tìm kiếm đại lý, điểm bán, hoặc chỉ đường đến đại lý.
- "inventory": Hỏi xem sản phẩm còn hàng không (tồn kho).
- "agronomy": Tư vấn nông học, hỏi cách bón phân, chữa bệnh cho cây.
- "dealer_contact_followup": Xin số điện thoại của đại lý vừa tìm được.
- "price_quote": Yêu cầu báo giá, hỏi giá.
- "loyalty_lookup": Tra cứu tích điểm, hạng thành viên, chiết khấu, ưu đãi, hoặc hỏi thông tin về số điện thoại cụ thể.
- "order_tracking": Theo dõi tiến độ, kiểm tra trạng thái đơn hàng.
- "faq": Các câu hỏi chung chung về công ty, chính sách, hoặc hỏi đáp khác.

Quy tắc sinh kế hoạch:
- Bạn trả về MỘT mảng JSON các ý định. Mỗi object có cấu trúc:
  {"intent": "<tên intent>", "entities": {"<tên entity>": "<giá trị>"}}
- Nếu câu có nhiều vế, hãy phân tích thành nhiều object trong mảng.
- Ví dụ "Tôi muốn mua phân cho sầu riêng, tư vấn luôn loại phù hợp." ->
  [{"intent": "purchase", "entities": {"crop": "sầu riêng"}}, {"intent": "agronomy", "entities": {"crop": "sầu riêng"}}]
- Ví dụ "Đại lý số 2 lúc nãy cho xin số điện thoại" ->
  [{"intent": "dealer_contact_followup", "entities": {"ordinal": 2}}]
- Ví dụ "Số điện thoại của mình 0987654321, có tích điểm gì chưa" ->
  [{"intent": "loyalty_lookup", "entities": {"phone": "0987654321"}}]
- ĐẶC BIỆT: Nếu câu của người dùng chỉ là cung cấp số điện thoại hoặc địa chỉ (ví dụ: "0388509046 rạch giá kiên giang") để trả lời bot, bạn PHẢI phân tích dựa trên câu trước của bot. Nếu câu trước đang hỏi tồn kho, thì intent phải là "inventory". Nếu đang theo dõi đơn, intent là "order_tracking". Nếu đang tư vấn bón phân/chữa bệnh, intent là "agronomy". KHÔNG được tự ý gán là "price_quote" hoặc "loyalty_lookup" nếu ngữ cảnh trước đó không liên quan.
- CHỈ output JSON mảng, KHÔNG giải thích thêm.
"""

async def plan_cfc_intents(text: str, conversation_state: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Gọi Ollama để phân tích semantic intent plan."""
    prompt = f"User message: {text}\nPlan:"
    
    # Lấy recent turns làm context nếu cần
    messages = []
    if conversation_state:
        recent = conversation_state.get("recent_turns", [])
        # Lấy 2 turns gần nhất để làm context phụ
        for turn in recent[-2:]:
            messages.append({"role": "user", "content": turn.get("user", "")})
            messages.append({"role": "assistant", "content": turn.get("bot", "")})
    if messages:
        history = "\n".join(f"{item['role']}: {item['content']}" for item in messages)
        prompt = f"Lịch sử gần nhất:\n{history}\n\n{prompt}"

    try:
        result = await generate_ai_text(
            prompt=prompt,
            system_prompt=_PLANNER_SYSTEM_PROMPT,
            preferred_provider="ollama",
            temperature=0.1,
            output_format="json",
            prompt_id="cfc.semantic-plan.v1",
        )
        response_text = result.get("text", "") if result.get("success") else ""
        if response_text:
            plan = json.loads(response_text)
            if isinstance(plan, list):
                return plan
            elif isinstance(plan, dict) and "intent" in plan:
                return [plan]
    except Exception as e:
        logger.warning(f"Lỗi khi chạy semantic planner: {e}")
        
    return []

def resolve_priority(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Quyết định ý định chính (primary) dựa trên mức ưu tiên."""
    if not candidates:
        return None
        
    # Mức ưu tiên: purchase > dealer_location > order_tracking > loyalty_lookup > dealer_contact_followup > price_quote > inventory > agronomy > faq
    priority_map = {
        "purchase": 1,
        "dealer_location": 2,
        "order_tracking": 3,
        "loyalty_lookup": 4,
        "dealer_contact_followup": 5,
        "price_quote": 6,
        "inventory": 7,
        "agronomy": 8,
        "faq": 9
    }
    
    sorted_candidates = sorted(candidates, key=lambda x: priority_map.get(x.get("intent", "faq"), 99))
    return sorted_candidates[0]

def map_semantic_intent_to_query_intent(semantic_intent: str) -> str:
    """Phiên dịch intent của LLM (Semantic) sang hệ thống định tuyến cũ (Deterministic)"""
    mapping = {
        "purchase": "cfc_purchase_request",
        "dealer_location": "cfc_dealer_location_request",
        "order_tracking": "cfc_order_status_request",
        "loyalty_lookup": "cfc_loyalty_lookup_request",
        "dealer_contact_followup": "dealer_contact_followup",
        "price_quote": "cfc_price_unverified",
        "inventory": "cfc_inventory_request",
        "agronomy": "cfc_agronomy_review_request",
        "faq": "unknown"
    }
    return mapping.get(semantic_intent, "unknown")
