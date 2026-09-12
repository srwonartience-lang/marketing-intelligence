"""콘텐츠 본문에서 광고/검색 플랫폼을 식별한다.

대시보드 첫 화면의 1차 축은 카테고리가 아니라 플랫폼이다. 실무자는 자기가
로그인하는 계정(Google Ads, Meta Ads, YouTube ...) 단위로 "내 일인지"를
판단하기 때문이다. 그래서 platform 태깅은 화면 기능이 아니라 데이터 요건이다.

플랫폼 후보는 코드에 하드코딩하지 않고 platforms 시트에서 읽어온다. 다만
platform_name만으로는 실제 기사에서 잘 잡히지 않아(예: "Google Ads"를
"AdWords"/"구글 애즈"로 쓰거나, Merchant Center처럼 하위 제품명만 등장)
플랫폼별 별칭을 큐레이션해서 함께 쓴다.
"""

import re

_WS_RE = re.compile(r"\s+")
_HANGUL_RE = re.compile(r"[가-힣]")

# platform_name -> 추가 별칭. platform_name 자체는 항상 키워드에 포함되므로 여기
# 다시 적지 않는다. 지나치게 일반적인 말(단독 "메타", 단독 "검색")은 오탐이
# 많아 의도적으로 뺐다 — "메타"는 메타버스/메타데이터에, "검색"은 거의 모든
# 마케팅 기사에 걸린다.
PLATFORM_ALIASES = {
    "Google Ads": [
        "adwords", "google adwords", "performance max", "pmax",
        "merchant center", "google shopping", "demand gen",
        "google ads editor", "smart bidding", "responsive search ad",
        "구글 애즈", "구글애즈", "구글 광고", "퍼포먼스 맥스",
    ],
    "Google Search": [
        "google search console", "search console", "googlebot",
        "google serp", "core update", "search central",
        "구글 검색", "서치 콘솔", "구글봇",
    ],
    "Google AI Overview": ["ai overview", "ai overviews", "sge", "search generative experience", "ai 개요"],
    "Google AI Mode": ["ai mode", "ai 모드"],
    "Meta Ads": [
        "facebook ads", "instagram ads", "meta ads manager", "ads manager",
        "advantage+", "advantage plus", "meta for business", "meta business suite",
        "메타 광고", "메타 애즈", "페이스북 광고", "인스타그램 광고", "광고 관리자",
    ],
    "Instagram": ["instagram", "reels", "인스타그램", "릴스"],
    "Facebook": ["facebook", "페이스북"],
    "YouTube": ["youtube", "yt shorts", "youtube shorts", "유튜브", "쇼츠"],
    "YouTube Ads": [
        "youtube ads", "video action campaign", "trueview", "in-stream ad",
        "youtube responsive ad", "youtube campaign", "bumper ad",
        "유튜브 광고", "유튜브 애즈",
    ],
    "Google Analytics 4": [
        "ga4", "google analytics", "구글 애널리틱스", "지에이포",
        "gtm", "google tag manager", "태그 매니저",
    ],
    "ChatGPT": ["chatgpt", "챗gpt", "챗지피티"],
    "ChatGPT Search": ["chatgpt search", "searchgpt", "챗gpt 검색"],
    "Microsoft Ads": ["microsoft advertising", "bing ads", "빙 광고", "마이크로소프트 광고"],
    "Bing": ["bing", "bingbot", "빙"],
    "Copilot": ["copilot", "코파일럿"],
    "TikTok Ads": ["tiktok ads", "tiktok for business", "틱톡 광고"],
    "TikTok": ["tiktok", "tik tok", "틱톡"],
    "Perplexity": ["perplexity", "퍼플렉시티"],
    "Amazon Ads": ["amazon ads", "amazon advertising", "아마존 광고"],
    "Display & Video 360": ["dv360", "display & video 360", "display and video 360", "디스플레이 앤 비디오"],
    # 회사명 단독("naver", "카카오")은 광고 플랫폼과 무관한 기업 뉴스까지 끌어와서
    # 제외했다. 실제로 "카카오·SKT·KT 3사3색 AI 서비스" 기사가 카카오모먼트로
    # 잡히는 오탐이 확인됐다. 광고 제품명 단위로만 매칭한다.
    "Naver Search Ads": [
        "naver ads", "naver search ad", "네이버 광고", "네이버 검색광고",
        "네이버 성과형", "파워링크", "스마트스토어", "네이버 gfa",
    ],
    "Kakao Moment": [
        "kakao moment", "kakao ads", "카카오모먼트", "카카오 모먼트",
        "카카오 광고", "카카오톡 채널", "카카오 비즈보드",
    ],
}

# 한글은 뒤에 조사가 붙어("유튜브가", "메타 광고의") 단어 경계(\b)만으로는 매칭이
# 안 된다. 형태소 분석기를 쓰지 않고 이 문제를 줄이기 위해, 한글 키워드에는
# 조사 한 개까지 붙는 것을 허용한다. 이렇게 하면 "유튜브가"는 잡고 "유튜브"가
# 다른 단어의 일부인 경우("메타"→"메타버스")는 잡지 않는다.
_PARTICLES = [
    "에서도", "에서는", "으로는", "에게는", "에서", "에게", "으로", "에는", "라고", "라며",
    "부터", "까지", "만을", "만이", "은", "는", "이", "가", "을", "를", "의", "에", "와",
    "과", "도", "만", "로", "랑",
]
_PARTICLE_GROUP = "(?:" + "|".join(_PARTICLES) + ")?"


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").lower())


def _build_pattern(keyword: str) -> re.Pattern:
    """한글이 섞인 키워드는 조사 허용 + 한글/영숫자 경계로, 순수 ASCII 키워드는
    기존 분류기와 같은 단어 경계(\\b)로 매칭한다."""
    escaped = re.escape(keyword)
    if _HANGUL_RE.search(keyword):
        return re.compile(
            r"(?<![가-힣A-Za-z0-9])" + escaped + _PARTICLE_GROUP + r"(?![가-힣A-Za-z0-9])"
        )
    return re.compile(r"\b" + escaped + r"\b")


def build_platform_keywords(platforms: list) -> dict:
    """platform_id -> [compiled pattern, ...]. platforms 시트 행을 입력으로 받는다."""
    keywords = {}
    for platform in platforms:
        name = platform["platform_name"]
        terms = [_normalize(name)] + [_normalize(a) for a in PLATFORM_ALIASES.get(name, [])]
        # 긴 별칭이 짧은 별칭을 포함하는 경우(예: "youtube ads" ⊃ "youtube")가 있어
        # 중복을 제거하되 순서는 유지한다.
        seen = set()
        patterns = []
        for term in terms:
            if term and term not in seen:
                seen.add(term)
                patterns.append(_build_pattern(term))
        keywords[platform["platform_id"]] = patterns
    return keywords


def tag_text(text: str, platform_keywords: dict) -> list:
    """(platform_id, confidence) 리스트. 매칭된 별칭 수를 신뢰도 근사치로 쓴다
    (processing/classifier.py의 topic 분류와 같은 방식)."""
    normalized = _normalize(text)
    matches = []
    for platform_id, patterns in platform_keywords.items():
        hit_count = sum(1 for p in patterns if p.search(normalized))
        if hit_count > 0:
            confidence = min(1.0, round(0.6 + 0.2 * hit_count, 2))
            matches.append((platform_id, confidence))
    return matches
