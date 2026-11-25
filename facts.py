"""토요일 시리즈 "신기한 동물 사실": 동물 사진 한 장 + 확실한 사실 하나 + 시큰둥한 한 줄.

- 사실 문장은 아래 목록에 사람이 미리 확인해 둔 것만 쓴다(AI가 사실을 지어내지 않게).
- 사진은 수요일 아기 동물과 같은 방식: Pexels(키 있으면) 또는 위키미디어 공용에서 후보를 받고, Gemini가 보고 한 장을 고른다.
- 한국판이 먼저 고른 사진을 state/facts_pick.json 에 남기고, 미국판은 같은 주면 그대로 쓴다.
"""
import argparse, base64, datetime as dt, io, json, os, re, subprocess, time
from zoneinfo import ZoneInfo
import requests
from PIL import Image
import animals_render, weather
from animals import commons, pexels, UA
from books import git_push, models

# (사진 검색어, 영어 이름, 한국어 이름, [한국어 두 줄], [영어 두 줄])  — 첫 줄 = 사실, 둘째 줄 = 덧붙임
FACTS = [
    ("sea otters holding hands", "Sea otter", "해달", ["잘 때 서로 손을 잡고 잔다.", "자다가 떠내려가지 않으려고."], ["They hold hands while sleeping.", "So nobody drifts away."]),
    ("octopus", "Octopus", "문어", ["심장이 세 개다.", "그래도 고민은 하나씩 한다."], ["It has three hearts.", "Still only one problem at a time."]),
    ("wombat", "Wombat", "웜뱃", ["똥이 정육면체 모양이다.", "굴러가지 않게 쌓아 둔다."], ["Its poop is cube-shaped.", "Stacks nicely. Rolls never."]),
    ("koala", "Koala", "코알라", ["지문이 사람과 거의 똑같다.", "현장에 남기면 곤란해진다."], ["Its fingerprints look like ours.", "Bad news for crime scenes."]),
    ("flamingo", "Flamingo", "플라밍고", ["분홍색은 먹는 것 때문이다.", "새우랑 조류를 끊으면 하얘진다."], ["The pink comes from its food.", "No shrimp, no pink."]),
    ("gentoo penguin pebble", "Gentoo penguin", "젠투펭귄", ["마음에 든 짝에게 조약돌을 준다.", "반지보다는 싸게 먹힌다."], ["It gifts pebbles to win a mate.", "Cheaper than a ring."]),
    ("elephant", "Elephant", "코끼리", ["거울 속 자기 모습을 알아본다.", "그래서 더 오래 본다."], ["It recognizes itself in a mirror.", "Then keeps looking."]),
    ("crow", "Crow", "까마귀", ["사람 얼굴을 몇 년씩 기억한다.", "잘해 주는 게 좋다."], ["It remembers faces for years.", "Be nice to crows."]),
    ("sloth hanging tree", "Sloth", "나무늘보", ["화장실은 일주일에 한 번 간다.", "그것도 나무에서 내려와서."], ["It climbs down to poop once a week.", "Just the once."]),
    ("giraffe tongue", "Giraffe", "기린", ["혀가 검푸른색이고 50cm쯤 된다.", "햇볕에 덜 타게 진한 색이다."], ["Its tongue is dark and about 50 cm.", "Built-in sunscreen."]),
    ("hummingbird", "Hummingbird", "벌새", ["뒤로 날 수 있는 거의 유일한 새다.", "후진도 우아하게."], ["One of the only birds that fly backward.", "Reverse, but make it elegant."]),
    ("bottlenose dolphin", "Dolphin", "돌고래", ["각자 고유한 휘파람 이름이 있다.", "부르면 대답도 한다."], ["Each one has a signature whistle name.", "And answers to it."]),
    ("squirrel acorn", "Squirrel", "다람쥐", ["숨긴 도토리를 다 못 찾는다.", "덕분에 숲에 나무가 자란다."], ["It forgets many buried acorns.", "Forests say thanks."]),
    ("axolotl", "Axolotl", "아홀로틀", ["다리가 잘려도 다시 자란다.", "심장 일부도 다시 만든다."], ["It can regrow lost legs.", "Even parts of its heart."]),
    ("cat meowing", "Cat", "고양이", ["다 큰 고양이끼리는 거의 야옹 안 한다.", "야옹은 사람 전용이다."], ["Adult cats rarely meow at each other.", "Meows are for humans."]),
    ("dog nose close up", "Dog", "강아지", ["코 주름이 지문처럼 다 다르다.", "코로 신분 확인 가능."], ["Every nose print is unique.", "Like a fingerprint, but wetter."]),
    ("owl", "Owl", "올빼미", ["눈알을 굴리지 못한다.", "대신 목을 270도 돌린다."], ["It can't move its eyeballs.", "So it turns its head 270°."]),
    ("pig mud", "Pig", "돼지", ["땀을 거의 흘리지 못한다.", "그래서 진흙 목욕을 한다."], ["Pigs barely sweat.", "Mud is their air conditioning."]),
    ("zebra", "Zebra", "얼룩말", ["줄무늬가 한 마리도 똑같지 않다.", "얼룩말 신분증."], ["No two zebras share the same stripes.", "Built-in ID card."]),
    ("hippopotamus", "Hippo", "하마", ["피부에서 붉은 액체가 나온다.", "천연 자외선 차단제다."], ["It secretes a reddish fluid.", "Natural sunscreen."]),
    ("polar bear", "Polar bear", "북극곰", ["털은 투명하고 피부는 검다.", "하얗게 보일 뿐이다."], ["Its fur is clear, its skin is black.", "White is just a look."]),
    ("butterfly flower", "Butterfly", "나비", ["발로 맛을 본다.", "앉는 순간 시식 끝."], ["It tastes with its feet.", "Landing is tasting."]),
    ("kangaroo", "Kangaroo", "캥거루", ["뒤로는 거의 걷지 못한다.", "앞만 보고 산다."], ["It can barely walk backward.", "Only forward, always."]),
    ("jellyfish", "Jellyfish", "해파리", ["뇌도 심장도 없다.", "5억 년 넘게 잘 살았다."], ["No brain, no heart.", "Doing fine for 500 million years."]),
    ("rat", "Rat", "쥐", ["간지럼을 태우면 웃는다.", "사람 귀엔 안 들리는 소리로."], ["Rats laugh when tickled.", "Too high-pitched for us to hear."]),
    ("honey bee flower", "Honeybee", "꿀벌", ["춤으로 꽃 위치를 알려준다.", "방향과 거리까지."], ["It dances to share where flowers are.", "Direction and distance included."]),
    ("chameleon", "Chameleon", "카멜레온", ["혀가 몸길이만큼 길다.", "나오는 건 순식간."], ["Its tongue can match its body length.", "Out in a blink."]),
    ("ostrich", "Ostrich", "타조", ["눈이 뇌보다 크다.", "보는 건 잘한다."], ["Its eye is bigger than its brain.", "Great at looking."]),
    ("platypus", "Platypus", "오리너구리", ["알을 낳는 포유류다.", "부리도 있고 독도 있다."], ["A mammal that lays eggs.", "Also has a bill. And venom."]),
    ("goldfish", "Goldfish", "금붕어", ["기억력 3초는 헛소문이다.", "몇 달씩 기억한다."], ["The 3-second memory is a myth.", "It remembers for months."]),
    ("orca", "Orca", "범고래", ["할머니가 무리를 이끈다.", "경험이 곧 지도다."], ["Grandmothers lead the pod.", "Experience is the map."]),
    ("seahorse", "Seahorse", "해마", ["새끼는 수컷이 낳는다.", "육아휴직도 수컷 몫."], ["The male gives birth.", "Dad does the delivery."]),
    ("fruit bat", "Bat", "박쥐", ["진짜로 나는 유일한 포유류다.", "날다람쥐는 활공일 뿐."], ["The only mammal that truly flies.", "Flying squirrels just glide."]),
    ("pigeon", "Pigeon", "비둘기", ["모네와 피카소 그림을 구별한다.", "실험으로 확인됐다."], ["It can tell Monet from Picasso.", "Science checked."]),
    ("shark", "Shark", "상어", ["몸에 뼈가 하나도 없다.", "전부 연골이다."], ["Sharks have no bones.", "All cartilage."]),
    ("cheetah", "Cheetah", "치타", ["으르렁대지 못한다.", "대신 새처럼 짹짹거린다."], ["Cheetahs can't roar.", "They chirp like birds."]),
    ("cow pasture", "Cow", "소", ["친한 친구가 따로 있다.", "떨어지면 스트레스 받는다."], ["Cows have best friends.", "And miss them when apart."]),
    ("horse", "Horse", "말", ["서서 잠을 잘 수 있다.", "깊은 잠은 누워서 잔다."], ["Horses can sleep standing up.", "Deep sleep needs lying down."]),
    ("starfish", "Starfish", "불가사리", ["피가 없다.", "대신 바닷물이 몸을 돈다."], ["Starfish have no blood.", "Seawater does the job."]),
    ("puffin", "Puffin", "퍼핀", ["부리에 물고기를 10마리 넘게 문다.", "한 번에 장 봐 온다."], ["It can carry 10+ fish in its beak.", "One trip, full groceries."]),
    ("capybara", "Capybara", "카피바라", ["다른 동물이 등에 올라도 안 비킨다.", "온화함의 끝판왕."], ["Other animals sit on it. It allows it.", "Peak chill."]),
    ("snail", "Snail", "달팽이", ["이빨이 1만 개가 넘는다.", "혀에 줄지어 나 있다."], ["Snails can have over 10,000 teeth.", "Lined up on the tongue."]),
]


