import time
import urllib.error
import urllib.request

import feedparser

from collectors.base_collector import BaseCollector
from utils.logger import get_logger

logger = get_logger(__name__)

# 일부 사이트는 WAF가 봇처럼 보이는 요청(User-Agent 없음/feedparser 기본 요청 방식)을
# 빈 응답으로 차단한다. 식별 가능한 UA로 직접 fetch하여 우회 없이 정상 수신한다.
USER_AGENT = "Mozilla/5.0 (compatible; MarketingIntelligenceCollector/1.0)"
REQUEST_TIMEOUT_SECONDS = 15
MAX_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 2


class RSSCollector(BaseCollector):
    def collect(self, source: dict) -> list[dict]:
        rss_url = source["rss_url"]
        source_id = source["source_id"]

        if not str(rss_url).strip():
            raise ValueError(f"Missing rss_url for source_id={source_id}")

        raw_bytes = self._fetch(rss_url, source_id)
        feed = feedparser.parse(raw_bytes)

        if feed.bozo and not feed.entries:
            raise ValueError(
                f"RSS feed parse failed for {source_id} ({rss_url}): {feed.bozo_exception}"
            )

        raw_items = [self._to_raw_item(entry, source_id) for entry in feed.entries]

        logger.info(f"[{source_id}] Collected {len(raw_items)} raw items from {rss_url}")
        return raw_items

    @staticmethod
    def _fetch(rss_url: str, source_id: str) -> bytes:
        """일시적인 네트워크 오류(타임아웃, 5xx 등)에 대비해 짧게 한 번 재시도한다."""
        request = urllib.request.Request(rss_url, headers={"User-Agent": USER_AGENT})
        last_error = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                    return response.read()
            except (urllib.error.URLError, TimeoutError) as e:
                last_error = e
                if attempt < MAX_ATTEMPTS:
                    logger.warning(
                        f"[{source_id}] Fetch attempt {attempt} failed ({e}), retrying..."
                    )
                    time.sleep(RETRY_DELAY_SECONDS)

        raise ValueError(f"Failed to fetch RSS feed for {source_id} ({rss_url}): {last_error}") from last_error

    @staticmethod
    def _to_raw_item(entry, source_id: str) -> dict:
        return {
            "source_id": source_id,
            "title": entry.get("title", ""),
            "url": entry.get("link", ""),
            "published_at_raw": entry.get("published", entry.get("updated", "")),
            "author": entry.get("author", ""),
            "summary_raw": entry.get("summary", entry.get("description", "")),
        }
