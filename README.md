# Marketing Intelligence — Data Collector

국내외 마케팅 트렌드를 자동으로 수집·분석하는 Marketing Intelligence 서비스의 데이터 수집 파이프라인입니다.

MVP 단계에서는 PostgreSQL/Supabase 대신 **Google Sheets**를 데이터베이스로 사용합니다.
현재 구현 범위는 RSS 기반 콘텐츠 수집기(Data Collector), Event Clustering, 주제/카테고리 분류(룰 기반 + LLM), 그리고 그 결과를 보여주는 정적 대시보드(Signal Desk)입니다. AI Insight, Trend Score는 당분간 보류합니다.

## 프로젝트 구조

```
Marketing Intelligence/
├── .env                    # 환경변수 (직접 작성, git에 커밋하지 않음)
├── .env.example            # 환경변수 템플릿
├── requirements.txt
├── main.py                       # RSS 수집 엔트리포인트 (병렬 수집 오케스트레이션)
├── cluster_events.py             # Event Clustering 엔트리포인트
├── classify_content.py           # 룰(키워드) 기반 분류 엔트리포인트
├── classify_content_llm.py       # Gemini 기반 분류 엔트리포인트
├── classify_platforms.py         # 룰 기반 플랫폼 태깅 엔트리포인트
├── seed_platforms.py             # platforms 시트에 빠진 플랫폼 추가 (재실행 안전)
├── export_classification_review.py  # 분류 결과를 별도 리뷰 시트로 내보내기
├── generate_dashboard.py         # Signal Desk 정적 대시보드(docs/index.html) 생성
├── templates/
│   └── dashboard_template.html   # 대시보드 HTML/CSS/JS 템플릿
├── docs/
│   └── index.html                # 생성된 대시보드 (GitHub Pages가 서빙)
├── credentials/
│   └── *.json               # Google 서비스 계정 키 (직접 배치, git에 커밋하지 않음)
├── config/
│   └── settings.py         # 환경변수 로드 및 상수
├── collectors/
│   ├── base_collector.py   # 수집기 공통 인터페이스
│   └── rss_collector.py    # RSS 수집 로직 (UA 지정, 재시도 포함)
├── sheets/
│   ├── client.py                    # Google Sheets 인증/연결 (다른 스프레드시트도 열 수 있음)
│   ├── sources_repository.py        # sources 시트 read
│   ├── contents_repository.py       # contents 시트 read/write, watermark 계산
│   ├── events_repository.py         # events, content_events 시트 read/write
│   ├── taxonomy_repository.py       # categories, topics, platforms 시트 read
│   ├── content_topics_repository.py # content_topics 시트 read/write (assigned_by로 분류 방식 구분)
│   ├── content_platforms_repository.py # content_platforms 시트 read/write
│   └── dashboard_repository.py      # 대시보드용 조인 (플랫폼·소스 등급·조치 등급)
├── processing/
│   ├── cleaner.py            # 텍스트 정제, 날짜/언어 처리
│   ├── deduplicator.py       # content_hash 생성 및 중복 판별
│   ├── similarity.py         # TF-IDF 코사인 유사도 (순수 Python, Event Clustering용)
│   ├── event_clusterer.py    # 콘텐츠를 이벤트로 묶는 클러스터링 로직
│   ├── classifier.py         # 룰(키워드) 기반 토픽 분류기
│   ├── platform_tagger.py    # 룰 기반 플랫폼 식별 (한글 조사 처리 포함)
│   ├── action_tier.py        # 조치 필요 / 알아둘 것 / 참고 3등급 판정
│   ├── llm_classifier.py     # Gemini 기반 토픽 분류기 (배치 처리, 재시도)
│   └── event_categorizer.py  # 콘텐츠 분류 결과로 이벤트 category_id를 다수결로 유도
├── models/
│   ├── content.py           # Content 데이터 모델
│   └── event.py             # Event 데이터 모델
├── utils/
│   └── logger.py             # 로깅 설정
├── .github/workflows/
│   └── collect.yml          # 매일 자동 수집 + 클러스터링 + 룰기반 분류 + 대시보드 생성/배포
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

## 주제/카테고리 분류

`categories`(7개) / `topics`(30개) 시트에 미리 정의해 둔 taxonomy를 기준으로, 콘텐츠(및 그 콘텐츠가 속한 이벤트)에 카테고리를 붙이는 단계입니다. 같은 콘텐츠를 **룰 기반**과 **LLM(Gemini)** 두 방식으로 각각 분류해 `content_topics` 시트의 `assigned_by` 컬럼으로 나란히 비교할 수 있게 설계했습니다.

```bash
python classify_content.py       # 룰(키워드) 기반, 무료·빠름
python classify_content_llm.py   # Gemini 기반, GEMINI_API_KEY 필요
python export_classification_review.py   # 두 결과를 별도 리뷰 시트로 내보내 정성평가
```

- 룰 기반: topic_name(영문)과 수작업으로 큐레이션한 한글 동의어를 단어 경계 매칭. 무료지만 재현율이 낮고(약 10~15%), 지나치게 일반적인 단어(예: "플랫폼")는 오탐 위험이 커서 의도적으로 키워드에서 제외했습니다.
- LLM 기반: 콘텐츠를 배치(기본 10개)로 묶어 한 번의 요청으로 분류. 재현율은 높지만(약 55~65%), Gemini 무료 티어의 **일일 요청 한도가 매우 낮아** 수백 건 단위 백로그 처리에는 여러 날에 걸쳐 나눠 돌려야 합니다. 이미 처리된 콘텐츠는 재실행 시 건너뜁니다.
- 이벤트의 `category_id`는 그 이벤트에 연결된 콘텐츠들이 받은 토픽의 카테고리를 다수결로 집계해 채웁니다 (`processing/event_categorizer.py`).

## 플랫폼 태깅

퍼포먼스 마케터가 아침에 던지는 질문은 "무슨 마케팅 뉴스가 있나"가 아니라 **"내가 운영하는 채널(Google Ads, Meta Ads, YouTube …)에 손대야 할 변경이 생겼나"** 입니다. 그래서 대시보드 첫 화면의 1차 축은 카테고리가 아니라 플랫폼이고, 플랫폼 태깅은 화면 기능이 아니라 데이터 요건입니다.

```bash
python seed_platforms.py       # 1회성: platforms 시트에 빠진 플랫폼 추가 (재실행 안전)
python classify_platforms.py   # 룰 기반 플랫폼 태깅 → content_platforms 시트
```

- `platforms` 시트의 활성 행을 읽어 `platform_name` + 큐레이션한 별칭(`processing/platform_tagger.py`)으로 매칭합니다. 플랫폼 목록을 코드에 하드코딩하지 않습니다.
- 별칭은 실제 기사 표기를 반영합니다. 예를 들어 Google Ads는 `adwords`, `performance max`, `merchant center`, `구글 애즈` 등으로 등장합니다.
- **한글 조사 처리**: 기존 토픽 분류기는 단어 경계(`\b`)만 쓰기 때문에 "유튜브가", "메타 광고의"처럼 조사가 붙으면 매칭되지 않습니다. 플랫폼 태거는 한글이 포함된 키워드에 한해 조사 한 개까지 붙는 것을 허용하되 앞뒤가 한글/영숫자면 매칭하지 않습니다. 덕분에 "유튜브가"는 잡고 "메타버스"는 잡지 않습니다. 형태소 분석기 없이 얻을 수 있는 절충안입니다.
- 회사명 단독(`naver`, `카카오`)은 광고 플랫폼과 무관한 기업 뉴스를 끌어오는 오탐이 실제로 확인되어 별칭에서 제외했고, 광고 제품명(`카카오모먼트`, `네이버 검색광고`) 단위로만 매칭합니다.
- 현재 코퍼스 기준 전체 콘텐츠의 약 16%에 플랫폼이 붙습니다(747건 중 123건, 할당 148개). 나머지는 대부분 업계 동향·AI 리서치로, 특정 광고 채널과 무관한 글입니다.
- **이미 태깅된 콘텐츠는 재실행해도 다시 태깅되지 않습니다.** `assigned_by='rule_based'`로 처리된 `content_id`는 건너뛰기 때문에, 별칭을 추가해도 과거 콘텐츠에는 소급 적용되지 않습니다. 전체를 다시 태깅하려면 `content_platforms` 시트에서 해당 행을 지우고 실행해야 합니다.

### 채널 상위-하위 관계 (rollup)

`generate_dashboard.py`의 `PLATFORM_ROLLUP`은 한 채널이 함께 집계할 하위 플랫폼을 정의합니다. YouTube Ads를 운영하는 사람에게 YouTube 자체의 변경은 남의 일이 아니기 때문입니다.

| 채널 | 함께 보는 플랫폼 |
|---|---|
| YouTube Ads | YouTube |
| Meta Ads | Instagram, Facebook |
| Google Search | Google AI Overview, Google AI Mode |

이 관계가 없으면 실제로 놓치는 사례가 있었습니다. "Google announces October changes to Display & Video 360 API"는 본문이 "YouTube responsive ads"라고 써서 `YouTube`로만 태깅됐는데, 기본 채널에 `YouTube`가 없어 첫 화면에서 보이지 않았습니다. 태거 별칭을 고치는 방법도 있지만 위에 적은 대로 기존 데이터에 소급되지 않는 반면, 이 관계는 대시보드를 만들 때마다 적용되므로 즉시 반영됩니다.

## 조치 등급 (action tier)

모든 소식이 같은 무게로 놓이면 매일 전부 읽어야 하고, 그러면 며칠 안에 안 읽게 됩니다. `processing/action_tier.py`가 이벤트를 3등급으로 나눕니다.

| 등급 | 기준 | 첫 화면 처리 |
|---|---|---|
| **조치 필요** | 기존 캠페인·계정 설정이 영향받음. 지원 종료, 기능 제거, 강제 마이그레이션, 신규 광고주 요건 | 펼친 카드 (최대 3건) |
| **알아둘 것** | 신규 기능·베타·출시. 지금 손댈 필요는 없지만 다음 캠페인 설계에 영향 | 한 줄 목록 |
| **참고** | 업계 동향, 리서치, 브랜드 사례 | 첫 화면에서 제외, 건수만 표시 |

- **플랫폼이 하나도 안 붙은 이벤트는 무조건 참고입니다.** 어떤 채널 얘기인지 모르면 조치할 대상 자체가 없습니다. 이 규칙 하나가 첫 화면을 리서치·업계 동향으로 채우지 않는 가장 큰 장치입니다.
- 강한 신호(지원 종료, 기능 제거 등)는 소스와 무관하게 조치 필요로, 약한 신호(정책 변경, 기본값 변경 등)는 **공식 소스**(`sources.tier=Official`)일 때만 조치 필요로 올립니다. 공식 발표라는 사실이 곧 "확정된 변경"이라는 뜻이기 때문입니다.
- 요약/정리 글(`recap`, `roundup`, 주간 정리)은 개별 이벤트가 아니라 묶음이므로 참고로 내립니다. 첫 화면의 건수를 믿을 수 있게 하기 위함입니다.
- 등급은 `events` 시트에 저장하지 않고 대시보드를 만들 때마다 다시 계산합니다. 사람이 손으로 고치는 값이 아니라 (소스 등급 + 플랫폼 + 본문)에서 순수하게 유도되는 값이라, 저장해 두면 룰을 고칠 때마다 전체를 백필해야 합니다.
- 현재 코퍼스(368개 분류 이벤트) 기준 분포는 참고 331 / 알아둘 것 36 / 조치 필요 1 입니다. **대부분의 아침에 조치할 것이 없는 게 정상이고, 그게 이 화면이 파는 가치입니다.**

## Signal Desk 대시보드

분류가 확정된 이벤트만 모아 보여주는 정적 HTML 대시보드입니다. **오늘 / 업데이트 캘린더 / 전체 피드 / 카테고리별** 4개 뷰를 제공하며, 기본 화면은 "오늘"입니다.

"오늘" 화면은 읽을 피드가 아니라 **닫을 수 있는 체크리스트**로 설계했습니다. 1440×900 화면에서 스크롤 없이 다음이 모두 끝납니다.

1. **판정 한 줄** — "조치가 필요한 변경 N건" 또는 "오늘 확인할 주요 변경사항이 없습니다."
2. **내 채널 상태 행** — 채널별 건수. 타일을 누르면 그 채널만 필터링
3. **조치 필요 카드** + **알아둘 것 한 줄 목록**
4. **오늘 확인 완료** 버튼

- 기본 채널은 Google Ads · Meta Ads · YouTube Ads · Display & Video 360 · Google Search · Google Analytics 4 6개이며, 1440×900에서 한 줄에 들어갑니다.
- **NEW 판정**은 이벤트가 마지막으로 보도된 시점이 아니라 **처음 발견된 시점(`first_seen_at`)** 기준입니다. "확인 완료"를 누르면 그 시각이 브라우저(`localStorage`)에 저장되고, 다음 방문에는 그 이후 들어온 것만 보입니다. 한 번도 확인하지 않았다면 최근 24시간치를 보여줍니다.
- **공식 소스 표시**: `sources.tier=Official`인 매체는 카드에 "공식" 배지가 붙고 대표 링크로 맨 앞에 옵니다. 실무자는 플랫폼 공식 공지면 바로 움직이고 매체 보도면 한 번 더 확인하기 때문입니다.
- **갱신 지연 표시**: 상단에 대시보드 **생성 시각**을 보여주고, 20시간이 넘으면 "갱신 지연"을 붙입니다. 처음에는 가장 최근 기사의 시각으로 쟀는데, 2026-09-19 대시보드 생성이 실패한 날 화면이 어제 데이터인데도 경고가 뜨지 않았습니다 — 기사 시각은 파이프라인이 멈춰도 최근일 수 있기 때문입니다. 정상인 날 오전 9시에 보는 화면은 길어야 4시간 전 것이고 실패한 날은 24시간을 넘으므로 20시간에서 가릅니다. 좁은 화면에서는 평소 이 표시를 숨기지만 경고일 때는 보입니다. 하루 1회 수집 구조라 화면이 **실시간이 아니라는 점**은 푸터에 명시했습니다.
- 시각 비교는 문자열이 아니라 `Date.parse()` 값으로 합니다. 파이프라인이 쓰는 `first_seen_at`은 `+00:00` 형식이고 "확인 완료"가 저장하는 값은 `toISOString()`의 `Z` 형식이라, 문자열로 비교하면 같은 시각에서 판정이 뒤집힙니다.
- 조치 필요 카드는 **최대 2장**만 펼칩니다. 카드 실측 높이가 172px이라 3장이면 첫 화면(1440×900)을 넘깁니다. 나머지는 한 줄 목록으로 내려갑니다.
- 카테고리 컬러는 첫 화면에서 빼고 "전체 피드"·"카테고리별" 탭에서만 씁니다.

### 업데이트 캘린더

"오늘" 바로 다음에 오는 두 번째 뷰입니다. 이전 이름은 "아카이브"였는데, 지나간 것이라는 뉘앙스라 매일 보는 화면과 맞지 않아 바꿨습니다.

- 날짜를 고르면 **그날 수집·분류된 소식 전체**를 시간순으로 봅니다. "오늘" 화면이 내 채널에 조치할 것만 추린다면, 여기서는 조치 등급이나 채널과 관계없이 그날 들어온 것이 모두 보입니다. 놓친 날을 되짚거나 특정 시점에 무슨 일이 있었는지 확인하는 용도입니다.
- 달력의 각 날짜에는 `00건` 형식으로 **그날 분류가 끝난 소식의 건수**를 표시합니다. 숫자만 있으면 무엇을 세는 값인지 알 수 없어 단위를 붙였고, 두 자리로 자릿수를 맞춰 세로로 비교됩니다. 건수가 있는 날만 선택할 수 있습니다.
- 선택한 날짜 아래에는 그날의 등급별 구성(예: "참고 3건")과 시간의 의미를 한 줄로 설명합니다. 표시되는 시각은 그 이벤트가 **마지막으로 보도된 시각**입니다. 첫 화면에서 강한 컬러는 "조치 필요" 하나뿐이고, 민트색은 "확인 완료 / 변경 없음" 성공 상태 전용입니다.

```bash
python generate_dashboard.py
```

`templates/dashboard_template.html`을 읽어 실제 데이터(JSON)를 주입한 뒤 `docs/index.html`로 저장합니다. GitHub Actions가 매일 이 스크립트를 실행하고 결과를 커밋하므로, GitHub Pages를 `docs/` 폴더로 연결해두면 항상 최신 상태의 페이지가 유지됩니다.

**GitHub Pages 최초 설정 (1회, 수동)**:
1. 저장소 "Settings → Pages"로 이동
2. "Build and deployment → Source"를 **Deploy from a branch**로 설정
3. Branch를 **main**, 폴더를 **/docs**로 선택 후 저장
4. 잠시 후 `https://<사용자명>.github.io/<저장소명>/`에서 접속 가능

