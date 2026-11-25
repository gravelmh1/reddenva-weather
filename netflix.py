"""일요일 시리즈 "이번 주 넷플릭스 뭐 볼까": 넷플릭스 공식 나라별 주간 Top 10(한국/미국)으로 만든 카드.

- 순위·제목은 넷플릭스가 공개하는 공식 자료(top10.netflix.com의 all-weeks-countries.tsv)를 그대로 쓴다.
- 포스터·장면 사진은 저작권 때문에 쓰지 않는다. 우리 디자인(레드덴바) 카드로 만든다.
- 1위 작품 소개 한 줄은 위키백과 요약을 Gemini가 줄인 것만 쓴다(위키백과에 없으면 소개 줄을 빼고 순위만).
- 한국판은 위키백과 한국어 제목이 있으면 그 제목으로 보여 준다.
"""
import argparse, csv, datetime as dt, io, json, os, re, subprocess, time
from zoneinfo import ZoneInfo
import requests
import netflix_render, weather
from animals import UA
from books import git_push, models

TSV = "https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv"
ISO = {"kr": "KR", "us": "US"}


def load(region):
    r = requests.get(TSV, headers={**UA, "Accept": "text/tab-separated-values,*/*"}, timeout=90); r.raise_for_status()
    rows = [x for x in csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")), delimiter="\t") if x.get("country_iso2") == ISO[region]]
    if not rows: raise RuntimeError("넷플릭스 자료에 이 나라가 없음")
    week = max(x["week"] for x in rows)
    cur = [x for x in rows if x["week"] == week]
    tv = sorted([x for x in cur if x["category"].upper().startswith("TV")], key=lambda x: int(x["weekly_rank"]))
    film = sorted([x for x in cur if x["category"].lower().startswith("film")], key=lambda x: int(x["weekly_rank"]))
    print("주간:", week, "| 시리즈", len(tv), "| 영화", len(film))
    return week, tv, film


def norm(s): return re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())


def _page(lang, title):
    j = requests.get(f"https://{lang}.wikipedia.org/w/api.php", headers=UA, timeout=20, params={"action": "query", "format": "json", "prop": "extracts|langlinks",
                     "titles": title, "exintro": 1, "explaintext": 1, "lllang": "ko", "redirects": 1}).json()
    page = next(iter(j["query"]["pages"].values()))
    return None if "missing" in page else page


def wiki(title, kind, year):
    """영어 위키백과에서 넷플릭스 작품 문서를 찾아 (영어 제목, 한국어 제목, 영어 요약, 한국어 요약)을 돌려준다.
    요약에 'Netflix'가 들어 있는 문서만 인정해서 동명 작품을 잘못 고르지 않게 한다. 못 찾으면 None."""
    tv = [f"{title} ({y} TV series)" for y in (year, year - 1)] + [f"{title} (TV series)", f"{title} (American TV series)", f"{title} (British TV series)",
                                                                   f"{title} (South Korean TV series)", f"{title} (miniseries)"]
    film = [f"{title} ({y} film)" for y in (year, year - 1)] + [f"{title} (film)"]
    try:
        cands = (tv if kind == "tv" else film) + [title]
        s = requests.get("https://en.wikipedia.org/w/api.php", headers=UA, timeout=20, params={"action": "query", "format": "json", "list": "search", "srlimit": 5,
                         "srsearch": f'"{title}" Netflix {"series" if kind == "tv" else "film"}'}).json()
        cands += [h["title"] for h in s.get("query", {}).get("search", [])]
        seen = set()
        for t in cands:
            if t in seen: continue
            seen.add(t); page = _page("en", t)
            if not page: continue
            base = re.sub(r"\s*\(.*?\)$", "", page["title"]); ext = (page.get("extract") or "").strip()
            if norm(base) != norm(title) or "netflix" not in ext.lower(): continue
            ko_title = (page.get("langlinks") or [{}])[0].get("*", ""); ko_ext = ""
            if ko_title:
                kp = _page("ko", ko_title); ko_ext = ((kp or {}).get("extract") or "").strip()
            return {"en_title": base, "ko_title": re.sub(r"\s*\(.*?\)$", "", ko_title), "en": ext[:1500], "ko": ko_ext[:1500]}
    except Exception as e:
        print("  위키백과 조회 실패:", title, str(e)[:80])
    return None


def season(row):
    """시즌·파트 번호가 2 이상일 때만 표시 (시즌 1·리미티드 시리즈는 굳이 안 씀)."""
    m = re.search(r"\b(Season|Part|Volume)\s+(\d+)", row.get("season_title") or "", re.I)
    if not m or int(m.group(2)) < 2: return ("", "")
    word, n = m.group(1).title(), m.group(2)
    return (f"{ {'Season': '시즌', 'Part': '파트', 'Volume': '볼륨'}[word] } {n}", f"{word} {n}")


