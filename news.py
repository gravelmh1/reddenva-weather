"""매주 화요일 '이번 주 좋은 뉴스 TOP 3' 카드를 만든다.
한국판=한국 소식 / 미국판=미국 소식. 무료 RSS에서 지난 7일 기사를 모아 Gemini가 3개를 고르고 요약(근거 글에 있는 내용만).
사용: python news.py --region kr|us [--dry-run] [--force]"""
import argparse, datetime as dt, email.utils, json, os, re, time, urllib.parse
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
import news_render, weather
from books import git_push, models

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def gnews(q, ko):
    q = urllib.parse.quote(q + " when:7d")
    return (f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko" if ko
            else f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en")


FEEDS = {
    "kr": [gnews("훈훈 OR 미담 OR 선행 OR 감동", True), gnews("쾌거 OR 세계 최초 OR 국내 최초 OR 개발 성공", True),
           gnews("기부 OR 나눔 OR 의인 OR 구조 OR 기적", True), gnews("합격 OR 수상 OR 우승 OR 신기록 OR 복원", True)],
    "us": [gnews("heartwarming OR \"good news\" OR kindness", False), gnews("breakthrough OR \"first ever\" OR milestone OR \"record low\"", False),
           "https://www.goodnewsnetwork.org/feed/", "https://www.positive.news/feed/",
           "https://www.goodgoodgood.co/articles/rss.xml"],
}


def clean(html):
    return re.sub(r"\s+", " ", BeautifulSoup(html or "", "html.parser").get_text(" ")).strip()


def fetch_feed(url, since):
    try:
        r = requests.get(url, headers=UA, timeout=30); r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        print("  피드 실패:", url[:70], str(e)[:80]); return []
    out = []
    for it in root.iter("item"):
        g = lambda t: (it.findtext(t) or "").strip()
        title = clean(g("title"))
        src = it.find("source"); name = (src.text or "").strip() if src is not None else ""
        body = clean(it.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or g("description"))
        if "news.google.com" in url:   # 구글뉴스: 제목 끝의 '- 매체명' 분리, 설명은 관련 기사 제목이라 쓰지 않음
            if " - " in title and not name: title, name = title.rsplit(" - ", 1)
            elif name and title.endswith(" - " + name): title = title[: -len(name) - 3]
            body = ""
        try: d = email.utils.parsedate_to_datetime(g("pubDate")).astimezone(dt.timezone.utc)
        except Exception: d = None
        if d and d < since: continue
        if not name: name = urllib.parse.urlparse(url).netloc.replace("www.", "").split(".")[0]
        name = {"goodnewsnetwork": "Good News Network", "goodgoodgood": "Good Good Good"}.get(name, name)
        out.append(dict(title=title, text=body[:900], src=name, link=g("link")))
    print(f"  {url[:60]}… → {len(out)}건"); return out


BAD = {"kr": r"동물|강아지|고양이|반려|코알라|판다|새끼|펫|멸종|야생|구조견|비단뱀|호랑이|고래|사망|숨져|숨진|사고|화재|살인|구속|재판|논란|선거|대통령|국회|정당|투표|수사|검찰|의혹|전쟁|참사|폭행|사기",
       "us": r"\b(dog|dogs|cat|cats|puppy|kitten|animal|animals|zoo|wildlife|pet|pets|horse|bird|birds|whale|bear|otter|elephant|turtle|dies|died|death|killed|shooting|murder|trump|biden|election|congress|senate|ice|immigration|lawsuit|war|crash|fire)\b"}


def gather(region, since):
    seen, items = set(), []
    for u in FEEDS[region]:
        for it in fetch_feed(u, since):
            k = re.sub(r"\W+", "", it["title"].lower())[:40]
            if not k or k in seen: continue
            if re.search(BAD[region], it["title"] + " " + it["text"][:300], re.I): continue
            seen.add(k); items.append(it)
    return items


def pick(region, items, lang):
    key = os.environ["GEMINI_API_KEY"].strip(); ko = lang == "ko"
    lst = "\n".join(f"[{i}] ({it['src']}) {it['title']}" + (f" — {it['text'][:500]}" if it["text"] else "") for i, it in enumerate(items))
    if ko:
        spec = ('{"items":[{"id":번호,"hero":"소제목 12자 이내(키워드)","head":"헤드라인 18자 이내, 반드시 ~어요 체(예: ~했어요, ~성공했어요), ~습니다 금지","desc":"설명 1~2문장 70자 이내, 반드시 ~어요 체(~했어요), ~습니다 금지, 헤드라인을 그대로 반복하지 말고 후보 글의 추가 사실을 담기, 후보 글에 있는 사실만","country":"소식이 일어난 나라 코드(KR/US/기타)"}] (정확히 3개),'
                ' "quote":["한마디 첫 줄 16자 이내","둘째 줄 16자 이내"]}')
        place = "한국에서 일어난 소식"
        tone = '핵심 메시지는 "좋은 것만 보고 삽시다"(나쁜 소식은 안 봐도 된다, 좋은 것만 챙기자). 무심하고 건조한 한 마디(말투는 ~입니다/~죠). 예시 느낌(그대로 베끼지 말 것): "오늘은 이 정도면 충분합니다 / 좋은 소식만 챙겨 가시죠", "세상 괜찮은 구석이 꽤 있네요 / 이것만 보고 삽시다". 느낌표·이모지·"힘내요"·오글거리는 표현 금지'
    else:
        spec = ('{"items":[{"id":number,"hero":"short label max 22 chars","head":"headline max 40 chars","desc":"1-2 sentences max 100 chars, only facts in the candidate text","country":"country code where it happened (KR/US/other)"}] (exactly 3),'
                ' "quote":["line 1 max 30 chars","line 2 max 30 chars"]}')
        place = "something that happened in the United States"
        tone = 'core message: "let\'s only look at the good stuff" (we can skip the bad news). A deadpan, dry two-line remark. Style examples, do not copy: "Good things happened. Noted. / That is enough news for today.", "Plenty of decent corners out there. / Let\'s just look at these." No exclamation marks, emojis, "stay strong" or cringe'
    prompt = f"""You curate a weekly feel-good news card. From the CANDIDATES pick exactly 3 stories.
MUST: positive and uplifting (kindness, achievements, discoveries, milestones, cultural wins, community good); {place}; different topics from each other.
PREFER: warm human stories and small acts of kindness, discoveries and real achievements over ribbon-cuttings, awards ceremonies, openings or generic announcements.
MUST: the story happens in the same country as the card (KR card = Korea only, US card = United States only; foreign stories are not allowed even if the outlet is local).
MUST NOT: animals/pets/wildlife; deaths, crime, disasters, wars, tragedy-with-silver-lining; politics, elections, parties, policy fights or anything disputed; shops/products/ads/promotions; celebrity gossip; investing/stock tips; anything not clearly stated in the candidate text.
Use ONLY facts in the candidate text. Never invent numbers, names or places. If a story is thin, write a shorter desc.
QUOTE: {tone}. Do not just repeat the example phrase; write a fresh line each time.
Return ONLY JSON: {spec}

CANDIDATES:
{lst[:30000]}"""
    lim = dict(hero=12, head=18, desc=70) if ko else dict(hero=22, head=40, desc=105)
    last = None
    for m in (models(key)[:4] * 2):
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", headers={"x-goog-api-key": key},
                          json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.5, "responseMimeType": "application/json"}}, timeout=120)
        if not r.ok: last = f"{m} {r.status_code} {r.text[:150]}"; print("모델 건너뜀:", last); continue
        try:
            j = json.loads(re.sub(r"^```json|```$", "", r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()).strip())
            its, ids = j["items"][:3], set()
            for x in its:
                x["id"] = int(x["id"]); assert 0 <= x["id"] < len(items) and x["id"] not in ids; ids.add(x["id"])
                assert str(x.get("country", "")).strip().upper() == region.upper(), f"나라 {x.get('country')}"
                for k, n in lim.items():
                    x[k] = x[k].strip()
                    if k == "desc" and len(x[k]) > n:   # 문장 단위로 줄이기
                        acc = ""
                        for sn in re.split(r"(?<=[.!?])\s+", x[k]):
                            if len((acc + " " + sn).strip()) <= n: acc = (acc + " " + sn).strip()
                            else: break
                        x[k] = acc
                    assert x[k] and len(x[k]) <= n + (0 if k == "desc" else 4), f"{k} 길이 {len(x[k])}"
            assert len(its) == 3 and len(j["quote"]) >= 2 and all(len(q) <= (20 if ko else 36) for q in j["quote"][:2])
            print("요약 모델:", m); j["items"] = its; return j
        except Exception as e: last = f"{m} 검증 실패 {e}"; print("모델 건너뜀:", last)
    raise RuntimeError(f"Gemini 선별 실패: {last}")


