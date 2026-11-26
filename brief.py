"""모닝 브리프 · 마감 브리프 (한국판 @reddenva.kr / 미국판 @reddenva.us). ChatGPT 시황 브리핑을 대신할 무료 자동 버전.

- 숫자는 전부 공개 시세에서: 미국·해외 = Yahoo Finance 차트, 한국 = 네이버 증권(지수·종목·투자자별 매매·선물·국고채).
- 레드덴바 한마디와 뉴스 3줄은 Gemini 무료 API (실패하면 규칙 문장, 뉴스는 빼고 게시).
- 카드는 reels/brief_card.html 을 브라우저로 찍어서 만든다 (릴스와 같은 엔진). 릴스용 숫자는 reel_in/ 에 남긴다.

  python brief.py --region kr --kind morning [--dry-run] [--force] [--asof 2026-11-26T06:05] [--mock]
결과: out/{kind}-{region}-YYYY-MM-DD.jpg, out/{kind}-{region}-latest.json
"""
import argparse, datetime as dt, json, os, re, subprocess, sys, time, urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
KST, ET_, LA = ZoneInfo("Asia/Seoul"), ZoneInfo("America/New_York"), ZoneInfo("America/Los_Angeles")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
WD = "월화수목금토일"; EN_WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
KRX_HOL = {dt.date(*d) for d in [(2026, 12, 25), (2026, 12, 31), (2027, 1, 1), (2027, 2, 8), (2027, 2, 9), (2027, 3, 1), (2027, 5, 5), (2027, 5, 13),
                                 (2027, 6, 3), (2027, 8, 16), (2027, 9, 14), (2027, 9, 15), (2027, 9, 16), (2027, 10, 4), (2027, 10, 11), (2027, 12, 31)]}
NYSE_HOL = {dt.date(*d) for d in [(2026, 11, 26), (2026, 12, 25), (2027, 1, 1), (2027, 1, 18), (2027, 2, 15), (2027, 3, 26), (2027, 5, 31),
                                  (2027, 6, 18), (2027, 7, 5), (2027, 9, 6), (2027, 11, 25), (2027, 12, 24)]}
HOL_NAME = {dt.date(2026, 11, 26): ("추수감사절", "Thanksgiving"), dt.date(2026, 12, 25): ("크리스마스", "Christmas"), dt.date(2027, 1, 1): ("새해", "New Year's Day")}


def get(url, **kw):
    for i in range(3):
        try:
            r = requests.get(url, headers=H, timeout=25, **kw); r.raise_for_status(); return r
        except Exception:
            if i == 2: raise
            time.sleep(2 + i * 2)


def lab(d, ko=True): return f"{d.month}/{d.day} ({WD[d.weekday()]})" if ko else f"{EN_WD[d.weekday()]}, {d:%b} {d.day}"


# ------------------------------------------------------------------ 시세: Yahoo (미국·해외·선물·원자재·코인)
def yahoo(sym, now, name, unit="", dp=2, kind="pct", session=True):
    """session=True: 마지막으로 '끝난' 정규장 종가와 그날 5분 차트. False(선물·환율·코인): now 시점 값 vs 전일 정산/종가, 최근 24시간 차트."""
    q = urllib.parse.quote(sym)
    j = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{q}", params={"range": "1mo", "interval": "1d"}).json()["chart"]["result"][0]
    meta = j["meta"]; tz = ZoneInfo(meta["exchangeTimezoneName"]); nl = now.astimezone(tz)
    end = meta.get("currentTradingPeriod", {}).get("regular", {}).get("end")
    close_t = dt.datetime.fromtimestamp(end, tz).time() if end else dt.time(16, 0)
    daily = [(dt.datetime.fromtimestamp(t, tz).date(), c) for t, c in zip(j.get("timestamp", []), j["indicators"]["quote"][0]["close"]) if c is not None]
    done = lambda d: d < nl.date() or (d == nl.date() and nl.time() >= (dt.datetime.combine(d, close_t) + dt.timedelta(minutes=5)).time())
    daily = [x for x in daily if done(x[0])]
    j5 = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{q}", params={"range": "5d", "interval": "5m", "includePrePost": "false" if session else "true"}).json()["chart"]["result"][0]
    pts = [(dt.datetime.fromtimestamp(t, tz), c) for t, c in zip(j5.get("timestamp", []), j5["indicators"]["quote"][0]["close"]) if c is not None]
    pts = [p for p in pts if p[0] <= nl and daily and abs(p[1] / daily[-1][1] - 1) < .3]
    if session:
        d, last = daily[-1]; prev = daily[-2][1]
        spark = [c for t, c in pts if t.date() == d] or [c for _, c in daily[-20:]]
    else:
        last = pts[-1][1] if pts else daily[-1][1]
        prev = next((c for d, c in reversed(daily) if d < nl.date()), daily[-1][1]) if daily else last
        if daily and daily[-1][0] == nl.date() and len(daily) > 1: prev = daily[-2][1]
        cut = nl - dt.timedelta(hours=20); spark = [c for t, c in pts if t >= cut]
        d = nl.date()
    return mk(name, last, prev, d, spark, unit, dp, kind)


