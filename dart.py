"""수요일 시리즈 "레드덴바 다트 투자": 원숭이 다트 실험의 레드덴바 버전.

- 매주 수요일 레드덴바가 눈 감고 다트를 던져 한 종목을 고른다 (한국판 = 코스피 시가총액 상위 200, 미국판 = S&P 500). 진짜 무작위.
- 고른 종목에 가상으로 100만 원 / $1,000 을 넣고 계속 들고 간다. 같은 돈을 같은 날 지수(코스피 / S&P 500)에 넣었을 때와 누적 성적을 비교.
- 기록은 state/dart_{region}.json. 시세는 Yahoo Finance 차트(무료). 종목 한 줄 소개만 Gemini.

  python dart.py --region kr [--dry-run] [--force] [--day 2026-12-02] [--demo 3]
  --demo N: 시험용. 지난 N주 수요일에 이미 던졌던 것처럼 과거 시세로 채워서 'N+1주차' 모습을 미리 본다 (state 저장 안 함)
"""
import argparse, datetime as dt, json, os, random, re, subprocess, sys, time
from zoneinfo import ZoneInfo
import requests
import weather
from books import git_push, models

H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
CFG = {"kr": dict(index="^KS11", index_name="코스피", amount=1_000_000, cur="원", tz="Asia/Seoul"),
       "us": dict(index="^GSPC", index_name="S&P 500", amount=1000, cur="$", tz="America/Los_Angeles")}

# 네이버·위키백과가 안 될 때 쓰는 예비 종목판 (대형주)
KR_FALLBACK = [("005930", "삼성전자"), ("000660", "SK하이닉스"), ("373220", "LG에너지솔루션"), ("207940", "삼성바이오로직스"), ("005380", "현대차"),
               ("000270", "기아"), ("068270", "셀트리온"), ("035420", "NAVER"), ("035720", "카카오"), ("005490", "POSCO홀딩스"), ("051910", "LG화학"),
               ("006400", "삼성SDI"), ("105560", "KB금융"), ("055550", "신한지주"), ("012330", "현대모비스"), ("028260", "삼성물산"), ("066570", "LG전자"),
               ("003550", "LG"), ("034730", "SK"), ("017670", "SK텔레콤"), ("030200", "KT"), ("015760", "한국전력"), ("032830", "삼성생명"),
               ("086790", "하나금융지주"), ("316140", "우리금융지주"), ("009150", "삼성전기"), ("018260", "삼성에스디에스"), ("010130", "고려아연"),
               ("011200", "HMM"), ("003670", "포스코퓨처엠"), ("096770", "SK이노베이션"), ("033780", "KT&G"), ("090430", "아모레퍼시픽"),
               ("259960", "크래프톤"), ("352820", "하이브"), ("329180", "HD현대중공업"), ("012450", "한화에어로스페이스"), ("042660", "한화오션"),
               ("010950", "S-Oil"), ("024110", "기업은행"), ("000810", "삼성화재"), ("034020", "두산에너빌리티"), ("323410", "카카오뱅크"),
               ("097950", "CJ제일제당"), ("271560", "오리온"), ("036570", "엔씨소프트"), ("251270", "넷마블"), ("011170", "롯데케미칼")]
US_FALLBACK = [("AAPL", "Apple"), ("MSFT", "Microsoft"), ("NVDA", "Nvidia"), ("AMZN", "Amazon"), ("GOOGL", "Alphabet"), ("META", "Meta Platforms"),
               ("TSLA", "Tesla"), ("BRK-B", "Berkshire Hathaway"), ("JPM", "JPMorgan Chase"), ("V", "Visa"), ("JNJ", "Johnson & Johnson"), ("WMT", "Walmart"),
               ("PG", "Procter & Gamble"), ("MA", "Mastercard"), ("HD", "Home Depot"), ("XOM", "ExxonMobil"), ("KO", "Coca-Cola"), ("PEP", "PepsiCo"),
               ("COST", "Costco"), ("DIS", "Disney"), ("NKE", "Nike"), ("MCD", "McDonald's"), ("SBUX", "Starbucks"), ("NFLX", "Netflix"), ("ADBE", "Adobe"),
               ("CRM", "Salesforce"), ("INTC", "Intel"), ("AMD", "AMD"), ("CSCO", "Cisco"), ("ORCL", "Oracle"), ("IBM", "IBM"), ("BA", "Boeing"),
               ("CAT", "Caterpillar"), ("GE", "GE Aerospace"), ("F", "Ford"), ("GM", "General Motors"), ("UBER", "Uber"), ("ABNB", "Airbnb"),
               ("PYPL", "PayPal"), ("T", "AT&T"), ("VZ", "Verizon"), ("CVS", "CVS Health"), ("UNH", "UnitedHealth"), ("LLY", "Eli Lilly"), ("PFE", "Pfizer"),
               ("MRK", "Merck"), ("CMG", "Chipotle"), ("DPZ", "Domino's"), ("HSY", "Hershey"), ("LULU", "Lululemon")]


