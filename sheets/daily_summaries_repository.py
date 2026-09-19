"""daily_summaries 시트: 날짜별 AI 요약 저장소.

추가만 하는(append-only) 기록으로 둔다. 같은 날짜를 다시 요약하면 기존 행을 고치지
않고 새 행을 덧붙이고, 읽을 때 날짜별로 가장 최근 행을 쓴다. 기존 행을 찾아 제자리에서
고치려면 행 번호를 계산해 update()해야 하는데, 이 방식은 스케줄 실행과 수동 실행이
겹치면 서로 덮어쓴다는 것이 contents 시트에서 이미 확인됐다.
"""

import gspread

from config import settings
from sheets.client import get_spreadsheet
from utils.logger import get_logger

logger = get_logger(__name__)

HEADERS = ["date", "summary", "event_count", "fingerprint", "model", "generated_at"]


def ensure_sheet():
    """시트가 없으면 헤더와 함께 만든다. 처음 실행하는 환경에서 수동 준비 없이 동작하게."""
    spreadsheet = get_spreadsheet()
    try:
        return spreadsheet.worksheet(settings.SHEET_DAILY_SUMMARIES)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=settings.SHEET_DAILY_SUMMARIES, rows=200, cols=len(HEADERS)
        )
        worksheet.update([HEADERS], "A1", value_input_option="RAW")
        logger.info(f"Created sheet '{settings.SHEET_DAILY_SUMMARIES}'")
        return worksheet


def get_latest_summaries() -> dict:
    """date -> 가장 최근 행. 시트가 아직 없으면 빈 dict.

    대시보드 생성 단계도 이 함수를 쓰므로 시트가 없다고 예외를 던지면 안 된다.
    요약 기능이 한 번도 돌지 않은 상태에서도 대시보드는 만들어져야 한다.

    numericise_ignore=['all']: 기본값이면 gspread가 숫자처럼 보이는 문자열을 숫자로
    바꿔 버려, 날짜나 지문 문자열이 원래 값과 달라질 수 있다.
    """
    try:
        worksheet = get_spreadsheet().worksheet(settings.SHEET_DAILY_SUMMARIES)
    except gspread.exceptions.WorksheetNotFound:
        return {}

    latest = {}
    for row in worksheet.get_all_records(numericise_ignore=["all"]):
        date = str(row.get("date", "")).strip()
        if not date or not str(row.get("summary", "")).strip():
            continue
        current = latest.get(date)
        if current is None or str(row.get("generated_at", "")) > str(current.get("generated_at", "")):
            latest[date] = row
    return latest


def append_summaries(rows: list) -> None:
    """INSERT_ROWS로 원자적으로 이어붙인다.

    value_input_option="RAW": USER_ENTERED로 쓰면 시트가 "2026-09-18"을 날짜 서식으로
    바꿔 로케일에 따라 "2026. 9. 18"처럼 표시하고, 읽어 올 때 캘린더 날짜와 맞지 않게 된다.
    """
    if not rows:
        logger.info("No daily summaries to append")
        return

    worksheet = ensure_sheet()
    values = [[str(row.get(h, "")) for h in HEADERS] for row in rows]
    worksheet.append_rows(values, value_input_option="RAW", insert_data_option="INSERT_ROWS")
    logger.info(f"Appended {len(values)} daily summaries")
