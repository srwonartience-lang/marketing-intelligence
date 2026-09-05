"""분류 결과(content_topics)를 사람이 눈으로 보고 정성평가하기 좋은 형태로
별도 리뷰 스프레드시트에 내보낸다. 메인 DB의 여러 시트(contents/sources/topics/
categories/content_events/events)를 조인해 한 줄에 다 보이게 만든다.

룰 기반과 LLM 분류를 각각 실행해 assigned_by 값으로 나란히 비교할 수 있다.
"""

from config import settings
from sheets.client import get_spreadsheet_by_id, get_worksheet
from utils.logger import get_logger

logger = get_logger(__name__)

REVIEW_HEADERS = [
    "content_id",
    "title",
    "summary",
    "topic_name",
    "category_name",
    "confidence_score",
    "assigned_by",
    "assigned_at",
    "source_name",
    "published_at",
    "content_url",
    "event_id",
    "event_title",
    "정확한가",
    "비고",
]


def build_review_rows() -> list:
    content_topics = get_worksheet(settings.SHEET_CONTENT_TOPICS).get_all_records()
    topics = {t["topic_id"]: t for t in get_worksheet(settings.SHEET_TOPICS).get_all_records()}
    categories = {c["category_id"]: c["category_name"] for c in get_worksheet(settings.SHEET_CATEGORIES).get_all_records()}
    contents = {c["content_id"]: c for c in get_worksheet(settings.SHEET_CONTENTS).get_all_records()}
    sources = {s["source_id"]: s["source_name"] for s in get_worksheet(settings.SHEET_SOURCES).get_all_records()}
    content_event_map = {r["content_id"]: r["event_id"] for r in get_worksheet(settings.SHEET_CONTENT_EVENTS).get_all_records()}
    events = {e["event_id"]: e["event_title"] for e in get_worksheet(settings.SHEET_EVENTS).get_all_records()}

    rows = []
    for ct in content_topics:
        content = contents.get(ct["content_id"], {})
        topic = topics.get(ct["topic_id"], {})
        category_name = categories.get(topic.get("category_id"), "")
        event_id = content_event_map.get(ct["content_id"], "")

        rows.append([
            ct["content_id"],
            content.get("title", ""),
            content.get("summary", ""),
            topic.get("topic_name", ct["topic_id"]),
            category_name,
            ct.get("confidence_score", ""),
            ct.get("assigned_by", ""),
            ct.get("assigned_at", ""),
            sources.get(content.get("source_id"), content.get("source_id", "")),
            content.get("published_at", ""),
            content.get("url", ""),
            event_id,
            events.get(event_id, ""),
            "",  # 정확한가 (사용자가 직접 채움)
            "",  # 비고
        ])
    return rows


def run_export() -> None:
    if not settings.CLASSIFICATION_REVIEW_SHEET_ID:
        raise ValueError("CLASSIFICATION_REVIEW_SHEET_ID가 .env에 설정되어 있지 않습니다")

    rows = build_review_rows()
    logger.info(f"Built {len(rows)} review rows from content_topics")

    review_sh = get_spreadsheet_by_id(settings.CLASSIFICATION_REVIEW_SHEET_ID)
    worksheet = review_sh.get_worksheet(0)

    worksheet.clear()
    worksheet.update([REVIEW_HEADERS] + rows, value_input_option="USER_ENTERED")
    logger.info(f"Wrote {len(rows)} rows to review sheet '{worksheet.title}'")


if __name__ == "__main__":
    run_export()
