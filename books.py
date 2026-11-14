"""매주 지난주 베스트셀러 1권을 골라 '줄거리·핵심·결론' 카드로 만든다.
순위: 한국=알라딘 한국소설 주간 / 미국=NYT 하드커버 소설. 줄거리: 웹에서 모은 글만 근거로 Gemini가 요약(검색 기능은 안 씀).
사용: python books.py --region kr|us [--dry-run] [--force]"""
import argparse, datetime as dt, json, os, re, subprocess, sys, time, urllib.parse
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
import books_render, weather

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"}
BAD = ("youtube.com", "instagram.com", "facebook.com", "tiktok.com", "pinterest.", "amazon.", "coupang.")


def sh(*a, check=True): return subprocess.run(a, check=check, capture_output=True, text=True)


def git_push(paths, msg):
    sh("git", "config", "user.name", "weather-bot"); sh("git", "config", "user.email", "weather-bot@users.noreply.github.com")
    sh("git", "add", *paths)
    if sh("git", "diff", "--cached", "--quiet", check=False).returncode == 0: return
    sh("git", "commit", "-m", msg)
    for _ in range(4):
        sh("git", "pull", "--rebase", "--autostash", check=False)
        if sh("git", "push", check=False).returncode == 0: return
        time.sleep(5)
    raise RuntimeError("git push 실패")


# ---------- 1. 순위 ----------
def aladin_list():
    r = requests.get("https://www.aladin.co.kr/shop/common/wbest.aspx?BestType=Bestseller&BranchType=1&CID=50993", headers=UA, timeout=30)
    r.raise_for_status(); soup = BeautifulSoup(r.text, "html.parser")
    m = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d)주", soup.get_text(" "))
    period = f"{int(m.group(2))}월 {m.group(3)}주" if m else ""
    out = []
    for box in soup.select("div.ss_book_box"):
        a = box.select_one("a.bo3")
        if not a: continue
        title = re.sub(r"\s*[-(\[].*$", "", a.get_text(strip=True)) if len(a.get_text(strip=True)) > 40 else a.get_text(strip=True)
        author = ""
        for li in box.find_all("li"):
            t = li.get_text(" ", strip=True)
            if "(지은이)" in t:
                author = t.split("(지은이)")[0].strip(); break
        out.append(dict(title=title, author=author, desc="", period=period))
        if len(out) >= 8: break
    if not out: raise RuntimeError("알라딘 페이지에서 책 목록을 못 읽음 (구조 변경 가능성)")
    return out


def nyt_list():
    key = os.environ.get("NYT_API_KEY", "").strip()
    r = requests.get("https://api.nytimes.com/svc/books/v3/lists/current/hardcover-fiction.json", params={"api-key": key}, timeout=30)
    r.raise_for_status(); res = r.json()["results"]; out = []
    for b in res["books"][:8]:
        out.append(dict(title=b["title"].title().replace("'S", "'s"), author=re.sub(r"^by\s+", "", b["author"], flags=re.I),
                        desc=b.get("description", ""), period=res.get("published_date", "")))
    return out


# ---------- 2. 줄거리 자료 (공식 API만 사용: 위키백과, Google Books, 네이버 검색 API) ----------
def wiki_text(title, author, lang):
    out = []
    for lg in (("ko", "en") if lang == "ko" else ("en",)):
        try:
            h = {"User-Agent": "reddenva-books/1.0 (https://github.com/gravelmh1/reddenva-weather)"}
            r = requests.get(f"https://{lg}.wikipedia.org/w/api.php", params={"action": "query", "list": "search", "srsearch": f"{title} {author}", "srlimit": 3, "format": "json"}, headers=h, timeout=20)
            for hit in r.json()["query"]["search"]:
                if title.split()[0].lower() not in hit["title"].lower() and title.split()[0].lower() not in hit["snippet"].lower(): continue
                e = requests.get(f"https://{lg}.wikipedia.org/w/api.php", params={"action": "query", "prop": "extracts", "explaintext": 1, "titles": hit["title"], "format": "json"}, headers=h, timeout=20).json()
                txt = next(iter(e["query"]["pages"].values())).get("extract", "")
                if len(txt) > 300: out.append(f"[위키백과 {lg}: {hit['title']}]\n{txt[:7000]}"); break
        except Exception as ex: print("위키 실패", lg, type(ex).__name__)
    return out


def google_books(title, author):
    try:
        r = requests.get("https://www.googleapis.com/books/v1/volumes", params={"q": f"intitle:{title} inauthor:{author}", "maxResults": 3}, timeout=20)
        ds = [i["volumeInfo"].get("description", "") for i in r.json().get("items", [])]
        ds = [d for d in ds if len(d) > 150]
        return [f"[Google Books 소개]\n{d}" for d in ds[:2]]
    except Exception as ex: print("Google Books 실패", type(ex).__name__); return []