def get(url, **kw):
    for i in range(3):
        try:
            r = requests.get(url, headers={**H, **kw.pop("headers", {})}, timeout=25, **kw); r.raise_for_status(); return r
        except Exception:
            if i == 2: raise
            time.sleep(2 + 2 * i)


# ------------------------------------------------------------------ 종목판
def universe(region):
    """[(야후 심볼, 이름)] 200~500개. 실패하면 예비 목록."""
    try:
        if region == "kr":
            out = []
            for page in (1, 2):
                j = get("https://m.stock.naver.com/api/stocks/marketValue/KOSPI", params={"page": page, "pageSize": 100}).json()
                for s in j.get("stocks", []):
                    code, name = s.get("itemCode", ""), s.get("stockName", "")
                    if re.fullmatch(r"\d{6}", code) and not re.search(r"우$|우B$|우\(|스팩|리츠|ETN|KODEX|TIGER", name): out.append((code + ".KS", name))
            if len(out) >= 120: return out[:200]
            print("네이버 종목판 부족:", len(out))
        else:
            from bs4 import BeautifulSoup
            t = BeautifulSoup(get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies").text, "html.parser").select_one("table#constituents")
            out = [(tr.select("td")[0].get_text(strip=True).replace(".", "-"), tr.select("td")[1].get_text(strip=True)) for tr in t.select("tbody tr") if tr.select("td")]
            if len(out) >= 400: return out
            print("위키 S&P 500 목록 부족:", len(out))
    except Exception as e: print("종목판 받기 실패 → 예비 목록:", type(e).__name__, str(e)[:80])
    return [(c + ".KS", n) for c, n in KR_FALLBACK] if region == "kr" else US_FALLBACK


# ------------------------------------------------------------------ 시세
_cache = {}


def series(sym):
    """(날짜→종가 dict, 현재가). 6개월치 일봉."""
    if sym in _cache: return _cache[sym]
    j = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(sym)}", params={"range": "6mo", "interval": "1d"}).json()["chart"]["result"][0]
    tz = ZoneInfo(j["meta"].get("exchangeTimezoneName", "UTC"))
    closes = {dt.datetime.fromtimestamp(t, tz).date(): c for t, c in zip(j.get("timestamp", []), j["indicators"]["quote"][0]["close"]) if c}
    now = j["meta"].get("regularMarketPrice") or closes[max(closes)]
    _cache[sym] = (closes, float(now)); return _cache[sym]


def price_on(sym, day):
    """그날(없으면 그 전 마지막 거래일) 종가."""
    closes, _ = series(sym); ds = [d for d in closes if d <= day]
    return closes[max(ds)] if ds else None


def now_price(sym): return series(sym)[1]


