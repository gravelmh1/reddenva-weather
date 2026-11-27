"""수요일 시리즈 "레드덴바의 동전 던지기": 다음 주 수요일까지 지수가 오를지 내릴지 동전으로 정한다. (앞면 = 오른다, 뒷면 = 내린다)

- 종목은 절대 안 나온다 (리딩질 금지). 한국판 = 코스피, 미국판 = 나스닥 종합지수만.
- 매주 수요일: ① 지난주 동전(오른다/내린다)이 맞았는지 확인 (지난 수요일 → 오늘, 지수 등락) ② 누적 적중 전적 ③ 새 동전.
- 동전은 진짜 무작위(반반). 기록은 state/dart_{region}.json. 지수: 코스피 = 네이버 증권, 나스닥 = Yahoo Finance (둘 다 무료).

  python dart.py --region kr [--dry-run] [--force] [--day 2026-12-02] [--demo 4]
  --demo N: 시험용. 지난 N주 수요일에 이미 던졌던 것처럼 과거 지수로 채워서 'N+1주차' 모습을 미리 본다 (state 저장 안 함)
"""
import argparse, datetime as dt, json, os, random, re, subprocess, time
from zoneinfo import ZoneInfo
import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
CFG = {"kr": dict(index="KOSPI", index_name="코스피", tz="Asia/Seoul", src="네이버 증권"),
       "us": dict(index="^IXIC", index_name="Nasdaq", tz="America/Los_Angeles", src="Yahoo Finance")}


def get(url, **kw):
    hd = {**H, **kw.pop("headers", {})}
    for i in range(4):
        try:
            r = requests.get(url, headers=hd, timeout=25, **kw); r.raise_for_status(); return r
        except Exception:
            if i == 3: raise
            time.sleep(3 + 4 * i)


def closes(region):
    """{날짜: 종가} 약 6개월 + 지금 값. 장중이면 마지막 값이 현재가."""
    if region == "kr":
        t = get("https://fchart.stock.naver.com/sise.nhn", params={"symbol": "KOSPI", "timeframe": "day", "count": 140, "requestType": 0}).content.decode("euc-kr", "replace")
        c = {dt.datetime.strptime(a.split("|")[0], "%Y%m%d").date(): float(a.split("|")[4]) for a in re.findall(r'data="([^"]+)"', t)}
        if not c: raise RuntimeError("코스피 시세 없음")
        return c, c[max(c)]
    j = get("https://query1.finance.yahoo.com/v8/finance/chart/%5EIXIC", params={"range": "6mo", "interval": "1d"}).json()["chart"]["result"][0]
    tz = ZoneInfo(j["meta"].get("exchangeTimezoneName", "America/New_York"))
    c = {dt.datetime.fromtimestamp(t, tz).date(): v for t, v in zip(j.get("timestamp", []), j["indicators"]["quote"][0]["close"]) if v}
    return c, float(j["meta"].get("regularMarketPrice") or c[max(c)])


def on(c, day):
    ds = [d for d in c if d <= day]
    return c[max(ds)] if ds else None


def record(picks):
    done = [p for p in picks if "result" in p]
    hit = sum(1 for p in done if p["hit"])
    return {"n": len(done), "hit": hit, "miss": len(done) - hit, "rate": hit / len(done) if done else 0,
            "streak": [p["hit"] for p in done][-12:]}


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
    rng = random.SystemRandom(); c, now = closes(region)
    level = lambda d: now if d >= dt.datetime.now(tz).date() else on(c, d)

    if a.demo:  # 지난 N주 수요일에 던졌던 척 (과거 지수)
        for k in range(a.demo, 0, -1):
            d0 = today - dt.timedelta(weeks=k)
            st["picks"].append({"week": len(st["picks"]) + 1, "date": d0.isoformat(), "call": rng.choice(["up", "down"]), "entry": level(d0)})

    if st["picks"] and st["picks"][-1]["date"] == day:  # 오늘 이미 던졌으면 그대로 (재실행)
        new = st["picks"][-1]
    else:
        # 지난 동전들 채점: 던진 날 → 1주 뒤(오늘) 지수
        for p in st["picks"]:
            if "result" in p: continue
            d1 = dt.date.fromisoformat(p["date"]) + dt.timedelta(days=7)
            if d1 > today: continue
            end = level(min(d1, today)); chg = end / p["entry"] - 1
            p.update(exit=end, result=chg, hit=(chg > 0) == (p["call"] == "up"))
        new = {"week": len(st["picks"]) + 1, "date": day, "call": rng.choice(["up", "down"]), "entry": now}
        st["picks"].append(new)
    done = [p for p in st["picks"][:-1] if "result" in p]
    last = done[-1] if done else None
    rec = record(st["picks"][:-1])
    print(json.dumps({"new": new, "last": last, "rec": rec}, ensure_ascii=False))

    import dart_render
    card = dict(region=region, day=day, handle=f"@reddenva.{region}", week=new["week"], new=new, last=last, rec=rec, index_name=cfg["index_name"],
                top=(f"WEDNESDAY COIN · {today:%Y.%m.%d} ({'월화수목금토일'[today.weekday()]})" if ko else f"WEDNESDAY COIN · {today:%b %d, %Y} ({today:%a})".upper()),
                foot=(f"동전이 정한 방향 · 리딩질 금지 · 레드덴바는 책임 안 짐 · 지수: {cfg['src']}" if ko else
                      f"A coin decided it, not a forecast · Red Denva takes no responsibility · Index: {cfg['src']}"))
    img_rel = f"out/dart-{region}-{day}.jpg"; dart_render.card(card, img_rel)
    up = new["call"] == "up"
    if ko:
        res = (f"지난주 동전 {'적중' if last['hit'] else '빗나감'} ({cfg['index_name']} {last['result']:+.1%}) · 누적 {rec['hit']}승 {rec['miss']}패\n" if last else "")
        cap = (f"🪙 다음 주 수요일까지 {cfg['index_name']}는… {'오른다 📈' if up else '내린다 📉'} (레드덴바가 동전 던져서 정함)\n{res}\n"
               f"#동전던지기 #레드덴바 #코스피 #주식 #리딩질금지 #수요일")
    else:
        res = (f"Last week's coin: {'hit' if last['hit'] else 'miss'} (Nasdaq {last['result']:+.1%}) · record {rec['hit']}-{rec['miss']}\n" if last else "")
        cap = (f"🪙 By next Wednesday the Nasdaq will go… {'UP 📈' if up else 'DOWN 📉'} (Red Denva flipped a coin)\n{res}\n"
               f"#coinflip #reddenva #nasdaq #stocks #wednesday")
    import reel_data
    reel_data.save("dart", region, {"c": card, "cards": [os.path.abspath(img_rel)], "day": day})
    if not a.demo and not a.dry_run: json.dump(st, open(sf, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if a.dry_run: print("(dry-run) 카드 저장:", img_rel); print(cap); return
    from books import git_push
    git_push(["out", "state"], f"dart {region} {day} card")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    url = f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{sha}/{img_rel}"
    for _ in range(12):
        if requests.head(url, timeout=15).ok: break
        time.sleep(5)
    json.dump({"date": day, "image_url": url, "caption": cap, "title": "coin flip"}, open(lp, "w", encoding="utf-8"), ensure_ascii=False)
    git_push(["out"], f"dart {region} {day} latest.json"); print("저장 완료:", url)


if __name__ == "__main__":
    main()
