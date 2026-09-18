from flask import Blueprint,request,jsonify,session,render_template
from database import q,x
from services.notification_service import notify
from services.audit_service import log
bp=Blueprint('community',__name__)

def auth(): return session.get('user_id')
def is_friend(a,b):
    return bool(q('SELECT id FROM friends WHERE user_id=? AND friend_id=?',(a,b),one=True))
@bp.get('/local')
def local():return render_template('local.html')
@bp.get('/forum')
def forum():return render_template('forum.html')
@bp.get('/friends')
def friends():return render_template('friends.html')
@bp.get('/rooms')
def rooms():return render_template('rooms.html')
@bp.get('/rooms/<int:rid>')
def room_page(rid):
    uid=auth(); member=q('SELECT rm.member_role,r.name FROM room_members rm JOIN rooms r ON r.id=rm.room_id WHERE rm.room_id=? AND rm.user_id=? AND r.status=\'active\'',(rid,uid),one=True)
    if not member:return render_template('403.html'),403
    return render_template('room.html',room_id=rid,room_name=member['name'],member_role=member['member_role'])
@bp.get('/chat/<int:user_id>')
def chat(user_id):
    uid=auth()
    if not uid or not is_friend(uid,user_id):return render_template('403.html'),403
    target=q('SELECT id,username,names,last_names FROM users WHERE id=? AND status=\'approved\'',(user_id,),one=True)
    if not target:return render_template('404.html'),404
    return render_template('chat.html',target=target)
@bp.get('/notifications')
def notif_page():return render_template('notifications.html')
@bp.post('/api/posts')
def post():
    uid=auth();d=request.get_json() or {};c=str(d.get('content','')).strip()
    if not uid:return jsonify(ok=False,message='No autenticado.'),401
    if not c:return jsonify(ok=False,message='Escribe algo.'),400
    return jsonify(ok=True,id=x('INSERT INTO posts(user_id,content) VALUES(?,?)',(uid,c[:4000])),message='Publicado.')
@bp.get('/api/posts')
def posts():return jsonify(ok=True,posts=[dict(r) for r in q("SELECT p.*,u.username,u.names,u.last_names,sr.name social_rank_name FROM posts p JOIN users u ON u.id=p.user_id LEFT JOIN social_ranks sr ON sr.id=u.social_rank_id WHERE p.status='active' ORDER BY p.created_at DESC")])
@bp.post('/api/posts/<int:pid>/comment')
def comment(pid):
    uid=auth();d=request.get_json() or {};c=str(d.get('content','')).strip()
    if not uid:return jsonify(ok=False,message='No autenticado.'),401
    if not q("SELECT id FROM posts WHERE id=? AND status='active'",(pid,),one=True):return jsonify(ok=False,message='Publicación no encontrada.'),404
    if not c:return jsonify(ok=False,message='Escribe un comentario.'),400
    cid=x('INSERT INTO comments(post_id,user_id,content) VALUES(?,?,?)',(pid,uid,c[:2000]));return jsonify(ok=True,id=cid,message='Comentario añadido.')
@bp.get('/api/posts/<int:pid>/comments')
def comments(pid):return jsonify(ok=True,comments=[dict(r) for r in q('SELECT c.*,u.username,u.names,u.last_names FROM comments c JOIN users u ON u.id=c.user_id WHERE c.post_id=? AND c.status=\'active\' ORDER BY c.created_at',(pid,))])
@bp.post('/api/forum')
def forum_post():
    uid=auth();d=request.get_json() or {}
    if not uid:return jsonify(ok=False,message='No autenticado.'),401
    fid=x('INSERT INTO forums(category,title,content,user_id) VALUES(?,?,?,?)',(d.get('category','Comunidad'),str(d.get('title','Tema'))[:160],str(d.get('content',''))[:5000],uid));return jsonify(ok=True,id=fid,message='Tema creado.')