def mk(name, last, prev, d, spark, unit="", dp=2, kind="pct"):
    chg = last - prev
    q = {"name": name, "last": round(last, dp), "prev": round(prev, dp), "chg": round(chg, 4), "pct": round(chg / prev * 100, 2) if prev else 0.0,
         "date": d.isoformat(), "unit": unit, "dp": dp, "kind": kind, "spark": thin(spark)}
    if kind == "bp": q["bp"] = round(chg * 100, 1)
    return q


def thin(v, n=60):
    v = [round(x, 4) for x in v if x is not None]
    if len(v) <= n: return v
    step = (len(v) - 1) / (n - 1); return [v[round(i * step)] for i in range(n)]


# ------------------------------------------------------------------ 시세: 네이버 (한국)
def fchart(sym, tf="day", n=40):
    t = get("https://fchart.stock.naver.com/sise.nhn", params={"symbol": sym, "timeframe": tf, "count": n, "requestType": 0}).content.decode("euc-kr", "replace")
    return [a.split("|") for a in re.findall(r'data="([^"]+)"', t)]


def naver(sym, now, name, unit="", dp=2):
    """마지막으로 끝난 한국 정규장(15:30) 종가 + 그날 분봉."""
    nl = now.astimezone(KST)
    daily = [(dt.date(int(a[0][:4]), int(a[0][4:6]), int(a[0][6:8])), float(a[4])) for a in fchart(sym)]
    daily = [x for x in daily if x[0] < nl.date() or (x[0] == nl.date() and nl.time() >= dt.time(15, 45))]
    d, last = daily[-1]; prev = daily[-2][1]
    spark = []
    if True:  # 하루 차트는 Yahoo 5분봉 (값·등락률은 네이버 그대로)
        try:
            ys = {"KOSPI": "^KS11", "KOSDAQ": "^KQ11"}.get(sym, f"{sym}.KS")
            j5 = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ys)}", params={"range": "5d", "interval": "5m"}).json()["chart"]["result"][0]
            ysp = [c for t, c in zip(j5.get("timestamp", []), j5["indicators"]["quote"][0]["close"]) if c is not None and dt.datetime.fromtimestamp(t, KST).date() == d]
            print("분봉", sym, "Yahoo", len(ysp))
            ysp = [c for c in ysp if abs(c / last - 1) < .15]  # 엉뚱한 값 걸러내기
            if len(ysp) >= 10: spark = ysp + [last]
        except Exception as e: print("Yahoo 분봉 실패", sym, e)
    return mk(name, last, prev, d, spark or [c for _, c in daily[-20:]], unit, dp)


def naver_flows(day):
    """코스피 현물 투자자별 순매수(억원)와 코스피200 선물 투자자별 순매수(억원)."""
    out = {}
    for key, path in (("spot", "KOSPI"), ("fut", "FUT")):
        try:
            j = get(f"https://m.stock.naver.com/api/index/{path}/trend", params={"bizdate": day.strftime("%Y%m%d")}).json()
            print("수급", path, {k: j.get(k) for k in ("bizdate", "foreignValue", "institutionalValue", "personalValue")})
            if j.get("bizdate") == day.strftime("%Y%m%d"):
                N = lambda s: int(str(s).replace(",", "").replace("+", ""))
                out[key] = {"frn": N(j["foreignValue"]), "ins": N(j["institutionalValue"]), "ind": N(j["personalValue"])}
        except Exception as e: print("수급 실패", path, e)
    return out


def naver_ktb(now):
    j = get("https://m.stock.naver.com/front-api/marketIndex/prices", params={"category": "bond", "reutersCode": "KR10YT=RR", "page": 1, "pageSize": 30}).json()
    rows = sorted((dt.date.fromisoformat(r["localTradedAt"][:10]), float(r["closePrice"])) for r in j["result"])
    rows = [r for r in rows if r[0] <= now.astimezone(KST).date()]
    return mk("국고채 10년", rows[-1][1], rows[-2][1], rows[-1][0], [r[1] for r in rows[-20:]], "%", 3, "bp")


def k200_basis(day):
    fut = {a[0][:8]: float(a[4]) for a in fchart("FUT", n=10)}; spot = {a[0][:8]: float(a[4]) for a in fchart("KPI200", n=10)}
    k = day.strftime("%Y%m%d")
    if k in fut and k in spot: return {"fut": fut[k], "spot": spot[k], "basis": round(fut[k] - spot[k], 2)}


# ------------------------------------------------------------------ 반도체 현물가 (이 채널의 메인): D램 현물 · GPU 임대료
QPX = "https://chip.qpx.kr/prices/{}"  # DRAMeXchange 현물 표를 매일 남긴 이력 (차트용)
DX_ITEMS = [("DDR5 16Gb (2Gx8) 4800/5600", "DDR5 16Gb"), ("DDR4 16Gb (2Gx8) 3200", "DDR4 16Gb"), ("DDR4 8Gb (1Gx8) 3200", "DDR4 8Gb"), ("MLC 64Gb 8GBx8", "NAND 64Gb")]


def back(series, d, days):
    t = d - dt.timedelta(days=days); old = [v for k, v in series if k <= t]
    return old[-1] if old else None


