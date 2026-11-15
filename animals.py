"""수요일 시리즈 "이번 주 아기 동물": 아기 동물(강아지 여러 견종 + 다른 동물) 사진 한 장 + 시큰둥한 두 줄.

- 매주 동물을 바꿔 가며(해마다 섞은 순서, ISO 주차 기준) 사진 후보를 받는다. PEXELS_API_KEY가 있으면 Pexels, 없으면 위키미디어 공용(무료·키 불필요).
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
# (검색어, 영어 이름, 한국어 이름). 강아지 여러 견종 + 다른 아기 동물. 레서판다는 넣지 않음(형 요청).
SUBJECTS = [("golden retriever puppy", "Golden retriever puppy", "아기 골든 리트리버"), ("kitten", "Kitten", "아기 고양이"), ("shiba inu puppy", "Shiba inu puppy", "아기 시바견"),
            ("duckling", "Duckling", "아기 오리"), ("welsh corgi puppy", "Corgi puppy", "아기 웰시 코기"), ("lamb", "Lamb", "아기 양"), ("samoyed puppy", "Samoyed puppy", "아기 사모예드"),
            ("baby rabbit", "Baby bunny", "아기 토끼"), ("beagle puppy", "Beagle puppy", "아기 비글"), ("sea otter pup", "Sea otter pup", "아기 해달"), ("labrador retriever puppy", "Labrador puppy", "아기 래브라도"),
            ("piglet", "Piglet", "아기 돼지"), ("pomeranian puppy", "Pomeranian puppy", "아기 포메라니안"), ("baby elephant calf", "Baby elephant", "아기 코끼리"), ("siberian husky puppy", "Husky puppy", "아기 허스키"),
            ("fox kit cub", "Fox kit", "아기 여우"), ("dachshund puppy", "Dachshund puppy", "아기 닥스훈트"), ("seal pup", "Seal pup", "아기 물범"), ("french bulldog puppy", "French bulldog puppy", "아기 프렌치 불도그"),
            ("foal", "Foal", "아기 말"), ("poodle puppy", "Poodle puppy", "아기 푸들"), ("baby hedgehog hoglet", "Baby hedgehog", "아기 고슴도치"), ("border collie puppy", "Border collie puppy", "아기 보더 콜리"),
            ("penguin chick", "Penguin chick", "아기 펭귄"), ("maltese puppy", "Maltese puppy", "아기 몰티즈"), ("baby goat kid", "Baby goat", "아기 염소"), ("bernese mountain dog puppy", "Bernese puppy", "아기 버니즈"),
            ("fawn deer", "Fawn", "아기 사슴"), ("pug puppy", "Pug puppy", "아기 퍼그"), ("giant panda cub", "Panda cub", "아기 판다"), ("jindo dog puppy", "Jindo puppy", "아기 진돗개"),
            ("koala joey", "Koala joey", "아기 코알라"), ("bichon frise puppy", "Bichon puppy", "아기 비숑"), ("calf highland cattle", "Highland calf", "아기 소"), ("cocker spaniel puppy", "Cocker spaniel puppy", "아기 코커 스패니얼"),
            ("chick baby chicken", "Chick", "병아리"), ("australian shepherd puppy", "Aussie puppy", "아기 오스트레일리안 셰퍼드"), ("alpaca cria", "Baby alpaca", "아기 알파카"), ("akita puppy", "Akita puppy", "아기 아키타"),
            ("polar bear cub", "Polar bear cub", "아기 북극곰"), ("schnauzer puppy", "Schnauzer puppy", "아기 슈나우저"), ("baby capybara", "Baby capybara", "아기 카피바라"), ("chihuahua puppy", "Chihuahua puppy", "아기 치와와"),
            ("lion cub", "Lion cub", "아기 사자"), ("shih tzu puppy", "Shih tzu puppy", "아기 시추"), ("baby hamster", "Baby hamster", "아기 햄스터"), ("great pyrenees puppy", "Great Pyrenees puppy", "아기 그레이트 피레니즈"),
            ("gosling", "Gosling", "아기 거위"), ("yorkshire terrier puppy", "Yorkie puppy", "아기 요크셔 테리어"), ("baby sloth", "Baby sloth", "아기 나무늘보"), ("german shepherd puppy", "German shepherd puppy", "아기 저먼 셰퍼드"),
            ("tiger cub", "Tiger cub", "아기 호랑이")]


def order(year):
    """해마다 순서를 섞는다(연도가 씨앗이라 한국판·미국판이 같은 주에 같은 동물을 고름)."""
    import random
    idx = list(range(len(SUBJECTS))); random.Random(year * 7919).shuffle(idx); return idx


def commons(q):
    r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=25, params={
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrsearch": f"{q} filetype:bitmap", "gsrlimit": 20,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1400})
    out = []
    for p in sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99)):
        ii = (p.get("imageinfo") or [{}])[0]; em = ii.get("extmetadata", {}); lic = em.get("LicenseShortName", {}).get("value", "")
        if ii.get("mime") != "image/jpeg" or ii.get("width", 0) < 1200 or ii.get("height", 0) < 900: continue
        if not re.match(r"(CC0|CC BY|Public domain)", lic, re.I): continue
        artist = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", ""))).strip(); artist = re.split(r"\s+\.\s+|Photo uploaded|\(talk\)| from ", artist)[0].strip()[:32] or "Wikimedia Commons"
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
    prompt = f"""You are picking ONE photo for a weekly Instagram card "Baby animal of the week" (this week: {en} / {ko}).
