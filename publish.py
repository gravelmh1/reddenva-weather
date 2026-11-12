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


def threads(region: str, image_url: str, text: str) -> str:
    uid, token = os.environ[f"THREADS_USER_ID_{region.upper()}"], os.environ[f"THREADS_TOKEN_{region.upper()}"]
    c = _post(f"{TH}/{uid}/threads", {"media_type": "IMAGE", "image_url": image_url, "text": text[:480]}, token)["id"]
    time.sleep(10)  # 컨테이너 준비 대기
    return _post(f"{TH}/{uid}/threads_publish", {"creation_id": c}, token)["id"]
