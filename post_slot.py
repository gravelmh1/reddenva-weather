"""Make는 하루 두 번(아침 날씨 시각, 낮 1시 주간 시각) 항상 같은 워크플로(post-{region}.yml)를 깨우고,
항상 같은 파일(out/{region}-post.json)을 읽는다. 어떤 카드를 낼지는 여기서 현지 시각으로 정한다.
(Make 안에 시간 수식을 두면 편집하다 깨지기 쉬워서 전부 이쪽으로 옮김)

  python post_slot.py kr              → 'slot=weather' 또는 'slot=weekly' 출력 ($GITHUB_OUTPUT 용). 브리프는 Make가 slot=morning/close 로 지정
  python post_slot.py kr --clear      → post.json을 '게시할 것 없음'으로 (주간 시각 시작할 때. 실패해도 아침 날씨가 다시 올라가지 않게)
  python post_slot.py kr --write SLOT → 오늘 게시할 카드 정보를 post.json에 기록
"""
import datetime as dt, json, os, shutil, sys
from zoneinfo import ZoneInfo

region = sys.argv[1]
now = dt.datetime.now(ZoneInfo({"kr": "Asia/Seoul", "us": "America/Los_Angeles"}[region])); day = now.date().isoformat()
post = f"out/{region}-post.json"
NONE = {"date": "none", "image_url": "", "image_url2": "", "image_url3": "", "caption": "", "title": ""}


def today(path):
    return os.path.exists(path) and json.load(open(path, encoding="utf-8")).get("date") == day


if len(sys.argv) == 2:
    # 낮 12~13시대 = 주간(월 책·화 뉴스·수 강아지·목 파생 브리핑·금 주말 여행·토 동물 상식·일 넷플릭스) 시각. 한국판은 미국 서머타임 때 12시에 깨워지므로 12시도 포함.
    # 모닝·마감 브리프는 다른 시리즈와 시각이 겹칠 수 있어서 Make가 slot=morning / slot=close 로 직접 지정해서 깨운다.
    print("slot=" + ("weekly" if now.hour in (12, 13) else "weather"))
elif sys.argv[2] == "--clear":
    json.dump(NONE, open(post, "w", encoding="utf-8")); print("post.json 비움")
elif sys.argv[2] == "--write":
    slot = sys.argv[3]
    src = [f"out/{region}-latest.json"] if slot == "weather" else [f"out/{slot}-{region}-latest.json"] if slot in ("morning", "close") else [f"out/books-{region}-latest.json", f"out/news-{region}-latest.json", f"out/puppy-{region}-latest.json", f"out/deriv-{region}-latest.json", f"out/trip-{region}-latest.json", f"out/facts-{region}-latest.json", f"out/netflix-{region}-latest.json"]
    for p in src:
        if today(p):
            m = json.load(open(p, encoding="utf-8")); m.setdefault("image_url2", ""); m.setdefault("image_url3", "")  # 2·3장이면 Make가 캐러셀로
            json.dump(m, open(post, "w", encoding="utf-8"), ensure_ascii=False); print("post.json ←", p); break
    else:
        json.dump(NONE, open(post, "w", encoding="utf-8")); print("오늘 게시할 카드 없음 → post.json 비움")
