"""분류가 확정된 이벤트로 Signal Desk 정적 대시보드(docs/index.html)를 생성한다.
GitHub Actions가 매일 수집/클러스터링/분류 다음 단계로 이 스크립트를 실행하고,
결과물을 GitHub Pages가 그대로 서빙한다.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from sheets.dashboard_repository import get_classified_events_for_dashboard
from utils.logger import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = BASE_DIR / "templates" / "dashboard_template.html"
OUTPUT_PATH = BASE_DIR / "docs" / "index.html"


def render_dashboard(events: list, generated_at: str) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.replace("__CLASSIFIED_EVENTS_JSON__", json.dumps(events, ensure_ascii=False))
    html = html.replace("__GENERATED_AT_JSON__", json.dumps(generated_at, ensure_ascii=False))
    return html


def run_generate() -> None:
    events = get_classified_events_for_dashboard()
    logger.info(f"Fetched {len(events)} classified events for dashboard")

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = render_dashboard(events, generated_at)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    logger.info(f"Wrote dashboard to {OUTPUT_PATH} ({len(html)} bytes)")


if __name__ == "__main__":
    run_generate()
