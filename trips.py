"""금요일 시리즈 "주말 여행 추천" (WEEKEND PICK): 3장 캐러셀.
한국판 = 서울 안 나들이 장소, 미국판 = LA 근교~캘리포니아. 장소와 사실 정보는 trips_data.py 목록에서만 가져오고,
주말(토·일) 날씨는 그 장소 좌표로 Open-Meteo에서 받는다. Gemini는 위키미디어 후보 사진을 직접 보고 3장을 고르고
짧은 문구(추천 이유·사진 설명·팁·레드덴바 한마디)만 쓴다.

  python trips.py --region kr [--dry-run] [--force]
결과: out/trip-{region}-{day}-{1,2,3}.jpg, out/trip-{region}-latest.json (image_url, image_url2, image_url3)
"""
import argparse, base64, datetime as dt, io, json, os, random, re, subprocess, time
import tags
from zoneinfo import ZoneInfo
import requests
from PIL import Image
import trips_data, trips_render
from animals import commons, UA
from books import git_push, models

TZ = {"kr": "Asia/Seoul", "us": "America/Los_Angeles"}
SEASON = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring", 6: "summer", 7: "summer", 8: "summer", 9: "fall", 10: "fall", 11: "fall"}


def sky(code, ko):
    if code >= 95: return "천둥번개" if ko else "Storms"
    if code in (71, 73, 75, 77, 85, 86): return "눈" if ko else "Snow"
    if code >= 51: return "비" if ko else "Rain"
    if code in (45, 48): return "안개" if ko else "Fog"
    if code == 0: return "맑음" if ko else "Sunny"
    if code in (1, 2): return "구름 조금" if ko else "Some clouds"
    return "흐림" if ko else "Cloudy"


def weekend_weather(spots, region, sat):
    """여러 장소를 한 번에 요청. 실패하면 None들."""
    unit = "celsius" if region == "kr" else "fahrenheit"
    for wait in (0, 4, 8, 12):
        time.sleep(wait)
        try:
            r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=(10, 40), params={
                "latitude": ",".join(str(s["lat"]) for s in spots), "longitude": ",".join(str(s["lon"]) for s in spots),
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code", "timezone": TZ[region],
                "start_date": sat.isoformat(), "end_date": (sat + dt.timedelta(days=1)).isoformat(), "temperature_unit": unit})
            r.raise_for_status(); js = r.json(); js = js if isinstance(js, list) else [js]
            out = []
            for j in js:
                d = j["daily"]
                out.append([dict(hi=round(d["temperature_2m_max"][i]), lo=round(d["temperature_2m_min"][i]), rain=int(d["precipitation_probability_max"][i] or 0),
                                 code=int(d["weather_code"][i] or 0)) for i in range(2)])
            return out
        except Exception as e:
            print("주말 날씨 실패:", str(e)[:100])
    return [None] * len(spots)


def ranked(region, today, used, wx):
    """계절·날씨·최근 사용 여부로 순서를 정한다(같은 주면 같은 순서)."""
    spots = trips_data.KR if region == "kr" else trips_data.US
    season = SEASON[today.month]; rnd = random.Random(today.isocalendar()[0] * 100 + today.isocalendar()[1] + (0 if region == "kr" else 50))
    scored = []
    for s, w in zip(spots, wx):
        if s["name"] in used: continue
        sc = rnd.random()
        if season in s["seasons"].split(): sc += 2
        if w:
            wet = max(x["rain"] for x in w) >= 60; cold = min(x["lo"] for x in w) <= (-5 if region == "kr" else 30)
            if (wet or cold) and s["indoor"]: sc += 1.5
            if wet and not s["indoor"]: sc -= 2
        scored.append((sc, s, w))
    return [(s, w) for sc, s, w in sorted(scored, key=lambda x: -x[0])]


def photos_for(spot):
    seen, out = set(), []
    for q in spot["q"]:
        try: cs = commons(q)
        except Exception as e: print("  사진 검색 실패", q, str(e)[:60]); continue
        for c in cs:
            if c["id"] in seen: continue
            seen.add(c["id"])
            try:
                r = requests.get(c["url"], headers=UA, timeout=25); r.raise_for_status()
                c["im"] = Image.open(io.BytesIO(r.content)).convert("RGB"); out.append(c)
            except Exception as e: print("  사진 받기 실패", str(e)[:60])
            if len(out) >= 12: return out
    return out


