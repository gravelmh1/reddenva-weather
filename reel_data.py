"""카드를 만들 때 쓴 내용을 릴스용으로 남겨둔다 (reel_in/, 저장소에는 올리지 않음).
같은 워크플로 실행 안에서 reel.py가 읽어 영상을 만든다. 실패해도 카드 게시에는 영향 없게 조용히 넘어간다.

  reel_data.save("news", "kr", {"c": card}, photos={"p1": pil_image_or_path})
"""
import json, os

DIR = "reel_in"


def save(kind, region, data, photos=None):
    try:
        os.makedirs(DIR, exist_ok=True)
        for name, ph in (photos or {}).items():
            path = os.path.abspath(f"{DIR}/{kind}-{region}-{name}.jpg")
            if isinstance(ph, str):
                if not os.path.exists(ph): continue
                from PIL import Image
                Image.open(ph).convert("RGB").save(path, quality=92)
            else:
                ph.convert("RGB").save(path, quality=92)
            data[name] = path
        with open(f"{DIR}/{kind}-{region}.json", "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, default=lambda o: None)
    except Exception as e:  # 릴스는 덤. 카드 게시를 막지 않는다
        print("릴스용 데이터 저장 실패(무시):", type(e).__name__, e)


def load(kind, region):
    p = f"{DIR}/{kind}-{region}.json"
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
