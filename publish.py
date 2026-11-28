"""Instagram / Threads 공식 API로 이미지 한 장을 게시한다. (컨테이너 생성 → 게시 2단계)"""
import os
import time
import requests
import tags

IG = "https://graph.instagram.com/v21.0"
FB = "https://graph.facebook.com/v21.0"  # EAA… 토큰(시스템 사용자, 만료 없음)은 이쪽 주소를 쓴다


def ig_base(token: str) -> str:
    return FB if token.startswith("EAA") else IG
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
    B = ig_base(token)
    c = _post(f"{B}/{uid}/media", {"image_url": image_url, "caption": tags.for_instagram(caption)}, token)["id"]
    _ig_wait(c, token)
    return _post(f"{B}/{uid}/media_publish", {"creation_id": c}, token)["id"]


def _ig_wait(c: str, token: str):
    for _ in range(12):  # 컨테이너가 FINISHED 될 때까지 최대 ~60초
        s = requests.get(f"{ig_base(token)}/{c}", params={"fields": "status_code"}, headers={"Authorization": f"Bearer {token}"}, timeout=30).json()
        if s.get("status_code") == "FINISHED": return
        if s.get("status_code") == "ERROR": raise RuntimeError(f"Instagram 컨테이너 오류: {s}")
        time.sleep(5)


def instagram_reel(region: str, video_url: str, cover_url: str, caption: str) -> str:
    """세로 영상을 릴스로. 영상 처리(FINISHED)까지 최대 ~5분 기다린 뒤 게시. 피드에도 보이게 share_to_feed."""
    uid, token = os.environ[f"IG_USER_ID_{region.upper()}"], os.environ[f"IG_TOKEN_{region.upper()}"]
    B = ig_base(token)
    data = {"media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": "true"}
    if cover_url: data["cover_url"] = cover_url
    c = _post(f"{B}/{uid}/media", data, token)["id"]
    for _ in range(60):
        s = requests.get(f"{B}/{c}", params={"fields": "status_code,status"}, headers={"Authorization": f"Bearer {token}"}, timeout=30).json()
        if s.get("status_code") == "FINISHED": break
        if s.get("status_code") == "ERROR": raise RuntimeError(f"릴스 영상 처리 오류: {s}")
        time.sleep(5)
    else:
        raise RuntimeError("릴스 영상 처리가 5분 안에 안 끝남")
    return _post(f"{B}/{uid}/media_publish", {"creation_id": c}, token)["id"]


def instagram_carousel(region: str, image_urls: list, caption: str) -> str:
    """2~3장 카드를 Instagram 캐러셀로. (Make의 2장/3장 경로와 같은 역할)"""
    uid, token = os.environ[f"IG_USER_ID_{region.upper()}"], os.environ[f"IG_TOKEN_{region.upper()}"]
    B = ig_base(token)
    kids = []
    for u in image_urls:
        k = _post(f"{B}/{uid}/media", {"image_url": u, "is_carousel_item": "true"}, token)["id"]
        _ig_wait(k, token); kids.append(k)
    c = _post(f"{B}/{uid}/media", {"media_type": "CAROUSEL", "children": ",".join(kids), "caption": tags.for_instagram(caption)}, token)["id"]
    _ig_wait(c, token)
    return _post(f"{B}/{uid}/media_publish", {"creation_id": c}, token)["id"]


def fit_threads(text: str, limit: int = 500) -> str:
    """Threads 글자 수 제한(500자)에 맞춘다. 넘치면 해시태그 줄 → 💬 줄 순서로 빼고, 그래도 넘치면 끝을 …로 자른다."""
    paras = text.split("\n\n")
    for drop in ("#", "💬"):
        if len("\n\n".join(paras)) <= limit: break
        if len(paras) > 1 and paras[-1].lstrip().startswith(drop): paras.pop()
    out = "\n\n".join(paras)
    return out if len(out) <= limit else out[: limit - 1].rstrip() + "…"


def _th_container(uid, token, data, caption):
    """Threads 글 컨테이너. 해시태그 줄 대신 대표 태그 1개를 주제 태그로 붙인다.
    주제 태그 때문에 실패하면(API 변경 등) 태그 없이 한 번 더 시도해서 게시는 꼭 되게 한다."""
    text, topic = tags.for_threads(caption)
    body = dict(data, text=fit_threads(text))
    if topic:
        try:
            return _post(f"{TH}/{uid}/threads", dict(body, topic_tag=topic), token, retries=1)["id"]
        except RuntimeError as e:
            print(f"Threads 주제 태그({topic}) 실패 → 태그 없이 다시: {e}")
    return _post(f"{TH}/{uid}/threads", body, token)["id"]


def threads(region: str, image_url: str, text: str) -> str:
    uid, token = os.environ[f"THREADS_USER_ID_{region.upper()}"], os.environ[f"THREADS_TOKEN_{region.upper()}"]
    c = _th_container(uid, token, {"media_type": "IMAGE", "image_url": image_url}, text)
    time.sleep(10)  # 컨테이너 준비 대기
    pid = _post(f"{TH}/{uid}/threads_publish", {"creation_id": c}, token)["id"]
    return pid


def threads_carousel(region: str, image_urls: list, text: str) -> str:
    """여러 장(목요일 파생 브리핑 2장 등)을 Threads 캐러셀로."""
    uid, token = os.environ[f"THREADS_USER_ID_{region.upper()}"], os.environ[f"THREADS_TOKEN_{region.upper()}"]
    kids = [_post(f"{TH}/{uid}/threads", {"media_type": "IMAGE", "image_url": u, "is_carousel_item": "true"}, token)["id"] for u in image_urls]
    time.sleep(10)
    c = _th_container(uid, token, {"media_type": "CAROUSEL", "children": ",".join(kids)}, text)
    time.sleep(10)
    pid = _post(f"{TH}/{uid}/threads_publish", {"creation_id": c}, token)["id"]
    return pid
