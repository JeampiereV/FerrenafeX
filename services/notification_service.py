from database import x
def notify(uid,title,message,typ='system',link=None):return x('INSERT INTO notifications(user_id,type,title,message,link) VALUES(?,?,?,?,?)',(uid,typ,title,message,link))
