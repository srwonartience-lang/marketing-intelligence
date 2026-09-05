from datetime import datetime, timezone
from typing import Optional

from models.event import Event
from processing.similarity import build_tfidf_vectors, cosine_similarity
from utils.logger import get_logger

logger = get_logger(__name__)

TIME_WINDOW_DAYS = 3
SIMILARITY_THRESHOLD = 0.3


def _parse_dt(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _within_window(a: Optional[datetime], b: Optional[datetime]) -> bool:
    if a is None or b is None:
        return False
    return abs((a - b).total_seconds()) <= TIME_WINDOW_DAYS * 86400


def cluster_contents(contents: list, existing_events: list) -> tuple:
    """아직 이벤트에 안 묶인 콘텐츠를 발행일 순으로 훑으며, 최근(TIME_WINDOW_DAYS 이내)
    이벤트 중 텍스트 유사도가 가장 높고 임계값을 넘는 이벤트에 배정한다. 없으면 그
    콘텐츠 자신을 대표로 삼아 새 이벤트를 만든다.

    반환: (new_events: list[Event], content_event_rows: list[dict], last_seen_updates: dict)
    """
    contents_sorted = sorted(contents, key=lambda c: c.get("published_at") or "")

    documents = {c["content_id"]: f"{c['title']} {c['summary']}" for c in contents_sorted}
    for e in existing_events:
        documents[e["event_id"]] = f"{e['event_title']} {e['event_summary']}"

    vectors = build_tfidf_vectors(documents)

    candidates = {e["event_id"]: dict(e) for e in existing_events}
    last_seen_updates = {}
    new_events = []
    content_event_rows = []

    for content in contents_sorted:
        content_id = content["content_id"]
        published_dt = _parse_dt(content.get("published_at"))
        content_vector = vectors.get(content_id, {})

        best_event_id = None
        best_score = 0.0

        for event_id, event in candidates.items():
            last_seen_dt = _parse_dt(last_seen_updates.get(event_id) or event.get("last_seen_at"))
            if not _within_window(published_dt, last_seen_dt):
                continue
            score = cosine_similarity(content_vector, vectors.get(event_id, {}))
            if score > best_score:
                best_score = score
                best_event_id = event_id

        assigned_at = datetime.now(timezone.utc).isoformat()

        if best_event_id and best_score >= SIMILARITY_THRESHOLD:
            content_event_rows.append({
                "content_id": content_id,
                "event_id": best_event_id,
                "similarity_score": round(best_score, 4),
                "assigned_by": "rule_based",
                "assigned_at": assigned_at,
            })
            if published_dt:
                current_last_seen = _parse_dt(
                    last_seen_updates.get(best_event_id) or candidates[best_event_id].get("last_seen_at")
                )
                if current_last_seen is None or published_dt > current_last_seen:
                    last_seen_updates[best_event_id] = content["published_at"]
        else:
            new_event_id = f"E{content_id[1:]}"
            new_event = Event(
                event_id=new_event_id,
                event_title=content["title"],
                event_summary=content["summary"],
                category_id="",
                first_seen_at=content.get("published_at", ""),
                last_seen_at=content.get("published_at", ""),
                status="active",
            )
            new_events.append(new_event)
            candidates[new_event_id] = {
                "event_id": new_event_id,
                "event_title": new_event.event_title,
                "event_summary": new_event.event_summary,
                "last_seen_at": new_event.last_seen_at,
            }
            vectors[new_event_id] = content_vector
            content_event_rows.append({
                "content_id": content_id,
                "event_id": new_event_id,
                "similarity_score": 1.0,
                "assigned_by": "rule_based",
                "assigned_at": assigned_at,
            })

    logger.info(
        f"Clustering: {len(contents_sorted)} contents -> {len(new_events)} new events, "
        f"{len(contents_sorted) - len(new_events)} merged into existing/new events"
    )
    return new_events, content_event_rows, last_seen_updates
