import re,json,time,urllib.request,sys
UA="Mozilla/5.0 (compatible; AchEventsGuide/1.0; +https://achevents.com)"
def get(u):
    return urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":UA}),timeout=30).read().decode("utf-8","ignore")
out={}
for city in ("bologna","milano"):
    h=get(f"https://www.cinemap.it/{city}/cinema")
    for p in sorted(set(re.findall(rf'href="(/{city}/cinema/[a-z0-9-]+)"',h))):
        time.sleep(1)
        try: s=get("https://www.cinemap.it"+p)
        except Exception as e: out[p]={"err":str(e)}; continue
        th=None
        for b in re.findall(r'<script[^>]*ld\+json[^>]*>(.*?)</script>',s,re.S):
            try: j=json.loads(b)
            except: continue
            if isinstance(j,dict) and j.get("@type")=="MovieTheater": th=j
        u=s.replace('\\"','"')
        ev=re.findall(r'"@type":"ScreeningEvent","name":"(.*?)","startDate":"(.*?)"',u)
        out[p]={"th":th,"n":len(ev),"giorni":sorted({d[:10] for _,d in ev}),"film":sorted({n for n,_ in ev})[:8]}
json.dump(out,open("out/cm.json","w"),ensure_ascii=False,indent=1)
