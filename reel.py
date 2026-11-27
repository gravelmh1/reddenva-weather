"""오늘 올릴 카드(out/{region}-post.json)를 세로 릴스 영상으로 만들어 Instagram 게시에 붙인다.

- reels.json 에서 지역별로 켜고 끈다. 꺼져 있으면 아무것도 안 함 → 지금처럼 카드 이미지로 게시.
- 카드 스크립트가 남긴 reel_in/{kind}-{region}.json(같은 실행 안에서 만든 숫자·문장)으로 장면을 짠다.
- 영상과 표지는 GitHub Release 'reels'에 올리고(저장소 용량 안 늘어남), 주소를 reel_out/{region}-video.json에 적는다.
- ig_post.py가 video_url이 있으면 릴스로 올리고, 실패하면 원래 카드 이미지로 올린다. Threads는 계속 카드 이미지.

  python reel.py --region kr --enabled   → 켜져 있으면 종료코드 0, 꺼져 있으면 1 (워크플로에서 설치 여부 판단)
  python reel.py --region kr             → 영상 만들고 올리고 post.json 갱신
  python reel.py --region kr --kind news --local out.mp4   → 업로드 없이 로컬 확인용
  python reel.py --region kr --preview   → 테스트 실행(dry-run)에서 만든 카드 전부 영상으로
"""
import argparse, datetime as dt, json, os, re, sys, time
import requests
import reel_data

ROOT = os.path.dirname(os.path.abspath(__file__))
KINDS = ["books", "news", "dart", "puppy", "deriv", "trip", "facts", "netflix", "morning", "close", "wrap", "ahead"]
CARD_LAST = {"ko": "한 장으로 보기", "en": "The full card"}


def rd(*texts, ko=True):
    """글자 수로 읽을 시간(초). 한국어 초당 ~10자, 영어 ~17자."""
    n = sum(len(re.sub(r"\[\[\w+:|\]\]", "", str(t or ""))) for t in texts)
    return max(2.0, min(6.0, 1.3 + n / (10 if ko else 17)))


def theme(name, particles=False):
    V = {
        "navy": dict(bg="radial-gradient(1200px 900px at 50% 20%, #24457f 0%, #14284d 55%, #0c1a35 100%)", fg="#fff", sub="#aebbd8", acc="#ffb27a",
                     chip="rgba(255,255,255,.12)", pill="#1f6fe5", panel="#fff", pfg="#14284d", psub="#6f7a90", shadow="0 30px 80px rgba(0,0,0,.35)",
                     pborder="none", tagbg="#e6ecf7", tagfg="#3b4a68", up="#e0482a", dn="#1f6fe5", today="#fdeee4"),
        "terminal": dict(bg="radial-gradient(1100px 900px at 50% 15%, #1d2a47 0%, #0f172b 60%, #0a1020 100%)", fg="#fff", sub="#9aa6c2", acc="#f0a04b",
                         chip="rgba(255,255,255,.1)", pill="#f0a04b", panel="#151f36", pfg="#fff", psub="#9aa6c2", shadow="0 30px 80px rgba(0,0,0,.45)",
                         pborder="1px solid rgba(255,255,255,.08)", tagbg="#22304f", tagfg="#cfd7ea", up="#2fd08a", dn="#ff5a5f", today="#22304f"),
        "book": dict(bg="radial-gradient(1100px 900px at 50% 18%, #43302a 0%, #2a1e1a 55%, #170f0d 100%)", fg="#fff7ea", sub="#cbb9a6", acc="#e8b45c",
                     chip="rgba(255,255,255,.1)", pill="#b5562f", panel="#fff7ea", pfg="#2b1f1a", psub="#7a6a5c", shadow="0 30px 80px rgba(0,0,0,.45)",
                     pborder="none", tagbg="#f1e3cc", tagfg="#5a4630", up="#e0482a", dn="#1f6fe5", today="#f1e3cc"),
        "cream": dict(bg="radial-gradient(1100px 900px at 50% 15%, #fffaf0 0%, #fbf3e3 60%, #f4e8d2 100%)", fg="#2b2622", sub="#7b6f63", acc="#e0482a",
                      chip="rgba(0,0,0,.06)", pill="#e0482a", panel="#fff", pfg="#2b2622", psub="#7b6f63", shadow="0 20px 50px rgba(80,50,20,.12)",
                      pborder="none", tagbg="#f6ead6", tagfg="#6b4f2a", up="#e0482a", dn="#1f6fe5", today="#f6ead6"),
        "screen": dict(bg="radial-gradient(1100px 900px at 50% 10%, #3a1218 0%, #160a0d 50%, #0b0b0d 100%)", fg="#fff", sub="#a9a9b3", acc="#ff5a5a",
                       chip="rgba(255,255,255,.1)", pill="#e23b3b", panel="#17171c", pfg="#fff", psub="#a9a9b3", shadow="0 30px 80px rgba(0,0,0,.5)",
                       pborder="1px solid rgba(255,255,255,.07)", tagbg="#26262d", tagfg="#ddd", up="#ff5a5a", dn="#5a8dff", today="#26262d"),
        "photo": dict(bg="radial-gradient(1100px 900px at 50% 15%, #2a3340 0%, #141a22 60%, #0c1016 100%)", fg="#fff", sub="#b9c2cf", acc="#ff8a4c",
                      chip="rgba(255,255,255,.1)", pill="#ff8a4c", panel="#fff", pfg="#1d2530", psub="#6a7482", shadow="0 30px 80px rgba(0,0,0,.45)",
                      pborder="none", tagbg="#eef1f5", tagfg="#3b4656", up="#e0482a", dn="#1f6fe5", today="#eef1f5"),
    }[name]
    return {"vars": V, "particles": particles}