# ------------------------------------------------------------------ 한 줄 소개 (Gemini)
def blurb(name, sym, region):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    ko = region == "kr"
    fallback = ("뭐 하는 회사인지는 각자 검색." if ko else "Google it. I didn't.")
    if not key: return {"what": "", "quip": fallback}
    prompt = f"""Company: {name} (ticker {sym}). Write for an Instagram card where a sleepy red panda picked this stock by throwing a dart blindfolded.
Return ONLY JSON: {{"what": "{'what the company mainly does, plain everyday Korean, max 18 chars, no hype (예: 반도체 메모리 만드는 회사)' if ko else 'what the company mainly does, plain English, max 34 chars, no hype'}",
"quip": "{'레드덴바의 시큰둥한 한마디. 건조하고 세련된 유머, 이모지·느낌표 금지, 투자 조언처럼 들리면 안 됨, max 18 chars (예: 이름은 들어봤음)' if ko else 'the red panda deadpan one-liner, dry sleek humor, no emoji or exclamation marks, must not sound like investment advice, max 32 chars'}"}}
Only state facts you are sure about. If you do not know the company well, keep "what" very generic (e.g. industry only)."""
    for m in models(key)[:4]:
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", headers={"x-goog-api-key": key},
                              json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": .7, "responseMimeType": "application/json"}}, timeout=40)
            j = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
            lim = 20 if ko else 38
            if 0 < len(j["what"]) <= lim and 0 < len(j["quip"]) <= lim and "!" not in j["quip"]: return j
        except Exception as e: print("Gemini", m, type(e).__name__)
    return {"what": "", "quip": fallback}


# ------------------------------------------------------------------ 성적
def score(region, picks, day):
    """각 픽의 지금 가치, 같은 돈을 지수에 넣었으면의 가치."""
    cfg = CFG[region]; rows = []
    for p in picks:
        cur = now_price(p["sym"]); idx_now = now_price(cfg["index"])
        r = cur / p["entry"] - 1; ri = idx_now / p["entry_idx"] - 1
        # 주간 대결: 던진 날부터 1주일 동안 그 종목 vs 지수 (아직 1주가 안 됐으면 지금까지)
        d1 = dt.date.fromisoformat(p["date"]) + dt.timedelta(days=7)
        if d1 < day:
            wr = price_on(p["sym"], d1) / p["entry"] - 1; wi = price_on(cfg["index"], d1) / p["entry_idx"] - 1
        else: wr, wi = r, ri
        rows.append({**p, "now": cur, "ret": r, "idx_ret": ri, "wk_ret": wr, "wk_idx": wi, "win": wr > wi})
    inv = sum(p["amount"] for p in rows)
    val = sum(p["amount"] * (1 + p["ret"]) for p in rows); vali = sum(p["amount"] * (1 + p["idx_ret"]) for p in rows)
    wins = sum(1 for p in rows if p["win"])
    return rows, {"wins": wins, "losses": len(rows) - wins, "invested": inv, "value": val, "value_idx": vali, "ret": val / inv - 1 if inv else 0, "ret_idx": vali / inv - 1 if inv else 0}


def throw(uni, used, rng):
    cand = [u for u in uni if u[0] not in used] or uni
    return rng.choice(cand)


def board(uni, hit, rng, n=24):
    """다트판에 보여줄 종목 24개 (맞은 종목 포함, 위치 무작위)."""
    others = rng.sample([u for u in uni if u[0] != hit[0]], min(n - 1, len(uni) - 1))
    b = others + [hit]; rng.shuffle(b); return b


