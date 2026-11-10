import sys,os,json,datetime
sys.argv=['x']; sys.path.insert(0,'scripts')
import cinema_auto as C
from zoneinfo import ZoneInfo
oggi=datetime.datetime.now(ZoneInfo("Europe/Rome")).date()
out={}
for u in ["https://www.cinemap.it/bologna/cinema/popup-jolly-bologna","https://www.cinemap.it/bologna/cinema/popup-medica-bologna","https://www.cinemap.it/milano/cinema/beltrade-milano","https://www.cinemap.it/bologna/cinema/odeon-bologna"]:
    h=C.scarica(u); open("out/"+u.split("/")[-1]+".html","w").write(h)
    out[u]=C.leggi_cinemap(h,u,oggi)
json.dump(out,open("out/cm_test.json","w"),ensure_ascii=False,indent=1)