def cards_scene(srcs, ko):
    per = 4.6 if len(srcs) == 1 else 3.6
    return dict(type="cards", kicker=CARD_LAST["ko" if ko else "en"], srcs=["file://" + s for s in srcs], dur=.6 + per * len(srcs))


ICON = lambda c: "⛈️" if c >= 95 else "❄️" if 71 <= c <= 77 or c in (85, 86) else "🌦️" if 80 <= c <= 82 else "🌧️" if 51 <= c <= 67 else "🌫️" if c in (45, 48) else "☁️" if c == 3 else "⛅" if c == 2 else "🌤️" if c == 1 else "☀️"
KO_DAY = "월화수목금토일"; EN_DAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ------------------------------------------------------------------ 시리즈별 장면
def weather(d, region):
    ko = d["ko"]; dm = d["dm"]; m = d["morning"]
    cold = (m <= 3) if ko else (m <= 38)
    chip = f"{d['city']} · {d['month']}월 {d['day']}일 {d['wd']}" if ko else f"{d['city']} · {d['wd']}, {d['mon_en']} {d['day']}"
    if d.get("alert"):
        pill, pc = d["alert"][0], "#e0482a"
    elif dm:
        pill = (f"{'▲' if dm > 0 else '▼'} 어제보다 {abs(dm)}° {'따뜻해요' if dm > 0 else '추워요'}" if ko else f"{'▲' if dm > 0 else '▼'} {abs(dm)}° {'warmer' if dm > 0 else 'colder'} than yesterday")
        pc = "#e0482a" if dm > 0 else "#1f6fe5"
    else:
        pill, pc = ("어제랑 같아요" if ko else "Same as yesterday"), "#5b6b8c"
    hook = dict(type="hook", chip=chip, label="출근길 아침 7~9시" if ko else "Morning commute, 7–9am",
                big=dict({"from": m - (dm or 0), "to": m}, suf="°"), pill=pill, pillc=pc, pose=d["pose"], dur=1.9 + 1.9)
    rows = [list(r) for r in d["rows"]]
    t2 = dict(type="tiles", kicker="오늘 하루" if ko else "Today", title=d["headline"],
              tiles=[dict(l="낮 최고" if ko else "High", n=d["hi"], suf="°", vc="var(--up)"), dict(l="밤 최저" if ko else "Low", n=d["lo"], suf="°", vc="var(--dn)")],
              rows=rows, pose="a18" if cold else "a05", poseh=240)
    t2["dur"] = 1.7 + rd(d["headline"], *[r[1] for r in rows], ko=ko)
    wk = d["week"]
    for w in wk:
        w["ic"] = ICON(w["code"]); w["c"] = "#e0482a" if w["today"] or w["wd"] == 6 else "#1f6fe5" if w["wd"] == 5 else "#8a94a8" if w["faded"] else "#14284d"
    ti = [i for i, w in enumerate(wk) if w["today"]][0]; T = wk[ti]; nxt = wk[ti + 1:]
    day = lambda w: (KO_DAY[w["wd"]] if ko else EN_DAY[w["wd"]])
    rain = [w for w in nxt if w["rain"] >= 60]
    hi = max(w["hi"] for w in nxt) if nxt else T["hi"]; lo = min(w["lo"] for w in nxt) if nxt else T["lo"]
    if rain:
        wt = f"{day(rain[0])}요일 비 소식 ({rain[0]['rain']}%)" if ko else f"Rain likely {day(rain[0])} ({rain[0]['rain']}%)"
    elif hi - T["hi"] >= (5 if ko else 8):
        ds = "·".join(day(w) for w in nxt if w["hi"] == hi)
        wt = f"{ds}엔 {hi}°까지 올라가요" if ko else f"Up to {hi}° by {ds}"
    elif T["lo"] - lo >= (4 if ko else 7):
        ds = "·".join(day(w) for w in nxt if w["lo"] == lo)
        wt = f"{ds} 아침 {lo}°까지 내려가요" if ko else f"Down to {lo}° by {ds}"
    else:
        wt = "이번 주는 큰 변화 없어요" if ko else "A steady week ahead"
    week = dict(type="week", kicker="이번 주" if ko else "This week", title=wt, days=wk, dur=1.6 + 2.8)
    return theme("navy", particles=cold), [hook, t2, week, cards_scene([d["card"]], ko)]


def deriv(d, region):
    if region == "kr": return deriv_kr(d)
    nd = d["net_d"]; lev, am = nd["lev"], nd["am"]
    verb = lambda v: "[[up:bought]]" if v > 0 else "[[dn:sold]]"
    if (lev > 0) != (am > 0):
        lines = [f"Hedge funds {verb(lev)},", f"asset managers {verb(am)}"]
    else:
        lines = [f"Hedge funds and", f"asset managers {verb(lev)}"]
    hook = dict(type="hook", kicker=f"THURSDAY DERIVATIVES · {d['asof']}", lines=lines, size="s",
                sub=f"E-mini S&P 500 futures since the {d['xm']} expiry", pose="a06", poseh=320, dur=2.2 + 2.0)
    chg = lambda k: [v - d["net"][k][0] for v in d["net"][k]]  # 만기 이후 누적 변화
    ser = [dict(name="Hedge funds", c="#3fc7b0", v=chg("lev"), sign=True), dict(name="Asset managers", c="#f0a04b", v=chg("am"), sign=True),
           dict(name="Dealers", c="#a98bff", v=chg("dl"), sign=True)]
    ser.sort(key=lambda x: -x["v"][-1])
    for i, x in enumerate(ser): x["below"] = i == len(ser) - 1
    ser[1]["nolab"] = True
    chart = dict(type="chart", kicker=f"Since the {d['xm']} expiry", title="Who bought, who sold", unit="change in net contracts", series=ser, tickfmt="k",
                 symmetric=False, foot="Source: CFTC · not investment advice", drawdur=2.2, dur=3.0 + 2.6)
    allv = ser[0]["v"] + ser[1]["v"]
    if min(allv) < 0 < max(allv): chart["symmetric"] = True
    tiles = [dict(l=t, v=v, c=cs, cc=cc) for t, v, cs, sub, cc in d["tiles"]]
    t3 = dict(type="tiles", kicker="This week's numbers", title=f"As of {d['asof']}", tiles=tiles, nsz=92, foot="Sources: FRED, Yahoo Finance · not investment advice", dur=2.0 + 3.6)
    return theme("terminal"), [hook, chart, t3, cards_scene(d["cards"], False)]


