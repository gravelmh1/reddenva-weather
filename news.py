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
    "kr": [gnews("훈훈 OR 미담 OR 선행 OR 감동", True), gnews("기부 OR 나눔 OR 의인 OR 재회 OR 기적", True),
           gnews("따뜻한 OR 눈물 OR 고마워 OR 깜짝 선물 OR 감사", True), gnews("완치 OR 생명 구한 OR 장학금 OR 봉사", True),
           "https://www.yna.co.kr/rss/society.xml", "https://www.hani.co.kr/rss/society/", "https://www.khan.co.kr/rss/rssdata/society_news.xml", "https://rss.nocutnews.co.kr/nocutnews.xml"],
    "us": [gnews("heartwarming OR \"good news\" OR kindness", False), gnews("generosity OR donated OR reunited OR surprise OR \"paid it forward\"", False),
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


BAD = {"kr": r"동물|강아지|고양이|반려|코알라|판다|새끼|펫|멸종|야생|구조견|비단뱀|호랑이|고래|사망|숨져|숨진|사고|화재|살인|구속|재판|논란|선거|대통령|국회|정당|투표|수사|검찰|의혹|전쟁|참사|폭행|사기|우승|수상|개관|복원|출시|계약|투자|선정|협약|대상|MVP|챔피언|발표|공개|착공|준공|MOU|배우|가수|아이돌|연예|개그맨|방송인|예능|드라마|팬들|출연|열애|결혼|이혼|스타",
       "us": r"\b(dog|dogs|cat|cats|puppy|kitten|animal|animals|zoo|wildlife|pet|pets|horse|bird|birds|whale|bear|otter|elephant|turtle|dies|died|death|wins|win|award|awarded|championship|opens|opening|launch|launches|killed|shooting|murder|trump|biden|election|congress|senate|ice|immigration|lawsuit|war|crash|fire)\b"}


def gather(region, since):
    seen, items = set(), []
    for u in FEEDS[region]:
        for it in fetch_feed(u, since):
            k = re.sub(r"\W+", "", it["title"].lower())[:40]
            if not k or k in seen: continue
            if re.search(BAD[region], it["title"] + " " + it["text"][:300] + " " + it["src"], re.I): continue
            if region == "kr" and "news.google" not in u and not re.search(r"훈훈|미담|선행|기부|나눔|의인|재회|기적|감사|선물|장학금|봉사|완치|구했|도왔|양보", it["title"]): continue
            seen.add(k); items.append(it)
    return items


def gem(prompt, temp=0.3):
    key = os.environ["GEMINI_API_KEY"].strip(); last = None
    for m in (models(key)[:4] * 2):
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", headers={"x-goog-api-key": key},
                          json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": temp, "responseMimeType": "application/json"}}, timeout=120)
        if not r.ok: last = f"{m} {r.status_code}"; continue
        try: return json.loads(re.sub(r"^```json|```$", "", r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()).strip())
        except Exception as e: last = f"{m} {e}"
    raise RuntimeError(f"Gemini 실패: {last}")


def shortlist(items, region):
    """1차: 제목만 보고 '구체적인 사람 이야기' 후보 12개로 압축."""
    lst = "\n".join(f"[{i}] {it['title']}" for i, it in enumerate(items))
    p = f"""From these news titles pick the 12 best (at least 8 if available) that look like a CONCRETE, specific human story with a clear 'who did what' and a happy outcome, that happened in {'Korea' if region=='kr' else 'the United States'}.
Reject: rescues from fire/drowning/accidents, vague or syrupy titles, clickbait ('눈물', 'tears', 'you won't believe'), generic campaigns, donations by companies/organizations as PR, politics, sports, awards, openings, celebrities, animals, anything sad, anything unclear.
Return ONLY JSON: {{"ids":[numbers]}}

{lst[:20000]}"""
    ids = gem(p)["ids"]
    return [i for i in dict.fromkeys(int(x) for x in ids) if 0 <= i < len(items)][:12]


def enrich(it):
    """구글뉴스 링크를 원문 주소로 풀고 본문 앞부분을 가져온다. 실패하면 기존 text 유지."""
    link = it["link"]
    try:
        if "news.google.com" in link:
            from googlenewsdecoder import gnewsdecoder
            d = {}
            for wait in (0, 6, 12):
                time.sleep(wait); d = gnewsdecoder(link, interval=2)
                if d.get("success"): break
            if not d.get("success"): print("  디코드 실패:", str(d)[:100]); return
            link = d["decoded_url"]
        r = requests.get(link, headers=UA, timeout=25); r.raise_for_status()
        r.encoding = r.apparent_encoding if not r.encoding or r.encoding.lower() == "iso-8859-1" else r.encoding
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "nav", "header", "footer", "aside"]): t.decompose()
        paras = [clean(p.get_text(" ")) for p in soup.find_all("p")]
        body = " ".join(p for p in paras if len(p) > 40)
        og = soup.find("meta", property="og:description")
        txt = ((og.get("content") + " ") if og and og.get("content") else "") + body
        print("  본문", len(txt), link[:70])
        if len(txt) > 150: it["text"] = txt[:1200]; it["link"] = link
    except Exception as e:
        print("  본문 실패:", it["title"][:30], str(e)[:60])


