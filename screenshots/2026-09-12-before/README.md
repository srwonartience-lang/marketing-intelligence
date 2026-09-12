# Signal Desk — 개선 전 스냅샷 (2026-09-12)

`docs/index.html` 을 수정하기 전 상태의 기록.

| 파일 | 내용 |
|---|---|
| `01-feed.png` | 전체 피드 탭 (368건, 상단 영역) |
| `02-category.png` | 카테고리별 탭 (전체 선택 상태) |
| `03-timeline.png` | 타임라인 탭 (2026년 9월 / 9월 11일 선택) |
| `index-before.html` | 그 시점의 원본 파일 전체 (데이터 포함, 그대로 열면 재현됨) |
| `_snapshot_tool.py` | 아래 캡처 절차에 쓴 스크립트 |

## 캡처 방법 / 한계
이 머신에 Chrome·node 가 없어 헤드리스 캡처가 불가능했고, macOS Quick Look 은 JS 를
실행하지 않아 빈 화면만 나왔다. 그래서 `_snapshot_tool.py` 로 `index.html` 의
`CLASSIFIED_EVENTS` 를 읽어 JS 가 만들어내는 마크업과 동일한 정적 HTML 을 탭별로 생성한 뒤
`qlmanage -t -s 1600` 으로 렌더링했다.

- 레이아웃·색·간격·데이터는 실제 페이지와 동일하다.
- 웹폰트(Inter / JetBrains Mono)는 Quick Look 이 네트워크를 쓰지 않아 시스템 폰트로
  대체 렌더링됐다. 자간·크기는 CSS 값 그대로다.
- 각 이미지는 페이지 상단 1600px 영역이다(피드 전체 높이는 82,593px).