def deriv_kr(d):
    c = d["cum_last"]; who = {"frn": "외국인", "ins": "기관", "ind": "개인"}
    buy = max(c, key=c.get); sell = min(c, key=c.get)
    lines = [f"{who[buy]} [[up:순매수]]", f"{who[sell]} [[dn:순매도]]"]
    hook = dict(type="hook", kicker=f"목요일 파생 브리핑 · {d['asof']}", lines=lines, size="s",
                sub=f"{d['xm']} 만기 이후 코스피200 선물 누적", pose="a06", poseh=320, dur=2.2 + 2.0)
    ser = [dict(name=who[k], c=col, v=d["cum"][k], sign=True) for k, col in (("frn", "#f0a04b"), ("ins", "#3fc7b0"), ("ind", "#a98bff"))]
    ser.sort(key=lambda x: -x["v"][-1])
    for i, x in enumerate(ser): x["below"] = i == len(ser) - 1
    ser[1]["nolab"] = True
    chart = dict(type="chart", kicker=f"{d['xm']} 만기 이후", title="누가 사고 누가 팔았나", unit="누적 순매수 · 억원", series=ser, tickfmt="k",
                 symmetric=False, foot="자료: 네이버 증권 · 투자 권유 아님", drawdur=2.2, dur=3.0 + 2.6)
    allv = ser[0]["v"] + ser[-1]["v"]
    if min(allv) < 0 < max(allv): chart["symmetric"] = True
    tiles = [dict(l=t, v=v, c=cs, cc=cc) for t, v, cs, sub, cc in d["tiles"]]
    t3 = dict(type="tiles", kicker="이번 주 숫자", title=f"{d['asof']} 마감 기준", tiles=tiles, nsz=92, foot="자료: 네이버 증권, Yahoo Finance · 투자 권유 아님", dur=2.0 + 3.6)
    th = theme("terminal"); th["vars"].update(up="#ff5a5f", dn="#4d8dff")  # 한국식: 빨강 상승, 파랑 하락
    return th, [hook, chart, t3, cards_scene(d["cards"], True)]


def books(d, region):
    c = d["c"]; ko = region == "kr"; title = c["title"]
    tt = f"《{title}》" if ko else title
    size = "" if len(tt) <= (8 if ko else 14) else "s" if len(tt) <= (13 if ko else 24) else "xs"
    hook = dict(type="hook", kicker=c["badge"], lines=[tt], size=size, sub=c["author"], pose="a19", poseh=320, dur=1.8 + rd(c["badge"], title, ko=ko))
    keys = c.get("keys") or []; keys = keys if isinstance(keys, list) else [keys]
    key = dict(type="quote", kicker=c.get("l2") or ("핵심" if ko else "KEY POINT"), text=keys[0] if keys else c.get("tag", ""), pose="a08", poseh=260)
    key["dur"] = 1.5 + rd(key["text"], ko=ko)
    q = " ".join(x.strip() for x in c["quote"])
    quote = dict(type="quote", kicker=c["head"], text=q, pose="a12", poseh=260, dur=1.6 + rd(q, ko=ko))
    return theme("book"), [hook, key, quote, cards_scene(d["cards"], ko)]


def news(d, region):
    c = d["c"]; ko = region == "kr"
    hook = dict(type="hook", kicker=c["badge"], lines=(["이번 주", "[[acc:좋은 뉴스]] TOP 3"] if ko else ["This week's", "[[acc:good news]]"]),
                sub=None if ko else "Top 3", pose="a12", poseh=320, dur=1.9 + 1.6)
    items = [dict(num=i + 1, tag=x["hero"], h=x["head"]) for i, x in enumerate(c["items"][:3])]
    lst = dict(type="list", kicker="TOP 3", title=None, items=items, gap=.45, dur=1.8 + rd(*[i["tag"] + i["h"] for i in items], ko=ko))
    q = " ".join(x.strip() for x in c["quote"])
    quote = dict(type="quote", kicker="오늘의 한 줄" if ko else "Quote of the week", text=f"“{q.strip('“”')}”", by=f"— {c['author']}", dur=1.6 + rd(q, ko=ko))
    return theme("cream"), [hook, lst, quote, cards_scene(d["cards"], ko)]


