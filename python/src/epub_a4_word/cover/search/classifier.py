from __future__ import annotations

from .models import CandidateCategory, CandidateClassification, SearchCandidate, SearchKind

_KEYWORDS = {
    CandidateCategory.SPINE: ("spine", "book spine", "書脊", "背脊"),
    CandidateCategory.FULL_SPREAD: (
        "full spread",
        "full cover",
        "dust jacket",
        "wraparound",
        "wrap around",
        "展開圖",
        "完整書衣",
        "完整封面",
    ),
    CandidateCategory.BACK: ("back cover", "rear cover", "book back", "背面", "封底"),
    CandidateCategory.REFERENCE_PHOTO: (
        "photo",
        "angle",
        "side view",
        "實拍",
        "多角度",
        "側面",
    ),
    CandidateCategory.FRONT: ("front cover", "book cover", "封面", "正面"),
}


def classify_candidate(
    candidate: SearchCandidate,
    requested_kind: SearchKind | None = None,
) -> CandidateClassification:
    requested = SearchKind(requested_kind or candidate.query_kind)
    category = CandidateCategory(requested.value)
    confidence = 0.62
    reasons = [f"搜尋類型：{requested.value}"]
    text = " ".join(
        (
            candidate.title,
            candidate.image_url,
            candidate.preview_url,
            candidate.source_page,
        )
    ).casefold()

    for candidate_category in (
        CandidateCategory.SPINE,
        CandidateCategory.FULL_SPREAD,
        CandidateCategory.BACK,
        CandidateCategory.REFERENCE_PHOTO,
        CandidateCategory.FRONT,
    ):
        matched = next((word for word in _KEYWORDS[candidate_category] if word.casefold() in text), None)
        if matched:
            category = candidate_category
            confidence = 0.88
            reasons.append(f"關鍵字：{matched}")
            break

    if candidate.width_px and candidate.height_px:
        ratio = candidate.width_px / candidate.height_px
        if ratio <= 0.28:
            category = CandidateCategory.SPINE
            confidence = max(confidence, 0.82)
            reasons.append("圖片比例狹長")
        elif ratio >= 1.35:
            category = CandidateCategory.FULL_SPREAD
            confidence = max(confidence, 0.82)
            reasons.append("圖片比例接近展開書衣")

    if confidence < 0.55:
        category = CandidateCategory.UNKNOWN
    return CandidateClassification(category, confidence, tuple(reasons))
