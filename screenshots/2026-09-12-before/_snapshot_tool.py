# -*- coding: utf-8 -*-
"""docs/index.html 의 JS 렌더 결과를 그대로 정적 HTML로 구워낸다 (JS 없이 캡처하기 위함)."""
import re, json, datetime, os, sys

SRC = "/Users/serin/Documents/Project/Marketing Intelligence/docs/index.html"
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
src = open(SRC, encoding="utf-8").read()

EVENTS = json.loads(re.search(r'const CLASSIFIED_EVENTS\s*=\s*(\[.*?\]);\n', src, re.S).group(1))
GENERATED_AT = re.search(r'const GENERATED_AT = "([^"]+)"', src).group(1)
HEAD = src[:src.index("</head>")+7]          # style 포함 헤드 그대로 재사용

CATEGORY_ORDER = ["SEO / GEO","AI Trends","Data & AI Research","Marketing Industry",
                  "Performance Marketing","Commerce & Retail","Brand Marketing"]
CATEGORY_KEY = {"SEO / GEO":"geo","AI Trends":"ai","Data & AI Research":"research",
                "Marketing Industry":"industry","Performance Marketing":"perf",
                "Commerce & Retail":"commerce","Brand Marketing":"brand"}
DOW = ['일','월','화','수','목','금','토']

def fmt(d):                                   # 원본 JS와 동일 (연도 없음)
    dt = datetime.date(*map(int, d.split('-')))
    return f"{dt.month}월 {dt.day}일 ({DOW[(dt.weekday()+1)%7]})"

def purl(ev): return ev["sources"][0]["url"] if ev["sources"] else "#"
def spills(ev): return "".join(f'<a class="badge caption" href="{s["url"]}">{s["name"]}</a>' for s in ev["sources"])
def clabel(ev): return f'{len(ev["sources"])}개 매체 보도' if len(ev["sources"]) > 1 else "단일 매체"
def chip(ev): return f'<span class="badge chip mono-eyebrow chip-{CATEGORY_KEY[ev["category"]]}">{ev["category"]}</span>'
def key(ev): return ev["date"] + ev["time"]

def card(ev, compact):
    if compact:
        return (f'<a class="mini-card" href="{purl(ev)}"><div class="row-top">{chip(ev)}</div>'
                f'<h4>{ev["title"]}</h4><div class="mini-meta">'
                f'<span class="mono-caption">{ev["sources"][0]["name"]}</span>'
                f'<span class="mono-caption">{fmt(ev["date"])}</span></div></a>')
    multi = len(ev["sources"]) > 1
    return (f'<div class="article-card"><div class="row-top">{chip(ev)}'
            f'<span class="mono-caption">{fmt(ev["date"])} · {ev["time"]}</span></div>'
            f'<h3 class="disp-md"><a href="{purl(ev)}">{ev["title"]}</a></h3>'
            f'<p class="body-md">{ev["summary"]}</p><div class="row-meta">'
            f'<div class="sources">{spills(ev)}</div>'
            f'<span class="badge {"badge-mint mono-caption" if multi else "mono-caption"}">{clabel(ev)}</span>'
            f'</div></div>')

srt = sorted(EVENTS, key=key, reverse=True)
latest = srt[0]["date"]
n_cat = len({e["category"] for e in EVENTS})
n_src = len({s["name"] for e in EVENTS for s in e["sources"]})

# --- feed
feed = "".join(card(e, False) for e in srt)

# --- category (전체 선택 상태)
bycat = {}
for e in EVENTS: bycat.setdefault(e["category"], []).append(e)
pills = [f'<button class="cat-pill mono-btn all active all" data-cat="all">전체 '
         f'<span class="mono-caption" style="color:inherit">{len(EVENTS)}</span></button>']
for c in [c for c in CATEGORY_ORDER if c in bycat]:
    pills.append(f'<button class="cat-pill mono-btn {CATEGORY_KEY[c]}" data-cat="{c}">'
                 f'<span class="dot"></span>{c} <span class="mono-caption" style="color:inherit">{len(bycat[c])}</span></button>')
cat_grid = "".join(card(e, True) for e in srt)

# --- timeline (최신 달 / 최신 날짜 선택)
by_date = {}
for e in EVENTS: by_date.setdefault(e["date"], []).append(e)
vy, vm = int(latest[:4]), int(latest[5:7])       # 1-based month
cal = "".join(f'<div class="cal-dow mono-caption">{d}</div>' for d in DOW)
first_dow = (datetime.date(vy, vm, 1).weekday() + 1) % 7
days_in = (datetime.date(vy + (vm == 12), (vm % 12) + 1, 1) - datetime.timedelta(days=1)).day
cal += '<div class="cal-day empty"></div>' * first_dow
for d in range(1, days_in + 1):
    ds = f"{vy}-{vm:02d}-{d:02d}"
    items = by_date.get(ds)
    cls = "cal-day body-md" + (" has-events" if items else "") + (" selected" if ds == latest else "")
    cnt = '<span class="cnt">%d</span>' % len(items) if items else ''
    cal += '<div class="%s">%d%s</div>' % (cls, d, cnt)