# ------------------------------------------------------------------ 메인
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--region", required=True, choices=["kr", "us"])
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--day"); ap.add_argument("--demo", type=int, default=0)
    a = ap.parse_args(); region = a.region; cfg = CFG[region]; ko = region == "kr"
    tz = ZoneInfo(cfg["tz"]); today = dt.date.fromisoformat(a.day) if a.day else dt.datetime.now(tz).date(); day = today.isoformat()
    os.makedirs("out", exist_ok=True); os.makedirs("state", exist_ok=True)
    if not a.force and today.weekday() != 2: print("수요일이 아님 → 건너뜀"); return
    lp = f"out/dart-{region}-latest.json"
    if not a.force and os.path.exists(lp) and json.load(open(lp, encoding="utf-8")).get("date") == day: print("오늘 이미 만들었음. 건너뜀"); return
    sf = f"state/dart_{region}.json"
    st = json.load(open(sf, encoding="utf-8")) if os.path.exists(sf) and not a.demo else {"picks": []}
    rng = random.SystemRandom(); uni = universe(region); print("종목판", len(uni), "개")

    if a.demo:  # 지난 N주 수요일에 던졌던 척 (과거 시세)
        for k in range(a.demo, 0, -1):
            d0 = today - dt.timedelta(weeks=k); s, n = throw(uni, {p["sym"] for p in st["picks"]}, rng)
            try: st["picks"].append({"week": len(st["picks"]) + 1, "date": d0.isoformat(), "sym": s, "name": n, "entry": price_on(s, d0),
                                     "entry_idx": price_on(cfg["index"], d0), "amount": cfg["amount"]})
            except Exception as e: print("데모 시세 실패", s, e)
        st["picks"] = [p for p in st["picks"] if p["entry"] and p["entry_idx"]]

    if st["picks"] and st["picks"][-1]["date"] == day:  # 오늘 이미 던졌으면 그대로 (재실행)
        new = st["picks"][-1]; prev = st["picks"][:-1]
    else:
        for _ in range(8):
            s, n = throw(uni, {p["sym"] for p in st["picks"]}, rng)
            try:
                new = {"week": len(st["picks"]) + 1, "date": day, "sym": s, "name": n, "entry": now_price(s), "entry_idx": now_price(cfg["index"]), "amount": cfg["amount"]}
                break
            except Exception as e: print("시세 없음, 다시 던짐:", s, type(e).__name__)
        else: raise RuntimeError("다트가 계속 빗나감 (시세 받기 실패)")
        new.update(blurb(n, s, region)); prev = list(st["picks"])
        st["picks"].append(new)
    rows, tot = score(region, prev, today) if prev else ([], None)
    last = rows[-1] if rows else None
    b = board(uni, (new["sym"], new["name"]), rng)
    print(json.dumps({"new": new, "last": last, "tot": tot}, ensure_ascii=False, default=str))

    import dart_render
    c = dict(region=region, day=day, handle=f"@reddenva.{region}", week=new["week"], new=new, last=last, tot=tot, rows=rows,
             index_name=cfg["index_name"], amount=cfg["amount"],
             top=(f"WEDNESDAY DART · {today:%Y.%m.%d} ({'월화수목금토일'[today.weekday()]})" if ko else f"WEDNESDAY DART · {today:%b %d, %Y} ({today:%a})".upper()),
             foot=("다트가 고른 종목 · 리딩질 금지 · 레드덴바는 책임 안 짐 (가상 투자) · 시세: Yahoo Finance" if ko else
                   "A dart picked it, not a tip · Red Denva takes no responsibility (paper money) · Prices: Yahoo Finance"))
    img_rel = f"out/dart-{region}-{day}.jpg"; dart_render.card(c, img_rel)
    nm = new["name"]
    if ko:
        res = (f"주간 전적 다트 {tot['wins']}승 {tot['losses']}패 · 누적 레드덴바 {tot['ret']:+.1%} vs {cfg['index_name']} {tot['ret_idx']:+.1%}\n다트가 고른 종목이에요. 리딩질 금지.\n" if tot else "다트가 고른 종목이에요. 리딩질 금지.\n")
        cap = f"🎯 레드덴바 다트 투자 {new['week']}주차: {nm}\n{res}\n#다트투자 #레드덴바 #주식 #코스피 #가상투자 #수요일"
    else:
        res = (f"Weekly record: darts {tot['wins']}-{tot['losses']} · total Red Denva {tot['ret']:+.1%} vs S&P 500 {tot['ret_idx']:+.1%}\nA dart picked it. Not a tip.\n" if tot else "A dart picked it. Not a tip.\n")
        cap = f"🎯 Red Denva dart portfolio, week {new['week']}: {nm}\n{res}\n#dartboard #reddenva #stocks #sp500 #papertrading #wednesday"
    import reel_data
    reel_data.save("dart", region, {"c": {k: v for k, v in c.items()}, "board": [list(x) for x in b], "cards": [os.path.abspath(img_rel)], "day": day})
    if not a.demo: json.dump(st, open(sf, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if a.dry_run: print("(dry-run) 카드 저장:", img_rel); print(cap); return
    git_push(["out", "state"], f"dart {region} {day} card")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    url = f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{sha}/{img_rel}"
    for _ in range(12):
        if requests.head(url, timeout=15).ok: break
        time.sleep(5)
    json.dump({"date": day, "image_url": url, "caption": cap, "title": "dart portfolio"}, open(lp, "w", encoding="utf-8"), ensure_ascii=False)
    git_push(["out"], f"dart {region} {day} latest.json"); print("저장 완료:", url)


if __name__ == "__main__":
    main()