## 자동 실행 (GitHub Actions)

`.github/workflows/collect.yml`이 매일 **KST 05:17(UTC 20:17)** 에 다음 순서로 자동 실행합니다:

1. `main.py` — RSS 수집
2. `cluster_events.py` — Event Clustering
3. `classify_content.py` — 룰 기반 주제 분류
4. `classify_platforms.py` — 룰 기반 플랫폼 태깅
5. `generate_dashboard.py` — 대시보드 생성
6. `docs/index.html` 변경분을 커밋 후 push (GitHub Pages 자동 반영)

주 사용자가 출근해 화면을 보는 시각이 오전 9시라, 그 전에 갱신이 끝나 있어야 합니다. 처음 KST 09:00에서 06:00으로 당겼는데, 실제로는 **07:58~08:40에야 시작**했습니다. 실행 자체는 1~2분이고 나머지 2시간 남짓은 GitHub 예약 실행의 대기열 지연입니다 — 예약 실행은 정각에 몰려 크게 밀립니다. 9월 15일은 08:40에 끝나 여유가 20분뿐이었습니다. 그래서 붐비지 않는 17분으로 옮기고 한 시간 더 당겨(05:17), 같은 수준으로 밀려도 8시 전에 끝나게 했습니다.

Google Sheets API 호출은 `sheets/client.py`에서 gspread의 `BackOffHTTPClient`로 합니다. 요청 한도 초과(429)·타임아웃(408)·서버 오류(5xx)가 나면 2→4→8…초로 기다렸다 다시 요청합니다. 2026-09-19 실행에서 수집·분류·태깅은 모두 성공했는데 대시보드 생성만 실패했고 같은 데이터로 로컬에서는 성공했습니다. 대시보드 생성은 시트를 연달아 11번 통째로 읽는데, 앞 단계들이 API를 많이 쓴 직후라 분당 한도에 걸린 것으로 봅니다. 재시도가 없으면 이런 일시적 오류 하나로 하루치 화면이 갱신되지 않습니다.

