"""게시한 글의 공개 링크(permalink)를 찾아서 state/links-{region}.json 에 남긴다. (형에게 링크 전달용)

  python links.py --region kr --ig 18132480424914270 --threads 18121545031769103 --label morning-2026-11-27
ig_post.py / threads_post.py 가 게시 직후 자동으로 부른다. 실패해도 게시에는 영향 없음.
"""
import argparse, json, os
import requests
import publish


def ig_link(region, mid):
    t = os.environ.get(f"IG_TOKEN_{region.upper()}", "").strip()
    base = publish.FB if t.startswith("EAA") else publish.IG
    r = requests.get(f"{base}/{mid}", params={"fields": "permalink"}, headers={"Authorization": f"Bearer {t}"}, timeout=30)
    r.raise_for_status(); return r.json().get("permalink")


def th_link(region, mid):
    t = os.environ.get(f"THREADS_TOKEN_{region.upper()}", "").strip()
    r = requests.get(f"{publish.TH}/{mid}", params={"fields": "permalink"}, headers={"Authorization": f"Bearer {t}"}, timeout=30)
    r.raise_for_status(); return r.json().get("permalink")


def save(region, label, key, mid):
    try:
        url = (ig_link if key == "instagram" else th_link)(region, mid)
    except Exception as e:
        print("링크 찾기 실패:", key, mid, e); return None
    print(f"{key} 링크: {url}")
    p = f"state/links-{region}.json"
    d = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    d.setdefault(label, {})[key] = url
    d = dict(list(d.items())[-60:])  # 최근 것만
    os.makedirs("state", exist_ok=True)
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return url


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--region", required=True); ap.add_argument("--label", required=True)
    ap.add_argument("--ig"); ap.add_argument("--threads")
    a = ap.parse_args()
    if a.ig: save(a.region, a.label, "instagram", a.ig)
    if a.threads: save(a.region, a.label, "threads", a.threads)
