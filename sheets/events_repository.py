from gspread.utils import rowcol_to_a1

from config import settings
from models.event import Event
from sheets.client import get_worksheet
from utils.logger import get_logger

logger = get_logger(__name__)


def get_all_events() -> list:
    worksheet = get_worksheet(settings.SHEET_EVENTS)
    return worksheet.get_all_records()


def get_clustered_content_ids() -> set:
    """content_events 시트에서 이미 이벤트로 배정된 content_id 집합을 반환한다."""
    worksheet = get_worksheet(settings.SHEET_CONTENT_EVENTS)
    values = worksheet.get_all_values()

    if len(values) <= 1:
        return set()

    headers = values[0]
    content_idx = headers.index("content_id")
    return {row[content_idx] for row in values[1:] if len(row) > content_idx and row[content_idx]}


def get_content_event_map() -> dict:
    """content_id -> event_id. 콘텐츠 분류 결과로부터 이벤트의 category_id를 유도할 때 쓴다."""
    worksheet = get_worksheet(settings.SHEET_CONTENT_EVENTS)
    return {r["content_id"]: r["event_id"] for r in worksheet.get_all_records()}


def append_events(events: list) -> None:
    if not events:
        logger.info("No new events to append")
        return

    worksheet = get_worksheet(settings.SHEET_EVENTS)
    headers = worksheet.row_values(1)

    rows = [[event.to_dict().get(h, "") for h in headers] for event in events]
    worksheet.append_rows(rows, value_input_option="USER_ENTERED", insert_data_option="INSERT_ROWS")
    logger.info(f"Appended {len(rows)} new events")


def append_content_events(rows: list) -> None:
    if not rows:
        logger.info("No content-event links to append")
        return

    worksheet = get_worksheet(settings.SHEET_CONTENT_EVENTS)
    headers = worksheet.row_values(1)

    values = [[row.get(h, "") for h in headers] for row in rows]
    worksheet.append_rows(values, value_input_option="USER_ENTERED", insert_data_option="INSERT_ROWS")
    logger.info(f"Appended {len(values)} content-event links")


def _batch_update_column(worksheet, column_name: str, updates: dict) -> int:
    """{event_id: value} 여러 건을 한 번의 batch_update로 특정 컬럼에 반영한다."""
    headers = worksheet.row_values(1)
    id_col = headers.index("event_id")
    target_col = headers.index(column_name)

    values = worksheet.get_all_values()
    row_by_event_id = {row[id_col]: i + 1 for i, row in enumerate(values) if i > 0 and len(row) > id_col}

    batch_data = []
    for event_id, value in updates.items():
        row_number = row_by_event_id.get(event_id)
        if row_number is None:
            continue
        # 셀 주소는 worksheet.cell()로 조회하면 매번 API 호출이 발생해 대량
        # 업데이트 시 분당 읽기 할당량을 초과한다. 로컬 계산으로 대체한다.
        cell = rowcol_to_a1(row_number, target_col + 1)
        batch_data.append({"range": cell, "values": [[value]]})

    if batch_data:
        worksheet.batch_update(batch_data)
    return len(batch_data)


def update_events_last_seen(updates: dict) -> None:
    """{event_id: last_seen_at} 여러 건을 한 번의 batch_update로 반영한다."""
    if not updates:
        return
    worksheet = get_worksheet(settings.SHEET_EVENTS)
    count = _batch_update_column(worksheet, "last_seen_at", updates)
    if count:
        logger.info(f"Updated last_seen_at for {count} events")


def update_events_category(updates: dict) -> None:
    """{event_id: category_id} 여러 건을 한 번의 batch_update로 반영한다."""
    if not updates:
        return
    worksheet = get_worksheet(settings.SHEET_EVENTS)
    count = _batch_update_column(worksheet, "category_id", updates)
    if count:
        logger.info(f"Updated category_id for {count} events")
