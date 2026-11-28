"""주간 성적표: Instagram·Threads 게시물별 반응을 모아 시리즈별로 점수를 매긴다. (읽기만 함, 게시 안 함)

- Instagram: 좋아요·댓글(공개 값) + 가능하면 도달·저장·공유(인사이트 권한이 토큰에 있을 때)
- Threads: 조회·좋아요·답글·리포스트(threads_manage_insights 권한이 있을 때. 없으면 게시 수만)
- 시리즈 구분은 캡션으로: 날씨·책·좋은 뉴스·아기 동물·파생·주말 여행·동물 상식·넷플릭스.
  레드덴바 태그가 없는 글(ChatGPT가 올리는 MarketBrief 시황)은 '마켓브리프(참고)'로 따로 모아 비교만 한다.
- 결과: reports/latest.md (최신), reports/YYYY-MM-DD.md (보관), reports/history.json (팔로워 추이)

  python report.py                 # 지난주(월~일) 성적표
  python report.py --mock          # 가짜 데이터로 형식만 확인 (네트워크 없음)
"""
import argparse, datetime as dt, json, os, re, statistics, sys
from zoneinfo import ZoneInfo
import requests

FB = "https://graph.facebook.com/v21.0"
IG = "https://graph.instagram.com/v21.0"
TH = "https://graph.threads.net/v1.0"
IG_IDS = {"kr": "17841415970047103", "us": "17841468623391374"}
TZ = {"kr": "Asia/Seoul", "us": "America/Los_Angeles"}
FLAG = {"kr": "🇰🇷 @reddenva.kr", "us": "🇺🇸 @reddenva.us"}
START = dt.date(2026, 11, 1)  # 이보다 오래된 글은 안 봄

# (키, 이름, 요일) — 요일은 표 순서용
SERIES = [
    ("weather", "☀️ 오늘의 날씨", "매일"),
    ("books", "📚 이번 주 책", "월"),
    ("news", "📰 좋은 뉴스", "화"),
    ("animal", "🐾 아기 동물", "수"),
    ("deriv", "📊 파생 브리핑", "목"),
    ("trip", "📍 주말 여행", "금"),
    ("facts", "🦦 동물 상식", "토"),
    ("netflix", "🍿 넷플릭스", "일"),
    ("marketbrief", "📈 마켓브리프(참고)", "-"),
]
NAME = {k: n for k, n, _ in SERIES}


def classify(caption, ts_local):
    """레드덴바 시리즈 캡션 모양에 맞으면 그 시리즈, 아니면 마켓브리프(ChatGPT 시황. 레드덴바 태그를 달기도 해서 태그로는 못 가름)"""
    c = (caption or "").strip()
    rules = [
        ("books", r"^📚"), ("news", r"^📰"), ("animal", r"^🐾"), ("trip", r"^📍"), ("facts", r"^🦦"), ("netflix", r"^🍿"),
        ("deriv", r"^(📊 )?(목요일 파생 브리핑|Thursday Derivatives Briefing)"),
        ("weather", r"^(서울 \d+/\d+.*최고.*최저|Los Angeles .*high .*low)"),
    ]
    for key, pat in rules:
        if re.search(pat, c, re.I):
            return key
    return "marketbrief"