def dart(d, region):
    """수요일 동전 던지기: 지난주 채점 → 누적 전적 → 레드덴바가 동전 던짐 → 이번 주 방향 → 카드. 종목은 안 나옴."""
    import random
    c = d["c"]; ko = region == "kr"; new, last, rec, idx = c["new"], c.get("last"), c["rec"], c["index_name"]
    pc = lambda x: "0.0%" if abs(x) < 5e-4 else f"{x * 100:+.1f}%"
    word = lambda u: ("오른다" if u else "내린다") if ko else ("UP" if u else "DOWN")
    sc = []
    if last:
        lu = last["call"] == "up"; hit = last["hit"]; r = last["result"]
        sc.append(dict(type="hook", kicker=(f"지난주 동전: {word(lu)}" if ko else f"Last week's coin: {word(lu)}"), label=idx,
                       big=dict(to=round(r * 100, 1), dp=1, sign=True, suf="%"), bigc="var(--up)" if r > 0 else "var(--dn)",
                       sub=f"{last['entry']:,.2f} → {last['exit']:,.2f}",
                       pill=(("적중" if hit else "빗나감") if ko else ("HIT" if hit else "MISS")), pillc="#e0482a" if hit else "#5a6478",
                       pose="a04" if hit else "a06", poseh=260, dur=4.2))
    if rec["n"]:
        title = (f"누적 [[acc:{rec['hit']}승]] {rec['miss']}패" if ko else f"Record [[acc:{rec['hit']}-{rec['miss']}]]")
        tiles = [dict(l="레드덴바 적중률" if ko else "Red Denva's hit rate", n=round(rec["rate"] * 100), dp=0, suf="%", vc="var(--acc)"),
                 dict(l="원래 확률" if ko else "The odds", v="50%")]
        good = rec["rate"] > .5
        cm = (("확률보다 나음. 운이 좋음." if good else "확률보다 못함. 동전 탓.") if ko else ("Beating the odds. Lucky panda." if good else "Below the odds. Blame the coin."))
        sc.append(dict(type="tiles", kicker="주간 전적" if ko else "Weekly record", title=title, tiles=tiles, nsz=130,
                       rows=[["한마디" if ko else "Verdict", cm]], pose="a16" if good else "a15", poseh=220, dur=4.4))
    up = new["call"] == "up"
    sc.append(dict(type="coin", kicker=(f"{c['week']}주차 · 다음 주 수요일까지" if ko else f"Week {c['week']} · by next Wednesday"),
                   title=(f"{idx}는…" if ko else f"the {idx} goes…"), up=up, upw=word(True), dnw=word(False), flips=10 if up else 9,
                   spin0=.5, spin=2.6, top=190, dur=4.8))
    sc.append(dict(type="hook", kicker=(f"다음 주 수요일까지 {idx}는" if ko else f"By next Wednesday, the {idx} goes"),
                   lines=[f"[[{'up' if up else 'dn'}:{word(up)}]]"], size="xl", sub=(f"기준 {new['entry']:,.2f} · 동전이 정함" if ko else f"From {new['entry']:,.2f} · a coin decided"),
                   pill=("맞히면 동전 덕, 틀리면 동전 탓" if ko else "Not a forecast. Just a coin."), pillc="#14284d", pose="a00", poseh=280, dur=4.0))
    th = theme("terminal")
    if ko: th["vars"].update(up="#ff5a5f", dn="#4d8dff")
    else: th["vars"].update(up="#2fd08a", dn="#ff5a5f")
    return th, sc + [cards_scene(d["cards"], ko)]


def video_frames(path, fx, secs, fps=30):
    """영상을 1080x1920 세로로 꽉 차게 잘라(동물 얼굴 쪽 기준) JPG 프레임으로 뽑는다. 반환: (폴더, 장 수)"""
    import glob, shutil, subprocess
    sys.path.insert(0, os.path.join(ROOT, "reels")); from render import ffmpeg_bin
    out = os.path.abspath(os.path.join(os.path.dirname(path), "puppy-frames")); shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
    vf = (f"scale=-2:1920:flags=lanczos,crop=1080:1920:'max(0,min(iw-1080,iw*{fx:.3f}-540))':0,"
          f"scale=1080:1920,fps={fps},eq=saturation=1.06:contrast=1.03")
    subprocess.run([ffmpeg_bin(), "-y", "-loglevel", "error", "-i", path, "-t", f"{secs:.2f}", "-vf", vf, "-q:v", "3", f"{out}/f%04d.jpg"], check=True)
    return out, len(glob.glob(f"{out}/f*.jpg"))


def puppy(d, region, acc="#ff8a4c", pose="a00"):
    c = d["c"]; ko = region == "kr"; fx, fy = (c.get("focus") or [.5, .45])
    if d.get("video") and os.path.exists(d["video"]):
        # 영상 버전: 이름 → 첫째 줄 → 둘째 줄이 차례로 뜨고, 다 읽을 때까지 영상이 흐른다
        l1, l2 = (c["lines"] + ["", ""])[:2]
        t1 = 1.7; t2 = t1 + max(1.6, rd(l1, ko=ko) - .4); dur = max(7.5, t2 + rd(l2, ko=ko) + .6)
        # 글을 다 읽은 뒤에도 영상이 끝날 때까지(최대 20초) 흐른다
        dur = min(max(dur, float(d.get("vdur") or 0)), 20.0); frames, n = video_frames(d["video"], fx, min(dur, float(d.get("vdur") or dur)))
        day = dt.date.fromisoformat(d["day"]) if d.get("day") else dt.date.today()
        top = (f"{KO_DAY[day.weekday()]}요일 · {c['badge']}" if ko else f"{EN_DAY_FULL[day.weekday()]} · {c['badge']}")
        vs = dict(type="video", frames="file://" + frames, nframes=n, fps=30, top=top, dband=(f"{day.month}월" if ko else f"{day:%b}".upper()), dnum=str(day.day),
                  badge=("이번 주 주인공" if ko else "This week's star"), title=c["name"], lines=[l1, l2], lat=[t1, t2],
                  credit=(c.get("foot") or [""])[0], dur=dur)
        sc = [vs]
        if c.get("aside") and len(c["aside"]) >= 2:
            sc.append(dict(type="quote", kicker="레드덴바 한마디" if ko else "Red Denva says", text=c["aside"], pose=pose, poseh=320, dur=1.5 + rd(c["aside"], ko=ko)))
        th = theme("photo"); th["vars"]["acc"] = acc
        return th, sc + [cards_scene(d["cards"], ko)]
    ph = dict(type="photo", src="file://" + d["photo"], fx=fx, fy=fy, top=c.get("top"), badge=c["badge"], title=c["name"], lines=c["lines"][:2],
              credit=(c.get("foot") or [""])[0], dur=2.2 + rd(c["name"], *c["lines"][:2], ko=ko))
    sc = [ph]
    if c.get("aside") and len(c["aside"]) >= 6:
        sc.append(dict(type="quote", kicker="레드덴바 한마디" if ko else "Red Denva says", text=c["aside"], pose=pose, poseh=320, dur=1.5 + rd(c["aside"], ko=ko)))
    th = theme("photo"); th["vars"]["acc"] = acc
    return th, sc + [cards_scene(d["cards"], ko)]


