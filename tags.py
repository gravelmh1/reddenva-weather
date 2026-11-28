"""해시태그 규칙 (팔로워 늘리기용). 시리즈 파일들이 캡션 마지막 줄을 여기서 만든다.

- Instagram은 게시물당 해시태그 5개까지만 쓴다 (2025년 말부터 Instagram 권장·제한). 넘치면 앞에서부터 5개만 남기되 브랜드 태그는 지킨다.
- 맨 앞 태그 = 검색량이 가장 큰 대표 태그. Threads에는 이 하나를 '주제 태그(topic_tag)'로 붙이고, 본문의 해시태그 줄은 뺀다
  (Threads는 글 하나에 태그 1개만 링크가 되고, 나머지는 '#글자'로 지저분하게 보이기만 함).
- 브랜드 태그(#레드덴바 / #reddenva)는 항상 마지막. Market Brief 태그는 넣지 않는다.
"""
import re

MAX_IG = 5
BRAND = {"kr": "#레드덴바", "us": "#reddenva"}
_TAG_LINE = re.compile(r"(#\S+\s*)+")


def word(text: str, ko: bool = True, cut: int = 30) -> str:
    """제목·이름 → 해시태그용 한 단어 (공백·기호 제거). 못 만들면 빈 문자열."""
    return re.sub(r"[^0-9A-Za-z가-힣]" if ko else r"[^0-9A-Za-z]", "", text or "")[:cut]


def line(region: str, *tags: str) -> str:
    """대표 태그부터 순서대로 받아, 중복·빈 것을 빼고 브랜드 태그를 붙여 5개짜리 한 줄로."""
    brand = BRAND[region]
    out, seen = [], {brand.lower()}
    for t in tags:
        t = (t or "").strip().lstrip("#")
        if not t or ("#" + t).lower() in seen: continue
        seen.add(("#" + t).lower()); out.append("#" + t)
        if len(out) == MAX_IG - 1: break
    return " ".join(out + [brand])


def _split(caption: str):
    """(본문 문단들, 해시태그 목록)"""
    paras = (caption or "").split("\n\n")
    tags = []
    while paras and _TAG_LINE.fullmatch(paras[-1].strip() or "x"):
        tags = paras.pop().split() + tags
    return paras, tags


def for_instagram(caption: str) -> str:
    """Instagram 캡션: 해시태그가 5개를 넘으면 5개로 줄인다 (예전에 만든 카드 대비 안전장치)."""
    paras, tags = _split(caption)
    if len(tags) <= MAX_IG: return caption
    brand = [t for t in tags if t.lower() in (b.lower() for b in BRAND.values())][:1]
    keep = [t for t in tags if t not in brand][: MAX_IG - len(brand)] + brand
    return "\n\n".join(paras + [" ".join(keep)])


def for_threads(caption: str):
    """Threads용 (본문, 주제 태그). 주제 태그는 맨 앞 태그, 본문에서 해시태그 줄은 뺀다."""
    paras, tags = _split(caption)
    if not paras: return caption, ""
    topic = re.sub(r"[.&]", "", tags[0].lstrip("#"))[:50] if tags else ""
    return "\n\n".join(paras), topic
