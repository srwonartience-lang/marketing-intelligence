"""업데이트 캘린더의 날짜별 AI 요약을 만들어 daily_summaries 시트에 쌓는다.

요약이 없는 날, 또는 요약한 뒤 그날의 소식 구성이 바뀐 날만 새로 요약한다. 처음
실행하면 밀린 날짜(현재 약 34일)를 한 번에 채우고, 이후에는 하루 1~3번만 호출한다.

GEMINI_API_KEY가 없으면 아무것도 하지 않고 정상 종료한다. 이 단계는 매일 자동 실행
파이프라인 안에 있는데, 요약이 안 된다는 이유로 대시보드 갱신까지 멈추면 안 된다.

    venv/bin/python summarize_days.py               # 기본 (최대 40일)
    venv/bin/python summarize_days.py --max-days 5  # 호출 수 제한
    venv/bin/python summarize_days.py --dry-run     # 시트에 쓰지 않고 결과만 출력
"""

import argparse
import time
from datetime import datetime, timezone

from config import settings
from processing.day_summarizer import (
    REQUEST_DELAY_SECONDS,
    fingerprint,
    summarizable_days,
    summarize_day,
)
from sheets.daily_summaries_repository import append_summaries, get_latest_summaries
from sheets.dashboard_repository import get_classified_events_for_dashboard
from utils.logger import get_logger

logger = get_logger(__name__)

# 한 번 실행에서 요약할 최대 날짜 수. 밀린 날짜를 한 번에 채우기에 충분하면서, 룰이나
# 데이터가 잘못돼 모든 날짜의 지문이 한꺼번에 바뀌는 경우 무료 티어 한도를 다 쓰지 않게 막는다.
DEFAULT_MAX_DAYS = 40


def run_summarize(max_days: int, dry_run: bool) -> None:
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set, skipping daily summaries")
        return

    days = summarizable_days(get_classified_events_for_dashboard())
    existing = get_latest_summaries()

    todo = [
        date for date, day_events in days.items()
        if existing.get(date, {}).get("fingerprint") != fingerprint(day_events)
    ]
    # 최근 날짜가 먼저다. 한도에 걸려 일부만 처리되더라도 사용자가 보는 날부터 채운다.
    todo.sort(reverse=True)
    logger.info(
        f"Summarizable days: {len(days)}, already current: {len(days) - len(todo)}, "
        f"to summarize: {len(todo)} (this run: {min(len(todo), max_days)})"
    )
    todo = todo[:max_days]
    if not todo:
        return

    from processing.llm_classifier import get_client
    client = get_client()

    rows = []
    try:
        for i, date in enumerate(todo):
            day_events = days[date]
            summary = summarize_day(client, date, day_events)
            if summary:
                rows.append({
                    "date": date,
                    "summary": summary,
                    "event_count": len(day_events),
                    "fingerprint": fingerprint(day_events),
                    "model": settings.GEMINI_MODEL,
                    "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                })
                logger.info(f"{date} ({len(day_events)}건): {summary}")
            if i + 1 < len(todo):
                time.sleep(REQUEST_DELAY_SECONDS)
    finally:
        # 중간에 예외로 끊겨도 그때까지 만든 요약은 버리지 않는다. 호출 한도를 이미 쓴 결과다.
        if dry_run:
            logger.info(f"Dry run: {len(rows)} summaries generated, not written")
        else:
            append_summaries(rows)

    logger.info(f"Run finished: {len(rows)}/{len(todo)} days summarized")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="업데이트 캘린더 날짜별 AI 요약")
    parser.add_argument("--max-days", type=int, default=DEFAULT_MAX_DAYS)
    parser.add_argument("--dry-run", action="store_true", help="시트에 쓰지 않고 결과만 출력")
    args = parser.parse_args()
    run_summarize(args.max_days, args.dry_run)