def naver_snippets(title, author):
    cid, sec = os.environ.get("NAVER_CLIENT_ID", "").strip(), os.environ.get("NAVER_CLIENT_SECRET", "").strip()
    if not cid: return []
    hdr = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec}; lines = []
    for kind in ("blog", "webkr", "news", "kin"):
        try:
            r = requests.get(f"https://openapi.naver.com/v1/search/{kind}.json", params={"query": f"{title} {author} 줄거리", "display": 20, "sort": "sim"}, headers=hdr, timeout=20)
            for it in r.json().get("items", []):
                t = re.sub(r"<[^>]+>|&[a-z]+;", "", it.get("description", ""))
                if title.split()[0] in t or title.split()[0] in re.sub(r"<[^>]+>", "", it.get("title", "")): lines.append(t)
        except Exception as ex: print("네이버 실패", kind, type(ex).__name__)
    return [f"[네이버 검색 요약문 모음]\n" + "\n".join(lines[:60])] if lines else []


def gather(book, lang):
    chunks = wiki_text(book["title"], book["author"], lang) + google_books(book["title"], book["author"])
    if lang == "ko": chunks += naver_snippets(book["title"], book["author"])
    print("자료:", [c.split("]")[0] + "]" for c in chunks])
    return "\n\n".join(chunks), []


