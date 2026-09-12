"""이벤트를 실무 조치 등급 3단계로 나눈다.

첫 화면이 "닫을 수 있는 체크리스트"가 되려면 모든 소식이 같은 무게로 놓여서는
안 된다. 아침에 봐야 하는 것은 내 캠페인 세팅을 바꿔야 하는 변경뿐이고,
업계 동향·리서치는 읽고 싶을 때 읽으면 된다.

    ACTION   조치 필요  기존 캠페인/계정 설정이 영향받는 변경
    HEADS_UP 알아둘 것  신규 기능·베타·출시. 지금 손댈 필요는 없음
    CONTEXT  참고      업계 동향, 리서치, 사례

등급은 events 시트에 저장하지 않고 대시보드를 만들 때마다 다시 계산한다.
사람이 손으로 고치는 값이 아니라 (소스 tier + 플랫폼 + 본문)에서 순수하게
유도되는 값이라서, 저장해 두면 룰을 고칠 때마다 718행을 백필해야 한다.
"""

import re

TIER_ACTION = "action"
TIER_HEADS_UP = "heads_up"
TIER_CONTEXT = "context"

TIER_LABELS = {
    TIER_ACTION: "조치 필요",
    TIER_HEADS_UP: "알아둘 것",
    TIER_CONTEXT: "참고",
}

TIER_ORDER = [TIER_ACTION, TIER_HEADS_UP, TIER_CONTEXT]

# 하나만 걸려도 조치 필요. 기존 설정이 깨지거나 강제로 바뀐다는 신호들.
ACTION_STRONG = [
    "deprecat", "sunset", "end of support", "end of life", "discontinu",
    "will be removed", "has been removed", "no longer supported",
    "no longer available", "no longer be", "breaking change", "shutting down",
    "shut down", "mandatory", "will be required", "now required",
    "forced migration", "must migrate", "action required",
    # 기능 제거와 신규 광고주 요건은 실제 코퍼스에서 확인된 조치 유발 패턴이다.
    # 예: "DV360 changes remove targeting exclusions and add new business
    # identity requirements" — 기존 캠페인 타겟팅이 깨지고 인증을 새로 받아야 한다.
    "will remove", "removes support", "removing support", "removes access",
    "remove targeting", "removes targeting", "removing targeting",
    "new requirements", "additional requirements", "identity requirements",
    "verification requirements", "new business identity",
    "지원 종료", "지원 중단", "서비스 종료", "제공 종료", "판매 중단",
    "필수 적용", "필수 전환", "의무화", "강제 적용", "마이그레이션",
    "조치 필요", "필수 변경", "신규 요건", "요건 추가", "인증 의무",
    "타겟팅 제거", "타겟팅 삭제",
]

# 공식 소스일 때만 조치 필요로 올린다. 매체 보도라면 "알아둘 것"에 머문다.
# 공식 발표라는 사실이 곧 "확정된 변경"이라는 뜻이기 때문이다.
ACTION_WEAK = [
    "policy update", "policy change", "migrate to", "migration",
    "retire", "retiring", "phase out", "phasing out", "enforce",
    "enforcement", "new requirement", "requirements change",
    "opt out", "opt-out", "default to", "by default", "effective date",
    "정책 변경", "약관 변경", "기본값 변경", "기본 설정 변경", "정책 개편",
    "요건 변경", "적용 예정", "시행 예정",
]

# 신규 기능·베타·출시. 지금 당장 손댈 필요는 없지만 다음 캠페인 설계에 영향.
HEADS_UP_SIGNALS = [
    "new feature", "now available", "general availability", "launch",
    "launches", "launched", "rolls out", "rolling out", "rollout",
    "beta", "alpha", "pilot", "early access", "experiment", "testing",
    "tests", "expands", "introduc", "adds support", "announc", "preview",
    "출시", "베타", "신규", "추가", "공개", "도입", "테스트", "시범", "확대",
]

# 요약/정리 글은 개별 이벤트가 아니라 묶음이다. 첫 화면에 올리면 같은 내용이
# 두 번 세어지고 "몇 건"이라는 숫자를 믿을 수 없게 된다.
DIGEST_SIGNALS = [
    "recap", "roundup", "round-up", "this week in", "weekly wrap",
    "daily search forum", "search forum recap", "link roundup",
    "주간 정리", "이번 주", "뉴스 브리핑",
]

_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").lower())


def _has_any(text: str, signals: list) -> bool:
    return any(s in text for s in signals)


def classify_tier(title: str, summary: str, platform_ids: list, has_official_source: bool) -> str:
    """이벤트의 조치 등급을 판정한다.

    플랫폼이 하나도 안 붙은 이벤트는 무조건 참고다. 어떤 플랫폼 얘기인지
    모르면 실무자가 조치할 대상 자체가 없기 때문이다. 이 규칙 하나가
    첫 화면을 리서치·업계 동향으로 채우지 않는 가장 큰 장치다.
    """
    text = _normalize(f"{title} {summary}")

    if _has_any(text, DIGEST_SIGNALS):
        return TIER_CONTEXT

    if not platform_ids:
        return TIER_CONTEXT

    if _has_any(text, ACTION_STRONG):
        return TIER_ACTION

    if has_official_source and _has_any(text, ACTION_WEAK):
        return TIER_ACTION

    if has_official_source or _has_any(text, HEADS_UP_SIGNALS):
        return TIER_HEADS_UP

    return TIER_CONTEXT
