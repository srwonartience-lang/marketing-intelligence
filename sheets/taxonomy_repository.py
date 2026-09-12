from config import settings
from sheets.client import get_worksheet


def _is_active(record: dict) -> bool:
    return str(record.get("active", "")).strip().upper() == "TRUE"


def get_active_categories() -> list:
    worksheet = get_worksheet(settings.SHEET_CATEGORIES)
    return [r for r in worksheet.get_all_records() if _is_active(r)]


def get_active_topics() -> list:
    worksheet = get_worksheet(settings.SHEET_TOPICS)
    return [r for r in worksheet.get_all_records() if _is_active(r)]


def get_active_platforms() -> list:
    worksheet = get_worksheet(settings.SHEET_PLATFORMS)
    return [r for r in worksheet.get_all_records() if _is_active(r)]