def facts(d, region):
    return puppy(d, region, acc="#14957f", pose="a11")


def trip(d, region):
    ko = region == "kr"; s = d["spot"]; j = d["j"]; fx = d.get("fx") or [[.5, .5]] * 3
    p0 = dict(type="photo", src="file://" + d["p0"], fx=fx[0][0], fy=fx[0][1], badge="이번 주말 서울 나들이" if ko else "This weekend from LA",
              title=s["name"], lines=[j["why"]], top=s.get("area"), dur=2.2 + rd(s["name"], j["why"], ko=ko))
    rows = [("가는 법" if ko else "Getting there", s.get("how")), ("시간" if ko else "Hours", s.get("hours")), ("요금" if ko else "Entry", s.get("fee")), ("팁" if ko else "Tip", j.get("tip"))]
    items = [dict(tag=a, h=b) for a, b in rows if b]
    info = dict(type="list", kicker=s["name"], title="이렇게 가요" if ko else "Plan the trip", items=items, gap=.3, bg=None, dur=1.6 + rd(*[i["h"] for i in items], ko=ko))
    w = d.get("w") or []
    wl = [f"{lab} {ICON(z['code'])} {z['hi']}° / {z['lo']}°" + (f" · {'비' if ko else 'rain'} {z['rain']}%" if z.get("rain", 0) >= 40 else "")
          for lab, z in zip(("토" if ko else "Sat", "일" if ko else "Sun"), w)]
    if wl: info["items"].insert(0, dict(tag="주말 날씨" if ko else "Weekend weather", h="   ".join(wl)))
    info["dur"] = 1.6 + rd(*[i["h"] for i in info["items"]], ko=ko)
    if j.get("aside"): info["foot"] = ("레드덴바: " if ko else "Red Denva: ") + j["aside"]
    th = theme("photo"); th["vars"]["acc"] = "#ff8a4c"
    return th, [p0, info, cards_scene(d["cards"], ko)]


def netflix(d, region):
    c = d["c"]; ko = region == "kr"; t = c["title"]
    size = "" if len(t) <= (8 if ko else 14) else "s" if len(t) <= (13 if ko else 24) else "xs"
    sub = " · ".join(x for x in (c.get("season"), c.get("genre")) if x)
    hook = dict(type="hook", kicker=c["kicker"], lines=[t], size=size, sub=sub, pill=c["weeks"], pillc="#e23b3b", pose="a20", poseh=300, dur=2.0 + rd(c["kicker"], t, ko=ko))
    line = dict(type="quote", kicker="어떤 작품?" if ko else "What is it?", text=c["line"], by=(c["who_label"] + c["who"]) if c.get("who") else None,
                dur=1.6 + rd(c["line"], c.get("who"), ko=ko))
    items = [dict(num=r, h=tt, s=s or None) for r, tt, s in c["rest"]]
    if c.get("film"): items.append(dict(num="🎬", numc="#e23b3b", tag=c["film_label"], h=c["film"]))
    lst = dict(type="list", kicker=c["list_title"], title=None, items=items, gap=.25, dur=1.8 + rd(*[i["h"] for i in items], ko=ko))
    return theme("screen"), [hook, line, lst, cards_scene(d["cards"], ko)]


# ------------------------------------------------------------------ 모닝·마감 브리프 (brief.py)
def qval(q):
    if q.get("kind") == "text": return f"{q['last']:+,.{q.get('dp', 2)}f}"
    v = f"{q['last']:,.{q.get('dp', 2)}f}"
    u = q.get("unit", "")
    return "$" + v if u == "$" else v + "%" if u == "%" else v + ("원" if u == "원" and "/" not in q["name"] else "")


def qmove(q):
    """등락 숫자: % (기본) / bp (금리) / pt (VIX·베이시스)."""
    k = q.get("kind")
    if k == "bp": return None, f"{'▲' if q['bp'] > 0 else '▼' if q['bp'] < 0 else '–'} {abs(q['bp']):.1f}bp", q["bp"]
    if k == "pt": return None, f"{'▲' if q['chg'] > 0 else '▼' if q['chg'] < 0 else '–'} {abs(q['chg']):.2f}", q["chg"]
    if k == "text": return None, q.get("text", ""), 0
    return q["pct"], None, q["pct"]


def qrow(q, up, dn):
    p, txt, m = qmove(q)
    return dict(n=q["name"], v=qval(q), p=p, ptxt=txt, c=up if m > 0 else dn if m < 0 else "#8a94a8", spark=q.get("spark"), base=q.get("prev") if q.get("kind") != "text" else None)


