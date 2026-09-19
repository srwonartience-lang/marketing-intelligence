from typing import Callable
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from collectors.site_parsers.base import SiteParser

# www.tiktok.com/business/...는 ads.tiktok.com/business/...로 리다이렉트된다.
# robots.txt는 호스트별로 다르므로, 실제로 콘텐츠를 내려주는 호스트를 직접 요청해
# 그 호스트의 robots.txt로 허용 여부를 판단한다.
_CONTENT_HOST = "ads.tiktok.com"
_KNOWN_HOSTS = {_CONTENT_HOST, "www.tiktok.com", "tiktok.com"}


class TikTokAdsParser(SiteParser):
    """TikTok for Business 블로그 목록(서버 렌더링 HTML)에서 글 카드를 읽는다.

    목록 카드에 제목·게시일·요약·링크가 모두 들어 있어 상세 페이지를 열 필요가 없다.
    """

    @staticmethod
    def matches(url: str) -> bool:
        parts = urlsplit(url)
        host = parts.netloc.lower()
        return host in _KNOWN_HOSTS and parts.path.startswith("/business")

    def parse(
        self,
        source: dict,
        fetch_page: Callable[[str], str],
        known_urls: frozenset,
    ) -> list[dict]:
        parts = urlsplit(source["url"])
        list_url = urlunsplit((parts.scheme, _CONTENT_HOST, parts.path, parts.query, ""))

        soup = BeautifulSoup(fetch_page(list_url), "html.parser")
        cards = soup.select("div.articleCard")
        if not cards:
            raise ValueError(f"No article cards found at {list_url}; page structure may have changed")

        items = []
        seen_urls = set()
        for card in cards:
            link = card.select_one("a.main")
            title = card.select_one(".cardTitle")
            if not (link and link.get("href") and title):
                continue

            url = urljoin(list_url, link["href"])
            # 대표 글은 목록 상단과 본 목록에 두 번 나온다.
            if url in seen_urls:
                continue
            seen_urls.add(url)

            date = card.select_one(".publishedDate")
            description = card.select_one(".cardDescription")
            items.append({
                "source_id": source["source_id"],
                "title": title.get_text(strip=True),
                "url": url,
                "published_at_raw": date.get_text(strip=True) if date else "",
                "author": source.get("source_name", ""),
                "summary_raw": description.get_text(strip=True) if description else "",
            })

        if not items:
            raise ValueError(f"Article cards found at {list_url} but none had title and link")
        return items
