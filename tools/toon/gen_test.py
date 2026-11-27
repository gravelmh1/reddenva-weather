"""시장 풍자 카툰 그림 시험: Gemini 그림 모델에 레드덴바 스티커를 참고로 주고 한 컷 그림을 받아 본다. 게시 안 함."""
import base64, json, os, sys, time, requests
KEY = os.environ["GEMINI_API_KEY"].strip()
H = {"x-goog-api-key": KEY}
OUT = sys.argv[1] if len(sys.argv) > 1 else "samples/toon"
os.makedirs(OUT, exist_ok=True)
log = open(f"{OUT}/log.txt", "w")
def p(*a):
    print(*a); print(*a, file=log); log.flush()

ms = requests.get("https://generativelanguage.googleapis.com/v1beta/models", params={"pageSize": 300}, headers=H, timeout=30).json().get("models", [])
img_models = [m["name"].split("/")[-1] for m in ms if "image" in m["name"] and "generateContent" in m.get("supportedGenerationMethods", [])]
p("image models:", img_models)
pref = sorted(img_models, key=lambda n: (("flash" not in n), ("preview" in n), n))

def ref(name):
    return {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(open(f"assets/poses/{name}.png", "rb").read()).decode()}}
REFS = [ref("a00"), ref("a12"), ref("a05"), ref("a22")]
STYLE = ("Character reference: the attached stickers show RED DENVA, a chubby red panda mascot. Keep him EXACTLY on-model: sleepy half-closed eyes, "
         "deadpan face (expression only via eyebrows and mouth), orange face, cream ears and cheek patches, dark brown body and limbs, striped orange tail, "
         "thick dark-brown outline, flat saturated colors, clean vector sticker style. "
         "Draw ONE single-panel editorial cartoon (like a newspaper satire cartoon), square-ish 4:5, plain warm cream background, simple uncluttered scene, "
         "big readable shapes, high quality, polished. ABSOLUTELY NO TEXT, letters, numbers, logos or signs anywhere in the image. ")
SCENES = {
    "kr-rocket": "Satire of a day when Korean memory-chip stocks soared while the overall index barely moved: a giant shiny memory-chip-shaped rocket blasts off into the sky with flames, "
                 "while Red Denva sits next to a tiny turtle on the ground, both calmly sipping coffee and watching it go, unimpressed. The turtle represents the slow index.",
    "kr-elevator": "Satire: chip stocks shot up but the market index just strolled. Red Denva rides a very slow escalator holding a coffee, while next to him a chip-shaped elevator zooms upward "
                   "leaving speed lines. Red Denva glances sideways with a deadpan look.",
    "us-nap": "Satire of the US market the day before Thanksgiving when chip stocks dropped: a cozy Thanksgiving dinner table with a roast turkey; on a plate lie several cute computer chips "
              "tucked under tiny blankets, fast asleep with little Z's drawn as small curvy lines (no letters). Red Denva sits at the table in a food coma, eyes half closed, holding a fork.",
    "us-couch": "Satire: everyone, including the stock market, checked out early for the holiday. Red Denva lies on a couch under a blanket next to a sleeping bull and a sleeping bear, "
                "a half-eaten pumpkin pie on the coffee table, cozy lamp light.",
}
done = {}
for key, scene in SCENES.items():
    for m in pref[:4]:
        body = {"contents": [{"parts": [{"text": STYLE + "\nScene: " + scene}] + REFS}],
                "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}}
        try:
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", headers=H, json=body, timeout=180)
        except Exception as e:
            p(key, m, "ERR", e); continue
        if not r.ok:
            p(key, m, r.status_code, r.text[:300]); continue
        parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        imgs = [x for x in parts if "inlineData" in x or "inline_data" in x]
        if not imgs:
            p(key, m, "no image", json.dumps(parts)[:300]); continue
        d = imgs[0].get("inlineData") or imgs[0].get("inline_data")
        ext = "png" if "png" in d.get("mimeType", d.get("mime_type", "")) else "jpg"
        open(f"{OUT}/{key}.{ext}", "wb").write(base64.b64decode(d["data"]))
        p(key, m, "OK"); done[key] = m; break
    time.sleep(3)
p("done", done)