def season_note(region, d):
    m, part = d.month, ("early" if d.day <= 10 else "mid" if d.day <= 20 else "late")
    if region == "kr":
        notes = {11: {"early": "autumn foliage near its peak in Seoul", "mid": "late autumn in Seoul; foliage past peak, many leaves falling", "late": "late autumn turning to early winter in Seoul; most leaves have fallen, cold"},
                 12: "early winter in Seoul, bare trees, cold", 1: "midwinter in Seoul, cold, bare trees, possible snow", 2: "late winter in Seoul, cold",
                 3: "early spring in Seoul; blossoms start late March", 4: "spring in Seoul; cherry blossoms early April", 5: "late spring in Seoul, fresh green",
                 6: "early summer in Seoul", 7: "summer monsoon season in Seoul", 8: "hot summer in Seoul", 9: "early autumn in Seoul, still green", 10: "autumn in Seoul; foliage starts late October"}
    else:
        notes = {11: "late fall in Southern California; mild days, cool nights, desert season is ideal", 12: "winter in Southern California; mild coast, snow in mountains",
                 1: "winter in Southern California; snow in mountains, green hills after rain", 2: "late winter in Southern California", 3: "spring in Southern California; wildflowers in deserts",
                 4: "spring in Southern California; wildflowers", 5: "late spring in Southern California; May Gray on the coast", 6: "early summer; June Gloom on the coast, deserts get hot",
                 7: "summer; deserts very hot, beaches busy", 8: "hot summer; deserts dangerously hot", 9: "early fall; still hot inland", 10: "fall in Southern California; warm days"}
    n = notes[m]; return n[part] if isinstance(n, dict) else n


