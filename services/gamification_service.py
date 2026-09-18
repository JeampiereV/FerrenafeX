from database import q,x
from services.notification_service import notify
def points(uid):
    r=q('SELECT COALESCE(SUM(amount),0) p FROM points WHERE user_id=?',(uid,),one=True);return r['p']
def refresh_rank(uid):
    r=q('SELECT id FROM social_ranks WHERE min_points<=? ORDER BY min_points DESC LIMIT 1',(points(uid),),one=True)
    if r:x('UPDATE users SET social_rank_id=? WHERE id=?',(r['id'],uid))
def award(uid,amount,reason,obj_type=None,obj_id=None):
    x('INSERT INTO points(user_id,amount,reason,object_type,object_id) VALUES(?,?,?,?,?)',(uid,amount,reason,obj_type,obj_id));refresh_rank(uid);notify(uid,'Puntos obtenidos',f'+{amount} · {reason}','points','/profile')
def badge(uid,name):
    b=q('SELECT id FROM badges WHERE name=?',(name,),one=True)
    if b and not q('SELECT 1 FROM user_badges WHERE user_id=? AND badge_id=?',(uid,b['id']),one=True):
        x('INSERT INTO user_badges(user_id,badge_id) VALUES(?,?)',(uid,b['id']));notify(uid,'Nueva insignia',name,'badge','/profile')
