"""주말 브리프: 토요일 = 주간 정리(wrap), 일요일 = 다음 주 일정(ahead). 한국판·미국판. (ChatGPT 주말 글 대체)

- 주간 정리: 이번 주 등락(금요일 종가 vs 지난주 금요일 종가). 반도체 현물가·GPU(1주 변동) + 지수·금리·원자재 + 이번 주 핵심 뉴스 3.
- 다음 주 일정: 경제지표·중앙은행·큰 회사 실적(나스닥 공개 달력, 무료) + 휴장 + 요일별 날씨.
  한국판은 한국시간, 미국판은 뉴욕시간. 발표 시각을 모르는 건 시각 없이 쓴다 (지어내지 않음).
brief.py --kind wrap / ahead 로 부른다.
"""
import datetime as dt, re
from brief import (KST, ET_, LA, KRX_HOL, NYSE_HOL, HOL_NAME, WD, EN_WD, get, mk, fchart, safe, sky, lab, mood_of, POSE, pct_rich)
import urllib.parse


# ------------------------------------------------------------------ 주간 등락
def _week(daily, today):
    """daily = [(date, close)] → (마지막 날, 종가, 지난주 마지막 종가)."""
    daily = [x for x in daily if x[0] < today]
    end, last = daily[-1]
    mon = end - dt.timedelta(days=end.weekday())
    prev = next(c for d, c in reversed(daily) if d < mon)
    return end, last, prev, daily


def wk_y(sym, now, name, unit="", dp=2, kind="pct"):
    j = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}", params={"range": "6mo", "interval": "1d"}).json()["chart"]["result"][0]
    tz = dt.timezone(dt.timedelta(seconds=j["meta"].get("gmtoffset", 0)))
    daily = [(dt.datetime.fromtimestamp(t, tz).date(), c) for t, c in zip(j.get("timestamp", []), j["indicators"]["quote"][0]["close"]) if c is not None]
    end, last, prev, daily = _week(daily, now.astimezone(tz).date())
    q = mk(name, last, prev, end, [c for _, c in daily[-22:]], unit, dp, kind)
    q["hist"] = [[k.isoformat(), round(c, 4)] for k, c in daily[-66:]]
    return q


def wk_n(sym, now, name, unit="", dp=2):
    daily = [(dt.date(int(a[0][:4]), int(a[0][4:6]), int(a[0][6:8])), float(a[4])) for a in fchart(sym, n=80)]
    end, last, prev, daily = _week(daily, now.astimezone(KST).date() + dt.timedelta(days=1))
    q = mk(name, last, prev, end, [c for _, c in daily[-22:]], unit, dp)
    q["hist"] = [[k.isoformat(), c] for k, c in daily[-66:]]
    return q


def kr_wrap(now):
    y = lambda s, n, **k: safe(wk_y, s, now, n, **k)
    kospi = safe(wk_n, "KOSPI", now, "코스피"); kosdaq = safe(wk_n, "KOSDAQ", now, "코스닥")
    sam = safe(wk_n, "005930", now, "삼성전자", "원", 0); hyn = safe(wk_n, "000660", now, "SK하이닉스", "원", 0)
    us = [x for x in (y("^IXIC", "나스닥"), y("^GSPC", "S&P 500"), y("^SOX", "필라델피아 반도체")) if x]
    mac = [x for x in (y("^TNX", "美 국채 10년", unit="%", dp=3, kind="bp"), y("KRW=X", "원/달러", unit="원"), y("CL=F", "WTI 유가", unit="$"), y("GC=F", "금", unit="$", dp=1), y("^VIX", "VIX", kind="pt")) if x]
    top = [q for q in (kospi, kosdaq) if q] + [q for q in us if q["name"] == "나스닥"] + [q for q in (sam, hyn) if q] + [q for q in mac if q["name"] == "美 국채 10년"]
    end = dt.date.fromisoformat((kospi or us[0])["date"]); mon = end - dt.timedelta(days=end.weekday())
    lead = kospi or us[0]; mood = mood_of(lead["pct"] / 2)
    facts = {q["name"]: f"주간 {q['pct']:+.2f}%" for q in top + us + mac[1:4]}
    return {"region": "kr", "kind": "wrap", "title": "주간 정리", "kicker": "WEEKLY RECAP", "sub": f"{mon.month}/{mon.day} – {end.month}/{end.day} · 금요일 종가 기준",
            "mood": mood, "pose": POSE[mood], "facts": facts,
            "sections": [{"type": "mini", "title": "이번 주 성적", "small": "지난주 금요일 종가 대비", "items": top[:6], "cols": 3, "spark": True},
                         {"type": "rows", "title": "미국·원자재", "items": us + mac, "card": False}],
            "hook": {"kicker": "이번 주 성적", "lines": [f"{q['name']} {pct_rich(q['pct'])}" for q in top[:2]]},
            "foot": "자료: 네이버 증권, Yahoo Finance, DRAMeXchange, SemiAnalysis · 투자 권유 아님"}


