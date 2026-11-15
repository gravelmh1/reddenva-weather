"""수요일 시리즈 "이번 주 강아지": 아기 강아지 사진 한 장 + 시큰둥한 두 줄.

- 매주 견종을 바꿔 가며(ISO 주차 기준) 사진 후보를 받는다. PEXELS_API_KEY가 있으면 Pexels, 없으면 위키미디어 공용(무료·키 불필요).
- Gemini가 후보 사진을 직접 보고 "진짜 아기 강아지 사진인지, 귀여운지"를 확인해 한 장을 고르고 문구(한국어·영어)를 쓴다.
- 한국판이 먼저 고른 사진·문구를 state/puppy_pick.json 에 남기고, 미국판은 같은 주면 그대로 쓴다.
"""
import argparse, base64, datetime as dt, io, json, os, re, time
from zoneinfo import ZoneInfo
import requests
from PIL import Image
import animals_render, weather
from books import git_push, models

UA = {"User-Agent": "RedDenvaBot/1.0 (https://github.com/gravelmh1/reddenva-weather)"}
BREEDS = [("golden retriever", "골든 리트리버"), ("shiba inu", "시바견"), ("welsh corgi", "웰시 코기"), ("beagle", "비글"), ("samoyed", "사모예드"),
          ("labrador retriever", "래브라도 리트리버"), ("pomeranian", "포메라니안"), ("siberian husky", "시베리안 허스키"), ("dachshund", "닥스훈트"),
          ("french bulldog", "프렌치 불도그"), ("poodle", "푸들"), ("border collie", "보더 콜리"), ("maltese", "몰티즈"), ("bernese mountain dog", "버니즈 마운틴 도그"),
          ("pug", "퍼그"), ("jindo dog", "진돗개"), ("bichon frise", "비숑 프리제"), ("cocker spaniel", "코커 스패니얼"), ("australian shepherd", "오스트레일리안 셰퍼드"),
          ("akita", "아키타"), ("schnauzer", "슈나우저"), ("chihuahua", "치와와"), ("shih tzu", "시추"), ("great pyrenees", "그레이트 피레니즈"),
          ("yorkshire terrier", "요크셔 테리어"), ("german shepherd", "저먼 셰퍼드")]


def commons(q):
    r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=25, params={
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrsearch": f"{q} filetype:bitmap", "gsrlimit": 20,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1400})
    out = []
    for p in sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99)):
        ii = (p.get("imageinfo") or [{}])[0]; em = ii.get("extmetadata", {}); lic = em.get("LicenseShortName", {}).get("value", "")
        if ii.get("mime") != "image/jpeg" or ii.get("width", 0) < 1200 or ii.get("height", 0) < 900: continue
        if not re.match(r"(CC0|CC BY|Public domain)", lic, re.I): continue
        artist = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", ""))).strip()[:40] or "Wikimedia Commons"
        out.append({"id": "wm:" + p["title"], "url": ii["thumburl"], "artist": artist, "license": "퍼블릭 도메인" if re.match(r"(CC0|Public)", lic, re.I) else lic, "src": "Wikimedia Commons"})
    return out


def pexels(q, key):
    r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key}, params={"query": q, "per_page": 15}, timeout=25)
    if not r.ok: print("Pexels 응답", r.status_code); return []
    return [{"id": f"px:{p['id']}", "url": p["src"]["large2x"], "artist": p.get("photographer", "")[:40], "license": "", "src": "Pexels"} for p in r.json().get("photos", [])]


