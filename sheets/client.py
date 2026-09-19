import json

import gspread
from google.oauth2.service_account import Credentials
from gspread.http_client import BackOffHTTPClient

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_spreadsheet = None
_gspread_client = None
_spreadsheets_by_id = {}


def _authorize(credentials: Credentials) -> gspread.Client:
    """요청 한도(429)·타임아웃(408)·서버 오류(5xx)에서 자동으로 재시도하는 클라이언트를 만든다.

    기본 클라이언트는 한 번 실패하면 그대로 예외를 던진다. 2026-09-19 자동 실행에서
    수집·분류·태깅은 모두 성공했는데 마지막 대시보드 생성 단계만 실패했고, 같은
    데이터로 로컬에서 다시 돌리면 성공했다. 대시보드 생성은 시트를 연달아 11번
    통째로 읽는데 앞 단계들이 이미 API를 많이 쓴 직후라 분당 호출 한도에 걸린
    것으로 본다. BackOffHTTPClient는 2→4→8…초로 기다렸다 다시 요청하므로, 이런
    일시적 오류로 하루치 화면이 통째로 갱신되지 않는 일을 막는다.
    """
    return gspread.authorize(credentials, http_client=BackOffHTTPClient)


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
    client = _authorize(credentials)

    if settings.GOOGLE_SHEETS_ID:
        _spreadsheet = client.open_by_key(settings.GOOGLE_SHEETS_ID)
    else:
        _spreadsheet = client.open(settings.GOOGLE_SHEETS_NAME)

    logger.info(f"Connected to spreadsheet: {_spreadsheet.title}")
    return _spreadsheet


def get_worksheet(sheet_name: str):
    return get_spreadsheet().worksheet(sheet_name)


def get_spreadsheet_by_id(spreadsheet_id: str):
    """메인 DB가 아닌 다른 스프레드시트(예: 분류 결과 리뷰용 시트)를 같은
    서비스 계정 인증으로 연다."""
    global _gspread_client
    if spreadsheet_id not in _spreadsheets_by_id:
        if _gspread_client is None:
            _gspread_client = _authorize(_load_credentials())
        _spreadsheets_by_id[spreadsheet_id] = _gspread_client.open_by_key(spreadsheet_id)
    return _spreadsheets_by_id[spreadsheet_id]
