"""임시: GitHub 러너에서 한국 파생 데이터 출처가 열리는지 확인 (2차)."""
import requests, re
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
DH = dict(H, Referer="https://finance.daum.net/domestic/futures")
def show(name, u, h=H, n=1200):
    try:
        r = requests.get(u, headers=h, timeout=20); print(f"=== {name} {r.status_code} len={len(r.text)}"); print(r.text[:n].replace("\n", " "))
    except Exception as e: print("===", name, "ERR", e)
for code in ("KR10YT%3DRR", "KR3YT%3DRR"):
    show("mnaver bond " + code, f"https://m.stock.naver.com/front-api/marketIndex/prices?category=bond&reutersCode={code}&page=1&pageSize=10", n=800)
p = requests.get("https://finance.daum.net/domestic/futures", headers=DH, timeout=20).text
print("=== daum page api refs", sorted(set(re.findall(r'["\'](/api/[^"\']+)', p)))[:60])
for m in re.finditer(r'(investor|future)', p, re.I):
    pass
print("=== daum page snippets", [p[max(0,m.start()-120):m.start()+120].replace("\n"," ") for m in re.finditer(r'api', p)][:15])
for js in re.findall(r'src="(https://t1\.daumcdn\.net/media/kraken/finance/resources/dist/[^"]+\.js)"', p):
    t = requests.get(js, headers=H, timeout=30).text
    refs = sorted(set(re.findall(r'["\'`](/api/[^"\'`]{2,120})', t)))
    print("=== js", js.rsplit("/",1)[-1], len(t), [x for x in refs if re.search("invest|futur|deriv|program", x, re.I)][:80])
n = requests.get("https://finance.naver.com/sise/sise_index.naver?code=FUT", headers=H, timeout=20).text
print("=== naver new page api refs", sorted(set(re.findall(r'https?://[a-z\-\.]*naver\.com/[^"\'\\ ]*api[^"\'\\ ]{0,120}', n)))[:40])
print("=== naver investor snippets", [n[max(0,m.start()-200):m.start()+200] for m in re.finditer(r'외국인', n)][:4])
for u in ("https://m.stock.naver.com/api/index/FUT/basic", "https://m.stock.naver.com/api/index/FUT/trend", "https://m.stock.naver.com/api/index/KPI200/trend",
          "https://m.stock.naver.com/api/index/KOSPI/trend", "https://m.stock.naver.com/api/futures/FUT/trend", "https://m.stock.naver.com/front-api/index/trend?code=FUT",
          "https://api.stock.naver.com/index/FUT/trend", "https://m.stock.naver.com/api/index/FUT/investor", "https://finance.daum.net/api/investor/futures/days?page=1&perPage=5",
          "https://finance.daum.net/api/trend/futures_investors?page=1&perPage=5", "https://finance.daum.net/api/futures/investors/days?page=1&perPage=5",
          "https://finance.daum.net/api/futures?page=1", "https://finance.daum.net/api/futures/KR4101V30008"):
    show(u.split("//")[1][:70], u, DH if "daum" in u else H, 600)