def order(year):
    import random
    idx = list(range(len(FACTS))); random.Random(year * 104729).shuffle(idx); return idx


def judge(cands, en, ko, fact_en):
    """Gemini가 후보 사진을 보고 고른다. 쓸 만한 게 없으면 None."""
    key = os.environ["GEMINI_API_KEY"].strip(); parts = []
    for i, c in enumerate(cands):
        im = c["im"].copy(); im.thumbnail((640, 640)); b = io.BytesIO(); im.save(b, "JPEG", quality=80)
        parts += [{"text": f"[photo {i}] caption: {c['id'][:90]}"}, {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(b.getvalue()).decode()}}]
    prompt = f"""You are picking ONE photo for a weekly Instagram card "Weird animal fact" (this week: {en} / {ko}; fact: "{fact_en}").
Be a strict photo editor. A photo qualifies ONLY if: it is a real photograph of a living {en} (not a statue, toy, drawing, museum specimen, or dead animal),
the animal is the clear main subject, sharp, well lit, attractive at first glance, with a clean background; no people's faces, no watermark or big text, nothing sad or gory (no injury, cage, blood, prey).
Prefer a photo that also shows the fact if possible (e.g. holding hands, tongue out), but a beautiful clear portrait is fine.
Rate the best qualifying photo 1-10 as "score" honestly. If none qualifies or the best is below 7, return {{"best": -1, "why": "..."}}.
Return ONLY JSON:
{{"best": index, "score": 1..10, "why": "short reason",
 "focus_x": 0..1, "focus_y": 0..1,   // where the animal's face is (fraction of width/height)
 "aside_ko": "이 사실을 들은 마스코트 레드덴바의 시큰둥한 반응 한마디 (max 8 chars, 예: 처음 앎 / 부럽다 / 나도 할래)", "aside_en": "same idea, max 14 chars (e.g. TIL / Jealous / Same)"}}"""
    last = None
    for m in (models(key)[:4] * 2):
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", headers={"x-goog-api-key": key},
                          json={"contents": [{"parts": [{"text": prompt}] + parts}], "generationConfig": {"temperature": 0.5, "responseMimeType": "application/json"}}, timeout=60)
        if not r.ok: last = f"{m} {r.status_code}"; continue
        try:
            j = json.loads(re.sub(r"^```json|```$", "", r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()).strip())
            if int(j.get("best", -1)) < 0 or int(j.get("score", 0)) < 7: print("  쓸 만한 사진 없음:", j.get("score"), j.get("why", "")); return None
            assert 0 <= int(j["best"]) < len(cands) and len(j["aside_ko"]) <= 10 and len(j["aside_en"]) <= 16
            return j
        except Exception as e: last = f"{m} {type(e).__name__} {e}"
    raise RuntimeError(f"Gemini 실패: {last}")