def qtile(q, up, dn):
    p, txt, m = qmove(q)
    return dict(l=q["name"], v=qval(q), c=(("보합" if "원" in str(q.get("unit")) or any("\uac00" <= ch <= "\ud7a3" for ch in q["name"]) else "unch.") if p == 0 else f"{p:+.2f}%" if p is not None else txt or q.get("text", "")), cc=up if m > 0 else dn if m < 0 else "var(--psub)")


def heatbg(p, ko):
    k = min(1, abs(p) / 2.5); up, dn, g = ((232, 52, 58), (31, 111, 229), (96, 104, 122)) if ko else ((20, 160, 90), (229, 72, 77), (96, 104, 122))
    c = up if p >= 0 else dn; m = .3 + .7 * k
    return "rgb(" + ",".join(str(round(g[i] + (c[i] - g[i]) * m)) for i in range(3)) + ")"


def brief(d, region):
    """짧게, 핵심만, 캐릭터로. 모닝: 표지 → 날씨 → D램 → GPU → 간밤 시장(한마디) → 카드. 마감: 표지 → 한마디 → 지수 차트 → 수급/섹터 → 카드."""
    ko = region == "kr"; up, dn = ("#ff5a5f", "#4d8dff") if ko else ("#2fd08a", "#ff5a5f")
    th = theme("terminal"); th["vars"].update(up=up, dn=dn)
    sec = lambda t: next((x for x in d["sections"] if x["type"] == t), None)
    mvs = lambda q: f"[[{'up' if q['pct'] > 0 else 'dn'}:{q['pct']:+.2f}%]]" if q["pct"] else ("보합" if ko else "unch.")
    sc = []
    w = d.get("wx")
    if w:  # 날씨: 표지 바로 다음, 날씨 옷 입은 레드덴바 (모닝 = 오늘, 마감 = 내일)
        sc.append(dict(type="hook", chip=(f"{w.get('when', '오늘')} {w['city']} 날씨" if ko else f"{w['city']} weather {w.get('when', 'today').lower()}"), label=w["sky"],
                           big=dict({"from": w["lo"], "to": w["hi"]}, suf="°"), pill=(f"최저 {w['lo']}° · 비 올 확률 {w['rain']}%" if ko else f"Low {w['lo']}° · Rain {w['rain']}%"),
                           pillc="#1f6fe5" if w["rain"] >= 40 else "#5b6b8c", pose=w.get("pose", "w00"), poseh=420, top=200, dur=4.0))
    if d["kind"] in ("morning", "wrap"):  # 주간 정리도 모닝과 같은 흐름 (등락 = 1주)
        ch = sec("chips")
        if ch:
            for q in ch["dram"][:1]:
                since = dt.date.fromisoformat(q["since"]); last = dt.date.fromisoformat(q["date"])
                wk = " · ".join(f"{a} {q[k]:+.2f}%" for k, a in (("w1", "1주" if ko else "1W"), ("m1", "1달" if ko else "1M")) if q.get(k) is not None)
                sc.append(dict(type="chart", kicker=("D램 현물가 · DDR5 16Gb" if ko else "DRAM spot · DDR5 16Gb"), title=f"${q['last']:,.{q.get('dp', 2)}f}  {mvs(q)}",
                               series=[dict(name="DDR5 16Gb", c=up if q["pct"] > 0 else dn if q["pct"] < 0 else "#c8cfdb", v=q["spark"], dp=q.get("dp", 2))],
                               xlabs=[f"{since.month}/{since.day}", "3개월" if ko else "3 months", f"{last.month}/{last.day}"],
                               tight=True, symmetric=False, tickdp=1, drawdur=1.8, dur=4.6, foot=wk, footbig=True))
            gp = sorted(ch["gpu"], key=lambda q: -q["last"])
            if gp:
                col = {"B200": "#ffa94d", "H100": "#e9edf5", "A100": "#3ccfb4"}
                since = dt.date.fromisoformat(gp[0]["since"]); last = dt.date.fromisoformat(gp[0]["date"])
                sc.append(dict(type="chart", kicker=("GPU 임대료 · 1시간당" if ko else "GPU rental · per hour"), title="  ".join(f"{q['name']} {mvs(q)}" for q in gp),
                               series=[dict(name=f"{q['name']} ${q['last']:.2f}", c=col.get(q["name"], "#aaa"), v=[round((v / q["spark"][0] - 1) * 100, 2) for v in q["spark"]], dp=1, sign=True, nolab=True) for q in gp],
                               xlabs=[f"{since.month}/{since.day}", "3개월" if ko else "3 months", f"{last.month}/{last.day}"], base=0, baselab=("3개월 전" if ko else "start"),
                               tight=True, symmetric=False, tickdp=0, drawdur=1.8, dur=4.8, foot=("선 = 3개월 등락률" if ko else "Lines = 3-month % change"), footbig=True))
        big = sec("mini")
        items = big["items"] if big else []
        if items:
            rr = [qrow(q, up, dn) for q in items[:6]]
            sc.append(dict(type="board", kicker=big["title"], rows=rr, gap=.16, foot=f"“{d['comment']}”", pose=d.get("pose", "a05"), poseh=230, dur=1.4 + 0.45 * len(rr) + 2.2))
    else:
        hk = d["hook"]
        sc.append(dict(type="hook", kicker=hk["kicker"], lines=hk["lines"], size="s", sub=f"“{d['comment']}”", pose=d.get("pose", "a05"), poseh=360, dur=min(4.6, 1.8 + rd(*hk["lines"], d["comment"], ko=ko))))
        h = sec("hero") or sec("charts")
        if h:
            q = h.get("item") or h["hero"]; c = up if q["pct"] > 0 else dn if q["pct"] < 0 else "#8a94a8"
            xl = ["09:00", "12:00", "15:30"] if ko else ["9:30", "12:45", "4:00"]
            sc.append(dict(type="chart", kicker=h["title"], title=f"{qval(q)}  {mvs(q)}", series=[dict(name=q["name"], c=c, v=q["spark"], dp=q.get("dp", 2))],
                           base=q["prev"], baselab="전일" if ko else "prev.", xlabs=xl, tight=True, symmetric=False, tickdp=0, drawdur=1.8, dur=4.6,
                           foot=("점선 = 전일 종가" if ko else "Dashed line = previous close")))
        f = sec("flows")
        if f:
            WHO = [("frn", "외국인"), ("ins", "기관"), ("ind", "개인")]; PRG = [("arb", "차익"), ("non", "비차익"), ("tot", "전체")]
            groups = [dict(title=lab, rows=[dict(n=w, v=r[k], c=up if r[k] > 0 else dn) for k, w in (PRG if "tot" in r else WHO)]) for lab, r in f["rows"]]
            sc.append(dict(type="flows", kicker="수급", title="순매수 · 억원", groups=groups, dur=1.8 + 1.3 * len(groups) + 0.8))
        hs = sec("heat")
        if hs:
            sc.append(dict(type="heat", groups=[dict(title=hs["title"], cols=4 if len(hs["items"]) > 6 else 3, items=[dict(n=q["name"], p=q["pct"], bg=heatbg(q["pct"], ko)) for q in hs["items"]])],
                           top=230, dur=2.0 + 0.1 * len(hs["items"]) + 1.2))
    cards = d["cards"]
    if len(cards) > 1:  # 둘째 장 = 주요 뉴스 3개. 읽을 시간 주기
        sc.append(dict(type="cards", kicker=(("간밤 미국 주요 뉴스" if d["kind"] == "morning" else "오늘 장중 핵심 뉴스") if ko else "Top headlines"), srcs=["file://" + cards[1]], dur=7.5))
    return th, sc + [cards_scene(cards[:1], ko)]


