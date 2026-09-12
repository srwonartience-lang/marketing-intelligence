# Marketing Intelligence — Data Collector

국내외 마케팅 트렌드를 자동으로 수집·분석하는 Marketing Intelligence 서비스의 데이터 수집 파이프라인입니다.

MVP 단계에서는 PostgreSQL/Supabase 대신 **Google Sheets**를 데이터베이스로 사용합니다.
현재 구현 범위는 RSS 기반 콘텐츠 수집기(Data Collector)와 Event Clustering이며, 이후 AI 분류(주제/카테고리)·AI Insight 기능이 추가될 예정입니다. Trend Score는 당분간 보류합니다.

## 프로젝트 구조

```
Marketing Intelligence/
├── .env                    # 환경변수 (직접 작성, git에 커밋하지 않음)
├── .env.example            # 환경변수 템플릿
├── requirements.txt
├── main.py                 # RSS 수집 엔트리포인트 (병렬 수집 오케스트레이션)
├── cluster_events.py       # Event Clustering 엔트리포인트
├── credentials/
│   └── *.json               # Google 서비스 계정 키 (직접 배치, git에 커밋하지 않음)
├── config/
│   └── settings.py         # 환경변수 로드 및 상수
├── collectors/
│   ├── base_collector.py   # 수집기 공통 인터페이스
│   └── rss_collector.py    # RSS 수집 로직 (UA 지정, 재시도 포함)
├── sheets/
│   ├── client.py               # Google Sheets 인증/연결
│   ├── sources_repository.py   # sources 시트 read
│   ├── contents_repository.py  # contents 시트 read/write, watermark 계산
│   └── events_repository.py    # events, content_events 시트 read/write
├── processing/
│   ├── cleaner.py           # 텍스트 정제, 날짜/언어 처리
│   ├── deduplicator.py      # content_hash 생성 및 중복 판별
│   ├── similarity.py        # TF-IDF 코사인 유사도 (순수 Python)
│   └── event_clusterer.py   # 콘텐츠를 이벤트로 묶는 클러스터링 로직
├── models/
│   ├── content.py           # Content 데이터 모델
│   └── event.py             # Event 데이터 모델
├── utils/
│   └── logger.py             # 로깅 설정
├── .github/workflows/
│   └── collect.yml          # 매일 자동 수집 + 클러스터링 (GitHub Actions)
└── logs/
    └── collector.log
```

## 사전 준비: Google Cloud 서비스 계정 설정

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트를 생성합니다.
2. "API 및 서비스 → 라이브러리"에서 **Google Sheets API**, **Google Drive API**를 활성화합니다.
3. "API 및 서비스 → 사용자 인증 정보 → 사용자 인증 정보 만들기 → 서비스 계정"으로 서비스 계정을 생성합니다.
4. 생성한 서비스 계정의 "키" 탭에서 **JSON 키**를 새로 만들어 다운로드합니다.
5. 다운로드한 JSON 파일을 `credentials/` 폴더 아래에 저장합니다.
6. JSON 파일 안의 `client_email` 값을 확인하여, 대상 Google Sheets 파일의 공유 설정에 **편집자(Editor)** 권한으로 추가합니다.

