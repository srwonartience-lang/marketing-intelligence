import feedparser

from collectors.base_collector import BaseCollector
from collectors.http_client import fetch_bytes
from utils.logger import get_logger

logger = get_logger(__name__)


class RSSCollector(BaseCollector):
    def collect(self, source: dict) -> list[dict]:
        rss_url = source["rss_url"]
        source_id = source["source_id"]

        if not str(rss_url).strip():
            raise ValueError(f"Missing rss_url for source_id={source_id}")

        raw_bytes = fetch_bytes(rss_url, source_id)
        feed = feedparser.parse(raw_bytes)

        if feed.bozo and not feed.entries:
            raise ValueError(
                f"RSS feed parse failed for {source_id} ({rss_url}): {feed.bozo_exception}"
            )

        raw_items = [self._to_raw_item(entry, source_id) for entry in feed.entries]

        logger.info(f"[{source_id}] Collected {len(raw_items)} raw items from {rss_url}")
        return raw_items

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
