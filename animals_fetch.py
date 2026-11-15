"""시안용: 위키미디어 공용에서 아기 동물 사진 후보를 받아 samples/ 에 저장 (라이선스·저작자 정보 포함)."""
import json, os, re, sys, requests
UA = {"User-Agent": "RedDenvaBot/1.0 (https://github.com/gravelmh1/reddenva-weather)"}
QUERIES = sys.argv[1:] or ["red panda cub", "sea otter pup", "duckling", "baby elephant", "lamb spring", "fox kit", "baby hedgehog", "seal pup"]
os.makedirs("samples", exist_ok=True); meta = []
for q in QUERIES:
    r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=30, params={
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrsearch": f"{q} filetype:bitmap", "gsrlimit": 8,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1400})
    pages = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99)); n = 0
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]; em = ii.get("extmetadata", {})
        if ii.get("mime") != "image/jpeg" or ii.get("width", 0) < 1400 or ii.get("height", 0) < 1000: continue
        lic = em.get("LicenseShortName", {}).get("value", "")
        if not re.match(r"(CC0|CC BY|Public domain)", lic, re.I): continue
        fn = f"samples/{q.replace(' ', '_')}-{n}.jpg"
        img = requests.get(ii["thumburl"], headers=UA, timeout=60)
        if not img.ok: continue
        open(fn, "wb").write(img.content)
        meta.append({"file": fn, "query": q, "title": p["title"], "license": lic, "artist": re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", ""))[:80], "page": ii.get("descriptionurl")})
        n += 1
        if n >= 3: break
    print(q, n)
json.dump(meta, open("samples/meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