def judge(cands, en, ko):
    """Gemini가 후보 사진을 보고 고른다. 쓸 만한 게 없으면 None."""
    key = os.environ["GEMINI_API_KEY"].strip(); parts = []
    for i, c in enumerate(cands):
        im = c["im"].copy(); im.thumbnail((640, 640)); b = io.BytesIO(); im.save(b, "JPEG", quality=80)
        parts += [{"text": f"[photo {i}] caption: {c['id'][:90]}"}, {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(b.getvalue()).decode()}}]
    prompt = f"""You are picking ONE photo for a weekly Instagram card "Puppy of the week" (breed this week: {en} / {ko}).
Look at each photo. Be a strict photo editor. A photo qualifies ONLY if ALL are true: it is a real photograph of a real BABY puppy that visibly looks only a few weeks or months old
(round face, small soft body; NOT an adolescent or adult dog, NOT a statue/toy/drawing; reject if the caption says 6 months or older);
the puppy is the clear main subject, sharp, well lit, with a pleasant background, and is the kind of photo that makes people say "aww" at first glance
(soft expression; reject bared teeth, awkward poses, harsh flash, messy or dirty settings); no people's faces, no watermark or big text, nothing sad (no injury, cage, shelter misery, raw-looking newborn litter).
Rate the best qualifying photo's cuteness 1-10 as "score" honestly (10 = calendar-cover quality). If none qualifies or the best is below 8, return {{"best": -1, "why": "..."}}.
Then write the card text about what THIS puppy is visibly doing in the photo. Tone: deadpan, dry, sleek humor, like a bored narrator. Not childish, not gushing, no emoji, no exclamation marks.
Return ONLY JSON:
{{"best": index, "score": 1..10, "why": "short reason",
 "focus_x": 0..1, "focus_y": 0..1,   // where the puppy's face is in the photo (fraction of width/height)
 "name_ko": "아기 {ko}" (use the actual breed if clearly different; max 12 chars), "name_en": "{en.title()} puppy" (max 26 chars),
 "lines_ko": ["첫 줄 (max 17 chars, 명사형/~중. ~음. 식의 건조한 말투. 한국 사람이 읽어 자연스럽고 뜻이 바로 통하는 문장)", "둘째 줄 (max 17 chars)"],
 "lines_en": ["line 1 (max 32 chars)", "line 2 (max 32 chars)"],
 "aside_ko": "빨간 마스코트 레드덴바의 시큰둥한 한마디 (max 8 chars)", "aside_en": "same, max 14 chars"}}
Example of tone — lines_ko: ["코에 눈 묻은 줄 모름.", "알려주는 사람도 없음."], aside_ko: "나도 말 안 함"; lines_en: ["Paws up, waiting for a treat.", "Saying no is not an option."], aside_en: "I lost"."""
    last = None
    for m in (models(key)[:4] * 2):
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", headers={"x-goog-api-key": key},
                          json={"contents": [{"parts": [{"text": prompt}] + parts}], "generationConfig": {"temperature": 0.6, "responseMimeType": "application/json"}}, timeout=60)
        if not r.ok: last = f"{m} {r.status_code}"; continue
        try:
            j = json.loads(re.sub(r"^```json|```$", "", r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()).strip())
            if int(j.get("best", -1)) < 0 or int(j.get("score", 0)) < 8: print("  쓸 만한 사진 없음:", j.get("score"), j.get("why", "")); return None
            assert 0 <= int(j["best"]) < len(cands)
            assert len(j["lines_ko"]) == 2 and len(j["lines_en"]) == 2 and all(0 < len(x) <= 20 for x in j["lines_ko"]) and all(0 < len(x) <= 36 for x in j["lines_en"])
            assert 0 < len(j["name_ko"]) <= 14 and 0 < len(j["name_en"]) <= 30 and len(j["aside_ko"]) <= 10 and len(j["aside_en"]) <= 16
            assert not re.search(r"[!！]", "".join(j["lines_ko"] + j["lines_en"]))
            return j
        except Exception as e: last = f"{m} {type(e).__name__} {e}"
    raise RuntimeError(f"Gemini 실패: {last}")


def choose(week_no, used):
    """이번 주 견종부터 차례로(최대 4종) 후보를 받아 고른다."""
    key = os.environ.get("PEXELS_API_KEY", "").strip(); t0 = time.time()
    for k in range(5):
        en, ko = BREEDS[(week_no + k) % len(BREEDS)]; q = f"{en} puppy"
        cands = [c for c in (pexels(q, key) if key else commons(q)) if c["id"] not in used][:10]; got = []
        for c in cands:
            try:
                r = requests.get(c["url"], headers=UA, timeout=25); r.raise_for_status(); c["im"] = Image.open(io.BytesIO(r.content)).convert("RGB"); got.append(c)
            except Exception as e: print("  사진 받기 실패", str(e)[:60])
        print(f"{en}: 후보 {len(got)}장")
        if got:
            j = judge(got, en, ko)
            if j: return got[int(j["best"])], j
        if time.time() - t0 > 80: break
    raise RuntimeError("쓸 만한 강아지 사진을 못 찾음 → 이번 주는 올리지 않음")


