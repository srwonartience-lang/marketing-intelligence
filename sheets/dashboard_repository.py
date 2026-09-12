from collections import defaultdict

from config import settings
from processing.action_tier import classify_tier
from sheets.client import get_worksheet
from sheets.content_platforms_repository import get_content_platform_map

OFFICIAL_TIER = "official"


def _platform_label(platform: dict) -> str:
    """화면에 쓸 짧은 이름. "Google Analytics 4"처럼 긴 이름은 배지에서 줄인다."""
    short = {
        "Google Analytics 4": "GA4",
        "Google AI Overview": "AI Overview",
        "Google AI Mode": "AI Mode",
        "Naver Search Ads": "네이버 검색광고",
        "Kakao Moment": "카카오모먼트",
    }
    return short.get(platform["platform_name"], platform["platform_name"])


def get_classified_events_for_dashboard() -> list:
    """카테고리 분류가 확정된 이벤트만, 화면에 필요한 형태로 조인해서 반환한다.

    첫 화면이 "내 채널에 조치할 변경이 있나"에 답해야 하므로, 카테고리/제목/요약
    외에 세 가지를 더 내려보낸다.

    - platforms: 이벤트에 묶인 콘텐츠들의 플랫폼 합집합. 첫 화면의 1차 축.
    - is_official: 묶인 콘텐츠 중 하나라도 공식 소스(sources.tier=Official)인지.
      실무자는 플랫폼 공식 공지면 바로 움직이고 매체 보도면 한 번 더 확인한다.
    - action_tier: 조치 필요 / 알아둘 것 / 참고. 저장값이 아니라 매 빌드마다
      (소스 tier + 플랫폼 + 본문)에서 다시 계산한다.

    또 first_seen_at을 함께 내려보낸다. "새로 생긴 것"은 이벤트가 마지막으로
    보도된 시점(last_seen_at)이 아니라 처음 발견된 시점 기준이어야 한다.
    """
    events = get_worksheet(settings.SHEET_EVENTS).get_all_records()
    categories = {c["category_id"]: c["category_name"] for c in get_worksheet(settings.SHEET_CATEGORIES).get_all_records()}
    content_events = get_worksheet(settings.SHEET_CONTENT_EVENTS).get_all_records()
    contents = {c["content_id"]: c for c in get_worksheet(settings.SHEET_CONTENTS).get_all_records()}
    source_rows = get_worksheet(settings.SHEET_SOURCES).get_all_records()
    platform_rows = get_worksheet(settings.SHEET_PLATFORMS).get_all_records()

    sources = {s["source_id"]: s["source_name"] for s in source_rows}
    source_is_official = {
        s["source_id"]: str(s.get("tier", "")).strip().lower() == OFFICIAL_TIER
        for s in source_rows
    }
    platforms = {p["platform_id"]: p for p in platform_rows}
    content_platforms = get_content_platform_map()

    event_contents = defaultdict(list)
    for ce in content_events:
        content = contents.get(ce["content_id"])
        if content:
            event_contents[ce["event_id"]].append(content)

    dashboard_events = []
    for event in events:
        category_id = event.get("category_id")
        if not category_id:
            continue

        linked_contents = event_contents.get(event["event_id"], [])

        # 같은 매체가 여러 번 보도해도 한 번만 표시한다. 공식 소스가 있으면
        # 대표 링크로 맨 앞에 오도록 정렬한다.
        seen_source_names = set()
        event_sources = []
        for content in linked_contents:
            source_id = content["source_id"]
            source_name = sources.get(source_id, source_id)
            if source_name in seen_source_names:
                continue
            seen_source_names.add(source_name)
            event_sources.append({
                "name": source_name,
                "url": content["url"],
                "official": source_is_official.get(source_id, False),
            })

        if not event_sources:
            continue

        event_sources.sort(key=lambda s: not s["official"])
        is_official = any(s["official"] for s in event_sources)

        platform_ids = []
        for content in linked_contents:
            for platform_id in content_platforms.get(content["content_id"], []):
                if platform_id not in platform_ids and platform_id in platforms:
                    platform_ids.append(platform_id)

        title = event["event_title"]
        summary = event["event_summary"]
        tier = classify_tier(title, summary, platform_ids, is_official)

        last_seen_at = event["last_seen_at"]
        first_seen_at = event.get("first_seen_at") or last_seen_at
        dashboard_events.append({
            "category": categories.get(category_id, category_id),
            "date": last_seen_at[:10],
            "time": last_seen_at[11:16] if len(last_seen_at) >= 16 else "00:00",
            "first_seen_at": first_seen_at,
            "title": title,
            "summary": summary,
            "sources": event_sources,
            "platforms": [
                {"id": pid, "label": _platform_label(platforms[pid]), "company": platforms[pid]["company_name"]}
                for pid in platform_ids
            ],
            "action_tier": tier,
            "is_official": is_official,
        })

    return dashboard_events
