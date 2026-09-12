from config import settings
from sheets.client import get_worksheet
from utils.logger import get_logger

logger = get_logger(__name__)


def get_content_ids_tagged_by(assigned_by: str) -> set:
    """특정 방식으로 이미 플랫폼 태깅된 content_id 집합.

    content_topics와 같은 이유로 "아무 방식으로든"이 아니라 "이 방식으로"만
    걸러낸다. 룰 기반과 LLM 태깅 결과를 나중에 비교할 수 있어야 한다.
    """
    worksheet = get_worksheet(settings.SHEET_CONTENT_PLATFORMS)
    return {
        r["content_id"]
        for r in worksheet.get_all_records()
        if r.get("assigned_by") == assigned_by
    }


def get_content_platform_map() -> dict:
    """content_id -> [platform_id, ...]. 대시보드는 태깅 방식을 구분하지 않고
    붙어 있는 플랫폼을 모두 쓴다."""
    worksheet = get_worksheet(settings.SHEET_CONTENT_PLATFORMS)
    mapping = {}
    for r in worksheet.get_all_records():
        if r.get("content_id") and r.get("platform_id"):
            mapping.setdefault(r["content_id"], []).append(r["platform_id"])
    return mapping


def append_content_platforms(rows: list) -> None:
    """append_rows(INSERT_ROWS)로 원자적으로 이어붙인다. 직접 행 번호를 계산해
    update()하면 스케줄 실행과 수동 실행이 겹칠 때 서로 덮어쓴다(contents 시트에서
    실제로 발생한 문제)."""
    if not rows:
        logger.info("No content-platform assignments to append")
        return

    worksheet = get_worksheet(settings.SHEET_CONTENT_PLATFORMS)
    headers = worksheet.row_values(1)

    values = [[row.get(h, "") for h in headers] for row in rows]
    worksheet.append_rows(values, value_input_option="USER_ENTERED", insert_data_option="INSERT_ROWS")
    logger.info(f"Appended {len(values)} content-platform assignments")
