import json

import gspread
from google.oauth2.service_account import Credentials

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

_spreadsheet = None


def _load_credentials() -> Credentials:
    """로컬에서는 JSON 키 파일 경로를, GitHub Actions 등 클라우드에서는
    Secrets로 주입된 JSON 문자열을 사용한다. 파일을 커밋할 수 없는 환경을 위함이다."""
    if settings.GOOGLE_APPLICATION_CREDENTIALS_JSON:
        info = json.loads(settings.GOOGLE_APPLICATION_CREDENTIALS_JSON)
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    return Credentials.from_service_account_file(
        settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=SCOPES
    )


def get_spreadsheet():
    """Google Sheets 인증 후 대상 스프레드시트를 반환한다. 연결은 프로세스당 한 번만 수행한다."""
    global _spreadsheet
    if _spreadsheet is not None:
        return _spreadsheet

    credentials = _load_credentials()
    client = gspread.authorize(credentials)

    if settings.GOOGLE_SHEETS_ID:
        _spreadsheet = client.open_by_key(settings.GOOGLE_SHEETS_ID)
    else:
        _spreadsheet = client.open(settings.GOOGLE_SHEETS_NAME)

    logger.info(f"Connected to spreadsheet: {_spreadsheet.title}")
    return _spreadsheet


def get_worksheet(sheet_name: str):
    return get_spreadsheet().worksheet(sheet_name)
