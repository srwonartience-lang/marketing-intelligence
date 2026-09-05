from collections import Counter

from sheets.content_topics_repository import get_content_topic_map_by
from sheets.events_repository import get_all_events, get_content_event_map


def compute_event_category_updates(assigned_by: str, topic_to_category: dict) -> dict:
    """지정된 분류 방식(rule_based/llm)의 결과를 바탕으로, 아직 category_id가 없는
    이벤트에 채울 다수결 카테고리를 계산한다. 실제 시트 반영은 호출부에서
    update_events_category()로 한다.

    rule_based/llm 각 엔트리포인트가 같은 로직을 반복하지 않도록 공용으로 뺐다.
    """
    content_topic_map = get_content_topic_map_by(assigned_by)
    content_event_map = get_content_event_map()

    event_votes = {}
    for content_id, topic_ids in content_topic_map.items():
        event_id = content_event_map.get(content_id)
        if not event_id:
            continue
        for topic_id in topic_ids:
            category_id = topic_to_category.get(topic_id)
            if category_id:
                event_votes.setdefault(event_id, Counter())[category_id] += 1

    updates = {}
    for e in get_all_events():
        if e.get("category_id"):
            continue
        votes = event_votes.get(e["event_id"])
        if votes:
            updates[e["event_id"]] = votes.most_common(1)[0][0]
    return updates
