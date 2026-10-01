"""Compose concise CFC agronomy guidance from customer-facing RAG evidence.

This module never invents a crop protocol. It selects agronomy rows returned
by the knowledge search, removes lead-capture boilerplate from those rows, and
renders only a few useful sentences. Missing or ambiguous evidence is handed
to the agronomy contacts supplied by the caller.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable


_CONTACT_SENTENCE = re.compile(
    r"\b(?:ban\s+(?:gui|cho|nhan|de\s+lai)|de\s+lai\s+(?:sdt|so\s+dien\s+thoai)|"
    r"ky\s+su|chuyen\s+vien|admin|ben\s+minh\s+se\s+(?:goi|lien\s+he))\b",
    re.I,
)
_EXACT_DOSE_REQUEST = re.compile(
    r"\b(?:lieu(?:\s+luong)?|bao\s+nhieu\s*(?:kg|g|ml|lit|l|bao)?|"
    r"moi\s+(?:goc|cong|ha)|kg\s*/\s*(?:goc|cong|ha)|pha\s+bao\s+nhieu)\b",
    re.I,
)
_EXACT_DOSE_FACT = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:kg|g|ml|lit|l|bao)\s*(?:/\s*(?:goc|cong|ha|dot))?\b",
    re.I,
)


def _normalise(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "d").lower()
    return re.sub(r"\s+", " ", text).strip()


def _sentences(value: str) -> list[str]:
    cleaned = re.sub(r"[*_#]+", "", str(value or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"^dạ(?:\s+chào\s+bạn)?[!,.:;\s-]*", "", cleaned, flags=re.I)
    if not cleaned:
        return []
    rows: list[str] = []
    for part in re.split(r"(?<=[.!?])\s+", cleaned):
        part = part.strip()
        if not part:
            continue
        rows.append(part[0].upper() + part[1:])
    return rows


def _focus_instruction_sentence(sentence: str) -> str:
    """Drop stage-setting filler while retaining the source's instruction."""
    match = re.search(r"\b(?:bạn\s+)?(?:nên|cần|ưu tiên|tránh|tuyệt đối)\b", sentence, re.I)
    if match and match.start() > 35:
        focused = sentence[match.start():].strip()
        return focused[0].upper() + focused[1:]
    return sentence


def _information_sentences(value: str) -> list[str]:
    return [_focus_instruction_sentence(sentence) for sentence in _source_sentences(value)]


def _source_sentences(value: str) -> list[str]:
    rows: list[str] = []
    for sentence in _sentences(value):
        if _CONTACT_SENTENCE.search(_normalise(sentence)):
            continue
        rows.append(sentence)
    return rows


