import time
import urllib.error
import urllib.request

from utils.logger import get_logger

logger = get_logger(__name__)

# 일부 사이트는 WAF가 봇처럼 보이는 요청(User-Agent 없음/feedparser 기본 요청 방식)을
# 빈 응답으로 차단한다. 식별 가능한 UA로 직접 fetch하여 우회 없이 정상 수신한다.
USER_AGENT = "Mozilla/5.0 (compatible; MarketingIntelligenceCollector/1.0)"
# robots.txt는 User-Agent 전체 문자열이 아니라 이 제품 토큰으로 규칙을 매칭한다.
ROBOTS_AGENT = "MarketingIntelligenceCollector"
REQUEST_TIMEOUT_SECONDS = 15
MAX_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 2


def fetch_bytes(url: str, source_id: str) -> bytes:
    """일시적인 네트워크 오류(타임아웃, 5xx 등)에 대비해 짧게 한 번 재시도한다."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as e:
            last_error = e
            if attempt < MAX_ATTEMPTS:
                logger.warning(f"[{source_id}] Fetch attempt {attempt} failed ({e}), retrying...")
                time.sleep(RETRY_DELAY_SECONDS)

    raise ValueError(f"Failed to fetch {url} for {source_id}: {last_error}") from last_error