## 로컬 환경 설정

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` 파일을 열어 실제 값으로 채웁니다:

```
GOOGLE_APPLICATION_CREDENTIALS=credentials/<다운로드한 파일명>.json
GOOGLE_SHEETS_NAME=Marketing_Intelligence_DB
GOOGLE_SHEETS_ID=<시트 URL의 /d/와 /edit 사이 문자열>
LOG_LEVEL=INFO
```

- `GOOGLE_SHEETS_ID`를 채우면 이름 대신 ID로 시트를 엽니다 (이름 변경에 영향받지 않으므로 권장).

## sources 시트 형식

`sources` 시트는 다음 컬럼을 포함합니다:

| source_id | source_name | country | tier | source_type | url | rss_url | crawl_type | crawl_interval | active |
|---|---|---|---|---|---|---|---|---|---|
| S001 | Google Search Central | Global | Official | Search | https://developers.google.com/search/blog | https://developers.google.com/search/blog/feed.xml | RSS | 1 | TRUE |

- `active=TRUE`이며 `crawl_type=RSS`인 행만 RSS 수집기의 대상이 됩니다.
- `crawl_type=CRAWL`인 소스는 RSS가 없는 소스로, 향후 별도의 크롤러가 처리합니다.
- RSS URL은 코드에 하드코딩하지 않고 `rss_url` 컬럼에서 읽어옵니다.

## 실행

```bash
python main.py
```

- 소스를 처음 수집할 때(해당 소스로 저장된 데이터가 없을 때)는 최신 20개 항목만 가져옵니다. 오래된 피드(전체 아카이브를 제공하는 경우)가 한 번에 쏟아지는 것을 방지하기 위함입니다.
- 이후 실행부터는 그 소스에서 마지막으로 저장된 시점(watermark) 이후의 새 글만 가져옵니다.
- 한 소스가 실패해도(네트워크 오류, rss_url 누락 등) 다른 소스 수집은 계속되며, 실패 내역은 `logs/collector.log`에 기록됩니다.
- 여러 소스는 `ThreadPoolExecutor`로 병렬 수집됩니다 (I/O 바운드 작업이므로 스레드로 충분).

## Event Clustering

같은 이슈를 여러 매체가 서로 다른 제목/문구로 보도해도 하나의 Event로 묶기 위한 단계입니다.

```bash
python cluster_events.py
```

- 아직 `content_events`에 배정되지 않은 콘텐츠만 대상으로 합니다.
- 제목+요약을 토큰화해 순수 Python으로 TF-IDF 벡터를 만들고, 코사인 유사도로 비교합니다 (외부 API/라이브러리 없음).
- 발행일이 3일(`TIME_WINDOW_DAYS`) 이내로 가까운 이벤트만 비교 대상으로 삼습니다.
- 유사도가 임계값(`SIMILARITY_THRESHOLD`, 기본 0.3) 이상이면 기존 이벤트에 배정하고, 아니면 그 콘텐츠를 대표로 새 이벤트를 만듭니다.
- 한계: 한글은 공백 기준 토큰화라 조사가 붙으면 다른 토큰으로 인식되어, 영어 기사보다 유사도가 다소 저평가될 수 있습니다. 형태소 분석기 도입 없이는 완전히 해결되지 않는 v1 한계입니다.

## 자동 실행 (GitHub Actions)

`.github/workflows/collect.yml`이 매일 KST 오전 9시(UTC 00:00)에 `main.py`(수집) → `cluster_events.py`(클러스터링) → `classify_content.py`(룰 기반 분류) 순서로 자동 실행합니다.

LLM(Gemini) 기반 분류(`classify_content_llm.py`)는 자동화에 포함하지 않았습니다. 무료 티어 일일 요청 한도가 낮아 매일 자동 실행 시 금방 소진되고, 룰 기반과 결과를 비교/검증하는 동안은 수동으로 실행하는 편이 낫다고 판단했습니다. 필요해지면 `GEMINI_API_KEY`를 GitHub Secrets에 등록하고 워크플로우에 단계를 추가하면 됩니다.

설정 방법:

1. 이 프로젝트를 GitHub 저장소로 푸시합니다. (**`credentials/` 폴더와 `.env`는 `.gitignore`에 의해 절대 커밋되지 않습니다.**)
2. 저장소의 "Settings → Secrets and variables → Actions"에서 다음 두 개의 Repository secret을 등록합니다.
   - `GOOGLE_APPLICATION_CREDENTIALS_JSON`: 서비스 계정 JSON 키 파일의 **전체 내용**을 그대로 붙여넣습니다.
   - `GOOGLE_SHEETS_ID`: 대상 스프레드시트 ID.
3. "Actions" 탭에서 "Daily Marketing Intelligence Pipeline" 워크플로우를 확인합니다. `workflow_dispatch`가 설정되어 있어 수동으로도 즉시 실행해볼 수 있습니다.

로컬에서는 `GOOGLE_APPLICATION_CREDENTIALS`(파일 경로)를, GitHub Actions에서는 `GOOGLE_APPLICATION_CREDENTIALS_JSON`(JSON 문자열)을 사용하도록 `sheets/client.py`가 자동으로 분기합니다.

## 구현 완료 항목

### Data Collector
1. [x] Google Sheets 연결
2. [x] sources 시트 읽기 (active=TRUE & crawl_type=RSS 필터링)
3. [x] RSS URL 가져오기 (하드코딩 없음)
4. [x] RSS 콘텐츠 수집 (병렬 처리, User-Agent 지정, 재시도 포함)
5. [x] 데이터 정제 (HTML 태그/엔티티 제거, 날짜 UTC 통일, 언어 감지)
6. [x] 중복 확인 (URL + content_hash 기반, 실행 간 유지)
7. [x] contents 시트 저장 (watermark 기반 증분 수집)
8. [x] 에러 로그 처리 (소스별 실패 격리, 파일 로그 기록)

### Event Clustering
1. [x] 미분류 콘텐츠 조회 (content_events 기준)
2. [x] TF-IDF 코사인 유사도 계산 (순수 Python)
3. [x] 시간 윈도우 기반 후보 이벤트 필터링
4. [x] 임계값 기반 배정/신규 이벤트 생성
5. [x] events / content_events 시트 저장
6. [x] GitHub Actions 자동화 연동

### 보류
- Trend Score, AI Insight
- 주제/카테고리 AI 분류 (categories, topics, platforms 시드 데이터는 준비되어 있음)

## 알려진 제약 사항

- 일부 소스(예: Cloudflare 봇 챌린지가 걸린 사이트)는 RSS를 프로그래밍적으로 가져올 수 없습니다. 이런 소스는 `rss_url`을 비워두면 자동으로 스킵되며, 향후 `crawl_type=CRAWL` 방식의 별도 크롤러로 전환이 필요합니다.
- Google Sheets 파일을 브라우저에서 열어놓은 상태로 스크립트를 실행하면, 실시간 편집(우발적인 셀 입력, 되돌리기 등)이 API가 쓴 데이터와 충돌할 수 있습니다. 수집 스크립트를 실행할 때는 시트 탭을 닫아두는 것을 권장합니다.
