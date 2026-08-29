from config import settings
from models.content import Content
from sheets.client import get_worksheet
from utils.logger import get_logger

logger = get_logger(__name__)


def get_existing_state() -> tuple[set, set, dict]:
    """contents 시트에서 기존 url 집합, content_hash 집합, 소스별 마지막 수집 시점을
    한 번의 API 호출로 가져온다.

    소스별 마지막 수집 시점(watermark)은 그 소스를 처음 수집하는 것이 아니라면,
    이후 실행에서 그 시점보다 최신인 항목만 가져오도록 필터링하는 데 쓰인다.
    """
    worksheet = get_worksheet(settings.SHEET_CONTENTS)
    values = worksheet.get_all_values()

    if len(values) <= 1:
        return set(), set(), {}

    headers = values[0]
    url_idx = headers.index("url")
    hash_idx = headers.index("content_hash")
    source_idx = headers.index("source_id")
    published_idx = headers.index("published_at")

    urls = set()
    hashes = set()
    last_published_by_source = {}

    for row in values[1:]:
        if len(row) > url_idx and row[url_idx]:
            urls.add(row[url_idx])
        if len(row) > hash_idx and row[hash_idx]:
            hashes.add(row[hash_idx])
        if len(row) > max(source_idx, published_idx):
            source_id = row[source_idx]
            published_at = row[published_idx]
            if source_id and published_at:
                current = last_published_by_source.get(source_id)
                if current is None or published_at > current:
                    last_published_by_source[source_id] = published_at

    return urls, hashes, last_published_by_source


def append_contents(contents: list[Content]) -> None:
    if not contents:
        logger.info("No new contents to append")
        return

    worksheet = get_worksheet(settings.SHEET_CONTENTS)
    headers = worksheet.row_values(1)

    rows = []
    for content in contents:
        data = content.to_dict()
        rows.append([data.get(header, "") for header in headers])

    worksheet.append_rows(rows, value_input_option="USER_ENTERED")
    logger.info(f"Appended {len(rows)} new rows to contents sheet")
