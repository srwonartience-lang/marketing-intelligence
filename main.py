from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from collectors.base_collector import BaseCollector
from collectors.rss_collector import RSSCollector
from collectors.web_collector import WebCollector
from models.content import Content
from processing.cleaner import (
    clean_author,
    clean_summary,
    clean_title,
    determine_content_type,
    detect_language,
    parse_published_at,
    utc_now_iso,
)
from processing.deduplicator import Deduplicator, compute_content_hash
from sheets.contents_repository import append_contents, get_existing_state
from sheets.sources_repository import get_active_crawl_sources, get_active_rss_sources
from utils.logger import get_logger

logger = get_logger(__name__)

# 소스를 처음 수집할 때(기존 저장 데이터가 없을 때) 가져올 최대 항목 수.
# 오래된 소스(OpenAI 등)가 전체 아카이브를 한 번에 쏟아내는 것을 방지한다.
FIRST_RUN_ITEM_LIMIT = 20


def build_content(raw_item: dict, source: dict, dedup: Deduplicator) -> Optional[Content]:
    url = raw_item["url"].strip()
    if not url:
        return None

    title = clean_title(raw_item["title"])
    summary = clean_summary(raw_item["summary_raw"])
    content_hash = compute_content_hash(title, summary)

    if dedup.is_duplicate(url, content_hash):
        return None

    dedup.mark_seen(url, content_hash)

    return Content(
        content_id=f"C{content_hash[:16]}",
        source_id=source["source_id"],
        title=title,
        url=url,
        published_at=raw_item["published_at"],
        collected_at=utc_now_iso(),
        author=clean_author(raw_item["author"]),
        language=detect_language(f"{title} {summary}"),
        content_type=determine_content_type(source),
        summary=summary,
        content_hash=content_hash,
        is_duplicate=False,
    )


def _fetch_source(source: dict, collector: BaseCollector) -> tuple:
    """네트워크 요청(수집)만 담당하는 워커. 스레드에서 병렬 실행되므로
    공유 상태(Deduplicator 등)는 건드리지 않고 결과만 반환한다."""
    try:
        raw_items = collector.collect(source)
        return source, raw_items, None
    except Exception as e:
        return source, [], e


def _plan_fetch_jobs(rss_collector: RSSCollector, web_collector: WebCollector) -> list[tuple]:
    """(source, 수집기) 쌍을 만든다. CRAWL 소스 중 전용 파서가 없는 것은 수집하지 않고 건너뛴다."""
    jobs = [(source, rss_collector) for source in get_active_rss_sources()]

    unsupported = []
    for source in get_active_crawl_sources():
        if web_collector.supports(source):
            jobs.append((source, web_collector))
        else:
            unsupported.append(source["source_id"])
    if unsupported:
        logger.info(f"CRAWL sources without a registered crawler, skipped: {unsupported}")

    return jobs


def run_collection(max_workers: int = 5) -> None:
    existing_urls, existing_hashes, last_published_by_source = get_existing_state()
    dedup = Deduplicator(existing_urls, existing_hashes)
    jobs = _plan_fetch_jobs(RSSCollector(), WebCollector(known_urls=frozenset(existing_urls)))

    fetch_results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_fetch_source, source, collector) for source, collector in jobs]
        for future in as_completed(futures):
            fetch_results.append(future.result())

    new_contents = []
    for source, raw_items, error in fetch_results:
        if error:
            logger.error(f"[{source['source_id']}] Collection failed, skipping source: {error}")
            continue

        for raw_item in raw_items:
            raw_item["published_at"] = parse_published_at(raw_item["published_at_raw"])
        raw_items.sort(key=lambda item: item["published_at"], reverse=True)

        watermark = last_published_by_source.get(source["source_id"])
        if watermark:
            # 게시일만 있고 시각이 없는 소스는 같은 날 올라온 새 글이 watermark와 같은 값이 된다.
            # 이미 저장된 글은 아래 build_content의 url/hash 중복 검사가 걸러내므로 >=로 안전하다.
            raw_items = [
                item for item in raw_items
                if not item["published_at"] or item["published_at"] >= watermark
            ]
        else:
            raw_items = raw_items[:FIRST_RUN_ITEM_LIMIT]

        collected_count = 0
        for raw_item in raw_items:
            try:
                content = build_content(raw_item, source, dedup)
            except Exception as e:
                logger.error(
                    f"[{source['source_id']}] Failed to process item '{raw_item.get('title')}': {e}"
                )
                continue

            if content is None:
                continue

            new_contents.append(content)
            collected_count += 1

        logger.info(f"[{source['source_id']}] {collected_count} new items ready to save")

    append_contents(new_contents)
    logger.info(f"Run finished: {len(new_contents)} new contents saved in total")


if __name__ == "__main__":
    run_collection()
