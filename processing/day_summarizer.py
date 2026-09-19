"""업데이트 캘린더의 날짜별 AI 요약.

캘린더에서 날짜를 고르면 그날 들어온 소식이 시간순으로 나열되는데, 10건이 넘는
날은 목록만으로 그날 무슨 일이 있었는지 잡기 어렵다. 그날의 소식을 2~3문장으로
묶어 목록 위에 보여준다.

GitHub Pages는 정적 사이트라 브라우저에서 LLM을 부를 수 없다. 그래서 파이프라인이
미리 요약해 daily_summaries 시트에 쌓아 두고, 대시보드는 그 결과를 읽어 넣기만 한다.

이 모듈은 Gemini 클라이언트를 모듈 최상단에서 import하지 않는다. 대시보드 생성
단계도 fingerprint()를 쓰는데, 그 단계가 LLM 라이브러리 유무에 좌우되면 안 되기
때문이다.
"""

import hashlib
import json
import time

from config import settings
from processing.action_tier import TIER_ACTION, TIER_HEADS_UP, TIER_LABELS
from utils.logger import get_logger

logger = get_logger(__name__)

# 하루 1~2건이면 캘린더 목록 자체가 요약이다. 실제 데이터에서 99일 중 중앙값이 1건이라
# 모든 날을 요약하면 대부분 제목을 되풀이하는 데 호출을 쓰게 된다. 3건 이상인 날은 34일로
# 전부 2026-07-16 이후이고, 2020년대 옛 기사가 드문드문 걸린 날은 자연히 빠진다.
MIN_EVENTS_FOR_SUMMARY = 3

REQUEST_DELAY_SECONDS = 4  # 무료 티어 분당 요청 제한 (llm_classifier와 같은 값)
MAX_RETRIES = 3
ITEM_SUMMARY_MAX_CHARS = 200

_TIER_RANK = {TIER_ACTION: 0, TIER_HEADS_UP: 1}

# 인과·수치 규칙은 실제 출력에서 확인된 실패 때문에 들어갔다. 처음 프롬프트("흐름을
# 묶어서 쓰라")로 2026-09-16을 요약하자 무관한 세 기사(AI Overviews CTR 감소,
# Paid Search incrementality, Coach의 Spotify 캠페인)를 "이에 따라"로 이어
# "CTR이 줄어서 채널을 다변화한다"는 없는 추세를 지어냈고, 원문의 "노출이 가장 큰
# 도메인이 23.1% 잃었다"를 "CTR 23.1% 감소"로 줄였다. 요약은 사람이 원문을 다시
# 확인하지 않고 믿는 자리라, 지어낸 인과관계가 가장 해롭다.

PROMPT_TEMPLATE = """당신은 퍼포먼스 마케터를 위한 일일 브리핑을 씁니다.
아래는 {date} 하루 동안 수집·분류된 마케팅 업계 소식 {count}건입니다. 목록은 중요한 것부터 정렬되어 있습니다.

규칙:
- 목록에 있는 내용에만 근거하세요. 목록에 없는 사실·날짜·수치·회사명을 만들지 마세요.
- 광고 플랫폼(Google Ads, Meta, YouTube 등)의 변경이 있으면 가장 먼저 쓰세요. [조치 필요] 항목이 있으면 반드시 언급하세요.
- 나머지 소식은 주제가 비슷한 것끼리 짧게 묶으세요. 기사를 하나씩 나열하지 마세요.
- 서로 다른 기사를 원인과 결과로 잇지 마세요. 같은 날 나왔다고 서로 관련 있는 것은 아닙니다. '이에 따라', '그 결과', '이로 인해' 같은 말은 한 기사가 직접 밝힌 인과관계에만 쓰세요.
- 수치를 쓸 때는 원문이 붙인 조건을 빼지 마세요 (예: '일부 사이트에서 20% 감소'를 '20% 감소'로 줄이지 않기).
- 최대 3문장, 한국어, 공백 포함 160자 이내로 쓰세요.
- 제품명·플랫폼명은 원문 표기를 그대로 쓰세요.

소식 목록:
{items}

다음 JSON 형식으로만 응답하세요 (다른 설명 없이 JSON만):
{{"summary": "..."}}
"""


def group_by_date(events: list) -> dict:
    """date -> [event, ...]. 대시보드 캘린더와 똑같이 event['date'] 기준으로 묶는다.
    요약의 날짜 단위가 캘린더와 어긋나면 엉뚱한 날에 요약이 붙는다."""
    grouped = {}
    for event in events:
        grouped.setdefault(event["date"], []).append(event)
    return grouped


def fingerprint(day_events: list) -> str:
    """그날 이벤트 구성의 지문. 클러스터링이 늦게 들어온 기사를 기존 날짜에 붙이면
    그날의 소식이 바뀌므로, 지문이 달라진 날만 다시 요약한다.

    'fp_' 접두어는 시트가 16진수 문자열(예: '12e45...')을 숫자로 해석하지 않게 한다.
    """
    titles = sorted(e["title"] for e in day_events)
    digest = hashlib.sha1("\n".join(titles).encode("utf-8")).hexdigest()[:16]
    return f"fp_{digest}"


def summarizable_days(events: list) -> dict:
    """요약 대상인 날짜만 남긴 date -> events."""
    return {
        date: day_events
        for date, day_events in group_by_date(events).items()
        if len(day_events) >= MIN_EVENTS_FOR_SUMMARY
    }


def _item_line(index: int, event: dict) -> str:
    tier = event.get("action_tier")
    tags = []
    if tier in _TIER_RANK:
        tags.append(TIER_LABELS[tier])
    tags += [p["label"] for p in event.get("platforms", [])]
    tag_text = f"[{' · '.join(tags)}] " if tags else ""
    summary = (event.get("summary") or "")[:ITEM_SUMMARY_MAX_CHARS]
    return f"{index}. {tag_text}{event['title']}\n   요약: {summary}"


def build_prompt(date: str, day_events: list) -> str:
    ordered = sorted(day_events, key=lambda e: (_TIER_RANK.get(e.get("action_tier"), 2), e["title"]))
    items = "\n".join(_item_line(i + 1, e) for i, e in enumerate(ordered))
    return PROMPT_TEMPLATE.format(date=date, count=len(day_events), items=items)


def summarize_day(client, date: str, day_events: list):
    """하루치를 요약한다. 재시도 후에도 실패하면 None — 다른 날짜 처리는 계속되어야 한다."""
    from google.genai import types

    prompt = build_prompt(date, day_events)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            summary = str(json.loads(response.text).get("summary", "")).strip()
            if summary:
                return summary
            logger.warning(f"{date}: Gemini returned an empty summary (attempt {attempt})")
        except Exception as e:
            logger.warning(f"{date}: Gemini summarize attempt {attempt} failed: {e}")
        if attempt < MAX_RETRIES:
            time.sleep(REQUEST_DELAY_SECONDS * attempt)

    logger.error(f"{date}: summary failed after {MAX_RETRIES} attempts, skipping")
    return None
