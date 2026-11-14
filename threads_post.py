"""latest.json의 오늘 카드를 Threads에 올린다. (Make가 깨운 실행에서만 호출)
- 토큰으로 사용자 ID를 직접 조회하므로 THREADS_USER_ID 비밀값이 필요 없다.
- state/{region}_threads.txt 에 오늘 날짜가 있으면 중복 게시하지 않는다.
"""
import argparse, datetime as dt, json, os, sys
from zoneinfo import ZoneInfo
import requests
import publish, weather


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True, choices=list(weather.REGIONS))
    a = ap.parse_args()
    reg = weather.REGIONS[a.region]
    day = dt.datetime.now(ZoneInfo(reg["tz"])).date().isoformat()
    token = os.environ.get(f"THREADS_TOKEN_{a.region.upper()}", "").strip()
    if not token:
        print("Threads 토큰이 없어서 건너뜀"); return
    meta = json.load(open(f"out/{a.region}-latest.json", encoding="utf-8"))
    if meta.get("date") != day:
        print(f"오늘 카드가 아님({meta.get('date')} != {day}). 건너뜀"); return
    sf = f"state/{a.region}_threads.txt"
    if os.path.exists(sf) and open(sf).read().strip() == day:
        print("Threads: 오늘 이미 게시함. 건너뜀"); return
    r = requests.get("https://graph.threads.net/v1.0/me", params={"fields": "id,username"},
                     headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    me = r.json()
    os.environ[f"THREADS_USER_ID_{a.region.upper()}"] = me["id"]
    pid = publish.threads(a.region, meta["image_url"], meta["caption"])
    print(f"Threads 게시 완료: @{me.get('username')} {pid}")
    os.makedirs("state", exist_ok=True)
    open(sf, "w").write(day)


if __name__ == "__main__":
    main()