def ahead(d, region):
    """다음 주 일정: 표지 → 이번 주 가장 큰 일정 2개(한마디) → 카드(오래)."""
    ko = region == "kr"; th = theme("terminal"); hk = d["hook"]
    sc = [dict(type="hook", kicker=hk["kicker"], lines=hk["lines"], size="s", sub=f"“{d['comment']}”", pose="a05", poseh=360, dur=min(4.8, 2.0 + rd(*hk["lines"], d["comment"], ko=ko)))]
    return th, sc + [dict(type="cards", kicker=CARD_LAST["ko" if ko else "en"], srcs=["file://" + d["cards"][0]], dur=8.0)]


ADAPT = dict(wrap=brief, ahead=ahead, dart=dart, weather=weather, morning=brief, close=brief, deriv=deriv, books=books, news=news, puppy=puppy, facts=facts, trip=trip, netflix=netflix)


SERIES = {"kr": {"weather": "[[acc:서울]] 날씨", "books": "이번 주 [[acc:책]]", "news": "[[acc:좋은 뉴스]]", "puppy": "[[acc:아기 동물]]", "dart": "[[acc:동전]] 던지기",
                 "deriv": "[[acc:파생]] 브리핑", "trip": "[[acc:주말 여행]]", "facts": "[[acc:동물 상식]]", "netflix": "[[acc:넷플릭스]]",
                 "morning": "[[acc:모닝]] 브리프", "close": "[[acc:마감]] 브리프", "wrap": "[[acc:주간]] 정리", "ahead": "다음 주 [[acc:일정]]"},
          "us": {"weather": "[[acc:LA]] weather", "books": "[[acc:Book]] of the week", "news": "[[acc:Good news]]", "puppy": "[[acc:Baby animal]]", "dart": "[[acc:Coin]] flip",
                 "deriv": "[[acc:Derivatives]]", "trip": "[[acc:Weekend trip]]", "facts": "[[acc:Animal facts]]", "netflix": "[[acc:Netflix]] top 10",
                 "morning": "[[acc:Morning]] Brief", "close": "[[acc:Closing]] Brief", "wrap": "[[acc:Weekly]] Recap", "ahead": "Week [[acc:Ahead]]"}}
EN_DAY_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# 시리즈마다 단색 배경 (색 계열은 확실히 다르게, 밝기·채도는 비슷하게 눌러서 세련되게)
SERIES_BG = {"dart": "#3b2f5c", "weather": "#1f4e8c", "books": "#6b4a2e", "news": "#f1e4c8", "puppy": "#93475f",
             "deriv": "#2b313c", "trip": "#1d6461", "facts": "#56632c", "netflix": "#6e1d29", "morning": "#2a2550", "close": "#14233d"}
SERIES_ACC = {"books": "#f3c97a", "netflix": "#ffb0a8", "puppy": "#ffc59e", "facts": "#f6d28a", "trip": "#ffc08a"}  # 배경 위에서 잘 보이게