# ---------------------------------------------------------------- 수집
def _get(url, token, **params):
    r = requests.get(url, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if not r.ok:
        raise RuntimeError(f"{r.status_code} {r.text[:200]}")
    return r.json()


def _paged(url, token, **params):
    out = []
    while url and len(out) < 300:
        d = _get(url, token, **params); params = {}
        out += d.get("data", [])
        last = out[-1]["timestamp"][:10] if out else "9999"
        if last < START.isoformat():
            break
        url = d.get("paging", {}).get("next")
    return out


def fetch_ig(region, token, notes):
    B = FB if token.startswith("EAA") else IG
    uid = IG_IDS[region]
    acct = {}
    try:
        acct = _get(f"{B}/{uid}", token, fields="username,followers_count,media_count")
    except Exception as e:
        notes.append(f"Instagram 계정 정보 못 읽음: {e}")
    media = _paged(f"{B}/{uid}/media", token, fields="id,caption,timestamp,media_type,permalink,like_count,comments_count", limit=50)
    metric_sets = ["reach,saved,shares,total_interactions", "reach,saved", "reach"]
    ok_set = None
    for m in media:
        if m["timestamp"][:10] < START.isoformat():
            continue
        for ms in ([ok_set] if ok_set else metric_sets):
            try:
                d = _get(f"{B}/{m['id']}/insights", token, metric=ms)
                for it in d.get("data", []):
                    m[it["name"]] = (it.get("values") or [{}])[0].get("value", it.get("total_value", {}).get("value"))
                ok_set = ms
                break
            except Exception as e:
                last_err = str(e)
        if ok_set is None:
            notes.append("Instagram 도달·저장 수는 못 읽음: 시스템 사용자 토큰에 instagram_manage_insights 권한이 없어요. 권한을 추가해 토큰을 다시 만들면 다음 리포트부터 자동으로 들어가요.")
            break
    return acct, media


def fetch_threads(token, notes):
    me = _get(f"{TH}/me", token, fields="id,username")
    acct = {"username": me.get("username")}
    try:
        d = _get(f"{TH}/{me['id']}/threads_insights", token, metric="followers_count")
        for it in d.get("data", []):
            acct["followers_count"] = it.get("total_value", {}).get("value")
    except Exception as e:
        notes.append(f"Threads 팔로워 수 못 읽음: {str(e)[:120]}")
    posts = _paged(f"{TH}/me/threads", token, fields="id,text,timestamp,permalink,media_type,is_quote_post", limit=50)
    for p in posts:
        p["caption"] = p.pop("text", "")
        if p["timestamp"][:10] < START.isoformat():
            continue
        try:
            d = _get(f"{TH}/{p['id']}/insights", token, metric="views,likes,replies,reposts,quotes,shares")
            for it in d.get("data", []):
                p[it["name"]] = (it.get("values") or [{}])[0].get("value", it.get("total_value", {}).get("value"))
        except Exception as e:
            notes.append(f"Threads 게시물 반응은 못 읽음(토큰에 threads_manage_insights 권한 필요): {str(e)[:120]}")
            break
    return acct, posts


# ---------------------------------------------------------------- 계산
def norm(items, region, kind):
    """게시물 → 공통 모양 {series, date, local, link, likes, comments, reach, eng, text}"""
    tz = ZoneInfo(TZ[region]); rows = []
    for m in items:
        t = dt.datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z").astimezone(tz)
        if t.date() < START:
            continue
        if kind == "ig":
            likes, com = m.get("like_count"), m.get("comments_count")
            reach = m.get("reach")
            eng = m.get("total_interactions")
            if eng is None and likes is not None:
                eng = (likes or 0) + (com or 0) + (m.get("saved") or 0) + (m.get("shares") or 0)
            extra = {"saved": m.get("saved"), "shares": m.get("shares")}
        else:
            likes, com, reach = m.get("likes"), m.get("replies"), m.get("views")
            eng = None if likes is None else sum((m.get(k) or 0) for k in ("likes", "replies", "reposts", "quotes", "shares"))
            extra = {"reposts": m.get("reposts")}
        rows.append(dict(series=classify(m.get("caption"), t), date=t.date().isoformat(), local=f"{t:%m/%d}({'월화수목금토일'[t.weekday()]}) {t:%H:%M}",
                         link=m.get("permalink", ""), likes=likes, comments=com, reach=reach, eng=eng,
                         text=(m.get("caption") or "").split("\n")[0][:60], **extra))
    return rows


def avg(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def f(x, d=1):
    if x is None:
        return "–"
    return f"{x:,.{d}f}" if isinstance(x, float) and x != int(x) else f"{int(round(x)):,}"


def pct(x):
    return "–" if x is None else f"{x*100:.1f}%"


def table(rows, week, prev, reach_label):
    """시리즈별 성적표. week/prev = (시작, 끝) 날짜 문자열"""
    inw = lambda r, w: w[0] <= r["date"] <= w[1]
    has_reach = any(r["reach"] is not None for r in rows)
    head = f"| 시리즈 | 이번 주 글 | 평균 반응 | 평균 좋아요 | 평균 댓글 |" + (f" 평균 {reach_label} | 반응률 |" if has_reach else "") + " 지난주 대비 | 누적 글 | 누적 평균 반응 |"
    out = [head, "|" + "---|" * (head.count("|") - 1)]
    for key, name, day in SERIES:
        allr = [r for r in rows if r["series"] == key]
        if not allr:
            continue
        w = [r for r in allr if inw(r, week)]; p = [r for r in allr if inw(r, prev)]
        we, pe = avg([r["eng"] for r in w]), avg([r["eng"] for r in p])
        chg = "–" if not (we is not None and pe) else (f"{(we/pe-1)*100:+.0f}%")
        cells = [f"{name}", str(len(w)), f(we), f(avg([r['likes'] for r in w])), f(avg([r['comments'] for r in w]))]
        if has_reach:
            rr = avg([r["reach"] for r in w])
            er = avg([r["eng"] / r["reach"] for r in w if r["reach"] and r["eng"] is not None])
            cells += [f(rr), pct(er)]
        cells += [chg, str(len(allr)), f(avg([r['eng'] for r in allr]))]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def best_worst(rows, week, reach_label="도달"):
    w = [r for r in rows if week[0] <= r["date"] <= week[1] and r["eng"] is not None and r["series"] != "marketbrief"]
    if not w:
        return ""
    w.sort(key=lambda r: r["eng"], reverse=True)
    line = lambda r: f"- {NAME[r['series']]} · {r['local']} · 반응 {f(r['eng'])}" + (f" / {reach_label} {f(r['reach'])}" if r["reach"] is not None else "") + f" · [{r['text']}]({r['link']})"
    out = ["**이번 주 베스트 3**"] + [line(r) for r in w[:3]]
    if len(w) > 3:
        out += ["", "**이번 주 아쉬운 글**", line(w[-1])]
    return "\n".join(out)


def verdict(rows, week, reach_label):
    """증권사 리포트처럼 한 줄 의견. 도달/조회 값이 있으면 그걸로(초기엔 좋아요가 0~1개라 변별력이 없음), 없으면 반응으로 순위."""
    w = [r for r in rows if week[0] <= r["date"] <= week[1] and r["series"] != "marketbrief"]
    use = "reach" if any(r["reach"] is not None for r in w) else "eng"
    lab = f"평균 {reach_label}" if use == "reach" else "평균 반응"
    by = {}
    for r in w:
        if r[use] is not None:
            by.setdefault(r["series"], []).append(r[use])
    if len(by) < 2:
        return ""
    sc = sorted(((statistics.mean(v), k) for k, v in by.items()), reverse=True)
    rd = statistics.mean([x for v in by.values() for x in v])
    mb = [r[use] for r in rows if week[0] <= r["date"] <= week[1] and r["series"] == "marketbrief" and r[use] is not None]
    s = f"> **투자의견** ({lab} 기준) · 비중 확대: {NAME[sc[0][1]]} ({f(sc[0][0])}) · 비중 축소 검토: {NAME[sc[-1][1]]} ({f(sc[-1][0])})"
    s += f"\n> 레드덴바 시리즈 글당 {f(rd)}" + (f" vs 마켓브리프 글당 {f(statistics.mean(mb))}" if mb else "")
    return s


def section(region, chan, acct, rows, week, prev, notes, hist_prev):
    fol = acct.get("followers_count")
    fol_s = "–" if fol is None else f"{fol:,}"
    if fol is not None and hist_prev is not None:
        fol_s += f" ({fol - hist_prev:+,} vs 지난 리포트)"
    reach_label = "도달" if chan == "Instagram" else "조회"
    md = [f"### {chan} · {FLAG[region]}", f"팔로워 {fol_s}", ""]
    if not rows:
        md.append("게시물이 없어요.")
    else:
        md += [verdict(rows, week, reach_label), "", table(rows, week, prev, reach_label), "", best_worst(rows, week, reach_label)]
    for n in dict.fromkeys(notes):
        md.append(f"\n_참고: {n}_")
    return "\n".join(x for x in md if x is not None)


# ---------------------------------------------------------------- 실행
def weeks(region, today=None):
    t = today or dt.datetime.now(ZoneInfo(TZ[region])).date()
    mon = t - dt.timedelta(days=t.weekday())
    ws, we = mon - dt.timedelta(days=7), mon - dt.timedelta(days=1)
    ps, pe = ws - dt.timedelta(days=7), ws - dt.timedelta(days=1)
    return (ws.isoformat(), we.isoformat()), (ps.isoformat(), pe.isoformat())


def mock_data(region):
    import random
    random.seed(region)
    caps = {"weather": "서울 11/25(수) 최고 6° · 최저 -4°\n\n#서울날씨 #레드덴바", "books": "📚 책\n\n#레드덴바", "news": "📰 뉴스\n\n#레드덴바",
            "animal": "🐾 아기\n\n#레드덴바", "deriv": "목요일 파생 브리핑\n\n#레드덴바", "trip": "📍 나들이\n\n#레드덴바", "marketbrief": "코스피 마감 시황"}
    tz = ZoneInfo(TZ[region]); items = []
    for i in range(20):
        d = dt.datetime(2026, 11, 13, 6, 5, tzinfo=tz) + dt.timedelta(days=i)
        items.append(dict(id=str(i), caption=caps["weather"], timestamp=d.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000"),
                          like_count=random.randint(3, 30), comments_count=random.randint(0, 3), reach=random.randint(50, 400), permalink="https://example.com"))
        k = ["books", "news", "animal", "deriv", "trip", None, None][d.weekday()]
        if k:
            items.append(dict(id=f"w{i}", caption=caps[k], timestamp=(d + dt.timedelta(hours=7)).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000"),
                              like_count=random.randint(5, 50), comments_count=random.randint(0, 5), reach=random.randint(80, 600), permalink="https://example.com"))
        items.append(dict(id=f"m{i}", caption=caps["marketbrief"], timestamp=(d + dt.timedelta(hours=2)).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000"),
                          like_count=random.randint(2, 20), comments_count=0, reach=random.randint(40, 300), permalink="https://example.com"))
    return {"followers_count": 120}, items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--today", help="기준 날짜(테스트용) YYYY-MM-DD")
    a = ap.parse_args()
    os.makedirs("reports", exist_ok=True)
    hp = "reports/history.json"
    hist = json.load(open(hp, encoding="utf-8")) if os.path.exists(hp) else []
    last = hist[-1] if hist else {}
    run_day = dt.datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    snap = {"date": run_day}
    parts, raw = [], {}
    wk_label = None
    for region in ("kr", "us"):
        today = dt.date.fromisoformat(a.today) if a.today else None
        week, prev = weeks(region, today)
        wk_label = wk_label or week
        R = region.upper()
        for chan, envk in (("Instagram", f"IG_TOKEN_{R}"), ("Threads", f"THREADS_TOKEN_{R}")):
            notes = []
            token = os.environ.get(envk, "").strip()
            try:
                if a.mock:
                    acct, items = mock_data(region) if chan == "Instagram" else ({}, [])
                elif not token:
                    notes.append(f"{envk} 비밀값이 없어서 건너뜀"); acct, items = {}, []
                elif chan == "Instagram":
                    acct, items = fetch_ig(region, token, notes)
                else:
                    acct, items = fetch_threads(token, notes)
            except Exception as e:
                notes.append(f"읽기 실패: {str(e)[:200]}"); acct, items = {}, []
            rows = norm(items, region, "ig" if chan == "Instagram" else "th")
            key = f"{chan.lower()}_{region}"
            snap[key] = acct.get("followers_count")
            raw[key] = rows
            parts.append(section(region, chan, acct, rows, week, prev, notes, last.get(key)))
            print(f"{key}: 게시물 {len(rows)}개, 팔로워 {acct.get('followers_count')}, 참고 {notes}")
    md = "\n\n---\n\n".join(parts)
    title = f"# 🐼 Red Denva 주간 성적표 · {wk_label[0]} ~ {wk_label[1]}\n\n" \
            f"_만든 날: {run_day} (한국 날짜). '반응' = 좋아요+댓글+저장+공유(Threads는 좋아요+답글+리포스트+인용+공유). " \
            f"'지난주 대비'는 평균 반응 변화. 최근 1~2일 글은 아직 반응이 쌓이는 중이라 낮게 보일 수 있어요. " \
            f"'누적'은 {START:%m/%d} 이후 전체._\n\n"
    body = title + md + "\n"
    if a.mock:
        print(body); return
    open("reports/latest.md", "w", encoding="utf-8").write(body)
    open(f"reports/{run_day}.md", "w", encoding="utf-8").write(body)
    json.dump(raw, open("reports/latest-data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    hist = [h for h in hist if h.get("date") != run_day] + [snap]
    json.dump(hist, open(hp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8").write(body)


if __name__ == "__main__":
    main()
