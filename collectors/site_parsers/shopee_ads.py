import json
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urlsplit

from collectors.site_parsers.base import SiteParser
from utils.logger import get_logger

logger = get_logger(__name__)

_STATE_MARKER = "window.__INITIAL_STATE__="

# 첫 수집(known_urls가 비어 있을 때)에도 상세 요청이 무한정 늘지 않도록 하는 상한.
# 상세 페이지는 본문 이미지가 인라인으로 박혀 있어 한 장에 1~2MB라 가볍지 않다.
MAX_DETAIL_FETCHES = 25


def extract_initial_state(html: str) -> dict:
    """Shopee Ads 페이지는 Vue SSR이라 목록/상세 데이터가 초기 상태 JSON으로 HTML에 들어 있다.
    뒤에 스크립트가 이어 붙어 있으므로 JSON 한 덩어리만 raw_decode로 읽는다."""
    start = html.find(_STATE_MARKER)
    if start == -1:
        raise ValueError("window.__INITIAL_STATE__ not found; page structure may have changed")
    state, _ = json.JSONDecoder().raw_decode(html, start + len(_STATE_MARKER))
    return state


class ShopeeAdsParser(SiteParser):
    """Shopee Ads(ads.shopee.<국가>) 뉴스를 읽는다.

    목록 카드는 제목만 있고 링크·날짜·요약이 없다. 링크는 /news/<id> 규칙이고,
    요약(desc)과 게시 시각(publistAt)은 상세 페이지 상태에만 있어서 새 글만 상세를 연다.
    국가별 사이트가 같은 템플릿이라 파서 하나로 처리한다. 다만 국가마다 갱신 상태가 다르다
    (예: 싱가포르·말레이시아 뉴스는 2021년에서 멈춰 있고 필리핀·대만은 최신).
    """

    @staticmethod
    def matches(url: str) -> bool:
        return urlsplit(url).netloc.lower().startswith("ads.shopee.")

    def parse(
        self,
        source: dict,
        fetch_page: Callable[[str], str],
        known_urls: frozenset,
    ) -> list[dict]:
        parts = urlsplit(source["url"])
        origin = f"{parts.scheme}://{parts.netloc}"

        state = extract_initial_state(fetch_page(source["url"]))
        try:
            articles = [
                article
                for category in state["article"]["list"].values()
                for article in category["list"]
            ]
        except KeyError as e:
            raise ValueError(f"Shopee Ads news list missing key {e}; page structure may have changed") from e
        if not articles:
            raise ValueError(f"No news articles found at {source['url']}; page structure may have changed")

        # id는 게시 순서와 무관하다(id가 작은 글이 더 최근일 수 있다). 목록은 사이트가 주는
        # 순서를 그대로 쓰고, 최종 날짜순 정렬은 게시 시각을 받아온 뒤 호출부가 한다.
        new_articles = [
            a for a in articles if f"{origin}/news/{a['id']}" not in known_urls
        ][:MAX_DETAIL_FETCHES]

        items = []
        for article in new_articles:
            url = f"{origin}/news/{article['id']}"
            try:
                detail = extract_initial_state(fetch_page(url))["article"]["detail"][str(article["id"])]
            except (ValueError, KeyError) as e:
                # 저장하지 않고 건너뛰면 다음 실행에서 다시 시도한다. 요약·날짜 없이 저장하면
                # 이미 저장된 url이 되어 영영 보강되지 않는다.
                logger.warning(f"[{source['source_id']}] Skipping {url}, detail unavailable: {e}")
                continue

            items.append({
                "source_id": source["source_id"],
                "title": article["name"],
                "url": url,
                "published_at_raw": self._to_iso(detail.get("publistAt")),
                "author": source.get("source_name", ""),
                "summary_raw": detail.get("desc", ""),
            })

        if new_articles and not items:
            raise ValueError(f"All {len(new_articles)} Shopee Ads detail pages failed to load")
        return items

    @staticmethod
    def _to_iso(unix_seconds) -> str:
        if not unix_seconds:
            return ""
        return datetime.fromtimestamp(int(unix_seconds), tz=timezone.utc).isoformat()