`seed_platforms.py`는 자동화에 넣지 않았습니다. taxonomy를 바꾸는 1회성 작업이라 매일 돌릴 이유가 없습니다.

LLM(Gemini) 기반 분류(`classify_content_llm.py`)는 자동화에 포함하지 않았습니다. 무료 티어 일일 요청 한도가 낮아 매일 자동 실행 시 금방 소진되고, 룰 기반과 결과를 비교/검증하는 동안은 수동으로 실행하는 편이 낫다고 판단했습니다. 필요해지면 `GEMINI_API_KEY`를 GitHub Secrets에 등록하고 워크플로우에 단계를 추가하면 됩니다.

설정 방법:

1. 이 프로젝트를 GitHub 저장소로 푸시합니다. (**`credentials/` 폴더와 `.env`는 `.gitignore`에 의해 절대 커밋되지 않습니다.**)
2. 저장소의 "Settings → Secrets and variables → Actions"에서 다음 두 개의 Repository secret을 등록합니다.
   - `GOOGLE_APPLICATION_CREDENTIALS_JSON`: 서비스 계정 JSON 키 파일의 **전체 내용**을 그대로 붙여넣습니다.
   - `GOOGLE_SHEETS_ID`: 대상 스프레드시트 ID.
3. "Actions" 탭에서 "Daily Marketing Intelligence Pipeline" 워크플로우를 확인합니다. `workflow_dispatch`가 설정되어 있어 수동으로도 즉시 실행해볼 수 있습니다.
4. 위 "GitHub Pages 최초 설정"도 함께 진행합니다.

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

