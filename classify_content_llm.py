from datetime import datetime, timezone

from config import settings
from processing.event_categorizer import compute_event_category_updates
from processing.llm_classifier import classify_contents
from sheets.content_topics_repository import append_content_topics, get_content_ids_classified_by
from sheets.contents_repository import get_unclassified_contents
from sheets.events_repository import update_events_category
from sheets.taxonomy_repository import get_active_topics
from utils.logger import get_logger

logger = get_logger(__name__)

ASSIGNED_BY = "llm"


def run_llm_classification() -> None:
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 .env에 설정되어 있지 않습니다")

    topics = get_active_topics()
    topic_to_category = {t["topic_id"]: t["category_id"] for t in topics}

    classified_ids = get_content_ids_classified_by(ASSIGNED_BY)
    contents = get_unclassified_contents(classified_ids)
    logger.info(f"Unclassified contents (by {ASSIGNED_BY}): {len(contents)}")

    matches = classify_contents(contents, topics)
    assigned_at = datetime.now(timezone.utc).isoformat()

    new_rows = [
        {
            "content_id": content_id,
            "topic_id": topic_id,
            "confidence_score": confidence,
            "assigned_by": ASSIGNED_BY,
            "assigned_at": assigned_at,
        }
        for content_id, topic_id, confidence in matches
    ]

    append_content_topics(new_rows)
    classified_count = len({row["content_id"] for row in new_rows})
    logger.info(
        f"Classified {classified_count}/{len(contents)} contents into {len(new_rows)} topic assignments"
    )

    updates = compute_event_category_updates(ASSIGNED_BY, topic_to_category)
    update_events_category(updates)
    logger.info(f"Run finished: {len(new_rows)} content-topic links, {len(updates)} events newly categorized")


if __name__ == "__main__":
    run_llm_classification()
