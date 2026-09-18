from math import radians,sin,cos,sqrt,atan2
from database import q
def dist(a,b,c,d):
    if None in (a,b,c,d):return None
    R=6371000; p=radians(a); q2=radians(c); dp=radians(c-a); dl=radians(d-b); z=sin(dp/2)**2+cos(p)*cos(q2)*sin(dl/2)**2; return R*2*atan2(sqrt(z),sqrt(1-z))
def nearby(lat,lon,radius):
    rows=q("SELECT h.*,u.username FROM help_requests h JOIN users u ON u.id=h.user_id WHERE h.status='active' AND h.sharing_location=1")
    out=[]
    for r in rows:
        d=dist(lat,lon,r['latitude'],r['longitude'])
        if d is not None and d<=min(radius,r['radius_m']):out.append({**dict(r),'distance_m':round(d)})
    return out
