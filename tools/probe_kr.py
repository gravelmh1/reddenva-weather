"""임시: GitHub 러너에서 한국 파생 데이터 출처가 열리는지 확인."""
import requests, json
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
DH = dict(H, Referer="https://finance.daum.net/")
G = [
 ("fchart FUT", "https://fchart.stock.naver.com/sise.nhn?symbol=FUT&timeframe=day&count=5&requestType=0", H),
 ("fchart KPI200", "https://fchart.stock.naver.com/sise.nhn?symbol=KPI200&timeframe=day&count=5&requestType=0", H),
 ("naver idx day FUT", "https://finance.naver.com/sise/sise_index_day.naver?code=FUT&page=1", H),
 ("naver idx day KPI200", "https://finance.naver.com/sise/sise_index_day.naver?code=KPI200&page=1", H),
 ("naver fut main", "https://finance.naver.com/sise/sise_index.naver?code=FUT", H),
 ("naver inv 01", "https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate=20261125&sosok=01", H),
 ("naver inv 03", "https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate=20261125&sosok=03", H),
 ("naver inv 04", "https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate=20261125&sosok=04", H),
 ("naver inv 05", "https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate=20261125&sosok=05", H),
 ("naver 10y", "https://finance.naver.com/marketindex/interestDailyQuote.naver?marketindexCd=IRR_GOVT10Y&page=1", H),
 ("naver 3y", "https://finance.naver.com/marketindex/interestDailyQuote.naver?marketindexCd=IRR_GOVT03Y&page=1", H),
 ("mnaver bond", "https://m.stock.naver.com/front-api/marketIndex/prices?category=bond&reutersCode=KR10YT%3DRR&page=1&pageSize=5", H),
 ("daum fut page", "https://finance.daum.net/domestic/futures", DH),
 ("daum api fut", "https://finance.daum.net/api/future/KR4101", DH),
 ("daum api fut days", "https://finance.daum.net/api/future/KR4101/days?perPage=5&page=1", DH),
 ("daum inv fut", "https://finance.daum.net/api/investor/future/days?perPage=5&page=1", DH),
 ("daum inv kospi", "https://finance.daum.net/api/investor/days?perPage=5&page=1&market=KOSPI", DH),
 ("daum k200 days", "https://finance.daum.net/api/market_index/days?page=1&perPage=5&market=KOSPI200&pagination=true", DH),
 ("yahoo KS200", "https://query1.finance.yahoo.com/v8/finance/chart/%5EKS200?range=5d&interval=1d", H),
 ("krx", "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd", H),
]
for name, u, h in G:
    try:
        r = requests.get(u, headers=h, timeout=20); t = r.text
        if "euc-kr" in r.headers.get("content-type", "").lower() or "naver.com/sise" in u or "marketindex" in u: t = r.content.decode("euc-kr", "replace")
        print(f"=== {name} {r.status_code} {r.headers.get('content-type')} len={len(t)}"); print(t[:1500].replace("\n", " ")[:1500])
    except Exception as e: print("===", name, "ERR", e)
import re
for name, obj in (("credit", "STATSCU0100000070BO"), ("credit2", "STATSCU0100000060BO")):
    try:
        body = {"dmSearch": {"tmpV40": "1000000", "tmpV41": "1", "tmpV1": "D", "tmpV45": "20261101", "tmpV46": "20261126", "OBJ_NM": obj}}
        r = requests.post("https://freesis.kofia.or.kr/meta/getMetaDataList.do", json=body, headers=dict(H, Referer="https://freesis.kofia.or.kr/"), timeout=30)
        print("=== freesis", name, r.status_code, r.text[:1500])
    except Exception as e: print("=== freesis ERR", e)
try:
    r = requests.get("https://finance.daum.net/domestic/futures", headers=DH, timeout=20)
    print("=== daum js", re.findall(r'src="([^"]+\.js)"', r.text)[:20])
except Exception as e: print(e)
