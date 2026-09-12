from collections import defaultdict

from config import settings
from sheets.client import get_worksheet


def get_classified_events_for_dashboard() -> list:
    """카테고리 분류가 확정된 이벤트만, 화면에 필요한 형태(제목/요약/날짜/시간/출처)로
    조인해서 반환한다. 미분류 이벤트는 대시보드에 노출하지 않는다."""
    events = get_worksheet(settings.SHEET_EVENTS).get_all_records()
    categories = {c["category_id"]: c["category_name"] for c in get_worksheet(settings.SHEET_CATEGORIES).get_all_records()}
    content_events = get_worksheet(settings.SHEET_CONTENT_EVENTS).get_all_records()
    contents = {c["content_id"]: c for c in get_worksheet(settings.SHEET_CONTENTS).get_all_records()}
    sources = {s["source_id"]: s["source_name"] for s in get_worksheet(settings.SHEET_SOURCES).get_all_records()}

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
        seen_source_names = set()
        event_sources = []
        for content in linked_contents:
            source_name = sources.get(content["source_id"], content["source_id"])
            if source_name not in seen_source_names:
                seen_source_names.add(source_name)
                event_sources.append({"name": source_name, "url": content["url"]})

        if not event_sources:
            continue

        last_seen_at = event["last_seen_at"]
        dashboard_events.append({
            "category": categories.get(category_id, category_id),
            "date": last_seen_at[:10],
            "time": last_seen_at[11:16] if len(last_seen_at) >= 16 else "00:00",
            "title": event["event_title"],
            "summary": event["event_summary"],
            "sources": event_sources,
        })

    return dashboard_events
