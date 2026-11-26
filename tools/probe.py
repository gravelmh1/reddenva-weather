"""데이터 출처 확인용 (시안 단계에서만 씀). 원문 앞부분을 samples/raw/에 저장."""
import requests, os, re
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
os.makedirs("samples/raw", exist_ok=True)
for name, url in [("dramx", "https://www.dramexchange.com/"), ("chip", "https://chip.qpx.kr/prices/dram-spot__ddr5-16gb-2gx8-4800-5600"),
                  ("gpu", "https://gpu-index.semianalysis.com/api/public-data"), ("prekospi", "https://www.prekospi.com/kospi200-night/history/2026-11-25"),
                  ("prekospi0", "https://www.prekospi.com/kospi200-night")]:
    try:
        r = requests.get(url, headers=H, timeout=30); t = r.text
        print(name, r.status_code, len(t), r.headers.get("content-type"))
        open(f"samples/raw/{name}.txt", "w").write(f"{r.status_code} {r.headers.get('content-type')}\n" + t[:400000])
    except Exception as e: print(name, "ERR", e)
