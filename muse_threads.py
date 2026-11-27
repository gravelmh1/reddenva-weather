"""Muse(메타 AI)가 인스타에 올린 시장 카툰을 Threads에 그대로 복사한다. (형: Muse는 Threads 권한이 없어 매번 허용을 눌러야 해서)

- 인스타 최근 게시물을 읽고, 아래 조건을 모두 만족하는 것만 복사:
  사진(IMAGE·CAROUSEL) · SINCE 이후 게시 · 우리 자동화가 올린 글이 아님(state/links-*.json 에 없는 링크) · 아직 복사 안 함
- 복사한 인스타 ID는 state/muse_{region}_threads.json 에 남겨서 두 번 올리지 않는다.
  python muse_threads.py --region kr [--dry-run]
"""
import argparse, datetime as dt, json, os, time
import requests
import publish
from ig_post import IG_IDS

SINCE = dt.datetime.fromisoformat(os.environ.get("MUSE_SINCE", "2026-11-27T07:00:00+00:00"))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--region", required=True, choices=["kr", "us"]); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(); R = a.region.upper()
    ig_tok = os.environ.get(f"IG_TOKEN_{R}", "").strip(); th_tok = os.environ.get(f"THREADS_TOKEN_{R}", "").strip()
    if not ig_tok or not th_tok: print("토큰 없음 → 건너뜀"); return
    base = publish.ig_base(ig_tok)
    uid = IG_IDS[a.region] if ig_tok.startswith("EAA") else "me"
    r = requests.get(f"{base}/{uid}/media", params={"fields": "id,caption,media_type,media_url,permalink,timestamp,children{media_type,media_url}", "limit": 15},
                     headers={"Authorization": f"Bearer {ig_tok}"}, timeout=30)
    r.raise_for_status(); items = r.json().get("data", [])
    lp = f"state/links-{a.region}.json"
    ours = {v.get("instagram") for v in (json.load(open(lp, encoding="utf-8")).values() if os.path.exists(lp) else []) if isinstance(v, dict)}
    sp = f"state/muse_{a.region}_threads.json"
    done = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else {}
    todo = []
    for it in items:
        t = dt.datetime.fromisoformat(it["timestamp"].replace("+0000", "+00:00"))
        why = ("동영상" if it["media_type"] not in ("IMAGE", "CAROUSEL_ALBUM") else "예전 글" if t < SINCE else "우리 자동화 글" if it.get("permalink") in ours
               else "이미 복사함" if it["id"] in done else None)
        print(f"{it['timestamp']} {it['media_type']:<14} {it.get('permalink')} → {why or '복사 대상'} | {(it.get('caption') or '')[:40]!r}")
        if not why: todo.append(it)
    if not todo: print("복사할 Muse 글 없음"); return
    me = requests.get(f"{publish.TH}/me", params={"fields": "id,username"}, headers={"Authorization": f"Bearer {th_tok}"}, timeout=30); me.raise_for_status()
    os.environ[f"THREADS_USER_ID_{R}"] = me.json()["id"]
    for it in sorted(todo, key=lambda x: x["timestamp"]):  # 오래된 것부터
        cap = (it.get("caption") or "").strip()
        if it["media_type"] == "CAROUSEL_ALBUM":
            urls = [c["media_url"] for c in it.get("children", {}).get("data", []) if c.get("media_type") == "IMAGE"][:10]
        else:
            urls = [it["media_url"]]
        if a.dry_run: print("(dry-run) Threads에 올릴 것:", it["permalink"], len(urls), "장"); continue
        pid = publish.threads(a.region, urls[0], cap) if len(urls) == 1 else publish.threads_carousel(a.region, urls, cap)
        print("Threads 게시 완료:", it["permalink"], "→", pid)
        done[it["id"]] = {"ig": it["permalink"], "threads": pid, "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        os.makedirs("state", exist_ok=True); json.dump(dict(list(done.items())[-100:]), open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(5)


if __name__ == "__main__":
    main()