Look at each photo. Be a strict photo editor. A photo qualifies ONLY if ALL are true: it is a real photograph of a real BABY animal of that kind that visibly looks very young
(round face, small soft body; NOT an adolescent or adult animal, NOT a statue/toy/drawing; for dogs and cats reject if the caption says 6 months or older);
the baby animal is the clear main subject (an adult parent next to it is fine if the baby is clearly the star), sharp, well lit, with a pleasant background, and is the kind of photo that makes people say "aww" at first glance
(soft expression; reject bared teeth, awkward poses, harsh flash, messy or dirty settings); no people's faces, no watermark or big text, nothing sad (no injury, cage, shelter misery); reject newborns whose eyes are still closed or that look hairless/raw, reject photos where the animal is held in or covered by human hands, and reject anything showing hunting, feeding on prey, or blood.
Rate the best qualifying photo's cuteness 1-10 as "score" honestly (10 = calendar-cover quality). If none qualifies or the best is below 8, return {{"best": -1, "why": "..."}}.
Then write the card text about what THIS baby animal is visibly doing in the photo. Tone: deadpan, dry, sleek humor, like a bored narrator. Not childish, not gushing, no emoji, no exclamation marks.
Return ONLY JSON:
{{"best": index, "score": 1..10, "why": "short reason",
 "focus_x": 0..1, "focus_y": 0..1,   // where the baby animal's face is in the photo (fraction of width/height)
 "name_ko": "{ko}" (keep as is unless the photo is clearly a different kind; max 14 chars), "name_en": "{en}" (max 26 chars),
 "lines_ko": ["첫 줄 (max 17 chars, 명사형/~중. ~음. 식의 건조한 말투. 한국 사람이 읽어 자연스럽고 뜻이 바로 통하는 문장. 쉬운 일상어만 쓰고, 그 동물에 맞지 않는 낱말(예: 코알라에게 '등딱지')은 쓰지 말 것)", "둘째 줄 (max 17 chars)"],
 "lines_en": ["line 1 (max 32 chars)", "line 2 (max 32 chars)"],
 "aside_ko": "이 사진을 본 마스코트 레드덴바의 시큰둥한 반응 한마디. 사진·문구와 뜻이 이어져야 함 (max 8 chars, 예: 졌다 / 부럽다 / 나도 말 안 함)", "aside_en": "same idea, max 14 chars (e.g. I lost / Jealous / Not telling)"}}
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
            assert 0 < len(j["name_ko"]) <= 16 and 0 < len(j["name_en"]) <= 30 and len(j["aside_ko"]) <= 10 and len(j["aside_en"]) <= 16
            assert not re.search(r"[!！]", "".join(j["lines_ko"] + j["lines_en"]))
            return j
        except Exception as e: last = f"{m} {type(e).__name__} {e}"
    raise RuntimeError(f"Gemini 실패: {last}")


def choose(year, week_no, used):
    """이번 주 차례의 동물부터 순서대로(최대 5종) 후보를 받아 고른다."""
    key = os.environ.get("PEXELS_API_KEY", "").strip(); t0 = time.time(); idx = order(year)
    for k in range(5):
        q, en, ko = SUBJECTS[idx[(week_no + k) % len(idx)]]
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
    raise RuntimeError("쓸 만한 아기 동물 사진을 못 찾음 → 이번 주는 올리지 않음")


def build(region, pick, day, photo):
    ko = region == "kr"; d = dt.date.fromisoformat(day); L = "ko" if ko else "en"
    credit = " · ".join(x for x in (pick["artist"], pick["license"], pick["src"]) if x)
    c = dict(top=(f"WEDNESDAY BABY · {d:%Y.%m.%d} ({'월화수목금토일'[d.weekday()]})" if ko else f"WEDNESDAY BABY · {d:%b %d, %Y} ({d:%a})".upper()),
             handle=f"@reddenva.{region}", photo=photo, focus=(pick["focus_x"], pick["focus_y"]),
             badge="이번 주 아기 동물" if ko else "Baby animal of the week", name=pick[f"name_{L}"], lines=pick[f"lines_{L}"], aside=pick[f"aside_{L}"],
             foot=[("사진: " if ko else "Photo: ") + credit, "레드덴바 · 매주 수요일, 귀여운 것만 봅니다" if ko else "Red Denva · Every Wednesday, cute things only"])
    cap = (f"🐾 이번 주 아기 동물: {c['name']}\n{c['lines'][0]} {c['lines'][1]}\n\n사진: {credit}\n\n#아기동물 #귀여운동물 #수요일 #귀여운것만 #레드덴바" if ko else
           f"🐾 Baby animal of the week: {c['name']}\n{c['lines'][0]} {c['lines'][1]}\n\nPhoto: {credit}\n\n#babyanimals #cuteanimals #wednesday #cute #reddenva")
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
        c, j = choose(iso[0], iso[1], set(hist.get("used", [])))
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