tl = ""
for ev in sorted(by_date[latest], key=lambda e: e["time"]):
    multi = len(ev["sources"]) > 1
    tl += (f'<div class="tl-item"><span class="tl-time mono-caption">{ev["time"]}</span>'
           f'<div class="tl-card">{chip(ev)}<h4><a href="{purl(ev)}">{ev["title"]}</a></h4>'
           f'<p class="body-md">{ev["summary"]}</p><div class="row-meta">'
           f'<div class="sources">{spills(ev)}</div>'
           f'<span class="badge {"badge-mint mono-caption" if multi else "mono-caption"}">{clabel(ev)}</span>'
           f'</div></div></div>')

def tabbar(active):
    out = '<div class="tabbar" role="tablist">'
    for t, label in [("feed","전체 피드"),("category","카테고리별"),("timeline","타임라인")]:
        out += f'<button class="mono-btn{" active" if t==active else ""}">{label}</button>'
    return out + "</div>"

SHELL = """{head}
<body>
<div class="hero"><div class="hero-inner"><div>
  <span class="eyebrow mono-eyebrow">Marketing Intelligence · Daily Brief</span>
  <h1 class="disp-xl">Signal Desk</h1>
  <span class="date body-md">최근 업데이트 — {latest} 수집분 기준</span>
</div><div class="ribbon" aria-hidden="true">
  <i style="height:60%"></i><i style="height:100%"></i><i style="height:40%"></i><i style="height:80%"></i>
  <i style="height:55%"></i><i style="height:95%"></i><i style="height:35%"></i><i style="height:70%"></i>
</div></div></div>
<div class="wrap">
  <div class="stats-row">
    <div class="stat-tile"><span class="n">{n_ev}</span><span class="l mono-eyebrow">분류된 이벤트</span></div>
    <div class="stat-tile"><span class="n">{n_cat}</span><span class="l mono-eyebrow">카테고리</span></div>
    <div class="stat-tile"><span class="n">{n_src}</span><span class="l mono-eyebrow">매체 수</span></div>
  </div>
  <p class="note"><span class="caption">Google Sheets DB에서 카테고리 분류가 확정된 이벤트만 표시합니다. 매일 자동으로 수집·분류되어 이 페이지도 함께 갱신됩니다. 제목을 클릭하면 원문으로 연결됩니다.</span></p>
  {tabbar}
  <div class="content">{body}</div>
</div>
<footer class="site-footer"><span class="caption">Marketing Intelligence · {gen} 생성</span></footer>
</body></html>"""

views = {
 "01-feed": (tabbar("feed"), f'<div id="feed-view" class="view active"><div class="list">{feed}</div></div>'),
 "02-category": (tabbar("category"),
    f'<div id="category-view" class="view active"><div class="cat-filter">{"".join(pills)}</div>'
    f'<p class="cat-count-label caption">전체 · {len(EVENTS)}개 이벤트</p>'
    f'<div class="cat-grid">{cat_grid}</div></div>'),
 "03-timeline": (tabbar("timeline"),
    f'<div id="timeline-view" class="view active" style="display:grid;grid-template-columns:320px 1fr;gap:28px;align-items:start">'
    f'<div class="cal"><div class="cal-head"><span class="disp-md">{vy}년 {vm}월</span>'
    f'<div class="cal-nav"><button>‹</button><button disabled>›</button></div></div>'
    f'<div class="cal-grid">{cal}</div><div class="cal-legend">'
    f'<span class="cal-day selected" style="width:20px;height:20px;font-size:10px;flex:none;display:inline-flex;">·</span>'
    f'<span class="caption">선택된 날짜 · 숫자는 그날 분류된 이벤트 수</span></div></div>'
    f'<div><div class="tl-head"><span class="disp-md">{fmt(latest)}</span>'
    f'<span class="mono-caption count">{len(by_date[latest])}건</span></div>'
    f'<div class="tl">{tl}</div></div></div>'),
}
for name, (tb, body) in views.items():
    html = SHELL.format(head=HEAD, latest=fmt(latest), n_ev=len(EVENTS), n_cat=n_cat, n_src=n_src,
                        tabbar=tb, body=body, gen=GENERATED_AT)
    open(os.path.join(OUT, name + ".html"), "w", encoding="utf-8").write(html)
    print("wrote", name + ".html", len(html))
