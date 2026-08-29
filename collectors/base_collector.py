from abc import ABC, abstractmethod


class BaseCollector(ABC):
    """수집기 공통 인터페이스.

    RSS 외에 API 기반 수집기(예: Twitter API, Reddit API)를 추가할 때도
    이 인터페이스를 구현하면 동일한 파이프라인에서 사용할 수 있다.
    """

    @abstractmethod
    def collect(self, source: dict) -> list[dict]:
        """단일 source에 대한 원시 콘텐츠 항목 리스트를 반환한다.

        실패 시 예외를 발생시킨다. 여러 source를 순회하며 실패를 격리하는 책임은
        호출부(orchestrator)에 있다.
        """
        raise NotImplementedError
