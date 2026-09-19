import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

GOOGLE_APPLICATION_CREDENTIALS = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS", "credentials/service_account.json"
)
# GitHub Actions 등 파일을 커밋할 수 없는 클라우드 환경에서는 JSON 키 전체를
# 이 값(Secrets)으로 주입한다. 설정되어 있으면 파일 경로 대신 이 값을 사용한다.
GOOGLE_APPLICATION_CREDENTIALS_JSON = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", "")
GOOGLE_SHEETS_NAME = os.getenv("GOOGLE_SHEETS_NAME", "Marketing Intelligence DB")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "")

# 분류 결과를 사람이 직접 정성평가하는 별도 스프레드시트 (메인 DB와 분리된 파일).
CLASSIFICATION_REVIEW_SHEET_ID = os.getenv("CLASSIFICATION_REVIEW_SHEET_ID", "")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "collector.log"

SHEET_SOURCES = "sources"
SHEET_CONTENTS = "contents"
SHEET_EVENTS = "events"
SHEET_CONTENT_EVENTS = "content_events"
SHEET_CATEGORIES = "categories"
SHEET_TOPICS = "topics"
SHEET_CONTENT_TOPICS = "content_topics"
SHEET_PLATFORMS = "platforms"
SHEET_CONTENT_PLATFORMS = "content_platforms"
SHEET_DAILY_SUMMARIES = "daily_summaries"