def _candidate_rows(search_result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = search_result.get("results")
    candidates = [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    if not candidates and search_result.get("answer"):
        candidates = [dict(search_result)]
    eligible: list[dict[str, Any]] = []
    for row in candidates:
        try:
            score = float(row.get("score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        if (
            str(row.get("category") or "").strip().lower() != "agronomy"
            or str(row.get("audience") or "customer").strip().lower() == "internal"
            or not str(row.get("answer") or "").strip()
            or not str(row.get("source_id") or "").strip()
            or score < 0.52
        ):
            continue
        row["score"] = score
        eligible.append(row)
    eligible.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return eligible


def _crop_scoped_answer_matches(
    row: dict[str, Any],
    *,
    requested_crop: str,
    known_crop_terms: Iterable[str],
) -> bool:
    """Reject a crop-specific answer for another crop without crop-pair rules."""
    crop_norm = _normalise(requested_crop).removeprefix("cay ").strip()
    if not crop_norm:
        return True
    useful = _normalise(" ".join(_source_sentences(str(row.get("answer") or ""))))
    if not useful:
        return False
    terms = {
        _normalise(term).removeprefix("cay ").strip()
        for term in known_crop_terms
        if _normalise(term).removeprefix("cay ").strip()
    }
    mentioned = {term for term in terms if re.search(rf"\b{re.escape(term)}\b", useful)}
    return not mentioned or crop_norm in mentioned


_QUERY_STOPWORDS = {
    "cay", "cho", "thi", "la", "gi", "nao", "sao", "voi", "dang", "bi", "nen",
    "dung", "bon", "phan", "giup", "minh", "toi", "em", "anh", "chi", "giai", "doan",
}


def _meaningful_tokens(value: Any) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", _normalise(value))
        if len(token) >= 2 and token not in _QUERY_STOPWORDS
    }


def _candidate_text(row: dict[str, Any]) -> str:
    return " ".join(str(row.get(field) or "") for field in (
        "answer", "question_examples", "learning_tags", "intent",
    ))


def _guidance_relevance(row: dict[str, Any], *, query: str, slots: dict[str, Any]) -> float:
    combined_norm = _normalise(_candidate_text(row))
    candidate_tokens = _meaningful_tokens(combined_norm)
    query_tokens = _meaningful_tokens(query)
    coverage = len(query_tokens & candidate_tokens) / max(len(query_tokens), 1)
    slot_scores: list[float] = []
    for field in ("crop_stage", "symptom"):
        value = _normalise(slots.get(field))
        if not value:
            continue
        slot_tokens = _meaningful_tokens(value)
        recall = len(slot_tokens & candidate_tokens) / max(len(slot_tokens), 1)
        if value in combined_norm:
            recall = 1.0
        slot_scores.append(recall)
    slot_score = sum(slot_scores) / len(slot_scores) if slot_scores else 0.0
    return float(row.get("score") or 0.0) + coverage * 0.08 + slot_score * 0.18


def _compact_sentences(sentences: list[str], *, limit: int = 440, max_sentences: int = 3) -> str:
    selected: list[str] = []
    length = 0
    for sentence in sentences:
        candidate = sentence.strip()
        if not candidate:
            continue
        extra = len(candidate) + (1 if selected else 0)
        if selected and (len(selected) >= max_sentences or length + extra > limit):
            break
        if not selected and len(candidate) > limit:
            clipped = candidate[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-")
            selected.append(clipped + ".")
            break
        selected.append(candidate)
        length += extra
    return " ".join(selected).strip()


def _context_label(slots: dict[str, Any]) -> str:
    parts: list[str] = []
    crop = str(slots.get("crop") or "").strip()
    stage = str(slots.get("crop_stage") or "").strip()
    symptom = str(slots.get("symptom") or "").strip()
    if crop:
        parts.append(crop)
    if stage:
        parts.append(f"giai đoạn {stage}")
    if symptom:
        parts.append(f"đang {symptom}")
    return ", ".join(parts)


def build_grounded_agronomy_guidance(
    *,
    query: str,
    slots: dict[str, Any],
    search_result: dict[str, Any],
    known_crop_terms: Iterable[str] = (),
    contacts: Iterable[tuple[str, str]] = (),
    force_expert: bool = False,
) -> dict[str, Any]:
    """Return a concise grounded answer plus provenance for pipeline tracing."""
    context = _context_label(slots)
    crop = str(slots.get("crop") or "").strip()
    candidates = [
        row for row in _candidate_rows(search_result)
        if _crop_scoped_answer_matches(
            row,
            requested_crop=crop,
            known_crop_terms=known_crop_terms,
        )
    ]
    candidates.sort(
        key=lambda row: _guidance_relevance(row, query=query, slots=slots),
        reverse=True,
    )
    contact_text = " hoặc ".join(
        f"{str(name).strip()} {str(phone).strip()}"
        for name, phone in contacts
        if str(name).strip() and str(phone).strip()
    )
    if not candidates:
        subject = f" cho {context}" if context else " này"
        answer = (
            f"Dạ trường hợp{subject} chưa có hướng dẫn đủ sát trong dữ liệu hiện tại, "
            "nên mình chưa chốt công thức hoặc liều để tránh hướng dẫn sai."
        )
        if contact_text:
            answer += f" Bạn gửi ảnh hiện trạng, tuổi cây và khu vực; cần xử lý nhanh thì liên hệ {contact_text} ạ."
        return {
            "answer": answer,
            "source_ids": [],
            "source_intents": [],
            "score": 0.0,
            "requires_expert": True,
            "evidence_count": 0,
        }

    top_score = float(candidates[0].get("score") or 0.0)
    selected = [candidates[0]]
    top_tokens = _meaningful_tokens(_candidate_text(candidates[0]))
    query_tokens = _meaningful_tokens(query)
    slot_tokens = _meaningful_tokens(" ".join(
        str(slots.get(field) or "") for field in ("crop_stage", "symptom")
    ))
    for row in candidates[1:]:
        if len(selected) >= 2 or float(row.get("score") or 0.0) < max(0.58, top_score - 0.12):
            break
        row_tokens = _meaningful_tokens(_candidate_text(row))
        newly_covered = (query_tokens - top_tokens) & row_tokens
        complements_requested_facet = bool(newly_covered & slot_tokens)
        if (
            str(row.get("intent") or "") != str(selected[0].get("intent") or "")
            and (complements_requested_facet or len(newly_covered) >= 2)
        ):
            selected.append(row)

    facts: list[str] = []
    for index, row in enumerate(selected):
        useful = _information_sentences(str(row.get("answer") or ""))
        if index:
            useful = useful[:1]
        facts.extend(useful)
    content = _compact_sentences(facts)
    if not content:
        return build_grounded_agronomy_guidance(
            query=query,
            slots=slots,
            search_result={},
            known_crop_terms=known_crop_terms,
            contacts=contacts,
        )

    prefix = f"Dạ với {context}, theo cẩm nang CFC: " if context else "Dạ theo cẩm nang CFC: "
    answer = prefix + content[0].lower() + content[1:]
    query_norm = _normalise(query)
    source_text = _normalise(" ".join(str(row.get("answer") or "") for row in selected))
    exact_dose_missing = bool(_EXACT_DOSE_REQUEST.search(query_norm) and not _EXACT_DOSE_FACT.search(source_text))
    high_risk = any(str(row.get("risk_level") or "").lower() == "high" for row in selected)
    ambiguous = str(search_result.get("confidence") or "").lower() == "low" or top_score < 0.62
    requires_expert = exact_dose_missing or high_risk or ambiguous or force_expert
    if requires_expert and contact_text:
        if exact_dose_missing:
            answer += (
                " Cẩm nang hiện chưa có mức kg/gốc cho đúng trường hợp này; "
                f"cần xử lý nhanh thì bạn liên hệ {contact_text} để được xem đúng hiện trạng vườn ạ."
            )
        else:
            answer += f" Liều cụ thể cần xem tuổi cây và hiện trạng vườn; bạn liên hệ {contact_text} để xử lý nhanh ạ."

    source_ids = list(dict.fromkeys(str(row.get("source_id") or "").strip() for row in selected if row.get("source_id")))
    source_intents = list(dict.fromkeys(str(row.get("intent") or "").strip() for row in selected if row.get("intent")))
    return {
        "answer": answer,
        "source_ids": source_ids,
        "source_intents": source_intents,
        "score": top_score,
        "requires_expert": requires_expert,
        "evidence_count": len(selected),
    }