def judge(spot, cands, w, region, today):
    key = os.environ["GEMINI_API_KEY"].strip(); ko = region == "kr"; parts = []
    for i, c in enumerate(cands):
        im = c["im"].copy(); im.thumbnail((560, 560)); b = io.BytesIO(); im.save(b, "JPEG", quality=78)
        parts += [{"text": f"[photo {i}] file: {c['id'][:90]}"}, {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(b.getvalue()).decode()}}]
    wtxt = "unknown" if not w else (f"Sat {sky(w[0]['code'], False)} {w[0]['hi']}/{w[0]['lo']}, rain {w[0]['rain']}%; "
                                     f"Sun {sky(w[1]['code'], False)} {w[1]['hi']}/{w[1]['lo']}, rain {w[1]['rain']}% ({'°C' if ko else '°F'})")
    facts = {k: spot[k] for k in ("name", "area", "how", "hours", "fee", "course") if spot.get(k)}
    lang = ("Korean (natural, casual-polite ~해요 or noun endings; easy everyday words)" if ko else "English")
    lim = dict(why=22, cap=14, tip=26, aside=20) if ko else dict(why=46, cap=28, tip=50, aside=34)
    prompt = f"""You are the photo editor and writer of a weekly Instagram carousel "WEEKEND PICK" recommending ONE place to visit this weekend.
Place facts (the ONLY facts you may use): {json.dumps(facts, ensure_ascii=False)}
Today: {today.isoformat()}. Season reality check: {season_note(region, today)}. Weekend weather there: {wtxt}.
1) From the photos choose exactly 3 that best SELL a visit: real photos of THIS place, beautiful, sharp, well lit, different views (no near-duplicates).
   The photos must look like what a visitor would see THIS weekend: reject photos that clearly show a different season (e.g. lush summer green or spring blossoms in late autumn/winter, snow in summer). Season-neutral views (buildings, sea, rocks, sky, night) are fine.
   Reject: maps, signs/station boards, shop interiors, close-up faces, watermarks/big text, construction, animals in cages, blurry or dark photos. Avoid photos where random people are the main subject.
   Order them: first = the most striking cover photo. Rate honestly how much the 3 photos together make people want to go, 1-10, as "score" (10 = travel magazine quality; dull alleys, gray skies, clutter, wires = low). If fewer than 3 photos qualify or the score is below 7, return {{"photos": [], "score": n}}.
2) Write in {lang}:
   - "why": one-line reason to go THIS weekend, true to the season reality and the weather (never claim peak foliage/blossoms unless the season note says so). max {lim['why']} chars.
   - for each chosen photo "cap": an inviting label of what the view is (e.g. "{'호수 위 노을' if ko else 'Golden hour on the bluffs'}"), not a dry description; never mention "person/people". max {lim['cap']} chars.
   - "tip": one practical tip about timing, clothing or what to bring, based on the weekend weather. Do NOT repeat the directions, hours or fees above, and add no new facts. max {lim['tip']} chars.
   - "aside": deadpan dry one-liner by the bored red panda mascot "Red Denva", related to the place or weather. max {lim['aside']} chars. No emoji, no exclamation marks.
Return ONLY JSON: {{"score": 1..10, "photos": [{{"i": index, "cap": "...", "fx": 0..1, "fy": 0..1}}, ...3], "why": "...", "tip": "...", "aside": "..."}}
(fx, fy = where the main subject is, as a fraction of width/height, for cropping)."""
    last = None
    for m in models(key)[:4] * 2:
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", headers={"x-goog-api-key": key}, timeout=90,
                          json={"contents": [{"parts": parts + [{"text": prompt}]}], "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"}})
        if not r.ok: last = f"{m} {r.status_code}"; print("모델 건너뜀:", last); time.sleep(2); continue
        try:
            j = json.loads(re.sub(r"^```json|```$", "", r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()).strip())
            ph = j.get("photos") or []
            if not ph or int(j.get("score", 10)) < 7: print("  사진 부족/매력 부족 판정:", m, j.get("score")); return None
            ids = [int(p["i"]) for p in ph[:3]]
            assert len(set(ids)) == 3 and all(0 <= i < len(cands) for i in ids)
            for k in ("why", "tip", "aside"):
                j[k] = j[k].strip().strip('"'); assert j[k] and len(j[k]) <= lim[k] + 4, f"{k} 길이"
            for p in ph[:3]:
                p["cap"] = p["cap"].strip(); assert p["cap"] and len(p["cap"]) <= lim["cap"] + 3, "cap 길이"
            j["photos"] = ph[:3]; print("판정 모델:", m); return j
        except Exception as e: last = f"{m} 검증 실패 {e}"; print("모델 건너뜀:", last)
    raise RuntimeError(f"Gemini 실패: {last}")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--region", required=True, choices=["kr", "us"])
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true"); a = ap.parse_args()
    region = a.region; ko = region == "kr"
    now = dt.datetime.now(ZoneInfo(TZ[region])); today = now.date(); day = today.isoformat()
    os.makedirs("out", exist_ok=True); os.makedirs("state", exist_ok=True)
    if not a.force and today.weekday() != 4: print("금요일이 아님 → 건너뜀"); return
    lp = f"out/trip-{region}-latest.json"
    if not a.force and os.path.exists(lp) and json.load(open(lp, encoding="utf-8")).get("date") == day: print("오늘 이미 만들었음"); return
    sf = f"state/trip_{region}.txt"; hist = open(sf, encoding="utf-8").read().splitlines() if os.path.exists(sf) else []
    used = {l.split("|")[1] for l in hist[-12:] if "|" in l}   # 최근 12주 장소는 다시 안 고름
    sat = today + dt.timedelta(days=(5 - today.weekday()) % 7)
    spots = trips_data.KR if ko else trips_data.US
    wx = weekend_weather(spots, region, sat)
    t0 = time.time(); pick = None
    for spot, w in ranked(region, today, used, wx)[:3]:
        if time.time() - t0 > 100: break
        print("장소 후보:", spot["name"])
        cands = photos_for(spot); print("  사진 후보", len(cands))
        if len(cands) < 3: continue
        j = judge(spot, cands, w, region, today)
        if j: pick = (spot, w, cands, j); break
    if not pick: raise RuntimeError("쓸 만한 장소·사진을 못 찾음 → 이번 주는 올리지 않음")
    spot, w, cands, j = pick
    ph = [dict(cands[p["i"]], cap=p["cap"], fx=float(p.get("fx", .5)), fy=float(p.get("fy", .5))) for p in j["photos"]]
    rel = [f"out/trip-{region}-{day}-{n}.jpg" for n in (1, 2, 3)]
    trips_render.carousel(region, today, spot, w, ph, j, rel)
    import reel_data
    reel_data.save("trip", region, {"spot": {k: spot.get(k) for k in ("name", "area", "how", "hours", "fee")}, "w": w, "sat": sat.isoformat(),
                   "j": {k: j.get(k) for k in ("why", "tip", "aside")}, "caps": [p["cap"] for p in ph], "fx": [[p["fx"], p["fy"]] for p in ph],
                   "cards": [os.path.abspath(r) for r in rel]}, photos={f"p{i}": p["im"] for i, p in enumerate(ph)})
    name = spot["name"]
    tag = re.sub(r"[^0-9A-Za-z가-힣]", "", name)
    cap = (f"📍 이번 주말 서울 나들이: {name} ({spot['area']})\n\n" + tags.line("kr", "서울가볼만한곳", tag, "서울나들이", "주말나들이") if ko else
           f"📍 Weekend pick from LA: {name} ({spot['area']})\n\n" + tags.line("us", "thingstodoinLA", tag, "LAweekend", "californiatravel"))
    print(json.dumps(j, ensure_ascii=False)); print(cap)
    if a.dry_run: print("(dry-run) 카드 저장:", rel); return
    with open(sf, "a", encoding="utf-8") as fh: fh.write(f"{day}|{name}\n")
    git_push(["out", "state"], f"trip {region} {day} cards")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    urls = [f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{sha}/{r}" for r in rel]
    for u in urls:
        for _ in range(12):
            if requests.head(u, timeout=15).ok: break
            time.sleep(5)
    json.dump({"date": day, "image_url": urls[0], "image_url2": urls[1], "image_url3": urls[2], "caption": cap, "title": "weekend pick"},
              open(lp, "w", encoding="utf-8"), ensure_ascii=False)
    git_push(["out"], f"trip {region} {day} latest.json"); print("저장 완료:", urls)


if __name__ == "__main__":
    main()