def pitch(info, title):
    """위키백과 요약만 근거로 한 줄 소개·장르를 쓴다. 근거가 없으면 빈 값."""
    if not info or not (info["en"] or info["ko"]) or not os.environ.get("GEMINI_API_KEY"): return None
    key = os.environ["GEMINI_API_KEY"].strip()
    prompt = f"""Write a tiny card blurb for the Netflix title "{title}" using ONLY facts stated in the Wikipedia text below. Do not add anything that is not in the text
(no ratings, no awards, no cast unless stated, no plot twists or spoilers past the setup). If the text is not about this title, return {{"ok": false}}.
Tone: dry, deadpan, short. No emoji, no exclamation marks.
Return ONLY JSON: {{"ok": true, "genre_ko": "장르 (max 8 chars, 예: 범죄 스릴러)", "genre_en": "max 16 chars",
 "line_ko": "한 줄 소개, 결말 스포일러 금지 (max 30 chars, ~하는 이야기. 식)", "line_en": "one-line setup, no spoilers (max 52 chars)",
 "who_ko": "이런 사람한테 추천 (max 18 chars, 예: 주말 몰아보기 할 사람)", "who_en": "who it's for (max 34 chars)"}}
WIKIPEDIA (English): {info['en']}
WIKIPEDIA (Korean): {info['ko']}"""
    for m in models(key)[:4]:
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", headers={"x-goog-api-key": key},
                          json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"}}, timeout=60)
        if not r.ok: continue
        try:
            j = json.loads(re.sub(r"^```json|```$", "", r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()).strip())
            if not j.get("ok"): return None
            assert len(j["line_ko"]) <= 34 and len(j["line_en"]) <= 60 and len(j["who_ko"]) <= 22 and len(j["who_en"]) <= 40 and len(j["genre_ko"]) <= 10
            assert not re.search(r"[!！]", j["line_ko"] + j["line_en"])
            return j
        except Exception as e: print("  소개 문구 실패", m, e)
    return None


def label(row, region, info):
    t = row["show_title"]
    if region == "kr" and info and info.get("ko_title"): t = info["ko_title"]
    s = season(row)[0 if region == "kr" else 1]
    return t, s


def build(region, week, tv, film, day):
    ko = region == "kr"; end = dt.date.fromisoformat(week); start = end - dt.timedelta(days=6)
    yr = end.year; top = tv[0]; info = wiki(top["show_title"], "tv", yr); p = pitch(info, top["show_title"])
    title, seas = label(top, region, info)
    rest = []
    for row in tv[1:5]:
        t, s = label(row, region, wiki(row["show_title"], "tv", yr) if ko else None); rest.append((int(row["weekly_rank"]), t, s))
    f = film[0] if film else None
    ft = label(f, region, wiki(f["show_title"], "film", yr) if ko else None)[0] if f else ""
    weeks = int(top.get("cumulative_weeks_in_top_10") or 1)
    rng = f"{start.month}/{start.day}–{end.month}/{end.day}"
    c = dict(top="SUNDAY NETFLIX", date=day, handle=f"@reddenva.{region}",
             kicker=(f"지난주 한국 넷플릭스 시리즈 1위 · {rng}" if ko else f"Last week's #1 series on Netflix US · {rng}"),
             title=title, season=seas, genre=(p or {}).get("genre_ko" if ko else "genre_en", ""),
             line=(p or {}).get("line_ko" if ko else "line_en", "") or ("지난주 한국에서 가장 많이 본 넷플릭스 시리즈." if ko else "The most-watched Netflix series in the US last week."), who=(p or {}).get("who_ko" if ko else "who_en", ""), who_label="추천: " if ko else "For: ",
             weeks=(f"{weeks}주째 Top 10" if ko else f"{weeks} week{'s' if weeks > 1 else ''} in Top 10"),
             list_title="시리즈 2~5위" if ko else "Series #2–5", rest=rest,
             film_label="영화 1위" if ko else "#1 film", film=ft,
             foot=["출처: 넷플릭스 공식 Top 10 (주간 시청 순위)" if ko else "Source: Netflix official Top 10 (weekly)",
                   "레드덴바 · 매주 일요일, 이번 주 뭐 볼까" if ko else "Red Denva · Every Sunday, what to watch"])
    s_txt = f" {seas}" if seas else ""
    tag = re.sub(r"[^0-9A-Za-z가-힣]", "", title)[:24]
    cap = (f"🍿 지난주 한국 넷플릭스 시리즈 1위: 《{title}》{s_txt}\n\n#{tag} #넷플릭스 #넷플릭스추천 #드라마추천 #주말뭐보지 #레드덴바" if ko else
           f"🍿 Last week's #1 series on Netflix US: {title}{s_txt}\n\n#{tag} #Netflix #WhatToWatch #NetflixTop10 #weekend #reddenva")
    return c, cap


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--region", required=True, choices=["kr", "us"])
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args(); region = a.region
    tz = ZoneInfo(weather.REGIONS[region]["tz"]); today = dt.datetime.now(tz).date(); day = today.isoformat()
    os.makedirs("out", exist_ok=True)
    if not a.force and today.weekday() != 6:
        print("일요일이 아님 → 건너뜀"); return
    lp = f"out/netflix-{region}-latest.json"
    if not a.force and os.path.exists(lp) and json.load(open(lp, encoding="utf-8")).get("date") == day:
        print("오늘 이미 만들었음. 건너뜀"); return
    week, tv, film = load(region)
    if not tv: raise RuntimeError("시리즈 순위가 비어 있음")
    card, cap = build(region, week, tv, film, day)
    print(json.dumps(card, ensure_ascii=False)); print(cap)
    img_rel = f"out/netflix-{region}-{day}.jpg"; netflix_render.card(card, img_rel)
    if a.dry_run: print("(dry-run) 카드 저장:", img_rel); return
    git_push(["out"], f"netflix {region} {day} card")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    url = f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{sha}/{img_rel}"
    for _ in range(12):
        if requests.head(url, timeout=15).ok: break
        time.sleep(5)
    with open(lp, "w", encoding="utf-8") as fh:
        json.dump({"date": day, "image_url": url, "caption": cap, "title": "netflix of the week"}, fh, ensure_ascii=False)
    git_push(["out"], f"netflix {region} {day} latest.json"); print("저장 완료:", url)


if __name__ == "__main__":
    main()