def build(region, j, items, day):
    ko = region == "kr"; d = dt.date.fromisoformat(day)
    rows = [dict(hero=x["hero"], head=x["head"], desc=x["desc"], src=(f"출처: {items[x['id']]['src']}" if ko else f"Source: {items[x['id']]['src']}")) for x in j["items"]]
    q = [s.strip().strip("“”\"") for s in j["quote"][:2]]
    if ko:
        c = dict(top=f"WEEKLY GOOD NEWS · {d:%Y.%m.%d}", handle="@reddenva.kr", badge="이번 주 좋은 뉴스", title="이번 주 TOP 3", items=rows,
                 head="오늘의 레드덴바 한마디", quote=q, foot=["공개 보도를 요약했어요.", "AI 요약이라 오류가 있을 수 있어요."])
        cap = "📰 이번 주 좋은 뉴스 TOP 3\n\n" + "\n".join(f"{i+1}. {r['head']}\n{r['desc']}" for i, r in enumerate(rows)) + \
              f"\n\n💬 {q[0]} {q[1]}\n\n#좋은뉴스 #훈훈한소식 #긍정뉴스 #레드덴바"
    else:
        c = dict(top=f"WEEKLY GOOD NEWS · {d:%b %d, %Y}".upper(), handle="@reddenva.us", badge="This week's good news", title="This Week's Top 3", items=rows,
                 head="Red Denva says", quote=q, foot=["Summarized from public reports.", "AI summary may contain errors."])
        cap = "📰 This week's good news: Top 3\n\n" + "\n".join(f"{i+1}. {r['head']}\n{r['desc']}" for i, r in enumerate(rows)) + \
              f"\n\n💬 {q[0]} {q[1]}\n\n#goodnews #positivenews #uplifting #reddenva"
    return c, cap


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--region", required=True, choices=["kr", "us"])
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args(); region = a.region; lang = "ko" if region == "kr" else "en"
    tz = ZoneInfo(weather.REGIONS[region]["tz"]); day = dt.datetime.now(tz).date().isoformat()
    os.makedirs("out", exist_ok=True); os.makedirs("state", exist_ok=True)
    if not a.force and dt.date.fromisoformat(day).weekday() != 1:
        print("화요일이 아님 → 건너뜀"); return
    sf = f"state/news_{region}.txt"; posted = open(sf, encoding="utf-8").read().splitlines() if os.path.exists(sf) else []
    if posted and posted[-1].split("|")[0] == day and not a.force:
        print("오늘 이미 만들었음. 건너뜀"); return
    done = {re.sub(r"\W+", "", t.lower())[:40] for l in posted for t in l.split("|")[1:]}
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8)
    items = [it for it in gather(region, since) if re.sub(r"\W+", "", it["title"].lower())[:40] not in done]
    print(f"후보 {len(items)}건")
    if len(items) < 8: raise RuntimeError("후보 기사가 너무 적음 → 이번 주는 올리지 않음")
    j = pick(region, items, lang)
    print(json.dumps(j, ensure_ascii=False, indent=1))
    for x in j["items"]: print("  ·", items[x["id"]]["src"], "|", items[x["id"]]["title"], "|", items[x["id"]]["link"][:80])
    c, cap = build(region, j, items, day)
    img_rel = f"out/news-{region}-{day}.jpg"; news_render.card3(c, img_rel)
    if a.dry_run: print("(dry-run) 카드 저장:", img_rel); print("CARDJSON " + json.dumps(c, ensure_ascii=False)); print(cap); return
    with open(sf, "a", encoding="utf-8") as fh: fh.write(f"{day}|" + "|".join(items[x["id"]]["title"] for x in j["items"]) + "\n")
    git_push(["out", "state"], f"news {region} {day} card")
    repo, br = os.environ["GITHUB_REPOSITORY"], os.environ.get("GITHUB_REF_NAME", "main")
    url = f"https://raw.githubusercontent.com/{repo}/{br}/{img_rel}"
    for _ in range(12):
        if requests.head(url, timeout=15).ok: break
        time.sleep(5)
    with open(f"out/news-{region}-latest.json", "w", encoding="utf-8") as fh:
        json.dump({"date": day, "image_url": url, "caption": cap, "title": "weekly good news"}, fh, ensure_ascii=False)
    git_push(["out"], f"news {region} {day} latest.json"); print("저장 완료:", url)


if __name__ == "__main__":
    main()
