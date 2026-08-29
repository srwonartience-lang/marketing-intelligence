from config import settings
from sheets.client import get_worksheet
from utils.logger import get_logger

logger = get_logger(__name__)


def _is_active(record: dict) -> bool:
    return str(record.get("active", "")).strip().upper() == "TRUE"


def _is_rss_type(record: dict) -> bool:
    return str(record.get("crawl_type", "")).strip().upper() == "RSS"


def get_active_rss_sources() -> list[dict]:
    """sources 시트에서 active=TRUE이며 crawl_type=RSS인 소스만 반환한다.

    crawl_type으로 필터링하여 CRAWL 타입 소스(향후 별도 크롤러가 처리할 대상)와
    명확히 구분한다. 특정 소스명을 코드에 하드코딩하지 않는다.
    """
    worksheet = get_worksheet(settings.SHEET_SOURCES)
    records = worksheet.get_all_records()

    sources = [r for r in records if _is_active(r) and _is_rss_type(r)]

    missing_rss_url = [r["source_id"] for r in sources if not str(r.get("rss_url", "")).strip()]
    if missing_rss_url:
        logger.warning(f"RSS type sources missing rss_url, will fail to collect: {missing_rss_url}")

    logger.info(f"Active RSS sources: {len(sources)} / total rows: {len(records)}")
    return sources
