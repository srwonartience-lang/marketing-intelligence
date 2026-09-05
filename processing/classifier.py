import re

_WS_RE = re.compile(r"\s+")

# topic_name(영문)만으로는 한글 기사에서 거의 매칭되지 않아 실제 데이터로 확인한 뒤
# topic_name 기준 보강한 한글 동의어. 지나치게 일반적인 단어(예: "플랫폼" 단독)는
# 오탐이 많아 의도적으로 제외했다.
KOREAN_SYNONYMS = {
    "Paid Search": ["검색광고", "검색 광고"],
    "Paid Social": ["소셜 광고", "소셜미디어 광고"],
    "Performance Max": ["퍼포먼스 맥스"],
    "Programmatic": ["프로그래매틱"],
    "Attribution": ["어트리뷰션"],
    "Conversion Optimization": ["전환율 최적화", "전환 최적화"],
    "AI Advertising": ["ai 광고"],
    "GEO": ["생성형 엔진 최적화", "제너레이티브 엔진 최적화"],
    "AI Search": ["ai 검색"],
    "AI Visibility": ["ai 가시성", "ai 노출"],
    "AI Overview": ["ai overviews"],
    "Generative AI": ["생성형 ai", "생성형 인공지능"],
    "Brand Strategy": ["브랜드 전략", "브랜딩"],
    "Campaign": ["캠페인", "마케팅 캠페인"],
    "Consumer Insight": ["소비자 인사이트", "소비자 행동"],
    "E-commerce": ["이커머스", "전자상거래"],
    "Social Commerce": ["소셜커머스", "소셜 커머스"],
    "Advertising Industry": ["광고 산업", "광고업계"],
    "MarTech": ["마테크", "마케팅 기술"],
    "Agency": ["에이전시", "광고대행사", "대행사"],
    "Data Science": ["데이터 사이언스", "데이터사이언스"],
    "Data Visualization": ["데이터 시각화"],
    "Machine Learning": ["머신러닝", "기계학습"],
}


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").lower())


def build_topic_keywords(topics: list) -> dict:
    """topic_id -> 키워드 리스트. topic_name과, 있으면 큐레이션한 한글 동의어를 함께 쓴다."""
    keywords = {}
    for t in topics:
        kw = [_normalize(t["topic_name"])]
        kw += [_normalize(k) for k in KOREAN_SYNONYMS.get(t["topic_name"], [])]
        keywords[t["topic_id"]] = kw
    return keywords


def _contains_keyword(normalized_text: str, keyword: str) -> bool:
    """단순 substring 매칭은 'AI Mode'가 'AI model' 안에서 우연히 걸리는 등
    단어 경계를 무시해 오탐이 나기 쉽다. \\b로 온전한 단어(구) 단위로만 매칭한다."""
    pattern = r"\b" + re.escape(keyword) + r"\b"
    return re.search(pattern, normalized_text) is not None


def classify_text(text: str, topic_keywords: dict) -> list:
    """(topic_id, confidence) 리스트를 반환한다. 매칭 키워드 수를 신뢰도 근사치로 쓴다."""
    normalized = _normalize(text)
    matches = []
    for topic_id, keywords in topic_keywords.items():
        hit_count = sum(1 for kw in keywords if kw and _contains_keyword(normalized, kw))
        if hit_count > 0:
            confidence = min(1.0, round(0.6 + 0.2 * hit_count, 2))
            matches.append((topic_id, confidence))
    return matches
