"""out/{region}-post.json(post_slot.py가 정한 '지금 올릴 카드')을 Instagram에 직접 올린다.
예전에는 Make가 이 파일을 읽어 올렸지만(실행마다 5크레딧), 이제 Make는 워크플로만 깨우고(1크레딧) 게시는 여기서 한다.

- 워크플로 입력 ig=true 일 때만 호출된다 (Make 본문에서 켜고 끔 → 전환 전에는 중복 게시 없음).
- IG_TOKEN_{KR,US}: 시스템 사용자 토큰(EAA…, 만료 없음) 또는 Instagram 로그인 방식 장기 토큰(IGAA…).
- state/{region}_ig_{slot}.txt 에 오늘 날짜가 있으면 다시 올리지 않는다.

  python ig_post.py --region us --slot weather
"""
import argparse, datetime as dt, json, os
from zoneinfo import ZoneInfo
import requests
import publish, weather

# Instagram 비즈니스 계정 번호 (공개 정보, Meta 개발자 화면·Make에 보이는 값)
IG_IDS = {"kr": "17841415970047103", "us": "17841468623391374"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True, choices=list(weather.REGIONS))
    ap.add_argument("--slot", required=True)
    a = ap.parse_args()
    R = a.region.upper()
    day = dt.datetime.now(ZoneInfo(weather.REGIONS[a.region]["tz"])).date().isoformat()
    token = os.environ.get(f"IG_TOKEN_{R}", "").strip()
    if not token:
        raise SystemExit(f"IG_TOKEN_{R} 비밀값이 없어요. 게시하지 못함")
    meta = json.load(open(f"out/{a.region}-post.json", encoding="utf-8"))
    if meta.get("date") != day or not meta.get("image_url"):
        print(f"오늘 올릴 카드 없음({meta.get('date')}). 건너뜀"); return
    sf = f"state/{a.region}_ig_{a.slot}.txt"
    if os.path.exists(sf) and open(sf).read().strip() == day:
        print("Instagram: 오늘 이 시각 카드는 이미 게시함. 건너뜀"); return
    if token.startswith("EAA"):  # 시스템 사용자 토큰: 계정 번호를 직접 지정
        me = requests.get(f"{publish.FB}/{IG_IDS[a.region]}", params={"fields": "username"},
                          headers={"Authorization": f"Bearer {token}"}, timeout=30)
        me.raise_for_status(); me = me.json(); me["user_id"] = IG_IDS[a.region]
    else:
        r = requests.get(f"{publish.IG}/me", params={"fields": "user_id,username"},
                         headers={"Authorization": f"Bearer {token}"}, timeout=30)
        r.raise_for_status(); me = r.json()
    os.environ[f"IG_USER_ID_{R}"] = str(me.get("user_id") or me["id"])
    urls = [u for u in (meta["image_url"], meta.get("image_url2"), meta.get("image_url3")) if u]
    pid = None
    vf = f"reel_out/{a.region}-video.json"  # reel.py가 같은 실행에서 만든 영상 (같은 카드일 때만)
    if os.path.exists(vf):
        v = json.load(open(vf, encoding="utf-8"))
        if v.get("date") == day and v.get("image_url") == meta["image_url"]: meta.update(video_url=v["video_url"], cover_url=v.get("cover_url"))
    if meta.get("video_url"):  # reel.py가 영상을 만들었으면 릴스로. 실패하면 아래 카드 이미지로 대신 올림
        try:
            pid = publish.instagram_reel(a.region, meta["video_url"], meta.get("cover_url"), meta["caption"])
            print("릴스로 게시")
        except Exception as e:
            print("릴스 게시 실패 → 카드 이미지로 올림:", e)
    if pid:
        pass
    elif len(urls) > 1:
        pid = publish.instagram_carousel(a.region, urls, meta["caption"])
    else:
        pid = publish.instagram(a.region, urls[0], meta["caption"])
    print(f"Instagram 게시 완료: @{me.get('username')} {pid}")
    import links; links.save(a.region, f"{a.slot}-{day}", "instagram", pid)
    os.makedirs("state", exist_ok=True)
    open(sf, "w").write(day)


if __name__ == "__main__":
    main()