@bp.get('/api/forum')
def forum_list():return jsonify(ok=True,forums=[dict(r) for r in q("SELECT f.*,u.username,u.names,u.last_names FROM forums f JOIN users u ON u.id=f.user_id WHERE f.status='active' ORDER BY f.created_at DESC")])
@bp.post('/api/friends/request')
def friend_request():
    uid=auth();d=request.get_json() or {};target=int(d.get('user_id',0))
    if not uid or target==uid:return jsonify(ok=False,message='Solicitud inválida.'),400
    if not q("SELECT id FROM users WHERE id=? AND status='approved'",(target,),one=True):return jsonify(ok=False,message='Usuario no encontrado.'),404
    if is_friend(uid,target):return jsonify(ok=False,message='Ya son amigos.'),400
    x('INSERT OR REPLACE INTO friend_requests(sender_id,receiver_id,status) VALUES(?,?,\'pending\')',(uid,target));notify(target,'Solicitud de amistad','Tienes una nueva solicitud.','friend','/friends');return jsonify(ok=True,message='Solicitud enviada.')
@bp.get('/api/friends')
def friends_api():
    uid=auth()
    return jsonify(ok=True,friends=[dict(r) for r in q('SELECT u.id,u.username,u.names,u.last_names,sr.name social_rank_name FROM friends f JOIN users u ON u.id=f.friend_id LEFT JOIN social_ranks sr ON sr.id=u.social_rank_id WHERE f.user_id=?',(uid,))],received=[dict(r) for r in q('SELECT fr.id,fr.sender_id,u.username,u.names,u.last_names FROM friend_requests fr JOIN users u ON u.id=fr.sender_id WHERE fr.receiver_id=? AND fr.status=\'pending\'',(uid,))],sent=[dict(r) for r in q('SELECT fr.id,fr.receiver_id,u.username,u.names,u.last_names FROM friend_requests fr JOIN users u ON u.id=fr.receiver_id WHERE fr.sender_id=? AND fr.status=\'pending\'',(uid,))])
@bp.post('/api/friends/<int:req_id>/accept')
def friend_accept(req_id):
    uid=auth();r=q('SELECT * FROM friend_requests WHERE id=? AND receiver_id=? AND status=\'pending\'',(req_id,uid),one=True)
    if not r:return jsonify(ok=False,message='Solicitud no encontrada.'),404
    x("UPDATE friend_requests SET status='accepted' WHERE id=?",(req_id,));x('INSERT OR IGNORE INTO friends(user_id,friend_id) VALUES(?,?),(?,?)',(uid,r['sender_id'],r['sender_id'],uid));notify(r['sender_id'],'Solicitud aceptada', 'Ahora son amigos.','friend','/friends');return jsonify(ok=True,message='Solicitud aceptada.')
@bp.post('/api/friends/<int:req_id>/reject')
def friend_reject(req_id):
    uid=auth();r=q('SELECT * FROM friend_requests WHERE id=? AND receiver_id=? AND status=\'pending\'',(req_id,uid),one=True)
    if not r:return jsonify(ok=False,message='Solicitud no encontrada.'),404
    x("UPDATE friend_requests SET status='rejected' WHERE id=?",(req_id,));return jsonify(ok=True,message='Solicitud rechazada.')
@bp.post('/api/friends/remove')
def friend_remove():
    uid=auth();d=request.get_json() or {};fid=int(d.get('friend_id',0));x('DELETE FROM friends WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)',(uid,fid,fid,uid));return jsonify(ok=True,message='Amistad eliminada.')