def open_scene(kind, region, day=None):
    """모든 릴스의 첫 화면(=섬네일). 날짜 아이콘 + '목요일 파생 브리핑' 같은 제목."""
    tz = "Asia/Seoul" if region == "kr" else "America/Los_Angeles"
    from zoneinfo import ZoneInfo
    day = dt.date.fromisoformat(day) if day else dt.datetime.now(ZoneInfo(tz)).date(); w = day.weekday()
    if region == "kr":
        band, first = f"{day.month}월 {KO_DAY[w]}", ("오늘의" if kind == "weather" else f"{KO_DAY[w]}요일")
        if kind in ("morning", "close"): first = None
    else:
        band, first = f"{day:%b} · {EN_DAY[w]}".upper(), ("Today's" if kind == "weather" else EN_DAY_FULL[w])
        if kind in ("morning", "close"): first = None
    title = SERIES[region][kind]
    size = "s" if len(re.sub(r"\[\[\w+:|\]\]", "", title)) > (7 if region == "kr" else 11) else ""
    if first is None: size = "" if region == "kr" else "s"
    return dict(type="open", band=band, day=str(day.day), lines=[x for x in (first, title) if x], size=size,
                handle=f"@reddenva.{region}", pose="a00", poseh=230, dur=2.3)


def build(kind, region):
    d = reel_data.load(kind, region)
    if not d: raise SystemExit(f"reel_in/{kind}-{region}.json 없음 (이번 실행에서 카드를 안 만들었음)")
    th, scenes = ADAPT[kind](d, region)
    if kind in SERIES_BG: th["vars"]["bg"] = SERIES_BG[kind]
    if kind in SERIES_ACC: th["vars"]["acc"] = SERIES_ACC[kind]
    return {"theme": th, "scenes": [open_scene(kind, region, d.get("day") if kind in ("morning", "close", "puppy", "dart") else None)] + scenes}


# ------------------------------------------------------------------ 업로드 (GitHub Release)
def gh(method, url, **kw):
    h = {"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"}
    h.update(kw.pop("headers", {}))
    r = requests.request(method, url, headers=h, timeout=120, **kw)
    if not r.ok and r.status_code != 404: raise RuntimeError(f"GitHub {method} {url} → {r.status_code} {r.text[:200]}")
    return r


def upload(paths):
    repo = os.environ["GITHUB_REPOSITORY"]; api = f"https://api.github.com/repos/{repo}"
    r = gh("GET", f"{api}/releases/tags/reels")
    if r.status_code == 404:
        r = gh("POST", f"{api}/releases", json={"tag_name": "reels", "name": "Reels (자동 생성 영상 보관)", "body": "Instagram 릴스 게시용 영상. 3주 지나면 자동 삭제.", "prerelease": True})
    rel = r.json(); assets = gh("GET", f"{api}/releases/{rel['id']}/assets", params={"per_page": 100}).json()
    cut = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=21)
    for a in assets:  # 오래된 것·같은 이름 정리
        if dt.datetime.fromisoformat(a["created_at"].replace("Z", "+00:00")) < cut or a["name"] in [os.path.basename(p) for p in paths]:
            gh("DELETE", f"{api}/releases/assets/{a['id']}")
    urls = []
    for p in paths:
        ct = "video/mp4" if p.endswith(".mp4") else "image/jpeg"
        up = gh("POST", f"https://uploads.github.com/repos/{repo}/releases/{rel['id']}/assets", params={"name": os.path.basename(p)},
                headers={"Content-Type": ct}, data=open(p, "rb").read())
        urls.append(up.json()["browser_download_url"])
    return urls


def enabled(region):
    try: return bool(json.load(open(os.path.join(ROOT, "reels.json"))).get(region))
    except Exception: return False


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--region", required=True, choices=["kr", "us"])
    ap.add_argument("--enabled", action="store_true"); ap.add_argument("--kind"); ap.add_argument("--local")
    ap.add_argument("--preview", action="store_true", help="이번 실행에서 만든 카드 전부를 reel_out/에 영상으로 (테스트 실행용, 업로드 없음)")
    a = ap.parse_args()
    if a.enabled: sys.exit(0 if enabled(a.region) else 1)
    sys.path.insert(0, os.path.join(ROOT, "reels")); from render import render
    if a.preview:
        os.makedirs("reel_out", exist_ok=True)
        for k in ["weather"] + KINDS:
            if reel_data.load(k, a.region):
                data = build(k, a.region); o = f"reel_out/{k}-{a.region}.mp4"
                print(k, render(data, o, o.replace(".mp4", "-cover.jpg"), min(2.4, data["scenes"][0]["dur"] - .4)), "초 →", o)
        return
    if a.local:
        data = build(a.kind, a.region); cov = a.local.replace(".mp4", "-cover.jpg")
        print("길이", render(data, a.local, cov, min(2.4, data["scenes"][0]["dur"] - .4)), "초 →", a.local, cov); return
    if not enabled(a.region): print("릴스 꺼짐 (reels.json) → 카드 이미지로 게시"); return
    pj = f"out/{a.region}-post.json"; meta = json.load(open(pj, encoding="utf-8"))
    if not meta.get("image_url"): print("오늘 올릴 카드 없음"); return
    name = os.path.basename(meta["image_url"])
    kind = a.kind or next((k for k in KINDS if name.startswith(k + "-")), "weather")
    data = build(kind, a.region)
    os.makedirs("reel_out", exist_ok=True); stem = f"reel_out/{kind}-{a.region}-{meta['date']}"
    t = time.time(); dur = render(data, stem + ".mp4", stem + ".jpg", min(2.4, data["scenes"][0]["dur"] - .4))
    print(f"영상 {dur:.1f}초, 렌더 {time.time() - t:.0f}초")
    vu, cu = upload([stem + ".mp4", stem + ".jpg"])
    # post.json은 건드리지 않고 저장소에 안 올라가는 파일에 적는다(뒤 단계의 git pull --rebase를 막지 않게)
    json.dump({"date": meta["date"], "image_url": meta["image_url"], "video_url": vu, "cover_url": cu},
              open(f"reel_out/{a.region}-video.json", "w", encoding="utf-8")); print("릴스 준비 완료:", vu)


if __name__ == "__main__":
    main()
