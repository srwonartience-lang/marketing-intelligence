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

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "collector.log"

SHEET_SOURCES = "sources"
SHEET_CONTENTS = "contents"
