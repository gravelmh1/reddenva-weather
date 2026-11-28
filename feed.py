"""Red Denva 시리즈 목록(피드) 만들기.

out/ 안의 카드 그림(책·좋은 뉴스·아기 동물(매일)·파생 브리핑·주말 여행 등)을 모아
out/feed-{region}.json 으로 정리한다. 날씨는 넣지 않는다.
블로그(red-denva-market-brief)가 이 파일을 읽어 카테고리 카드로 보여준다.

사용: python feed.py kr   /   python feed.py us
"""
import datetime as dt
import json
import os
import re
import sys

RAW = "https://raw.githubusercontent.com/gravelmh1/reddenva-weather/main/out/"
SERIES = {
    # 파일 앞부분: (카테고리 키, 한국어 이름, 영어 이름)
    "books": ("books", "이번 주 책", "Book of the week"),
    "news": ("news", "좋은 뉴스", "Good news"),
    "dart": ("coin", "동전 던지기", "Coin flip"),
    "puppy": ("animal", "아기 동물", "Baby animal"),
    "baby": ("animal", "오늘의 아기 동물", "Today's baby animal"),  # 매일 10시 영상 (baby-daily.yml)
    "deriv": ("deriv", "파생 브리핑", "Derivatives brief"),
    "trip": ("trip", "주말 여행", "Weekend trip"),
    "facts": ("facts", "동물 상식", "Animal facts"),
    "netflix": ("netflix", "넷플릭스", "Netflix"),
    "morning": ("brief", "모닝 브리프", "Morning Brief"),
    "close": ("brief", "마감 브리프", "Closing Brief"),
    "wrap": ("brief", "주간 정리", "Weekly Recap"),
    "ahead": ("brief", "다음 주 일정", "Week Ahead"),
}
KO_DAYS = "월화수목금토일"
EN_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def date_label(d, region):
    day = dt.date.fromisoformat(d)
    if region == "kr":
        return f"{day:%Y.%m.%d} ({KO_DAYS[day.weekday()]})"
    return f"{EN_DAYS[day.weekday()]}, {day:%b} {day.day}, {day.year}"


def clean(caption, kind=""):
    """캡션에서 해시태그 줄을 빼고 (제목, 본문)으로 나눈다. 책은 둘째 줄(책 이름)이 제목."""
    lines = [l.strip() for l in (caption or "").splitlines()]
    lines = [l for l in lines if l and not re.fullmatch(r"(#\S+\s*)+", l)]
    if kind == "books" and len(lines) > 1:
        lines = lines[1:]
    if not lines:
        return "", ""
    title = re.sub(r"^[^\w《\"'(\[]+", "", lines[0]).strip()
    body = " ".join(lines[1:]).strip()
    if len(body) > 420:
        body = body[:417].rstrip() + "…"
    return title, body


def main(region):
    out = "out"
    path = os.path.join(out, f"feed-{region}.json")
    old = {}
    if os.path.exists(path):
        for it in json.load(open(path, encoding="utf-8")).get("items", []):
            old[(it["series"], it["date"])] = it

    groups = {}
    pat = re.compile(rf"^({'|'.join(SERIES)})-{region}-(\d{{4}}-\d{{2}}-\d{{2}})(?:-(\d))?\.jpg$")
    for name in os.listdir(out):
        m = pat.match(name)
        if m:
            groups.setdefault((m.group(1), m.group(2)), []).append((int(m.group(3) or 0), name))

    latest = {}
    for kind in SERIES:
        p = os.path.join(out, f"{kind}-{region}-latest.json")
        if os.path.exists(p):
            latest[kind] = json.load(open(p, encoding="utf-8"))

    items = []
    for (kind, date), files in groups.items():
        key, ko, en = SERIES[kind]
        prev = old.get((key, date), {})
        title, text = prev.get("title", ""), prev.get("text", "")
        lj = latest.get(kind)
        if lj and lj.get("date") == date:
            title, text = clean(lj.get("caption", ""), kind)
        items.append({
            "series": key,
            "label": ko if region == "kr" else en,
            "date": date,
            "date_label": date_label(date, region),
            "title": title or (ko if region == "kr" else en),
            "text": text,
            "images": [RAW + n for _, n in sorted(files)],
        })
    order = list(s[0] for s in SERIES.values())
    items.sort(key=lambda x: (x["date"], -order.index(x["series"])), reverse=True)
    feed = {
        "region": region,
        "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "categories": [{"series": v[0], "label": v[1] if region == "kr" else v[2]} for v in SERIES.values()],
        "items": items,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, indent=1)
    print(f"feed-{region}: {len(items)} items")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "kr")