def us_wrap(now):
    y = lambda s, n, **k: safe(wk_y, s, now, n, **k)
    idx = [x for x in (y("^GSPC", "S&P 500"), y("^IXIC", "Nasdaq"), y("^DJI", "Dow", dp=0), y("^SOX", "Chips (SOX)"), y("^RUT", "Russell 2000")) if x]
    mac = [x for x in (y("^TNX", "10-yr Treasury", unit="%", dp=3, kind="bp"), y("^VIX", "VIX", kind="pt"), y("CL=F", "WTI crude", unit="$"), y("GC=F", "Gold", unit="$", dp=1), y("BTC-USD", "Bitcoin", unit="$", dp=0)) if x]
    chip = [x for x in (y("NVDA", "Nvidia", unit="$"), y("MU", "Micron", unit="$"), y("AVGO", "Broadcom", unit="$"), y("TSM", "TSMC", unit="$")) if x]
    top = idx[:4] + [q for q in mac if q["name"] in ("10-yr Treasury", "VIX")]
    end = dt.date.fromisoformat(idx[0]["date"]); mon = end - dt.timedelta(days=end.weekday())
    mood = mood_of(idx[0]["pct"] / 2)
    facts = {q["name"]: f"week {q['pct']:+.2f}%" for q in idx + mac[:4] + chip[:2]}
    return {"region": "us", "kind": "wrap", "title": "Weekly Recap", "kicker": "WEEKLY RECAP", "sub": f"{mon:%b} {mon.day} – {end:%b} {end.day} · Friday close",
            "mood": mood, "pose": "a05" if mood == "flat" else POSE[mood], "facts": facts,
            "sections": [{"type": "mini", "title": "This week", "small": "vs. last Friday's close", "items": top[:6], "cols": 3, "spark": True},
                         {"type": "rows", "title": "Chip stocks · week", "items": chip + mac, "card": False}],
            "hook": {"kicker": "This week", "lines": [f"{q['name']} {pct_rich(q['pct'], us=True)}" for q in idx[:2]]},
            "foot": "Source: Yahoo Finance, DRAMeXchange, SemiAnalysis · not investment advice"}


# ------------------------------------------------------------------ 다음 주 일정 (나스닥 공개 달력)
NQ = {"Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/", "Accept": "application/json, text/plain, */*"}