# ---------- 3. 요약(Gemini, 검색 기능 없이 일반 요약만) ----------
def models(key):
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"pageSize": 200}, headers={"x-goog-api-key": key}, timeout=30)
    r.raise_for_status()
    names = [m["name"].split("/")[-1] for m in r.json().get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
    names = [n for n in names if "flash" in n and not any(x in n for x in ("image", "tts", "live", "audio", "robotics", "computer", "native", "thinking", "8b"))]
    return sorted([n for n in names if "lite" in n], reverse=True) + sorted([n for n in names if "lite" not in n], reverse=True)


def summarize(book, material, lang):
    key = os.environ["GEMINI_API_KEY"].strip()
    if lang == "ko":
        spec = ('{"plot": 줄거리 한국어 2~3문장, 최대 95자, 설정과 전개 중심(결말 금지), "keys": [핵심 3개, 각 22자 이내 명사형/짧은 문장],'
                ' "quote": [읽은 척 멘트 두 줄, 각 줄 16자 이내, 큰따옴표 없이, 대화하듯 자연스럽게 이어지는 한 문장을 둘로 나눔], "tag": 12자 이내 한 줄 요약}')
        rule = "한국어로 쓰세요. 결말·반전은 쓰지 마세요."
    else:
        spec = ('{"plot": 2-3 sentences, max 170 characters, premise and setup only (no ending), "keys": [3 key points, max 42 chars each],'
                ' "quote": [a casual one-sentence line someone could say to sound like they read it, split into 2 lines, each max 32 chars, no quote marks], "tag": max 24 chars tagline}')
        rule = "Write in English. No ending or twist spoilers."
    prompt = f"""You summarize books for a social card. Use ONLY the facts in SOURCE TEXT (and METADATA). Never invent plot, names or events.
If the sources are thin, write less and stay general. {rule}
Return ONLY JSON: {spec}

METADATA: title={book['title']}; author={book['author']}; publisher blurb={book.get('desc','')}

SOURCE TEXT:
{material[:24000]}"""
    last = None
    for m in models(key)[:5]:
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", headers={"x-goog-api-key": key},
                          json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"}}, timeout=120)
        if r.ok:
            try:
                txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                j = json.loads(re.sub(r"^```json|```$", "", txt.strip()).strip())
                if j.get("plot") and len(j.get("keys", [])) >= 3 and len(j.get("quote", [])) >= 2:
                    print("요약 모델:", m); return j
            except Exception as e: last = f"{m} 파싱 실패 {e}"
        else: last = f"{m} {r.status_code} {r.text[:150]}"
        print("모델 건너뜀:", last)
    raise RuntimeError(f"Gemini 요약 실패: {last}")


# ---------- 4. 카드/캡션 ----------
def build(region, book, j, urls, period):
    ko = region == "kr"
    if ko:
        c = dict(top=f"WEEKLY BOOK · {period}차", handle="@reddenva.kr", badge="지난주 한국소설 베스트 1위" if book["rank"] == 1 else f"지난주 한국소설 베스트 {book['rank']}위",
                 src=f"알라딘 {period}", title=book["title"], author=book["author"], tag=j.get("tag", ""),
                 l1="줄거리", plot=j["plot"], l2="핵심", keys=j["keys"], head="이렇게 말하면 읽은 척 가능", headsub="(결론)",
                 quote=[f"“{j['quote'][0].strip('“”\"')}", f"{j['quote'][1].strip('“”\"')}”"],
                 foot1="순위: 알라딘 한국소설 주간 / 줄거리: 웹 자료 기반 AI 요약(결말 제외, 오류 가능)", foot2="마음에 들면 책도 읽어보세요")
        cap = (f"📚 지난주 한국소설 베스트 {book['rank']}위\n《{book['title']}》 {book['author']}\n\n{j['plot']}\n\n"
               f"💬 이렇게 말하면 읽은 척 가능\n“{j['quote'][0].strip('“”\"')} {j['quote'][1].strip('“”\"')}”\n\n#베스트셀러 #책추천 #소설추천 #아는척가이드 #레드덴바")
    else:
        d = dt.date.fromisoformat(book["period"]) if re.match(r"\d{4}-\d\d-\d\d", book.get("period", "")) else dt.date.today()
        c = dict(top=f"WEEKLY BOOK · NYT {d.strftime('%b %d').upper()}", handle="@reddenva.us", badge=f"Last week's #{book['rank']} fiction",
                 src="NYT Hardcover Fiction", title=book["title"], author=book["author"], tag=j.get("tag", ""),
                 l1="THE STORY", plot=j["plot"], l2="KEY POINTS", keys=j["keys"], head="Say this to sound like you read it", headsub="",
                 quote=[f"“{j['quote'][0].strip('“”\"')}", f"{j['quote'][1].strip('“”\"')}”"],
                 foot1="Rank: NYT Hardcover Fiction / Summary: AI from public sources, no ending, may contain errors", foot2="If you like it, read the book")
        cap = (f"📚 Last week's #{book['rank']} on the NYT Hardcover Fiction list\n{book['title']} by {book['author']}\n\n{j['plot']}\n\n"
               f"💬 Say this to sound like you read it:\n“{j['quote'][0].strip('“”\"')} {j['quote'][1].strip('“”\"')}”\n\n#bookstagram #bestseller #booktok #reddenva")
    return c, cap


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--region", required=True, choices=["kr", "us"])
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args(); region = a.region; lang = "ko" if region == "kr" else "en"
    tz = ZoneInfo(weather.REGIONS[region]["tz"]); day = dt.datetime.now(tz).date().isoformat()
    os.makedirs("out", exist_ok=True); os.makedirs("state", exist_ok=True)
    sf = f"state/books_{region}.txt"; posted = open(sf, encoding="utf-8").read().splitlines() if os.path.exists(sf) else []
    if posted and posted[-1].split("|")[0] == day and not a.force:
        print("오늘 이미 만들었음. 건너뜀"); return
    lst = aladin_list() if region == "kr" else nyt_list()
    for i, b in enumerate(lst): b["rank"] = i + 1
    print("목록:", *[f"{b['rank']}. {b['title']} / {b['author']}" for b in lst], sep="\n  ")
    done = {l.split("|")[1] for l in posted if "|" in l}
    pick = next((b for b in lst if b["title"] not in done), lst[0])
    print("선택:", pick["rank"], pick["title"])
    material, urls = gather(pick, lang)
    if len(material) < 300 and not pick.get("desc"):
        raise RuntimeError("줄거리 자료를 충분히 못 모음 → 이번 주는 올리지 않음")
    j = summarize(pick, material, lang)
    print(json.dumps(j, ensure_ascii=False, indent=1))
    c, cap = build(region, pick, j, urls, pick.get("period", ""))
    img_rel = f"out/books-{region}-{day}.jpg"; books_render.card(c, img_rel)
    if a.dry_run: print("(dry-run) 카드 저장:", img_rel); print(cap); return
    with open(sf, "a", encoding="utf-8") as fh: fh.write(f"{day}|{pick['title']}\n")
    git_push(["out", "state"], f"books {region} {day} card")
    repo, br = os.environ["GITHUB_REPOSITORY"], os.environ.get("GITHUB_REF_NAME", "main")
    url = f"https://raw.githubusercontent.com/{repo}/{br}/{img_rel}"
    for _ in range(12):
        if requests.head(url, timeout=15).ok: break
        time.sleep(5)
    with open(f"out/books-{region}-latest.json", "w", encoding="utf-8") as fh:
        json.dump({"date": day, "image_url": url, "caption": cap, "title": pick["title"]}, fh, ensure_ascii=False)
    git_push(["out"], f"books {region} {day} latest.json"); print("저장 완료:", url)


if __name__ == "__main__":
    main()
