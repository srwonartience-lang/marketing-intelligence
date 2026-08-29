import html
import re
from datetime import datetime, timezone

from dateutil import parser as date_parser

from utils.logger import get_logger

logger = get_logger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_KOREAN_RE = re.compile(r"[가-힣]")


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def clean_title(raw_title: str) -> str:
    return strip_html(raw_title)


def clean_summary(raw_summary: str, max_length: int = 500) -> str:
    text = strip_html(raw_summary)
    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0] + "..."
    return text


def clean_author(raw_author: str) -> str:
    return strip_html(raw_author) or "Unknown"


def parse_published_at(raw_value: str) -> str:
    """RSS의 다양한 날짜 포맷을 UTC ISO 8601 문자열로 통일한다. 파싱 실패 시 빈 문자열."""
    if not raw_value:
        return ""
    try:
        dt = date_parser.parse(raw_value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError) as e:
        logger.warning(f"Failed to parse published_at '{raw_value}': {e}")
        return ""


def detect_language(text: str) -> str:
    """한글 포함 여부로 간단히 판별한다. 현재 MVP 소스는 모두 영문이지만
    한국어 소스(아이보스 등)가 활성화될 것을 대비한 최소 구현이다."""
    return "ko" if _KOREAN_RE.search(text or "") else "en"


def determine_content_type(source: dict) -> str:
    """현재는 모든 RSS 소스를 article로 취급한다.
    추후 소스별 콘텐츠 유형(영상, 팟캐스트 등)이 구분되면 이 함수만 확장하면 된다."""
    return "article"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