@bp.get('/api/chat/<int:user_id>')
def chat_list(user_id):
    uid=auth()
    if not uid or not is_friend(uid,user_id):return jsonify(ok=False,message='Solo puedes conversar con amigos.'),403
    rows=q('SELECT m.*,u.username sender_username FROM private_messages m JOIN users u ON u.id=m.sender_id WHERE (m.sender_id=? AND m.receiver_id=?) OR (m.sender_id=? AND m.receiver_id=?) ORDER BY m.created_at',(uid,user_id,user_id,uid))
    x('UPDATE private_messages SET read_at=CURRENT_TIMESTAMP WHERE sender_id=? AND receiver_id=? AND read_at IS NULL',(user_id,uid))
    return jsonify(ok=True,messages=[dict(r) for r in rows])
@bp.post('/api/chat/<int:user_id>')
def chat_send(user_id):
    uid=auth();d=request.get_json() or {};c=str(d.get('content','')).strip()
    if not uid or not is_friend(uid,user_id):return jsonify(ok=False,message='Solo puedes conversar con amigos.'),403
    if not c:return jsonify(ok=False,message='Mensaje vacío.'),400
    mid=x('INSERT INTO private_messages(sender_id,receiver_id,content) VALUES(?,?,?)',(uid,user_id,c[:4000]));notify(user_id,'Nuevo mensaje', 'Tienes un nuevo mensaje privado.','chat',f'/chat/{uid}');return jsonify(ok=True,id=mid,message='Mensaje enviado.')
@bp.post('/api/rooms')
def room_create():
    uid=auth();d=request.get_json() or {};name=str(d.get('name','Nueva sala')).strip()[:80]
    if not uid:return jsonify(ok=False,message='No autenticado.'),401
    if not name:return jsonify(ok=False,message='Nombre requerido.'),400
    rid=x('INSERT INTO rooms(name,owner_id) VALUES(?,?)',(name,uid));x('INSERT INTO room_members(room_id,user_id,member_role) VALUES(?,?,?)',(rid,uid,'owner'));log(uid,'room.created','room',rid,{'name':name});return jsonify(ok=True,id=rid,message='Sala creada.')
@bp.get('/api/rooms')
def room_list():
    uid=auth();return jsonify(ok=True,rooms=[dict(r) for r in q('SELECT r.*,rm.member_role FROM rooms r JOIN room_members rm ON rm.room_id=r.id WHERE rm.user_id=? AND r.status=\'active\'',(uid,))])
@bp.get('/api/rooms/<int:rid>/members')
def room_members(rid):
    uid=auth()
    if not q('SELECT 1 FROM room_members WHERE room_id=? AND user_id=?',(rid,uid),one=True):return jsonify(ok=False,message='No eres miembro de esta sala.'),403
    return jsonify(ok=True,members=[dict(r) for r in q('SELECT rm.user_id,rm.member_role,u.username,u.names,u.last_names FROM room_members rm JOIN users u ON u.id=rm.user_id WHERE rm.room_id=?',(rid,))])
@bp.post('/api/rooms/<int:rid>/command')
def room_command(rid):
    uid=auth();d=request.get_json() or {};cmd=str(d.get('command',''));qroom=q('SELECT * FROM rooms WHERE id=? AND status=\'active\'',(rid,),one=True);mem=q('SELECT * FROM room_members WHERE room_id=? AND user_id=?',(rid,uid),one=True)
    if not qroom or not mem:return jsonify(ok=False,message='No perteneces a esta sala.'),403
    from services.command_service import run
    result=run(uid,cmd,room=rid,context='room')
    return jsonify(result)
@bp.get('/api/notifications')
def notifications():
    uid=auth();return jsonify(ok=True,notifications=[dict(r) for r in q('SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC',(uid,))],unread=q('SELECT COUNT(*) c FROM notifications WHERE user_id=? AND read_at IS NULL',(uid,),one=True)['c'])
@bp.post('/api/notifications/read')
def read_notifications():
    uid=auth();d=request.get_json() or {};x('UPDATE notifications SET read_at=CURRENT_TIMESTAMP WHERE user_id=?'+(' AND id=?' if d.get('id') else ''),(uid,d['id']) if d.get('id') else (uid,));return jsonify(ok=True)