def chg_n(series, d, days):
    o = back(series, d, days); last = series[-1][1]
    return round((last / o - 1) * 100, 2) if o else None


def dramx():
    """DRAMeXchange 첫 화면 표: 품목 → (세션 평균가, 세션 변동 %), 업데이트 시각."""
    h = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", get("https://www.dramexchange.com/").text))
    h = re.sub(r"(\| ?)+", "|", h)
    out = {}
    for label, name in DX_ITEMS:
        m = re.search(re.escape(label) + r" ?\|([\d.]+)\|([\d.]+)\|([\d.]+)\|([\d.]+)\|([\d.]+)\|(-?[\d.]+) ?%", h)
        if m: out[name] = (float(m.group(5)), float(m.group(6)))
    up = re.search(r"DRAM Spot Price\|Last Update: ?([A-Za-z]{3})\.(\d+) (\d{4}) (\d\d):(\d\d)", h)
    when = dt.datetime.strptime(f"{up.group(1)} {up.group(2)} {up.group(3)} {up.group(4)}:{up.group(5)}", "%b %d %Y %H:%M").replace(tzinfo=ZoneInfo("Asia/Taipei")) if up else None
    print("DRAMeXchange", when, out)
    return out, when


def dram_hist(slug="dram-spot__ddr5-16gb-2gx8-4800-5600"):
    t = get(QPX.format(slug)).text
    rows = re.findall(r'<td class="strong mono">(\d{4}-\d\d-\d\d)</td><td class="num">([\d.]+)</td><td class="num">([\d.]+)</td><td class="num strong">([\d.]+)</td>', t)
    return sorted((dt.date.fromisoformat(a), float(avg)) for a, hi, lo, avg in rows)


def drams(now):
    """메인 = DDR5 16Gb (지금 게시된 세션 평균 + 3개월 차트), 나머지 품목은 값과 세션 변동."""
    try: tab, when = dramx()
    except Exception as e: print("DRAMeXchange 실패", e); tab, when = {}, None
    ser = safe(dram_hist) or []
    out = []
    if "DDR5 16Gb" in tab:
        last, pc = tab["DDR5 16Gb"]; d = (when or now).astimezone(KST).date()
        hist = [x for x in ser if x[0] < d] + [(d, last)]
    elif ser:
        hist = ser; d, last = ser[-1]; pc = None
    else: hist = []
    if hist:
        prev = last / (1 + pc / 100) if pc is not None else hist[-2][1]
        win = [v for k, v in hist if k > d - dt.timedelta(days=92)]
        q = mk("DDR5 16Gb", last, prev, d, win, "$", 3)
        q.update(w1=chg_n(hist, d, 7), m1=chg_n(hist, d, 30), since=(d - dt.timedelta(days=91)).isoformat(), full="DDR5 16Gb (2Gx8) 4800/5600")
        out.append(q)
    for name in ("DDR4 16Gb", "DDR4 8Gb", "NAND 64Gb"):
        if name in tab:
            v, pc = tab[name]; out.append(mk(name, v, v / (1 + pc / 100), (when or now).date(), [], "$", 3))
    return out


def gpu(now):
    j = get("https://gpu-index.semianalysis.com/api/public-data").json()
    rows = [(parsedate_to_datetime(r["date"]).date(), r) for r in j["index"]]
    rows = [x for x in rows if x[0] <= now.astimezone(dt.timezone.utc).date()]
    out = []
    for key, name in (("h100", "H100"), ("b200", "B200"), ("a100", "A100")):
        ser = [(k, r[key]) for k, r in rows if r.get(key)]
        if len(ser) < 3: continue
        d = ser[-1][0]; win = [v for k, v in ser if k > d - dt.timedelta(days=92)]
        q = mk(name, ser[-1][1], ser[-2][1], d, win, "$", 2)
        q.update(w1=chg_n(ser, d, 7), m1=chg_n(ser, d, 30), since=(d - dt.timedelta(days=91)).isoformat(), per="/hr")
        out.append(q)
    return out


def chips(now, ko, kind="morning"):
    if kind != "morning": return None  # 반도체 현물가·GPU는 모닝 브리프에만
    dr = (safe(drams, now) or [])[:1]  # D램은 DDR5 하나만
    gp = safe(gpu, now) or []
    if not dr and not gp: return None
    return {"type": "chips", "title": "반도체 현물가" if ko else "Chip spot prices", "small": ("DRAMeXchange · " if dr else "") + "SemiAnalysis GPU Index",
            "dram": dr, "gpu": gp}


# ------------------------------------------------------------------ 오늘 날씨 (모닝 브리프 머리에): Open-Meteo, 무료
def sky(code, ko):
    if code >= 95: return ("천둥번개" if ko else "Storms"), "storm"
    if code in (71, 73, 75, 77, 85, 86): return ("눈" if ko else "Snow"), "snow"
    if code >= 51: return ("비" if ko else "Rain"), "rain"
    if code in (45, 48): return ("안개" if ko else "Fog"), "fog"
    if code == 0: return ("맑음" if ko else "Sunny"), "sun"
    if code in (1, 2): return ("구름 조금" if ko else "Some clouds"), "part"
    return ("흐림" if ko else "Cloudy"), "cloud"


