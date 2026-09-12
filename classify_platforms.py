"""콘텐츠에 광고/검색 플랫폼을 태깅해 content_platforms 시트에 저장한다.

대시보드 첫 화면은 "내가 운영하는 채널에 변경이 있나"에 답하는 화면이므로
플랫폼 태깅 없이는 성립하지 않는다. classify_content.py(주제 분류)와 같은
룰 기반 방식이며, 매일 자동 실행 파이프라인에 포함된다.
"""

from datetime import datetime, timezone

from processing.platform_tagger import build_platform_keywords, tag_text
from sheets.content_platforms_repository import (
    append_content_platforms,
    get_content_ids_tagged_by,
)
from sheets.contents_repository import get_unclassified_contents
from sheets.taxonomy_repository import get_active_platforms
from utils.logger import get_logger

logger = get_logger(__name__)

ASSIGNED_BY = "rule_based"


def run_platform_tagging() -> None:
    platforms = get_active_platforms()
    platform_keywords = build_platform_keywords(platforms)
    logger.info(f"Active platforms: {len(platforms)}")

    tagged_ids = get_content_ids_tagged_by(ASSIGNED_BY)
    contents = get_unclassified_contents(tagged_ids)
    logger.info(f"Untagged contents (by {ASSIGNED_BY}): {len(contents)}")

    new_rows = []
    for content in contents:
        text = f"{content['title']} {content['summary']}"
        for platform_id, confidence in tag_text(text, platform_keywords):
            new_rows.append({
                "content_id": content["content_id"],
                "platform_id": platform_id,
                "confidence_score": confidence,
                "assigned_by": ASSIGNED_BY,
                "assigned_at": datetime.now(timezone.utc).isoformat(),
            })

    append_content_platforms(new_rows)
    tagged_count = len({row["content_id"] for row in new_rows})
    logger.info(
        f"Tagged {tagged_count}/{len(contents)} contents with {len(new_rows)} platform assignments"
    )


if __name__ == "__main__":
    run_platform_tagging()
