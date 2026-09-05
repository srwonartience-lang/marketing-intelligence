import json
import time

from google import genai
from google.genai import types

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

BATCH_SIZE = 10
REQUEST_DELAY_SECONDS = 4  # 무료 티어 분당 요청 제한을 넘지 않기 위한 배치 간 간격
MAX_RETRIES = 3
SUMMARY_MAX_CHARS = 300

PROMPT_TEMPLATE = """다음은 마케팅 인텔리전스 서비스의 토픽 분류 체계입니다:

{taxonomy}

아래 기사들을 분석해서, 각 기사에 명확하게 해당하는 토픽 id를 골라주세요.
애매하거나 명확히 해당하는 토픽이 없으면 topics를 빈 배열로 남겨두세요. 억지로 끼워맞추지 마세요.
한 기사에 토픽이 여러 개 해당할 수도 있습니다.

기사 목록:
{articles}

다음 JSON 형식으로만 응답하세요 (다른 설명 없이 JSON만):
[{{"content_id": "...", "topics": [{{"topic_id": "T0xx", "confidence": 0.0}}]}}]
"""


def get_client() -> genai.Client:
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def build_taxonomy_text(topics: list) -> str:
    return "\n".join(
        f"- {t['topic_id']} | {t['topic_name']} ({t['category_id']}): {t['description']}"
        for t in topics
    )


def _build_articles_text(batch: list) -> str:
    return "\n".join(
        f"{i + 1}. content_id={c['content_id']}\n"
        f"   제목: {c['title']}\n"
        f"   요약: {c['summary'][:SUMMARY_MAX_CHARS]}"
        for i, c in enumerate(batch)
    )


def classify_batch(client: genai.Client, taxonomy_text: str, batch: list) -> list:
    """콘텐츠 묶음을 한 번의 요청으로 분류한다. 실패 시 재시도 후, 그래도 실패하면
    이 배치는 건너뛰고 빈 리스트를 반환한다 (다른 배치 처리는 계속되어야 하므로)."""
    prompt = PROMPT_TEMPLATE.format(
        taxonomy=taxonomy_text,
        articles=_build_articles_text(batch),
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return json.loads(response.text)
        except Exception as e:
            logger.warning(f"Gemini batch classify attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(REQUEST_DELAY_SECONDS * attempt)

    logger.error(f"Gemini batch classify failed after {MAX_RETRIES} attempts, skipping this batch")
    return []


def classify_contents(contents: list, topics: list) -> list:
    """contents 전체를 배치로 나누어 분류하고, (content_id, topic_id, confidence) 튜플 리스트로 반환한다."""
    if not contents:
        return []

    valid_topic_ids = {t["topic_id"] for t in topics}
    taxonomy_text = build_taxonomy_text(topics)
    client = get_client()

    results = []
    for i in range(0, len(contents), BATCH_SIZE):
        batch = contents[i:i + BATCH_SIZE]
        batch_results = classify_batch(client, taxonomy_text, batch)

        for item in batch_results:
            content_id = item.get("content_id")
            for topic in item.get("topics", []):
                topic_id = topic.get("topic_id")
                if topic_id not in valid_topic_ids:
                    logger.warning(f"Gemini returned unknown topic_id '{topic_id}', skipping")
                    continue
                results.append((content_id, topic_id, topic.get("confidence", "")))

        logger.info(f"Batch {i // BATCH_SIZE + 1}/{(len(contents) - 1) // BATCH_SIZE + 1}: {len(batch)} contents processed")
        if i + BATCH_SIZE < len(contents):
            time.sleep(REQUEST_DELAY_SECONDS)

    return results
