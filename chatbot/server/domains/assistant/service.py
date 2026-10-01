"""
domains.assistant.service — Orchestration cho Trợ Lý Điều Hành AI và Quick Prompts.
"""

from typing import List, Dict, Any


def get_quick_prompts_list() -> List[Dict[str, str]]:
    """Danh sách prompt mẫu nhanh cho Trợ lý AI."""
    return [
        {"label": "Báo cáo kinh doanh", "query": "Tổng hợp tình hình khách hàng và leads mới hôm nay cho anh"},
        {"label": "Danh sách n8n", "query": "Liệt kê danh sách các workflow n8n và trạng thái hoạt động"},
        {"label": "Kiểm tra lỗi n8n", "query": "Kiểm tra xem có workflow n8n nào bị lỗi gần đây không?"},
        {"label": "Learning Queue", "query": "Tóm tắt các câu hỏi khách hàng đang chờ admin duyệt trong Learning Queue"}
    ]
