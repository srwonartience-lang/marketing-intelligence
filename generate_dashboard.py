"""분류가 확정된 이벤트로 Signal Desk 정적 대시보드(docs/index.html)를 생성한다.
GitHub Actions가 매일 수집/클러스터링/분류/플랫폼 태깅 다음 단계로 이 스크립트를
실행하고, 결과물을 GitHub Pages가 그대로 서빙한다.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from processing.day_summarizer import fingerprint, group_by_date
from sheets.daily_summaries_repository import get_latest_summaries
from sheets.dashboard_repository import get_classified_events_for_dashboard
from sheets.taxonomy_repository import get_active_platforms
from utils.logger import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "dashboard_template.html"
OUTPUT_PATH = BASE_DIR / "docs" / "index.html"

# 첫 화면 "내 채널 상태" 행의 기본 구성. 퍼포먼스 마케터가 매일 아침 확인하는
# 채널을 기본값으로 둔다. 사용자가 화면에서 고른 값은 브라우저에 저장되고,
# 고르기 전에는 이 순서대로 보여준다.
DEFAULT_MY_PLATFORMS = [
    "Google Ads",
    "Meta Ads",
    "YouTube Ads",
    "Display & Video 360",
    "Google Search",
    "Google Analytics 4",
]

# 채널이 함께 커버하는 하위 플랫폼. 광고 채널을 운영하는 사람은 그 채널이 올라가는
# 매체의 변경도 같이 봐야 한다. YouTube Ads를 돌리는 사람에게 YouTube 자체의
# 변경은 남의 일이 아니다.
#
# 이 관계가 없으면 실제로 놓치는 사례가 있었다. "Google announces October changes
# to Display & Video 360 API"는 본문이 "YouTube responsive ads"라고 써서 YouTube로만
# 태깅됐는데, 기본 채널에 YouTube가 없어 첫 화면에서 보이지 않았다. 태거 별칭을
# 고치는 방법도 있지만 이미 태깅된 콘텐츠에는 소급 적용되지 않는 반면, 이 관계는
# 대시보드를 만들 때마다 적용되므로 기존 데이터에도 즉시 반영된다.
PLATFORM_ROLLUP = {
    "YouTube Ads": ["YouTube"],
    "Meta Ads": ["Instagram", "Facebook"],
    "Google Search": ["Google AI Overview", "Google AI Mode"],
}


def build_platform_view(platforms: list) -> list:
    """화면에 쓸 플랫폼 목록. 기본 채널을 앞으로 정렬하고, platforms 시트에 아직
    없는 이름(예: seed_platforms.py 실행 전의 YouTube Ads)은 조용히 건너뛴다."""
    by_name = {p["platform_name"]: p for p in platforms}

    ordered = [by_name[name] for name in DEFAULT_MY_PLATFORMS if name in by_name]
    ordered_ids = {p["platform_id"] for p in ordered}
    rest = [p for p in platforms if p["platform_id"] not in ordered_ids]

    missing = [name for name in DEFAULT_MY_PLATFORMS if name not in by_name]
    if missing:
        logger.warning(
            f"Default platforms missing from platforms sheet, run seed_platforms.py: {missing}"
        )

    def covers(platform: dict) -> list:
        """이 채널로 집계할 platform_id 목록 (자기 자신 + 하위 플랫폼)."""
        ids = [platform["platform_id"]]
        for child_name in PLATFORM_ROLLUP.get(platform["platform_name"], []):
            child = by_name.get(child_name)
            if child and child["platform_id"] not in ids:
                ids.append(child["platform_id"])
        return ids

    return [
        {
            "id": p["platform_id"],
            "name": p["platform_name"],
            "company": p["company_name"],
            "is_default": p["platform_id"] in ordered_ids,
            "covers": covers(p),
        }
        for p in ordered + rest
    ]


def build_day_summaries(events: list) -> dict:
    """date -> AI 요약. 그날 소식 구성이 요약했을 때와 같은 날짜만 넣는다.

    지문이 다르면 요약 뒤에 그날 소식이 늘거나 바뀐 것이라, 목록에 없는 내용을
    요약하거나 새 소식을 빠뜨린 요약이 된다. 이 경우 보여주지 않는다 — 평소에는 같은
    파이프라인의 앞 단계(summarize_days.py)가 이미 다시 요약해 두므로, 그 단계가
    실패한 날에만 요약이 빠진다.

    요약을 읽다 실패해도 대시보드는 요약 없이 만들어져야 한다. 대시보드가 하루 갱신되지
    않는 것이 요약 하나 빠지는 것보다 훨씬 나쁘다.
    """
    try:
        latest = get_latest_summaries()
    except Exception as e:
        logger.warning(f"Could not read daily summaries, rendering without them: {e}")
        return {}

    summaries = {}
    for date, day_events in group_by_date(events).items():
        row = latest.get(date)
        if row and row.get("fingerprint") == fingerprint(day_events):
            summaries[date] = row["summary"]
    return summaries


def _script_json(value) -> str:
    """<script> 안에 넣을 JSON. 기사 요약이나 AI 요약에 '</script>'가 들어 있으면 그 자리에서
    스크립트가 끝나 페이지 전체가 깨진다. '</'를 '<\\/'로 바꿔도 JSON 값은 같다."""
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_dashboard(events: list, platforms: list, day_summaries: dict, generated_at: str) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.replace("__CLASSIFIED_EVENTS_JSON__", _script_json(events))
    html = html.replace("__PLATFORMS_JSON__", _script_json(platforms))
    html = html.replace("__DAILY_SUMMARIES_JSON__", _script_json(day_summaries))
    html = html.replace("__GENERATED_AT_JSON__", _script_json(generated_at))
    return html


def run_generate() -> None:
    events = get_classified_events_for_dashboard()
    platforms = build_platform_view(get_active_platforms())
    logger.info(f"Fetched {len(events)} classified events, {len(platforms)} platforms for dashboard")

    tier_counts = {}
    for event in events:
        tier_counts[event["action_tier"]] = tier_counts.get(event["action_tier"], 0) + 1
    logger.info(f"Action tier distribution: {tier_counts}")

    # 화면이 이 값으로 "지금 보는 게 오늘 만든 것인가"를 판정하므로, 표시용 문자열이
    # 아니라 브라우저가 정확히 해석할 수 있는 ISO 8601로 넘긴다.
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    day_summaries = build_day_summaries(events)
    logger.info(f"Daily summaries embedded: {len(day_summaries)}")
    html = render_dashboard(events, platforms, day_summaries, generated_at)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    logger.info(f"Wrote dashboard to {OUTPUT_PATH} ({len(html)} bytes)")


if __name__ == "__main__":
    run_generate()
