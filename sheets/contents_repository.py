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


def get_unclustered_contents(clustered_content_ids: set) -> list:
    """아직 content_events에 배정되지 않은 콘텐츠를 Event Clustering 입력으로 반환한다."""
    worksheet = get_worksheet(settings.SHEET_CONTENTS)
    records = worksheet.get_all_records()
    return [
        {
            "content_id": r["content_id"],
            "source_id": r["source_id"],
            "title": r["title"],
            "summary": r["summary"],
            "published_at": r["published_at"],
        }
        for r in records
        if r["content_id"] and r["content_id"] not in clustered_content_ids
    ]


def get_unclassified_contents(classified_content_ids: set) -> list:
    """아직 분류/태깅되지 않은 콘텐츠를 분류 입력으로 반환한다.

    제외할 content_id 집합을 호출자가 넘기므로 topic 분류(content_topics)와
    platform 태깅(content_platforms) 양쪽에서 같이 쓴다. 두 경우 모두 판단에
    필요한 입력은 제목과 요약뿐이다.
    """
    worksheet = get_worksheet(settings.SHEET_CONTENTS)
    records = worksheet.get_all_records()
    return [
        {
            "content_id": r["content_id"],
            "title": r["title"],
            "summary": r["summary"],
        }
        for r in records
        if r["content_id"] and r["content_id"] not in classified_content_ids
    ]


def append_contents(contents: list[Content]) -> None:
    """새 콘텐츠를 시트 맨 끝에 이어붙인다.

    직접 마지막 행 번호를 계산해 update()로 쓰는 방식은, 스케줄 실행과 수동
    재실행이 겹치는 등 두 프로세스가 동시에 돌면 같은 행 번호를 계산해 서로
    덮어쓰는 경쟁 상태(race condition)에 취약하다는 것이 실제로 확인됐다.
    대신 Google Sheets API가 서버 측에서 원자적으로 처리하는 append_rows()를
    쓰되, insert_data_option="INSERT_ROWS"를 명시한다. 이렇게 하면 API의
    테이블 끝 추정이 틀리더라도(과거 실제로 발생) 기존 셀을 덮어쓰는 대신
    새 행을 삽입하므로 최악의 경우에도 데이터 손실은 발생하지 않는다.
    """
    if not contents:
        logger.info("No new contents to append")
        return

    worksheet = get_worksheet(settings.SHEET_CONTENTS)
    headers = worksheet.row_values(1)

    rows = []
    for content in contents:
        data = content.to_dict()
        rows.append([data.get(header, "") for header in headers])

    worksheet.append_rows(rows, value_input_option="USER_ENTERED", insert_data_option="INSERT_ROWS")
    logger.info(f"Appended {len(rows)} new rows to contents sheet")