# (정규식, 중요도, 한국어 이름, 영어 이름). 위에서부터 먼저 맞는 것.
US_EV = [(r"Fed(eral)? (Funds|Interest) Rate|FOMC (Statement|Rate|Economic Projections)|Interest Rate Decision", 10, "FOMC 금리 결정", "FOMC rate decision"),
         (r"FOMC (Meeting )?Minutes", 7, "FOMC 의사록", "FOMC minutes"),
         (r"Nonfarm Payrolls|Non-Farm Employment Change|Unemployment Rate", 9, "미국 고용보고서", "Jobs report"),
         (r"\bCPI\b|Consumer Price Index", 9, "미국 소비자물가(CPI)", "CPI inflation"),
         (r"\bPCE\b|Personal Consumption Expenditure", 8, "미국 PCE 물가", "PCE inflation"),
         (r"\bGDP\b|Gross Domestic Product", 8, "미국 GDP", "GDP"),
         (r"\bPPI\b|Producer Price Index", 7, "미국 생산자물가(PPI)", "PPI"),
         (r"ISM Manufacturing PMI|ISM Manufacturing Index", 7, "미국 ISM 제조업", "ISM manufacturing"),
         (r"ISM (Non-Manufacturing|Services)", 7, "미국 ISM 서비스업", "ISM services"),
         (r"Retail Sales", 7, "미국 소매판매", "Retail sales"),
         (r"JOLTS|Job Openings", 6, "미국 구인건수(JOLTS)", "JOLTS job openings"),
         (r"ADP (Nonfarm )?Employment", 6, "미국 ADP 고용", "ADP jobs"),
         (r"Beige Book", 5, "연준 베이지북", "Fed Beige Book"),
         (r"Fed Chair|Powell", 6, "연준 의장 발언", "Fed Chair speaks"),
         (r"CB Consumer Confidence|Consumer Confidence", 5, "미국 소비자신뢰지수", "Consumer confidence"),
         (r"Michigan.*(Sentiment|Consumer)", 5, "미시간대 소비자심리", "UMich sentiment"),
         (r"Initial Jobless Claims", 3, "미국 신규 실업수당 청구", "Jobless claims")]
KR_EV = [(r"Interest Rate Decision|Rate Decision", 10, "한국은행 금리 결정", ""),
         (r"\bCPI\b|Consumer Price", 8, "한국 소비자물가", ""),
         (r"Trade Balance|Exports", 7, "한국 수출입", ""),
         (r"\bGDP\b", 8, "한국 GDP", ""),
         (r"Industrial Production|Industrial Output", 5, "한국 산업생산", "")]
OTHER_EV = [("Euro Zone", r"(Deposit Facility|Main Refinancing|ECB) Rate|ECB Interest Rate Decision", 7, "ECB 금리 결정", "ECB rate decision"),
            ("Japan", r"BoJ Interest Rate Decision|BOJ Rate", 7, "일본은행 금리 결정", "BoJ rate decision"),
            ("China", r"Caixin Manufacturing PMI|NBS Manufacturing PMI|Manufacturing PMI", 4, "중국 제조업 PMI", "China manufacturing PMI")]

# 실적: 이름(한국어). 반도체·AI는 중요도 가산
CO = {"NVDA": "엔비디아", "AVGO": "브로드컴", "MU": "마이크론", "AMD": "AMD", "ORCL": "오라클", "ADBE": "어도비", "CRM": "세일즈포스", "COST": "코스트코",
      "AAPL": "애플", "MSFT": "마이크로소프트", "GOOGL": "알파벳", "GOOG": "알파벳", "AMZN": "아마존", "META": "메타", "TSLA": "테슬라", "NFLX": "넷플릭스",
      "INTC": "인텔", "QCOM": "퀄컴", "TXN": "텍사스인스트루먼트", "MRVL": "마벨", "ASML": "ASML", "TSM": "TSMC", "LRCX": "램리서치", "AMAT": "어플라이드머티리얼즈",
      "KLAC": "KLA", "ARM": "ARM", "SNOW": "스노우플레이크", "PANW": "팔로알토", "CRWD": "크라우드스트라이크", "DELL": "델", "HPQ": "HP", "HPE": "HPE",
      "WMT": "월마트", "TGT": "타깃", "HD": "홈디포", "LOW": "로우스", "NKE": "나이키", "FDX": "페덱스", "MCD": "맥도날드", "DIS": "디즈니", "JPM": "JP모건",
      "GS": "골드만삭스", "MS": "모건스탠리", "BAC": "뱅크오브아메리카", "LULU": "룰루레몬", "PLTR": "팔란티어", "SMCI": "슈퍼마이크로", "WDAY": "워크데이", "INTU": "인튜이트"}
SEMI = {"NVDA", "AVGO", "MU", "AMD", "INTC", "QCOM", "TXN", "MRVL", "ASML", "TSM", "LRCX", "AMAT", "KLAC", "ARM", "SMCI", "DELL", "HPE", "ORCL"}


def nasdaq(path, day):
    return (get(f"https://api.nasdaq.com/api/calendar/{path}", params={"date": day.isoformat()}, headers=NQ).json().get("data") or {}).get("rows") or []