def pick(region, items, lang):
    key = os.environ["GEMINI_API_KEY"].strip(); ko = lang == "ko"
    lst = "\n".join(f"[{i}] ({it['src']}) {it['title']}" + (f" — {it['text'][:500]}" if it["text"] else "") for i, it in enumerate(items))
    if ko:
        spec = ('{"items":[{"id":번호,"hero":"소제목 12자 이내(키워드)","head":"헤드라인 18자 이내, 반드시 ~어요 체(예: ~했어요, ~성공했어요), ~습니다 금지","desc":"설명 1~2문장 70자 이내, 반드시 ~어요 체(~했어요), ~습니다 금지, 헤드라인을 그대로 반복하지 말고 후보 글의 추가 사실을 담기, 후보 글에 있는 사실만","country":"소식이 일어난 나라 코드(KR/US/기타)"}] (정확히 3개),'
                '}')
        place = "한국에서 일어난 소식"
    else:
        spec = ('{"items":[{"id":number,"hero":"short label max 22 chars","head":"headline max 40 chars","desc":"1-2 sentences max 100 chars, only facts in the candidate text","country":"country code where it happened (KR/US/other)"}] (exactly 3)}')
        place = "something that happened in the United States"
    prompt = f"""You curate a weekly feel-good news card. From the CANDIDATES pick exactly 3 stories.
MUST: genuinely heartwarming AND concrete — a real, specific episode (who did what, where, what happened) that makes an ordinary reader smile naturally. NOT forced or syrupy sentimentality, NOT vague, NOT promotional. Prefer stories with a clear, understandable plot a reader can retell in one sentence.
MUST: desc states the concrete facts (who, what, outcome) in plain, calm words; no exaggeration, no 'touching'/'moving' adjectives, no tear-jerking tone. Skip any candidate whose text does not make the story clear. {place}; three DIFFERENT kinds of stories (never two rescues, never two of the same theme such as firefighters/donations/reunions); prefer everyday relatable moments over dramatic emergencies; avoid near-death rescue and fire/drowning/accident stories altogether.
STRICTLY AVOID as dry/neutral news: sports results and championships, awards and prizes, restorations, openings, product/tech/industry announcements, economy/export figures, government programs, institutional press releases. If fewer than 3 truly heartwarming stories exist, still pick the 3 warmest.
MUST: the story happens in the same country as the card (KR card = Korea only, US card = United States only; foreign stories are not allowed even if the outlet is local).
MUST NOT: animals/pets/wildlife; deaths, crime, disasters, wars, tragedy-with-silver-lining; politics, elections, parties, policy fights or anything disputed; shops/products/ads/promotions; celebrity gossip; investing/stock tips; anything not clearly stated in the candidate text.
Use ONLY facts in the candidate text. Never invent numbers, names or places. If a story is thin, write a shorter desc.
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
            assert len(its) == 3
            print("요약 모델:", m); j["items"] = its; return j
        except Exception as e: last = f"{m} 검증 실패 {e}"; print("모델 건너뜀:", last)
    raise RuntimeError(f"Gemini 선별 실패: {last}")

QUOTES = {
    "kr": [("세상에서 가장 아름다운 것은", "마음으로 느껴야 해요", "헬렌 켈러"),
           ("아무리 작은 친절도", "결코 헛되지 않아요", "이솝"),
           ("천 리 길도", "한 걸음부터 시작해요", "노자"),
           ("어둠을 저주하기보다", "촛불 하나를 켜요", "속담"),
           ("친절은 듣지 못해도 들리고", "보지 못해도 보이는 말이에요", "마크 트웨인"),
           ("행복은 나눌수록", "두 배가 돼요", "속담"),
           ("세상을 좋게 만드는 일은", "지금 바로 시작할 수 있어요", "안네 프랑크")],
    "us": [("The best and most beautiful things", "must be felt with the heart.", "Helen Keller"),
           ("No act of kindness,", "no matter how small, is wasted.", "Aesop"),
           ("A journey of a thousand miles", "begins with a single step.", "Lao Tzu"),
           ("Better to light a candle", "than to curse the darkness.", "Proverb"),
           ("Kindness is the language the deaf", "can hear and the blind can see.", "Mark Twain"),
           ("Happiness shared", "is happiness doubled.", "Proverb"),
           ("Nobody need wait a moment", "before starting to improve the world.", "Anne Frank")],
}


def build(region, j, items, day):
    ko = region == "kr"; d = dt.date.fromisoformat(day)
    rows = [dict(hero=x["hero"], head=x["head"], desc=x["desc"], src=(f"출처: {items[x['id']]['src']}" if ko else f"Source: {items[x['id']]['src']}")) for x in j["items"]]
    ql = QUOTES[region]; qa, qb, who = ql[d.isocalendar()[1] % len(ql)]; q = [qa, qb]
    if ko:
        c = dict(top=f"WEEKLY GOOD NEWS · {d:%Y.%m.%d} ({'월화수목금토일'[d.weekday()]})", handle="@reddenva.kr", badge="이번 주 좋은 뉴스", title="이번 주 TOP 3", items=rows,
                 head="", author=who, quote=q, foot=["공개 보도를 요약했어요.", "AI 요약이라 오류가 있을 수 있어요."])
        cap = "📰 이번 주 좋은 뉴스 TOP 3\n\n" + "\n".join(f"{i+1}. {r['head']}\n{r['desc']}" for i, r in enumerate(rows)) + \
              f"\n\n💬 \"{q[0]} {q[1]}\" — {who}\n\n#좋은뉴스 #훈훈한소식 #긍정뉴스 #레드덴바"
    else:
        c = dict(top=f"WEEKLY GOOD NEWS · {d:%b %d, %Y} ({d:%a})".upper(), handle="@reddenva.us", badge="This week's good news", title="This Week's Top 3", items=rows,
                 head="", author=who, quote=q, foot=["Summarized from public reports.", "AI summary may contain errors."])
        cap = "📰 This week's good news: Top 3\n\n" + "\n".join(f"{i+1}. {r['head']}\n{r['desc']}" for i, r in enumerate(rows)) + \
              f"\n\n💬 \"{q[0]} {q[1]}\" — {who}\n\n#goodnews #positivenews #uplifting #reddenva"
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
    sl = shortlist(items, region); items = [items[i] for i in sl]; print("1차 후보", len(items))
    for it in items: enrich(it)
    ANIMAL = {"kr": r"동물|강아지|반려|고양이|댕댕|멍멍|펫|새끼|야생", "us": r"\b(dog|dogs|cat|cats|puppy|pup|kitten|pet|pets|animal|animals|horse|wildlife)\b"}[region]
    items = [it for it in items if len(it["text"]) > 150 and not re.search(ANIMAL, it["title"] + " " + it["text"][:600], re.I)]; print("본문 확보", len(items))
    if len(items) < 3: raise RuntimeError("본문 확보 기사 부족")
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
