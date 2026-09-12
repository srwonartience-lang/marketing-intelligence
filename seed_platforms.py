"""platforms 시트에 빠진 플랫폼 행을 채운다. 여러 번 실행해도 안전하다.

기존 platforms 시드(P001~P016)에는 YouTube와 Google Analytics 4가 없었다.
주 사용자인 퍼포먼스 마케터가 매일 확인하는 채널에 이 둘이 포함되므로,
첫 화면의 "내 채널 상태" 행이 이들을 0으로라도 보여줄 수 있어야 한다.
국내 채널(Naver, Kakao)은 현재 수집 소스가 적어 대체로 0으로 표시되지만,
0도 "오늘 이 채널은 변경 없음"이라는 유효한 답이다.
"""

from sheets.client import get_worksheet
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

# platform_id는 기존 P001~P016 다음 번호를 잇는다.
PLATFORM_SEEDS = [
    {"platform_id": "P017", "platform_name": "YouTube", "company_name": "Google", "platform_type": "Video", "active": "TRUE"},
    {"platform_id": "P018", "platform_name": "YouTube Ads", "company_name": "Google", "platform_type": "Advertising", "active": "TRUE"},
    {"platform_id": "P019", "platform_name": "Google Analytics 4", "company_name": "Google", "platform_type": "Analytics", "active": "TRUE"},
    {"platform_id": "P020", "platform_name": "Naver Search Ads", "company_name": "Naver", "platform_type": "Advertising", "active": "TRUE"},
    {"platform_id": "P021", "platform_name": "Kakao Moment", "company_name": "Kakao", "platform_type": "Advertising", "active": "TRUE"},
    {"platform_id": "P022", "platform_name": "Display & Video 360", "company_name": "Google", "platform_type": "Advertising", "active": "TRUE"},
]


def run_seed() -> None:
    worksheet = get_worksheet(settings.SHEET_PLATFORMS)
    existing = worksheet.get_all_records()
    existing_names = {str(r.get("platform_name", "")).strip() for r in existing}
    existing_ids = {str(r.get("platform_id", "")).strip() for r in existing}

    missing = [
        seed for seed in PLATFORM_SEEDS
        if seed["platform_name"] not in existing_names and seed["platform_id"] not in existing_ids
    ]

    if not missing:
        logger.info(f"platforms sheet already has all seeds ({len(existing)} rows), nothing to add")
        return

    headers = worksheet.row_values(1)
    rows = [[seed.get(h, "") for h in headers] for seed in missing]
    worksheet.append_rows(rows, value_input_option="USER_ENTERED", insert_data_option="INSERT_ROWS")
    logger.info(f"Added {len(rows)} platforms: {[s['platform_name'] for s in missing]}")


if __name__ == "__main__":
    run_seed()
