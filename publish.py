"""Instagram / Threads 공식 API로 이미지 한 장을 게시한다. (컨테이너 생성 → 게시 2단계)"""
import os
import time
import requests

IG = "https://graph.instagram.com/v21.0"
TH = "https://graph.threads.net/v1.0"


def _post(url, data, token, retries=3):
    last = None
    for i in range(retries):
        r = requests.post(url, data=data, headers={"Authorization": f"Bearer {token}"}, timeout=60)
        if r.ok:
            return r.json()
        last = r
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"{url} 실패: {last.status_code} {last.text[:300]}")


def instagram(region: str, image_url: str, caption: str) -> str:
    uid, token = os.environ[f"IG_USER_ID_{region.upper()}"], os.environ[f"IG_TOKEN_{region.upper()}"]
    c = _post(f"{IG}/{uid}/media", {"image_url": image_url, "caption": caption}, token)["id"]
    for _ in range(12):  # 컨테이너가 FINISHED 될 때까지 최대 ~60초
        s = requests.get(f"{IG}/{c}", params={"fields": "status_code"}, headers={"Authorization": f"Bearer {token}"}, timeout=30).json()
        if s.get("status_code") == "FINISHED": break
        if s.get("status_code") == "ERROR": raise RuntimeError(f"Instagram 컨테이너 오류: {s}")
        time.sleep(5)
    return _post(f"{IG}/{uid}/media_publish", {"creation_id": c}, token)["id"]


def _ig_wait(c: str, token: str):
    for _ in range(12):  # 컨테이너가 FINISHED 될 때까지 최대 ~60초
        s = requests.get(f"{IG}/{c}", params={"fields": "status_code"}, headers={"Authorization": f"Bearer {token}"}, timeout=30).json()
        if s.get("status_code") == "FINISHED": return
        if s.get("status_code") == "ERROR": raise RuntimeError(f"Instagram 컨테이너 오류: {s}")
        time.sleep(5)


def instagram_carousel(region: str, image_urls: list, caption: str) -> str:
    """2~3장 카드를 Instagram 캐러셀로. (Make의 2장/3장 경로와 같은 역할)"""
    uid, token = os.environ[f"IG_USER_ID_{region.upper()}"], os.environ[f"IG_TOKEN_{region.upper()}"]
    kids = []
    for u in image_urls:
        k = _post(f"{IG}/{uid}/media", {"image_url": u, "is_carousel_item": "true"}, token)["id"]
        _ig_wait(k, token); kids.append(k)
    c = _post(f"{IG}/{uid}/media", {"media_type": "CAROUSEL", "children": ",".join(kids), "caption": caption}, token)["id"]
    _ig_wait(c, token)
    return _post(f"{IG}/{uid}/media_publish", {"creation_id": c}, token)["id"]


def fit_threads(text: str, limit: int = 500) -> str:
    """Threads 글자 수 제한(500자)에 맞춘다. 넘치면 해시태그 줄 → 💬 줄 순서로 빼고, 그래도 넘치면 끝을 …로 자른다."""
    paras = text.split("\n\n")
    for drop in ("#", "💬"):
        if len("\n\n".join(paras)) <= limit: break
        if len(paras) > 1 and paras[-1].lstrip().startswith(drop): paras.pop()
    out = "\n\n".join(paras)
    return out if len(out) <= limit else out[: limit - 1].rstrip() + "…"


def threads(region: str, image_url: str, text: str) -> str:
    uid, token = os.environ[f"THREADS_USER_ID_{region.upper()}"], os.environ[f"THREADS_TOKEN_{region.upper()}"]
    c = _post(f"{TH}/{uid}/threads", {"media_type": "IMAGE", "image_url": image_url, "text": fit_threads(text)}, token)["id"]
    time.sleep(10)  # 컨테이너 준비 대기
    pid = _post(f"{TH}/{uid}/threads_publish", {"creation_id": c}, token)["id"]
    return pid


def threads_carousel(region: str, image_urls: list, text: str) -> str:
    """여러 장(목요일 파생 브리핑 2장 등)을 Threads 캐러셀로."""
    uid, token = os.environ[f"THREADS_USER_ID_{region.upper()}"], os.environ[f"THREADS_TOKEN_{region.upper()}"]
    kids = [_post(f"{TH}/{uid}/threads", {"media_type": "IMAGE", "image_url": u, "is_carousel_item": "true"}, token)["id"] for u in image_urls]
    time.sleep(10)
    c = _post(f"{TH}/{uid}/threads", {"media_type": "CAROUSEL", "children": ",".join(kids), "text": fit_threads(text)}, token)["id"]
    time.sleep(10)
    pid = _post(f"{TH}/{uid}/threads_publish", {"creation_id": c}, token)["id"]
    return pid
