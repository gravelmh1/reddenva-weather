"""날씨 카드를 만들어 Instagram과 Threads에 올린다.
사용: python run.py --region kr|us [--dry-run] [--force] [--mock 시나리오]
"""
import argparse
import datetime as dt
import os
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

import messages
import publish
import render
import weather

POST_HOUR = 6          # 현지 시각 06:00에 게시
WINDOW = (5 * 60 + 15, 6 * 60 + 50)  # 이 시간대(현지 05:15~06:50)가 아니면 자동 실행을 건너뜀


def sh(*cmd, check=True):
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def git_push(paths, msg):
    sh("git", "config", "user.name", "weather-bot"); sh("git", "config", "user.email", "weather-bot@users.noreply.github.com")
    sh("git", "add", *paths)
    if sh("git", "diff", "--cached", "--quiet", check=False).returncode == 0:
        return
    sh("git", "commit", "-m", msg)
    for _ in range(4):
        sh("git", "pull", "--rebase", "--autostash", check=False)
        if sh("git", "push", check=False).returncode == 0:
            return
        time.sleep(5)
    raise RuntimeError("git push 실패")


def wait_url(url):
    import requests
    for _ in range(24):
        r = requests.get(url, timeout=20)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
            return
        time.sleep(5)
    raise RuntimeError(f"이미지 주소가 열리지 않아요: {url}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True, choices=list(weather.REGIONS))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--mock")
    ap.add_argument("--emit", action="store_true", help="게시하지 않고 카드와 캡션 JSON만 저장 (Make 등 외부 도구가 게시)")
    a = ap.parse_args()
    reg = weather.REGIONS[a.region]
    now = dt.datetime.now(ZoneInfo(reg["tz"]))
    minutes = now.hour * 60 + now.minute
    if not (a.force or a.mock) and not (WINDOW[0] <= minutes <= WINDOW[1]):
        print(f"현지 시각 {now:%H:%M}: 게시 시간대가 아니라서 건너뛰어요."); return

    day = now.date().isoformat()
    done = [os.path.exists(f"state/{a.region}_{ch}.txt") and open(f"state/{a.region}_{ch}.txt").read().strip() == day
            for ch in ("instagram", "threads")]
    if all(done) and not (a.force or a.mock or a.dry_run):
        print("오늘 분은 이미 모두 게시했어요. 건너뜀."); return

    if a.mock:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tests")); import mock
        raw = mock.make(a.mock, now.date())
    else:
        raw = weather.fetch(a.region)
    p = weather.parse(raw, now.date().isoformat())
    f = messages.features(p, reg["unit"])
    cp = messages.build(f, a.region, reg["city"], now)

    os.makedirs("out", exist_ok=True); os.makedirs("state", exist_ok=True)
    img_rel = f"out/{a.region}-{day}.jpg"
    render.card(img_rel, a.region, now, p, f, cp, reg["city"])
    print(cp["caption"]); print(f"카드 저장: {img_rel}")
    if a.dry_run:
        print("(dry-run: 게시하지 않았어요)"); return

    for old in os.listdir("out"):  # 7일 지난 이미지 정리
        fp = os.path.join("out", old)
        if old.endswith(".jpg") and time.time() - os.path.getmtime(fp) > 7 * 86400: os.remove(fp)
    git_push(["out", "state"], f"{a.region} {day} card")
    repo, branch = os.environ["GITHUB_REPOSITORY"], os.environ.get("GITHUB_REF_NAME", "main")
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{img_rel}"
    wait_url(url)

    if a.emit:
        import json
        meta = {"date": day, "image_url": url, "caption": cp["caption"]}
        with open(f"out/{a.region}-latest.json", "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False)
        git_push(["out"], f"{a.region} {day} latest.json")
        print("latest.json 저장 완료 (게시는 외부 도구가 해요)"); return

    target = now.replace(hour=POST_HOUR, minute=0, second=0, microsecond=0)
    wait = (target - dt.datetime.now(ZoneInfo(reg["tz"]))).total_seconds()
    if 0 < wait <= 25 * 60:
        print(f"{wait/60:.0f}분 기다렸다가 06:00에 게시해요"); time.sleep(wait)

    for ch, fn in (("instagram", publish.instagram), ("threads", publish.threads)):
        sf = f"state/{a.region}_{ch}.txt"
        if os.path.exists(sf) and open(sf).read().strip() == day:
            print(f"{ch}: 오늘 이미 게시했어요, 건너뜀"); continue
        pid = fn(a.region, url, cp["caption"])
        print(f"{ch} 게시 완료: {pid}")
        open(sf, "w").write(day)
        git_push(["state"], f"{a.region} {ch} {day} posted")


if __name__ == "__main__":
    main()