def build(region, pick, day, photo):
    ko = region == "kr"; d = dt.date.fromisoformat(day); L = "ko" if ko else "en"
    credit = " · ".join(x for x in (pick["artist"], pick["license"], pick["src"]) if x)
    c = dict(top=(f"WEDNESDAY PUPPY · {d:%Y.%m.%d} ({'월화수목금토일'[d.weekday()]})" if ko else f"WEDNESDAY PUPPY · {d:%b %d, %Y} ({d:%a})".upper()),
             handle=f"@reddenva.{region}", photo=photo, focus=(pick["focus_x"], pick["focus_y"]),
             badge="이번 주 강아지" if ko else "Puppy of the week", name=pick[f"name_{L}"], lines=pick[f"lines_{L}"], aside=pick[f"aside_{L}"],
             foot=[("사진: " if ko else "Photo: ") + credit, "레드덴바 · 매주 수요일, 귀여운 것만 봅니다" if ko else "Red Denva · Every Wednesday, cute things only"])
    cap = (f"🐶 이번 주 강아지: {c['name']}\n{c['lines'][0]} {c['lines'][1]}\n\n사진: {credit}\n\n#강아지 #아기강아지 #수요일 #귀여운것만 #레드덴바" if ko else
           f"🐶 Puppy of the week: {c['name']}\n{c['lines'][0]} {c['lines'][1]}\n\nPhoto: {credit}\n\n#puppy #puppyoftheweek #wednesday #cute #reddenva")
    return c, cap


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--region", required=True, choices=["kr", "us"])
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args(); region = a.region
    tz = ZoneInfo(weather.REGIONS[region]["tz"]); today = dt.datetime.now(tz).date(); day = today.isoformat()
    os.makedirs("out", exist_ok=True); os.makedirs("state", exist_ok=True)
    if not a.force and today.weekday() != 2:
        print("수요일이 아님 → 건너뜀"); return
    lp = f"out/puppy-{region}-latest.json"
    if not a.force and os.path.exists(lp) and json.load(open(lp, encoding="utf-8")).get("date") == day:
        print("오늘 이미 만들었음. 건너뜀"); return
    iso = today.isocalendar(); week = f"{iso[0]}-W{iso[1]:02d}"; pf = "state/puppy_pick.json"; photo = f"out/puppy-photo-{week}.jpg"
    hist = json.load(open(pf, encoding="utf-8")) if os.path.exists(pf) else {"used": [], "pick": {}}
    pick = hist.get("pick", {})
    if pick.get("week") == week and os.path.exists(photo):
        print("이번 주 사진 재사용:", pick["id"])
    else:
        c, j = choose(iso[1], set(hist.get("used", [])))
        c["im"].save(photo, quality=92)
        pick = {"week": week, "id": c["id"], "artist": c["artist"], "license": c["license"], "src": c["src"], **{k: j[k] for k in ("focus_x", "focus_y", "name_ko", "name_en", "lines_ko", "lines_en", "aside_ko", "aside_en")}}
        hist = {"used": (hist.get("used", []) + [c["id"]])[-300:], "pick": pick}
        print("선택:", c["id"], "|", j.get("score"), j.get("why", "")); print(json.dumps(pick, ensure_ascii=False))
    card, cap = build(region, pick, day, photo)
    img_rel = f"out/puppy-{region}-{day}.jpg"; animals_render.card(card, img_rel)
    json.dump(hist, open(pf, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if a.dry_run: print("(dry-run) 카드 저장:", img_rel); print(cap); return
    git_push(["out", "state"], f"puppy {region} {day} card")
    import subprocess
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    url = f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{sha}/{img_rel}"
    for _ in range(12):
        if requests.head(url, timeout=15).ok: break
        time.sleep(5)
    with open(lp, "w", encoding="utf-8") as fh:
        json.dump({"date": day, "image_url": url, "caption": cap, "title": "puppy of the week"}, fh, ensure_ascii=False)
    git_push(["out"], f"puppy {region} {day} latest.json"); print("저장 완료:", url)


if __name__ == "__main__":
    main()
