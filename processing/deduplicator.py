import hashlib
import re

_NON_WORD_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_for_hash(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    text = _NON_WORD_RE.sub("", text)
    return _WS_RE.sub(" ", text).strip()


def compute_content_hash(title: str, summary: str) -> str:
    """제목+본문 요약을 정규화한 뒤 해시화한다.
    공백/구두점/대소문자 차이가 있는 거의 동일한 콘텐츠도 같은 해시를 갖도록 한다."""
    normalized = normalize_for_hash(title, summary)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class Deduplicator:
    """같은 실행(run) 내 중복과, 시트에 이미 저장된 콘텐츠와의 중복을 함께 판별한다."""

    def __init__(self, existing_urls: set, existing_hashes: set):
        self._seen_urls = set(existing_urls)
        self._seen_hashes = set(existing_hashes)

    def is_duplicate(self, url: str, content_hash: str) -> bool:
        return url in self._seen_urls or content_hash in self._seen_hashes

    def mark_seen(self, url: str, content_hash: str) -> None:
        self._seen_urls.add(url)
        self._seen_hashes.add(content_hash)
