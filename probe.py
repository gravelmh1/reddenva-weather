import requests, re, datetime as dt
from bs4 import BeautifulSoup
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36","Referer":"https://finance.naver.com/sise/sise_trans_style.naver"}
for sosok in ("03","04","05"):
    for page in (1,2):
        u=f"https://finance.naver.com/sise/investorDealTrendDay.naver?bizdate=20261116&sosok={sosok}&page={page}"
        r=requests.get(u,headers=UA,timeout=20); r.encoding="euc-kr"
        s=BeautifulSoup(r.text,"html.parser")
        print("==",sosok,page,r.status_code,len(r.text))
        for tr in s.select("tr")[:16]:
            t=[re.sub(r"\s+","",x.get_text()) for x in tr.select("th,td")]
            if any(t): print(" | ".join(t)[:200])
r=requests.get("https://finance.naver.com/sise/sise_trans_style.naver",headers=UA,timeout=20); r.encoding="euc-kr"
t=BeautifulSoup(r.text,"html.parser").get_text(" ")
i=t.find("선물"); print(re.sub(r"\s+"," ",t[i-300:i+900]))