def econ_events(day, ko):
    out = []
    for r in nasdaq("economicevents", day):
        c, n, g = (r.get("country") or "").strip(), (r.get("eventName") or "").strip(), (r.get("gmt") or "").strip()
        hit = None
        if c == "United States":
            hit = next(((rk, k, e) for pat, rk, k, e in US_EV if re.search(pat, n, re.I)), None)
        elif c == "South Korea" and ko:
            hit = next(((rk, k, n) for pat, rk, k, _ in KR_EV if re.search(pat, n, re.I)), None)
        else:
            hit = next(((rk, k, e) for cc, pat, rk, k, e in OTHER_EV if cc == c and re.search(pat, n, re.I)), None)
        if c in ("United States", "South Korea"): print("  달력", day, g, c, n, "→", hit[1] if hit else "-")
        if not hit: continue
        m = re.match(r"^(\d{1,2}):(\d{2})$", g)
        # 나스닥 달력의 'gmt' 칸은 실제로는 뉴욕시간 (ISM 10:00, 고용 8:30 으로 나옴)
        t = dt.datetime(day.year, day.month, day.day, int(m.group(1)), int(m.group(2)), tzinfo=ET_) if m else None
        out.append({"rank": hit[0], "ko": hit[1], "en": hit[2], "at": t, "day": day, "kind": "kr" if c == "South Korea" else "macro", "raw": n})
    return out


def earn_events(day):
    out = []
    for r in nasdaq("earnings", day):
        sym = (r.get("symbol") or "").strip(); cap = float(re.sub(r"[^\d.]", "", r.get("marketCap") or "") or 0)
        if sym not in CO and cap < 150e9: continue  # 잘 알려진 회사(이름표에 있는 곳)나 아주 큰 회사만
        tm = r.get("time") or ""
        when = "after" if "after" in tm else "pre" if "pre" in tm else ""
        rank = 4 + (3 if sym in SEMI else 0) + (2 if cap > 300e9 else 1 if cap > 100e9 else 0)
        nm = re.sub(r",? (Inc\.?|Corporation|Corp\.?|Incorporated|Company|Co\.|Ltd\.?|Limited|Group|plc|N\.V\.|\(The\)|Technology|Technologies)$", "", (r.get("name") or sym).strip())
        out.append({"rank": rank, "ko": f"{CO.get(sym, nm)} 실적", "en": f"{nm} earnings", "at": None, "day": day, "when": when, "kind": "earn", "sym": sym, "cap": cap})
    return sorted(out, key=lambda e: -e["cap"])[:4]


def week_wx(region, d0, d1):
    import weather
    r = weather.REGIONS[region]; ko = region == "kr"
    j = get("https://api.open-meteo.com/v1/forecast", params={"latitude": r["lat"], "longitude": r["lon"], "timezone": r["tz"], "start_date": d0.isoformat(), "end_date": d1.isoformat(),
            "temperature_unit": "celsius" if ko else "fahrenheit", "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"}).json()["daily"]
    out = {}
    for i, k in enumerate(j["time"]):
        code = int(j["weather_code"][i] or 0); txt, ic = sky(code, ko); rain = int(j["precipitation_probability_max"][i] or 0)
        if rain >= 60 and ic in ("sun", "part", "cloud", "fog"): txt, ic = ("비 소식" if ko else "Rain likely"), "rain"
        out[k] = {"sky": txt, "icon": ic, "hi": round(j["temperature_2m_max"][i]), "lo": round(j["temperature_2m_min"][i]), "rain": rain}
    return out