def choose(year, week_no, used):
    key = os.environ.get("PEXELS_API_KEY", "").strip(); t0 = time.time(); idx = order(year)
    for k in range(5):
        n = idx[(week_no + k) % len(idx)]; q, en, ko, lk, le = FACTS[n]
        cands = [c for c in (pexels(q, key) if key else commons(q)) if c["id"] not in used][:10]; got = []
        for c in cands:
            try:
                r = requests.get(c["url"], headers=UA, timeout=25); r.raise_for_status(); c["im"] = Image.open(io.BytesIO(r.content)).convert("RGB"); got.append(c)
            except Exception as e: print("  사진 받기 실패", str(e)[:60])
        print(f"{en}: 후보 {len(got)}장")
        if got:
            j = judge(got, en, ko, le[0])
            if j: return n, got[int(j["best"])], j
        if time.time() - t0 > 80: break
    raise RuntimeError("쓸 만한 동물 사진을 못 찾음 → 이번 주는 올리지 않음")


def build(region, pick, day, photo):
    ko = region == "kr"; d = dt.date.fromisoformat(day); L = "ko" if ko else "en"
    _, en, kname, lk, le = FACTS[pick["n"]]
    artist = re.sub(r"\s*[\(<].*$|\S+@\S+", "", pick["artist"]).strip()
    credit = " · ".join(x for x in (artist, pick["license"], pick["src"]) if x)
    c = dict(top=(f"SATURDAY FACT · {d:%Y.%m.%d}" if ko else f"SATURDAY FACT · {d:%b %d, %Y}".upper()), date=day,
             handle=f"@reddenva.{region}", photo=photo, focus=(pick["focus_x"], pick["focus_y"]), pose="a11.png", fact=True,
             badge="신기한 동물 사실" if ko else "Weird animal fact", name=kname if ko else en, lines=lk if ko else le, aside=pick[f"aside_{L}"],
             foot=[("사진: " if ko else "Photo: ") + credit, "레드덴바 · 매주 토요일, 아는 척 동물 상식" if ko else "Red Denva · Every Saturday, one weird animal fact"])
    tag = re.sub(r"[^0-9A-Za-z가-힣]", "", kname if ko else en)
    cap = (f"🦦 {kname}: {lk[0]}\n\n#{tag} #동물상식 #신기한사실 #토요일 #아는척 #레드덴바" if ko else
           f"🦦 {en}: {le[0]}\n\n#{tag} #animalfacts #funfacts #saturday #didyouknow #reddenva")
    return c, cap


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--region", required=True, choices=["kr", "us"])
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args(); region = a.region
    tz = ZoneInfo(weather.REGIONS[region]["tz"]); today = dt.datetime.now(tz).date(); day = today.isoformat()
    os.makedirs("out", exist_ok=True); os.makedirs("state", exist_ok=True)
    if not a.force and today.weekday() != 5:
        print("토요일이 아님 → 건너뜀"); return
    lp = f"out/facts-{region}-latest.json"
    if not a.force and os.path.exists(lp) and json.load(open(lp, encoding="utf-8")).get("date") == day:
        print("오늘 이미 만들었음. 건너뜀"); return
    iso = today.isocalendar(); week = f"{iso[0]}-W{iso[1]:02d}"; pf = "state/facts_pick.json"; photo = f"out/facts-photo-{week}.jpg"
    hist = json.load(open(pf, encoding="utf-8")) if os.path.exists(pf) else {"used": [], "done": [], "pick": {}}
    pick = hist.get("pick", {})
    if pick.get("week") == week and os.path.exists(photo):
        print("이번 주 사진 재사용:", pick["id"])
    else:
        n, c, j = choose(iso[0], iso[1], set(hist.get("used", [])))
        c["im"].save(photo, quality=92)
        pick = {"week": week, "n": n, "id": c["id"], "artist": c["artist"], "license": c["license"], "src": c["src"], **{k: j[k] for k in ("focus_x", "focus_y", "aside_ko", "aside_en")}}
        hist = {"used": (hist.get("used", []) + [c["id"]])[-300:], "pick": pick}
        print("선택:", FACTS[n][1], c["id"], "|", j.get("score"), j.get("why", ""))
    card, cap = build(region, pick, day, photo)
    img_rel = f"out/facts-{region}-{day}.jpg"; animals_render.card(card, img_rel)
    import reel_data; reel_data.save("facts", region, {"c": {k: v for k, v in card.items() if k != "photo"}, "cards": [os.path.abspath(img_rel)]}, photos={"photo": photo})
    json.dump(hist, open(pf, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if a.dry_run: print("(dry-run) 카드 저장:", img_rel); print(cap); return
    git_push(["out", "state"], f"facts {region} {day} card")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    url = f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{sha}/{img_rel}"
    for _ in range(12):
        if requests.head(url, timeout=15).ok: break
        time.sleep(5)
    with open(lp, "w", encoding="utf-8") as fh:
        json.dump({"date": day, "image_url": url, "caption": cap, "title": "animal fact"}, fh, ensure_ascii=False)
    git_push(["out"], f"facts {region} {day} latest.json"); print("저장 완료:", url)


if __name__ == "__main__":
    main()
