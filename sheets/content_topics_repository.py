from config import settings
from sheets.client import get_worksheet
from utils.logger import get_logger

logger = get_logger(__name__)


def get_content_ids_classified_by(assigned_by: str) -> set:
    """특정 분류 방식(assigned_by, 예: 'rule_based'/'llm')으로 이미 분류된
    content_id 집합을 반환한다.

    같은 콘텐츠를 룰 기반과 LLM 등 여러 방식으로 각각 분류해 결과를 비교하려면
    "아무 방식으로든 분류됨"이 아니라 "이 방식으로 분류됨"만 걸러내야, 한쪽을
    실행해도 다른 쪽 처리 대상이 가려지지 않는다.
    """
    worksheet = get_worksheet(settings.SHEET_CONTENT_TOPICS)
    return {
        r["content_id"]
        for r in worksheet.get_all_records()
        if r.get("assigned_by") == assigned_by
    }


def get_content_topic_map_by(assigned_by: str) -> dict:
    """content_id -> [topic_id, ...]. 특정 분류 방식의 결과만 모은다.

    이벤트 category_id는 이 결과들의 다수결로 유도하는데, rule_based와 llm
    분류가 뒤섞이면 어느 방식 때문에 카테고리가 정해졌는지 알 수 없게 되므로
    방식별로 분리해서 조회한다.
    """
    worksheet = get_worksheet(settings.SHEET_CONTENT_TOPICS)
    mapping = {}
    for r in worksheet.get_all_records():
        if r.get("assigned_by") == assigned_by:
            mapping.setdefault(r["content_id"], []).append(r["topic_id"])
    return mapping


def append_content_topics(rows: list) -> None:
    if not rows:
        logger.info("No content-topic assignments to append")
        return

    worksheet = get_worksheet(settings.SHEET_CONTENT_TOPICS)
    headers = worksheet.row_values(1)

    values = [[row.get(h, "") for h in headers] for row in rows]
    worksheet.append_rows(values, value_input_option="USER_ENTERED", insert_data_option="INSERT_ROWS")
    logger.info(f"Appended {len(values)} content-topic assignments")
