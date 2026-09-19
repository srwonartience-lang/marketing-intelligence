from abc import ABC, abstractmethod
from typing import Callable


class SiteParser(ABC):
    """RSS가 없는 사이트 하나를 위한 파서.

    파서는 "이 사이트의 HTML/데이터 구조를 어떻게 읽는가"만 안다. 실제 네트워크 요청은
    호출부가 넘겨주는 fetch_page가 대신하므로, robots.txt 준수·요청 간격·재시도 같은
    공통 매너는 파서마다 다시 구현하지 않는다. 사이트 구조가 바뀌면 해당 파서 한 곳만 고친다.
    """

    @staticmethod
    @abstractmethod
    def matches(url: str) -> bool:
        """이 파서가 처리할 수 있는 소스 url인지 판별한다."""
        raise NotImplementedError

    @abstractmethod
    def parse(
        self,
        source: dict,
        fetch_page: Callable[[str], str],
        known_urls: frozenset,
    ) -> list[dict]:
        """RSSCollector와 같은 형태의 원시 항목 리스트를 반환한다.

        known_urls는 이미 저장된 url 집합이다. 목록 페이지만으로 충분한 사이트는 무시해도 되고,
        항목마다 상세 페이지를 따로 열어야 하는 사이트는 이미 저장된 항목의 상세 요청을 건너뛰는 데 쓴다.
        구조가 예상과 다르면 빈 리스트로 조용히 넘기지 말고 ValueError를 발생시켜야 한다.
        (조용히 0건이 되면 사이트 개편을 "새 글 없음"으로 착각하게 된다.)
        """
        raise NotImplementedError