### 분류 & 대시보드
1. [x] 7개 카테고리 / 30개 토픽 taxonomy 구축
2. [x] 룰 기반 분류기 (키워드 매칭, 단어 경계 검사)
3. [x] LLM(Gemini) 분류기 (배치 처리, 재시도, 방식별 독립 추적)
4. [x] 분류 결과 정성평가용 별도 리뷰 시트
5. [x] 이벤트 category_id 다수결 유도
6. [x] Signal Desk 정적 대시보드 생성 + GitHub Pages 자동 배포
7. [x] 룰 기반 분류를 GitHub Actions 자동화에 연동
8. [x] 플랫폼 태깅 (한글 조사 처리 포함) + content_platforms 저장
9. [x] 조치 등급 3단계 판정 (소스 등급 + 플랫폼 + 본문 키워드)
10. [x] "오늘" 첫 화면 — 채널 상태 행, 조치 등급별 분리, 확인 완료 상태
11. [x] 본문 회색 대비 WCAG AA 충족 (#8f8f8f → #6b6b6b)
12. [x] 채널 상위-하위 관계(rollup)로 하위 플랫폼 변경까지 집계
13. [x] 첫 화면 실측 507px / 1440×900 (여유 393px)
14. [x] 업데이트 캘린더 — "오늘" 다음으로 배치, 건수 단위 표기, 뷰 설명 추가

### 보류
- Trend Score, AI Insight
- LLM 분류의 GitHub Actions 자동화 (무료 티어 한도 문제로 수동 실행 유지 중)
- 시행일(effective_date) 추출 — 조치 필요 항목에서 실무자가 가장 먼저 보는 값이지만 현재 데이터에 없습니다
- 내 채널 선택 설정 UI — 현재는 기본 채널 5개가 고정이고, 상태 타일 클릭으로 필터링만 가능합니다
- 팀 공유 확인 상태 — 현재 "확인 완료"는 브라우저별로만 저장됩니다

## 알려진 제약 사항

- 일부 소스(예: Cloudflare 봇 챌린지가 걸린 사이트)는 RSS를 프로그래밍적으로 가져올 수 없습니다. 이런 소스는 `rss_url`을 비워두면 자동으로 스킵되며, 향후 `crawl_type=CRAWL` 방식의 별도 크롤러로 전환이 필요합니다.
- **이 서비스는 실시간이 아닙니다.** RSS 수집이 하루 1회(KST 05:17 예약)만 돌기 때문에, 화면이 약속할 수 있는 것은 "매일 아침 갱신 · 최근 24시간"까지입니다. 실시간에 가깝게 하려면 공식 소스(Google/Meta 공식 블로그 등)만 3~6시간 간격 cron을 추가로 돌리는 편이 정확합니다. 있지도 않은 실시간성을 문구로 약속하면, 사용자가 이 화면을 믿고 확인을 끝내는 순간 제품이 거짓말을 하게 됩니다.
- 조치 등급은 키워드 룰이므로 완벽하지 않습니다. 새로운 표현이 등장하면 `processing/action_tier.py`의 신호 목록을 보강해야 합니다. 실제로 "DV360 changes remove targeting exclusions and add new business identity requirements" 같은 표현이 초기 룰에서 누락되어 보강했습니다.
- Google Sheets 파일을 브라우저에서 열어놓은 상태로 스크립트를 실행하면, 실시간 편집(우발적인 셀 입력, 되돌리기 등)이 API가 쓴 데이터와 충돌할 수 있습니다. 수집 스크립트를 실행할 때는 시트 탭을 닫아두는 것을 권장합니다.
