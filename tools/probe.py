"""데이터 출처 확인용 (시안 단계에서만 씀). 응답 앞부분을 samples/raw/probe2.txt에 저장."""
import requests, os
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Referer": "https://m.stock.naver.com/"}
os.makedirs("samples/raw", exist_ok=True)
D = "20261126"
URLS = [
    # 코스피200 선물 분봉
    f"https://api.finance.naver.com/siseJson.naver?symbol=FUT&requestType=1&startTime={D}&endTime={D}&timeframe=minute",
    "https://fchart.stock.naver.com/sise.nhn?symbol=FUT&timeframe=minute&count=400&requestType=0",
    "https://fchart.stock.naver.com/sise.nhn?symbol=KPI200&timeframe=minute&count=400&requestType=0",
    "https://api.stock.naver.com/chart/domestic/futures/FUT/minute",
    f"https://api.stock.naver.com/chart/domestic/futures/FUT/minute?startDateTime={D}0900&endDateTime={D}1600",
    "https://api.stock.naver.com/chart/domestic/index/KPI200/minute",
    "https://polling.finance.naver.com/api/realtime/domestic/futures/FUT",
    "https://m.stock.naver.com/api/index/FUT/price?pageSize=60&page=1",
    "https://m.stock.naver.com/api/index/FUT/basic",
    # 프로그램 매매
    f"https://m.stock.naver.com/api/index/KOSPI/program?bizdate={D}",
    f"https://m.stock.naver.com/api/index/KOSPI/programTrend?bizdate={D}",
    "https://m.stock.naver.com/front-api/index/program?category=KOSPI",
    f"https://finance.naver.com/sise/programDealTrendDay.naver?bizdate={D}",
    f"https://finance.naver.com/sise/sise_program.naver",
    f"https://finance.naver.com/sise/programDealTrendTime.naver?bizdate={D}&sosok=01",
    "https://finance.daum.net/api/trend/program_trading?market=KOSPI",
]
out = []
for u in URLS:
    try:
        r = requests.get(u, headers=H, timeout=25)
        t = r.content.decode("euc-kr", "replace") if "naver.com/sise" in u or "fchart" in u else r.text
        out.append(f"### {u}\n{r.status_code} {r.headers.get('content-type')} len={len(t)}\n{t[:1500]}\n")
    except Exception as e: out.append(f"### {u}\nERR {e}\n")
open("samples/raw/probe2.txt", "w").write("\n".join(out)); print("\n".join(x[:300] for x in out))