def today_wx(region, day):
    import weather
    r = weather.REGIONS[region]; ko = region == "kr"
    j = get("https://api.open-meteo.com/v1/forecast", params={"latitude": r["lat"], "longitude": r["lon"], "timezone": r["tz"],
            "start_date": day.isoformat(), "end_date": day.isoformat(), "temperature_unit": "celsius" if ko else "fahrenheit",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"}).json()["daily"]
    code = int(j["weather_code"][0] or 0); txt, ic = sky(code, ko)
    hi, lo, rain = j["temperature_2m_max"][0], j["temperature_2m_min"][0], int(j["precipitation_probability_max"][0] or 0)
    hc, lc = (hi, lo) if ko else ((hi - 32) / 1.8, (lo - 32) / 1.8)
    pose = ("w08" if code >= 95 else "w10" if code in (71, 73, 75, 77, 85, 86) else "w06" if rain >= 60 else "w05" if rain >= 40 else "w18" if code in (45, 48)
            else "w16" if hc >= 33 else "w13" if lc <= -5 else "w14" if lc <= 2 else "w15" if hc >= 28 and code <= 1 else {0: "w00", 1: "w01", 2: "w02", 3: "w04"}.get(code, "w03"))
    return {"city": r["city"] if ko else "LA", "sky": txt, "icon": ic, "hi": round(j["temperature_2m_max"][0]), "lo": round(j["temperature_2m_min"][0]),
            "rain": rain, "unit": r["unit"], "pose": pose}


# ------------------------------------------------------------------ 뉴스 3줄 · 레드덴바 한마디 (Gemini, 실패하면 빼거나 규칙 문장)
def gnews(q, ko, d0, d1):
    q = f"{q} after:{d0.isoformat()} before:{(d1 + dt.timedelta(days=1)).isoformat()}"
    url = (f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=ko&gl=KR&ceid=KR:ko" if ko
           else f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=en-US&gl=US&ceid=US:en")
    items = []
    for it in ET.fromstring(get(url).content).iter("item"):
        t = it.findtext("title") or ""; src = it.findtext("source") or ""
        try: pub = parsedate_to_datetime(it.findtext("pubDate"))
        except Exception: continue
        items.append({"title": re.sub(r"\s+-\s+[^-]+$", "", t).strip(), "src": src, "pub": pub})
    return items


def gem(prompt, temp=0.4):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key: raise RuntimeError("GEMINI_API_KEY 없음")
    from books import models  # 다른 시리즈와 같은 모델 고르기 (빠른 flash-lite 먼저)
    ms = models(key)
    last = None
    for m in (ms[:3] * 2):
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", headers={"x-goog-api-key": key}, timeout=35,
                              json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": temp, "responseMimeType": "application/json"}})
        except requests.RequestException as e: last = f"{m} {type(e).__name__}"; continue
        if not r.ok: last = f"{m} {r.status_code}"; continue
        try: return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        except Exception as e: last = f"{m} {e}"
    raise RuntimeError(f"Gemini 실패: {last}")


NEWS_Q = {("kr", "morning"): "뉴욕증시 OR 미국증시 OR 나스닥 OR 반도체 OR 엔비디아 OR 연준 OR 국제유가 OR 환율", ("kr", "close"): "코스피 OR 증시 OR 한국은행 OR 환율 OR 반도체",
          ("us", "morning"): "stocks OR futures OR Fed OR earnings OR economy", ("us", "close"): "stocks OR Wall Street OR Fed OR earnings OR Treasury yields"}


def news3(region, kind, now, facts):
    ko = region == "kr"; nl = now.astimezone(KST if ko else ET_)
    items = [it for it in gnews(NEWS_Q[(region, kind)], ko, nl.date() - dt.timedelta(days=1), nl.date()) if now - dt.timedelta(hours=30) <= it["pub"] <= now]
    items = items[:60]
    print("뉴스 후보", len(items))
    if len(items) < 3: return []
    lst = "\n".join(f"[{i}] {it['title']} ({it['src']}, {it['pub'].astimezone(KST if ko else ET_):%m/%d %H:%M})" for i, it in enumerate(items))
    p = f"""You write the 3-line news section of a {'Korean' if ko else 'US'} {'morning' if kind == 'morning' else 'market close'} market brief.
Market numbers for context (already shown elsewhere, do not repeat them as news): {json.dumps(facts, ensure_ascii=False)}
From the headlines below pick the 3 most market-moving, distinct stories (central bank, macro data, big company news, policy). Skip opinion, ads, stock tips, crypto hype, celebrity, duplicates.
Write each as: "head" = short headline (max {'18 Korean characters' if ko else '42 characters'}), "line" = one factual sentence (max {'45 Korean characters' if ko else '95 characters'}).
Use ONLY facts stated in the headline you picked. Never invent numbers or details. Write in {'Korean (뉴스 문체, ~했다/~한다)' if ko else 'plain English'}.
Return JSON: {{"items":[{{"i":index,"head":"...","line":"..."}}]}}
Headlines:
{lst}"""
    out = []
    for x in gem(p, 0.2).get("items", [])[:3]:
        it = items[int(x["i"])]; out.append({"head": x["head"].strip(), "line": x["line"].strip(), "src": it["src"]})
    return out


def quip(region, kind, facts, mood):
    ko = region == "kr"
    try:
        p = f"""You are Red Denva, a sleepy, deadpan red panda who posts a daily {'Korean' if ko else 'US'} stock market brief.
Write ONE short comment about today's numbers below: dry, witty, specific to the numbers (mention one concrete thing), never cheesy, no emojis, no hashtags, no investment advice, no predictions.
Write numbers exactly as digits with the % sign (e.g. "-8.75%", "$3.50"), never spelled out in words.
Sound like a real person who trades, not an AI: plain words, no forced metaphors, no exclamation marks.
Clean, polished language only: no slang, no profanity or near-profanity (e.g. never 졸라/존나/개-), nothing a brand account would regret.
{'Korean, casual polite (~요), max 30 characters.' if ko else 'English, max 55 characters.'}
Mood: {mood}. Numbers: {json.dumps(facts, ensure_ascii=False)}
Return JSON {{"text":"..."}}"""
        t = gem(p, 0.8)["text"].strip().strip('"“”')
        if re.search(r"졸라|존나|졸나|ㅈㄴ|씨발|시발|개빡|damn|hell|shit|fuck", t, re.I): raise ValueError(f"말투 걸러냄: {t}")
        if re.search(r"퍼센트|프로|percent", t, re.I): raise ValueError(f"숫자를 글자로 씀: {t}")
        if 4 <= len(t) <= (36 if ko else 66): return t
    except Exception as e: print("한마디 Gemini 실패 → 규칙 문장", e)
    return RULE[region][mood]


RULE = {"kr": {"surge": "다들 신났어요. 저는 그냥 누워서 볼게요.", "up": "무난하게 올랐어요. 커피는 제가 안 사요.", "flat": "거의 제자리예요. 시장도 졸린가 봐요.",
               "down": "살짝 빠졌어요. 이불 밖은 위험해요.", "plunge": "많이 빠졌어요. 오늘은 앱을 안 여는 것도 방법이에요.", "holiday": "미국은 쉬었어요. 저도 쉬고 싶어요."},
        "us": {"surge": "Everyone's thrilled. I'll be lying down.", "up": "A decent day up. I'm still not buying coffee.", "flat": "Basically flat. Even the market looks sleepy.",
               "down": "A bit lower. Staying under the blanket.", "plunge": "Rough one. Maybe don't open the app today.", "holiday": "Markets took the day off. Respect."}}


def mood_of(p):
    return "surge" if p >= 1.5 else "up" if p >= 0.4 else "flat" if p > -0.4 else "down" if p > -1.5 else "plunge"


POSE = {"surge": "a04", "up": "a16", "flat": "a05", "down": "a15", "plunge": "a10", "holiday": "a22"}


# ------------------------------------------------------------------ 브리프별 내용
def safe(f, *a, **k):
    try: return f(*a, **k)
    except Exception as e: print("  건너뜀:", a[1] if len(a) > 1 else a, type(e).__name__, e); return None


def kr_morning(now):
    us = lambda s, n, **k: safe(yahoo, s, now, n, **k)
    idx = [x for x in (us("^GSPC", "S&P 500"), us("^IXIC", "나스닥"), us("^SOX", "필라델피아 반도체")) if x]
    chips = [x for x in (us("NVDA", "엔비디아", unit="$"), us("MU", "마이크론", unit="$"), safe(naver, "005930", now, "삼성전자", "원", 0), safe(naver, "000660", now, "SK하이닉스", "원", 0),
                         us("TSM", "TSMC", unit="$"), us("AVGO", "브로드컴", unit="$")) if x]
    macro = [x for x in (us("EWY", "한국 ETF(EWY)", unit="$"), us("KRW=X", "원/달러", unit="원", session=False),
                         us("^TNX", "美 국채 10년", unit="%", dp=3, kind="bp"), us("^VIX", "VIX", kind="pt"),
                         us("CL=F", "WTI 유가", unit="$", session=False), us("GC=F", "금", unit="$", dp=1, session=False)) if x]
    usd = dt.date.fromisoformat(idx[0]["date"])
    exp = (now.astimezone(ET_) - dt.timedelta(days=1)).date()  # 한국 아침 = 미국 전날
    while exp.weekday() >= 5: exp -= dt.timedelta(days=1)
    hol = exp in NYSE_HOL and usd < exp
    lead = max(idx, key=lambda q: abs(q["pct"]))
    facts = {q["name"]: f"{q['pct']:+.2f}%" for q in idx + chips[:4]}
    mood = "holiday" if hol else mood_of(idx[1]["pct"] if len(idx) > 1 else idx[0]["pct"])
    d = {"region": "kr", "kind": "morning", "title": "모닝 브리프", "kicker": "MORNING BRIEF",
         "sub": (f"미국 {HOL_NAME.get(exp, ('휴장',))[0]} 휴장 · {lab(usd)} 종가 기준" if hol else f"{lab(usd)} 미국 장 마감 기준"),
         "mood": mood, "pose": POSE[mood], "facts": facts,
         "sections": [{"type": "big", "title": "간밤 미국 증시", "items": idx},
                      {"type": "rows", "title": "반도체 종목", "items": chips, "card_n": 4},
                      {"type": "mini", "title": "오늘 한국장 앞두고", "items": macro, "cols": 6, "card": False}],
         "hook": {"kicker": "간밤 미국", "lines": [f"{q['name'].replace('필라델피아 ', '')} {pct_rich(q['pct'])}" for q in idx[1:3]] if not hol else ["미국 증시", "[[acc:휴장]]"]},
         "foot": "자료: Yahoo Finance, 네이버 증권 · 투자 권유 아님"}
    return d


def kr_close(now):
    kospi = naver("KOSPI", now, "코스피"); day = dt.date.fromisoformat(kospi["date"])
    kosdaq = safe(naver, "KOSDAQ", now, "코스닥")
    stocks = [x for x in (safe(naver, c, now, n, "원", 0) for c, n in (("005930", "삼성전자"), ("000660", "SK하이닉스"), ("373220", "LG에너지솔루션"),
                                                                       ("005380", "현대차"))) if x]
    fl = naver_flows(day); bs = safe(k200_basis, day)
    macro = [x for x in (kosdaq, safe(yahoo, "KRW=X", now, "원/달러", unit="원", session=False), safe(naver_ktb, now)) if x]
    if bs: macro.append({"name": "K200 베이시스", "last": bs["basis"], "dp": 2, "unit": "pt", "kind": "text",
                         "text": f"선물 {bs['fut']:.2f}", "sign": True})
    mood = mood_of(kospi["pct"])
    facts = {"코스피": f"{kospi['last']:,.2f} ({kospi['pct']:+.2f}%)", **({"코스닥": f"{kosdaq['pct']:+.2f}%"} if kosdaq else {}),
             **{q["name"]: f"{q['pct']:+.2f}%" for q in stocks[:3]}, **({"외국인 현물(억원)": fl["spot"]["frn"]} if "spot" in fl else {})}
    secs = [{"type": "hero", "title": "오늘의 코스피", "item": kospi, "side": [m for m in macro if m["name"] != "국고채 10년"], "side_all": macro, "ch": 100}]
    if fl: secs.append({"type": "flows", "title": "누가 샀나", "small": "투자자별 순매수 · 억원", "rows": [[k, v] for k, v in (("코스피 현물", fl.get("spot")), ("코스피200 선물", fl.get("fut"))) if v]})
    secs += [{"type": "rows", "title": "시총 상위 종목", "items": stocks, "card": False}]
    who = {"frn": "외국인", "ins": "기관", "ind": "개인"}
    if "spot" in fl:
        s = fl["spot"]; b = max(s, key=s.get)
        hl = [f"코스피 {pct_rich(kospi['pct'])}", f"{who[b]} [[{'up' if s[b] > 0 else 'dn'}:{abs(s[b]):,}억]] 순매수"]
    else: hl = [f"코스피 {pct_rich(kospi['pct'])}"]
    return {"region": "kr", "kind": "close", "title": "마감 브리프", "kicker": "CLOSING BRIEF", "sub": f"{lab(day)} 한국 장 마감 15:30 기준",
            "mood": mood, "pose": POSE[mood], "facts": facts, "sections": secs, "hero": kospi, "flows": fl,
            "hook": {"kicker": f"{lab(day)} 마감", "lines": hl}, "foot": "자료: 네이버 증권, Yahoo Finance · 투자 권유 아님"}


def us_morning(now):
    y = lambda s, n, **k: safe(yahoo, s, now, n, **k)
    fut = [x for x in (y("ES=F", "S&P 500 futures", session=False), y("NQ=F", "Nasdaq 100 futures", session=False), y("YM=F", "Dow futures", session=False, dp=0)) if x]
    idx = [x for x in (y("^GSPC", "S&P 500"), y("^IXIC", "Nasdaq"), y("^DJI", "Dow", dp=0), y("^SOX", "Chips (SOX)")) if x]
    world = [x for x in (y("^N225", "Japan Nikkei", dp=0), y("^KS11", "Korea KOSPI"), y("^HSI", "Hang Seng", dp=0),
                         y("^STOXX50E", "Euro Stoxx 50"), y("^GDAXI", "Germany DAX", dp=0), y("^FTSE", "UK FTSE 100", dp=0)) if x]
    macro = [x for x in (y("^TNX", "10-yr Treasury", unit="%", dp=3, kind="bp"), y("^VIX", "VIX", kind="pt"), y("CL=F", "WTI crude", unit="$", session=False),
                         y("GC=F", "Gold", unit="$", dp=1, session=False), y("BTC-USD", "Bitcoin", unit="$", dp=0, session=False), y("DX-Y.NYB", "Dollar index", session=False)) if x]
    nl = now.astimezone(ET_); usd = dt.date.fromisoformat(idx[0]["date"])
    lead = fut[0] if fut else idx[0]
    mood = mood_of(lead["pct"] * 2)  # 선물은 변동이 작아서 2배로 본다
    facts = {q["name"]: f"{q['pct']:+.2f}%" for q in fut + idx[:2] + world[:3]}
    return {"region": "us", "kind": "morning", "title": "Morning Brief", "kicker": "MORNING BRIEF",
            "sub": f"Futures {nl:%-I:%M} a.m. ET · closes {usd:%-m/%-d}", "mood": mood, "pose": "a05" if mood == "flat" else POSE[mood], "facts": facts,
            "sections": [{"type": "big", "title": "Futures right now", "items": fut},
                         {"type": "mini", "title": f"Yesterday's close · {lab(usd, False)}", "items": idx, "cols": 4},
                         {"type": "heat", "title": "Overnight around the world", "items": world, "cols": 6},
                         {"type": "mini", "title": "Rates, oil & more", "items": macro, "cols": 6, "card": False}],
            "hook": {"kicker": "Before the bell", "lines": [f"{q['name'].replace(' futures', '')} {pct_rich(q['pct'], us=True)}" for q in fut[:2]], "sub": "Futures vs. yesterday's settle"},
            "foot": "Source: Yahoo Finance · not investment advice"}


SECTORS = [("XLK", "Tech"), ("XLC", "Comm."), ("XLY", "Discret."), ("XLF", "Financials"), ("XLV", "Health"), ("XLI", "Industrials"),
           ("XLP", "Staples"), ("XLE", "Energy"), ("XLB", "Materials"), ("XLU", "Utilities"), ("XLRE", "Real estate")]
MAG7 = [("AAPL", "Apple"), ("MSFT", "Microsoft"), ("NVDA", "Nvidia"), ("AMZN", "Amazon"), ("GOOGL", "Alphabet"), ("META", "Meta"), ("TSLA", "Tesla")]


def us_close(now):
    y = lambda s, n, **k: safe(yahoo, s, now, n, **k)
    spx = yahoo("^GSPC", now, "S&P 500"); day = dt.date.fromisoformat(spx["date"])
    idx = [x for x in (y("^IXIC", "Nasdaq"), y("^DJI", "Dow", dp=0), y("^RUT", "Russell 2000"), y("^SOX", "Semis (SOX)")) if x]
    sec = [x for x in (y(s, n, unit="$") for s, n in SECTORS) if x]
    mag = sorted([x for x in (y(s, n, unit="$") for s, n in MAG7) if x], key=lambda q: -q["pct"])
    macro = [x for x in (y("^TNX", "10-yr Treasury", unit="%", dp=3, kind="bp"), y("^VIX", "VIX", kind="pt"), y("CL=F", "WTI crude", unit="$", session=False),
                         y("GC=F", "Gold", unit="$", dp=1, session=False), y("BTC-USD", "Bitcoin", unit="$", dp=0, session=False), y("DX-Y.NYB", "Dollar index", session=False)) if x]
    mood = mood_of(spx["pct"])
    facts = {"S&P 500": f"{spx['last']:,.2f} ({spx['pct']:+.2f}%)", **{q["name"]: f"{q['pct']:+.2f}%" for q in idx[:2]},
             "best sector": f"{max(sec, key=lambda q: q['pct'])['name']} {max(q['pct'] for q in sec):+.2f}%" if sec else "",
             "worst sector": f"{min(sec, key=lambda q: q['pct'])['name']} {min(q['pct'] for q in sec):+.2f}%" if sec else ""}
    best = max(sec, key=lambda q: q["pct"]) if sec else None
    return {"region": "us", "kind": "close", "title": "Closing Brief", "kicker": "CLOSING BRIEF", "sub": f"{lab(day, False)} · U.S. close, 4 p.m. ET",
            "mood": mood, "pose": POSE[mood], "facts": facts, "hero": spx,
            "sections": [{"type": "hero", "title": "S&P 500 today", "item": spx, "side": [q for q in idx if q["name"] != "Russell 2000"], "side_all": idx, "ch": 90},
                         {"type": "heat", "title": "Sectors", "small": "SPDR sector ETFs", "items": sorted(sec, key=lambda q: -q["pct"])},
                         {"type": "heat", "title": "Magnificent 7", "items": mag, "cols": 7, "card": False},
                         {"type": "mini", "title": "Rates, oil & more", "items": macro, "cols": 6, "card": False}], "sectors": sec, "mag": mag,
            "hook": {"kicker": f"{lab(day, False)} close", "lines": [f"S&P 500 {pct_rich(spx['pct'], us=True)}"] + ([f"{best['name']} led {pct_rich(best['pct'], us=True)}"] if best else [])},
            "foot": "Source: Yahoo Finance · not investment advice"}


def pct_rich(p, us=False):
    return f"[[{'up' if p > 0 else 'dn' if p < 0 else 'acc'}:{p:+.2f}%]]"


BUILD = {("kr", "morning"): kr_morning, ("kr", "close"): kr_close, ("us", "morning"): us_morning, ("us", "close"): us_close}


# ------------------------------------------------------------------ 카드 (HTML → 1080x1350 JPEG)
def render_card(d, out):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH") or None)
        pg = b.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        pg.add_init_script(f"window.DATA = {json.dumps(d, ensure_ascii=False)};")
        pg.goto(f"file://{ROOT}/reels/brief_card.html")
        pg.wait_for_function("window.READY === true", timeout=60000)
        h = pg.evaluate("document.querySelector('#card').scrollHeight")
        if h > 1350: print(f"⚠ 카드 내용이 넘침: {h}px")
        pg.screenshot(path=out, type="jpeg", quality=93, clip={"x": 0, "y": 0, "width": 1080, "height": 1350})
        b.close()


def caption(d):
    ko = d["region"] == "kr"; tag = {"kr": {"morning": "#모닝브리프 #미국증시 #반도체 #나스닥 #레드덴바", "close": "#마감브리프 #코스피 #증시 #외국인 #레드덴바"},
                                      "us": {"morning": "#stockmarket #futures #premarket #investing #reddenva", "close": "#stockmarket #SP500 #Nasdaq #investing #reddenva"}}
    lines = [f"{d['title']} · {d['sub']}", "", f"🐾 {d['comment']}"]
    if d.get("news"): lines += [""] + [f"• {n['head']}: {n['line']}" for n in d["news"]]
    lines += ["", ("투자 권유 아님 · 자료 " if ko else "Not investment advice · Data: ") + d["foot"].split(":", 1)[-1].split("·")[0].strip(), "", tag[d["region"]][d["kind"]]]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--region", required=True, choices=["kr", "us"]); ap.add_argument("--kind", required=True, choices=["morning", "close"])
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true"); ap.add_argument("--asof", help="이 시각 기준으로 만들기 (현지 시각, 시안용)")
    ap.add_argument("--from-json", help="저장해둔 데이터로 카드만 다시 그리기"); ap.add_argument("--out")
    a = ap.parse_args()
    tz = KST if a.region == "kr" else LA
    now = dt.datetime.fromisoformat(a.asof).replace(tzinfo=tz) if a.asof else dt.datetime.now(tz)
    day = now.date(); os.makedirs("out", exist_ok=True)
    lp = f"out/{a.kind}-{a.region}-latest.json"
    if not a.force and not a.from_json:
        hol, mkt = (KRX_HOL, "KRX") if a.region == "kr" else (NYSE_HOL, "NYSE")
        if day.weekday() >= 5 or day in hol: print(f"{mkt} 휴장일 → 건너뜀"); return
        if os.path.exists(lp) and json.load(open(lp, encoding="utf-8")).get("date") == day.isoformat(): print("오늘 이미 만들었음"); return
    if a.from_json:
        d = json.load(open(a.from_json, encoding="utf-8"))
    else:
        t = time.time(); d = BUILD[(a.region, a.kind)](now); print(f"시세 {time.time() - t:.0f}초")
        ch = chips(now, a.region == "kr", a.kind)
        if ch:
            d["sections"].insert(0, ch); d["chips"] = ch
            for q in ch["dram"][:1] + ch["gpu"][:1]: d["facts"][q["name"] + (" GPU 시간당 임대료" if q in ch["gpu"] else " D램 현물")] = f"${q['last']} ({q['pct']:+.2f}%, 1주 {q['w1']:+.2f}%)" if q.get("w1") is not None else f"${q['last']} ({q['pct']:+.2f}%)"
            print("반도체", [(q["name"], q["last"], q["pct"], q["date"]) for q in ch["dram"] + ch["gpu"]])
        if a.kind == "morning":
            d["wx"] = safe(today_wx, a.region, day); print("날씨", d["wx"])
            if d["wx"]: w = d["wx"]; d["facts"]["오늘 " + w["city"] + " 날씨" if a.region == "kr" else w["city"] + " weather today"] = f"{w['sky']} {w['hi']}°/{w['lo']}° 강수 {w['rain']}%"
        d["comment"] = quip(a.region, a.kind, d["facts"], d["mood"])
        try: d["news"] = news3(a.region, a.kind, now, d["facts"])
        except Exception as e: print("뉴스 건너뜀:", type(e).__name__, e); d["news"] = []
        if d["news"]: d["sections"].append({"type": "news", "title": "오늘의 뉴스" if a.region == "kr" else "Headlines", "items": d["news"]})
        d.update(day=day.isoformat(), handle=f"@reddenva.{a.region}", made=now.isoformat())
    out = a.out or f"out/{a.kind}-{a.region}-{day.isoformat()}.jpg"
    render_card(d, os.path.abspath(out)); print("카드:", out)
    cap = caption(d); print(cap)
    import reel_data
    reel_data.save(a.kind, a.region, dict(d, cards=[os.path.abspath(out)]))
    json.dump(d, open(out.replace(".jpg", ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if a.dry_run or a.from_json: print("(dry-run) 게시용 정보 안 씀"); return
    from books import git_push
    git_push(["out"], f"{a.kind} {a.region} {day} card")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    url = f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{sha}/{out}"
    for _ in range(12):
        if requests.head(url, timeout=15).ok: break
        time.sleep(5)
    json.dump({"date": day.isoformat(), "image_url": url, "caption": cap, "title": d["title"]}, open(lp, "w", encoding="utf-8"), ensure_ascii=False)
    git_push(["out"], f"{a.kind} {a.region} {day} latest.json"); print("저장 완료:", url)


if __name__ == "__main__":
    main()
