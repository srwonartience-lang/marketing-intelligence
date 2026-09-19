import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from collectors.base_collector import BaseCollector
from collectors.http_client import (
    REQUEST_TIMEOUT_SECONDS,
    ROBOTS_AGENT,
    USER_AGENT,
    fetch_bytes,
)
from collectors.site_parsers import find_parser
from utils.logger import get_logger

logger = get_logger(__name__)

# 같은 사이트에 연속으로 요청을 쏘지 않기 위한 최소 간격.
REQUEST_DELAY_SECONDS = 1.0


class RobotsDisallowedError(ValueError):
    pass


class _PoliteFetcher:
    """robots.txt를 확인하고 요청 사이에 간격을 두며 페이지를 받아온다.

    collect() 한 번마다 새로 만들어 쓰므로 소스 간(스레드 간)에 공유되는 상태가 없다.
    """

    def __init__(self, source_id: str):
        self._source_id = source_id
        self._robots_by_host: dict[str, RobotFileParser] = {}
        self._made_request = False

    def __call__(self, url: str) -> str:
        if not self._robots_for(url).can_fetch(ROBOTS_AGENT, url):
            raise RobotsDisallowedError(f"robots.txt disallows fetching {url}")

        if self._made_request:
            time.sleep(REQUEST_DELAY_SECONDS)
        self._made_request = True

        return fetch_bytes(url, self._source_id).decode("utf-8", errors="replace")

    def _robots_for(self, url: str) -> RobotFileParser:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots_by_host:
            self._robots_by_host[host] = self._load_robots(host)
        return self._robots_by_host[host]

    def _load_robots(self, host: str) -> RobotFileParser:
        """robots.txt를 읽지 못하면 허용으로 간주하지 않고 수집을 거부한다.
        (파일이 아예 없는 404만 "제한 없음"으로 본다.)"""
        robots_url = f"{host}/robots.txt"
        request = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
        parser = RobotFileParser()

        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                parser.parse(response.read().decode("utf-8", errors="replace").splitlines())
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise ValueError(f"Could not read {robots_url} (HTTP {e.code}), refusing to crawl") from e
            parser.allow_all = True
        except (urllib.error.URLError, TimeoutError) as e:
            raise ValueError(f"Could not read {robots_url} ({e}), refusing to crawl") from e

        # parse()만 호출하면 "아직 읽지 않음" 상태로 남아 모든 url이 거부된다.
        parser.modified()
        return parser


class WebCollector(BaseCollector):
    """RSS가 없는 사이트(crawl_type=CRAWL)를 사이트별 파서로 수집한다.

    지원하는 사이트는 collectors/site_parsers에 등록된 파서로 결정된다. 파서가 없는 CRAWL 소스는
    supports()가 False를 돌려주므로 호출부가 걸러낸다. 사이트마다 이용 약관·robots.txt가 다르기 때문에
    "CRAWL이면 다 긁는다"가 아니라, 확인이 끝난 사이트만 파서로 등록하는 방식이다.
    """

    def __init__(self, known_urls: frozenset = frozenset()):
        self._known_urls = known_urls

    @staticmethod
    def supports(source: dict) -> bool:
        return find_parser(str(source.get("url", ""))) is not None

    def collect(self, source: dict) -> list[dict]:
        source_id = source["source_id"]
        parser = find_parser(str(source.get("url", "")))
        if parser is None:
            raise ValueError(f"No crawler registered for {source_id} ({source.get('url')})")

        raw_items = parser.parse(source, _PoliteFetcher(source_id), self._known_urls)

        logger.info(f"[{source_id}] Collected {len(raw_items)} raw items from {source['url']}")
        return raw_items