def ahead(region, now):
    ko = region == "kr"; tz = KST if ko else ET_
    today = now.astimezone(tz).date()
    mon = today + dt.timedelta(days=(7 - today.weekday()) % 7 or 7)  # 다음 월요일
    days = [mon + dt.timedelta(days=i) for i in range(6 if ko else 5)]  # 한국판은 토요일 새벽(미국 금요일 밤)까지
    us_days = [mon - dt.timedelta(days=1) + dt.timedelta(days=i) for i in range(7)] if ko else days
    ev = []
    for d in us_days:
        ev += safe(econ_events, d, ko) or []
        if d.weekday() < 5: ev += safe(earn_events, d) or []
    print("일정 후보", len(ev))
    by = {d: [] for d in days}
    for e in ev:
        if e["at"]:
            loc = e["at"].astimezone(tz); e["t"] = loc.strftime("%H:%M") if ko else loc.strftime("%-I:%M %p").replace(":00 ", " ").lower(); dd = loc.date()
        elif e["kind"] == "earn":
            if ko: dd, e["t"] = (e["day"] + dt.timedelta(days=1), "새벽") if e["when"] == "after" else (e["day"], "밤") if e["when"] == "pre" else (e["day"], "")
            else: dd, e["t"] = e["day"], {"after": "after close", "pre": "before open"}.get(e["when"], "")
        else: dd, e["t"] = e["day"], ""
        if dd in by: by[dd].append(e)
    for d in days:
        for hol, who in ((NYSE_HOL, ("미국 증시 휴장", "NYSE closed")), (KRX_HOL, ("한국 증시 휴장", ""))):
            if d in hol and (ko or who[1]): by[d].append({"rank": 11, "ko": who[0] + (f" ({HOL_NAME[d][0]})" if d in HOL_NAME else ""), "en": who[1] + (f" ({HOL_NAME[d][1]})" if d in HOL_NAME else ""), "t": "", "kind": "hol"})
    wx = safe(week_wx, region, days[0], days[-1]) or {}
    out, top = [], []
    for d in days:
        seen, lst = set(), []
        for e in sorted(by[d], key=lambda e: (-e["rank"], e.get("t") or "")):
            name = e["ko"] if ko else e["en"]
            if name in seen: continue
            seen.add(name); lst.append({"t": e.get("t", ""), "n": name, "k": e["kind"], "r": e["rank"]})
        lst = lst[:3]
        top += [(x["r"], d, x) for x in lst]
        if ko: lst.sort(key=lambda x: (not re.match(r"\d", x["t"]), x["t"]))  # 시각 순, 시각 없는 건 뒤
        if lst or d.weekday() < 5: out.append({"date": d.isoformat(), "wx": wx.get(d.isoformat()), "ev": lst})
    top = sorted(top, key=lambda x: -x[0])[:4]
    fri = days[4]
    if ko:
        facts = {f"{WD[d.weekday()]} {x['t']}".strip(): x["n"] for _, d, x in top}
        hl = [f"{WD[d.weekday()]} [[acc:{x['n'].replace('미국 ', '')}]]" for _, d, x in top[:2]]
        return {"region": "kr", "kind": "ahead", "title": "다음 주 일정", "kicker": "WEEK AHEAD", "sub": f"{mon.month}/{mon.day} – {fri.month}/{fri.day} · 한국시간",
                "mood": "flat", "pose": "a05", "facts": facts, "sections": [{"type": "week", "title": "요일별 일정 · 서울 날씨", "days": out}],
                "hook": {"kicker": "다음 주 일정", "lines": hl or ["조용한 한 주"]}, "foot": "자료: Nasdaq 경제·실적 달력, Open-Meteo · 시각은 한국시간"}
    facts = {f"{EN_WD[d.weekday()]} {x['t']}".strip(): x["n"] for _, d, x in top}
    hl = [f"{EN_WD[d.weekday()]} [[acc:{x['n']}]]" for _, d, x in top[:2]]
    return {"region": "us", "kind": "ahead", "title": "Week Ahead", "kicker": "WEEK AHEAD", "sub": f"{mon:%b} {mon.day} – {fri:%b} {fri.day} · New York time",
            "mood": "flat", "pose": "a05", "facts": facts, "sections": [{"type": "week", "title": "Day by day · LA weather", "days": out}],
            "hook": {"kicker": "Week ahead", "lines": hl or ["A quiet week"]}, "foot": "Source: Nasdaq economic & earnings calendars, Open-Meteo · times ET"}


BUILD = {("kr", "wrap"): kr_wrap, ("us", "wrap"): us_wrap, ("kr", "ahead"): lambda now: ahead("kr", now), ("us", "ahead"): lambda now: ahead("us", now)}
