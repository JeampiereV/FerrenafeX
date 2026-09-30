from flask import Blueprint,request,jsonify,session,render_template
from database import q,x
from services.notification_service import notify
from services.audit_service import log
from extensions import socketio
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
    uid=auth(); member=q("SELECT COALESCE(rm.member_role,'guest') member_role,r.name,r.visibility,r.owner_id FROM rooms r LEFT JOIN room_members rm ON rm.room_id=r.id AND rm.user_id=? WHERE r.id=? AND r.status='active' AND (r.visibility='public' OR rm.user_id IS NOT NULL OR EXISTS(SELECT 1 FROM users ou JOIN roles orole ON orole.id=ou.role_id WHERE ou.id=? AND orole.name='OWNER'))",(uid,rid,uid),one=True)
    if not member:return render_template('403.html'),403
    return render_template('room.html',room_id=rid,room_name=member['name'],member_role=member['member_role'] or 'guest',room_visibility=member['visibility'])
@bp.get('/chat/<int:user_id>')
def chat(user_id):
    uid=auth()
    if not uid or (not is_friend(uid,user_id) and not _owner(uid)):return render_template('403.html'),403
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
@bp.get('/api/forum/<int:fid>/comments')
def forum_comments(fid):
    if not q("SELECT id FROM forums WHERE id=? AND status='active'",(fid,),one=True): return jsonify(ok=False,message='Tema no encontrado.'),404
    return jsonify(ok=True,comments=[dict(r) for r in q("SELECT c.*,u.username,u.names,u.last_names,u.dni FROM forum_comments c JOIN users u ON u.id=c.user_id WHERE c.forum_id=? AND c.status='active' ORDER BY c.created_at",(fid,))])

@bp.post('/api/forum/<int:fid>/comments')
def forum_comment(fid):
    uid=auth(); d=request.get_json() or {}; content=str(d.get('content','')).strip()[:2000]
    if not content:return jsonify(ok=False,message='Escribe una respuesta.'),400
    f=q("SELECT * FROM forums WHERE id=? AND status='active'",(fid,),one=True)
    if not f:return jsonify(ok=False,message='Tema no encontrado.'),404
    cid=x('INSERT INTO forum_comments(forum_id,user_id,content) VALUES(?,?,?)',(fid,uid,content))
    notify(f['user_id'],'Nueva respuesta en tu foro','Alguien respondió a tu tema.','forum','/forum')
    return jsonify(ok=True,id=cid,message='Respuesta publicada.')

@bp.delete('/api/forum/<int:fid>')
def forum_delete(fid):
 uid=auth(); f=q('SELECT * FROM forums WHERE id=?',(fid,),one=True)
 if not uid or not f:return jsonify(ok=False,message='Tema no encontrado.'),404
 owner=is_owner(uid)
 if f['user_id']!=uid and not owner:return jsonify(ok=False,message='No tienes permiso para eliminar este tema.'),403
 x("UPDATE forums SET status='deleted' WHERE id=?",(fid,)); return jsonify(ok=True,message='Tema eliminado.')

@bp.post('/api/friends/request')
def friend_request():
    uid=auth();d=request.get_json() or {};target_value=str(d.get('user_id','')).strip()
    target=q("SELECT id FROM users WHERE (id=? OR dni=?) AND status='approved'",(target_value,target_value),one=True)
    target=target['id'] if target else 0
    if not uid or target==uid:return jsonify(ok=False,message='Solicitud inválida.'),400
    if not target:return jsonify(ok=False,message='Usuario no encontrado. Usa su ID visible.'),404
    if is_friend(uid,target):return jsonify(ok=False,message='Ya son amigos.'),400
    x('INSERT OR REPLACE INTO friend_requests(sender_id,receiver_id,status) VALUES(?,?,\'pending\')',(uid,target));notify(target,'Solicitud de amistad','Tienes una nueva solicitud.','friend','/friends');return jsonify(ok=True,message='Solicitud enviada.')
@bp.get('/api/friends')
def friends_api():
    uid=auth()
    return jsonify(ok=True,friends=[dict(r) for r in q('SELECT u.id,u.dni,u.username,u.names,u.last_names,sr.name social_rank_name FROM friends f JOIN users u ON u.id=f.friend_id LEFT JOIN social_ranks sr ON sr.id=u.social_rank_id WHERE f.user_id=?',(uid,))],received=[dict(r) for r in q('SELECT fr.id,fr.sender_id,u.username,u.names,u.last_names FROM friend_requests fr JOIN users u ON u.id=fr.sender_id WHERE fr.receiver_id=? AND fr.status=\'pending\'',(uid,))],sent=[dict(r) for r in q('SELECT fr.id,fr.receiver_id,u.username,u.names,u.last_names FROM friend_requests fr JOIN users u ON u.id=fr.receiver_id WHERE fr.sender_id=? AND fr.status=\'pending\'',(uid,))])
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
    if not uid or (not is_friend(uid,user_id) and not _owner(uid)):return jsonify(ok=False,message='Solo puedes conversar con amigos.'),403
    rows=q('SELECT m.*,u.username sender_username FROM private_messages m JOIN users u ON u.id=m.sender_id WHERE (m.sender_id=? AND m.receiver_id=?) OR (m.sender_id=? AND m.receiver_id=?) ORDER BY m.created_at',(uid,user_id,user_id,uid))
    x('UPDATE private_messages SET read_at=CURRENT_TIMESTAMP WHERE sender_id=? AND receiver_id=? AND read_at IS NULL',(user_id,uid))
    return jsonify(ok=True,messages=[dict(r) for r in rows])
@bp.post('/api/chat/<int:user_id>')
def chat_send(user_id):
    uid=auth();d=request.get_json() or {};c=str(d.get('content','')).strip()
    if not uid or not is_friend(uid,user_id):return jsonify(ok=False,message='Solo puedes enviar mensajes a tus amigos.'),403
    if not c:return jsonify(ok=False,message='Mensaje vacío.'),400
    mid=x('INSERT INTO private_messages(sender_id,receiver_id,content) VALUES(?,?,?)',(uid,user_id,c[:4000]))
    message=q('SELECT m.*,u.username sender_username FROM private_messages m JOIN users u ON u.id=m.sender_id WHERE m.id=?',(mid,),one=True)
    payload=dict(message)
    socketio.emit('private_message', payload, room=f'user:{user_id}')
    socketio.emit('private_message', payload, room=f'user:{uid}')
    notify(user_id,'Nuevo mensaje', 'Tienes un nuevo mensaje privado.','chat',f'/chat/{uid}')
    return jsonify(ok=True,id=mid,message='Mensaje enviado.',message_data=payload)


def _owner(uid):
    return bool(uid and q("SELECT 1 FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=? AND r.name='OWNER'", (uid,), one=True))


@bp.post('/api/chat/<int:user_id>/delete-all')
def chat_delete_all(user_id):
    uid=auth()
    if not _owner(uid):
        return jsonify(ok=False,message='Solo el Owner puede eliminar un chat completo.'),403
    if not q("SELECT id FROM users WHERE id=?",(user_id,),one=True):
        return jsonify(ok=False,message='Usuario no encontrado.'),404
    x("DELETE FROM private_messages WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)",(uid,user_id,user_id,uid))
    log(uid,'chat.deleted_all','chat',user_id,{'participants':[uid,user_id]})
    return jsonify(ok=True,message='Todo el chat fue eliminado.')


@bp.post('/api/chat/<int:user_id>/delete-latest')
def chat_delete_latest(user_id):
    uid=auth(); d=request.get_json() or {}
    if not _owner(uid):
        return jsonify(ok=False,message='Solo el Owner puede eliminar mensajes.'),403
    try:
        amount=int(d.get('amount',1))
    except (TypeError,ValueError):
        amount=0
    amount=max(1,min(200,amount))
    ids=q("""SELECT id FROM private_messages
           WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)
           ORDER BY id DESC LIMIT ?""",(uid,user_id,user_id,uid,amount))
    if not ids:
        return jsonify(ok=False,message='No hay mensajes para eliminar.'),404
    x('DELETE FROM private_messages WHERE id IN (%s)' % ','.join('?'*len(ids)), tuple(r['id'] for r in ids))
    log(uid,'chat.deleted_latest','chat',user_id,{'count':len(ids),'participants':[uid,user_id]})
    return jsonify(ok=True,message=f'Se eliminaron los últimos {len(ids)} mensajes.')
@bp.post('/api/rooms')
def room_create():
 uid=auth();d=request.get_json() or {};name=str(d.get('name','Nueva sala')).strip()[:80]
 if not uid:return jsonify(ok=False,message='No autenticado.'),401
 if not name:return jsonify(ok=False,message='Nombre requerido.'),400
 visibility='public' if str(d.get('visibility','private')).lower()=='public' else 'private'
 minutes=d.get('duration_minutes');
 try: minutes=int(minutes) if minutes is not None else 0
 except: minutes=0
 if minutes not in (5,30,60,120,1440): minutes=0
 rid=x("INSERT INTO rooms(name,owner_id,visibility,expires_at) VALUES(?,?,?,CASE WHEN ?=0 THEN NULL ELSE datetime('now', ? || ' minutes') END)",(name,uid,visibility,minutes,str(minutes)));x('INSERT INTO room_members(room_id,user_id,member_role) VALUES(?,?,?)',(rid,uid,'owner'));log(uid,'room.created','room',rid,{'name':name});return jsonify(ok=True,id=rid,message='Sala creada.')

def is_owner(uid): return bool(q("SELECT 1 FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=? AND r.name='OWNER'",(uid,),one=True))
def room_access(uid,rid,write=False):
 x("UPDATE rooms SET status='closed' WHERE id=? AND status='active' AND expires_at IS NOT NULL AND expires_at<=CURRENT_TIMESTAMP",(rid,))
 r=q("SELECT * FROM rooms WHERE id=? AND status='active'",(rid,),one=True)
 if not r:return None,None
 mem=q('SELECT * FROM room_members WHERE room_id=? AND user_id=?',(rid,uid),one=True)
 if is_owner(uid):return r,mem
 if r['visibility']=='public' or mem:return r,mem
 return r,None

@bp.get('/api/rooms')
def room_list():
 uid=auth(); owner=is_owner(uid)
 x("UPDATE rooms SET status='closed' WHERE expires_at IS NOT NULL AND expires_at<=CURRENT_TIMESTAMP AND status='active'")
 rows=q("SELECT r.*,COALESCE(rm.member_role,'guest') member_role,(SELECT COUNT(*) FROM room_members mm WHERE mm.room_id=r.id) member_count FROM rooms r LEFT JOIN room_members rm ON rm.room_id=r.id AND rm.user_id=? WHERE r.status='active' AND (?=1 OR r.visibility='public' OR rm.user_id IS NOT NULL) ORDER BY r.created_at DESC",(uid,1 if owner else 0))
 return jsonify(ok=True,rooms=[dict(r) for r in rows])

@bp.get('/api/rooms/<int:rid>/members')
def room_members(rid):
 uid=auth();r,mem=room_access(uid,rid)
 if not r or (not mem and not is_owner(uid) and r['visibility']!='public'):return jsonify(ok=False,message='No tienes acceso a esta sala.'),403
 return jsonify(ok=True,members=[dict(m) for m in q('SELECT rm.user_id,rm.member_role,u.username,u.names,u.last_names,u.dni,u.profile_photo FROM room_members rm JOIN users u ON u.id=rm.user_id WHERE rm.room_id=? ORDER BY rm.member_role DESC,u.names',(rid,))])

@bp.get('/api/room-users')
def room_users():
 uid=auth()
 if not uid:return jsonify(ok=False,message='No autenticado.'),401
 return jsonify(ok=True,users=[dict(u) for u in q("SELECT id,dni,username,names,last_names,profile_photo FROM users WHERE status='approved' AND id<>? ORDER BY names,last_names",(uid,))])

@bp.get('/api/rooms/<int:rid>/messages')
def room_messages(rid):
 uid=auth();r,mem=room_access(uid,rid)
 if not r or (not mem and not is_owner(uid) and r['visibility']!='public'):return jsonify(ok=False,message='No tienes acceso a esta sala.'),403
 rows=q('SELECT m.*,u.username,u.names,u.last_names,u.dni FROM room_messages m JOIN users u ON u.id=m.sender_id WHERE m.room_id=? ORDER BY m.created_at',(rid,))
 return jsonify(ok=True,messages=[dict(m) for m in rows])

@bp.post('/api/rooms/<int:rid>/messages')
def room_message(rid):
 uid=auth();r,mem=room_access(uid,rid);d=request.get_json() or {};msg=str(d.get('message','')).strip()[:4000]
 if not r or (not mem and not is_owner(uid) and r['visibility']!='public'):return jsonify(ok=False,message='No tienes acceso a esta sala.'),403
 if not msg:return jsonify(ok=False,message='Escribe un mensaje.'),400
 mid=x('INSERT INTO room_messages(room_id,sender_id,message) VALUES(?,?,?)',(rid,uid,msg))
 message=q('SELECT m.*,u.username,u.names,u.last_names,u.dni FROM room_messages m JOIN users u ON u.id=m.sender_id WHERE m.id=?',(mid,),one=True)
 payload=dict(message)
 socketio.emit('room_message', payload, room=f'room:{rid}')
 for m in q('SELECT user_id FROM room_members WHERE room_id=? AND user_id<>?',(rid,uid,)):notify(m['user_id'],'Nuevo mensaje en sala',f'Hay un nuevo mensaje en {r["name"]}.','room',f'/rooms/{rid}')
 return jsonify(ok=True,id=mid,message='Mensaje enviado.',message_data=payload)

@bp.post('/api/rooms/<int:rid>/members')
def room_add_member(rid):
 uid=auth();r,mem=room_access(uid,rid);d=request.get_json() or {};target=int(d.get('user_id',0))
 if not r or not mem or mem['member_role'] not in ('owner','admin') and not is_owner(uid):return jsonify(ok=False,message='Solo el creador o un administrador puede agregar miembros.'),403
 if not q("SELECT id FROM users WHERE id=? AND status='approved'",(target,),one=True):return jsonify(ok=False,message='Usuario no encontrado.'),404
 x('INSERT OR IGNORE INTO room_members(room_id,user_id,member_role) VALUES(?,?,\'member\')',(rid,target));notify(target,'Invitación a sala',f'Has sido invitado a {r["name"]}.','room',f'/rooms/{rid}');return jsonify(ok=True,message='Miembro agregado.')

@bp.delete('/api/rooms/<int:rid>/members/<int:target>')
def room_remove_member(rid,target):
 uid=auth();r,mem=room_access(uid,rid)
 if not r or (not is_owner(uid) and (not mem or mem['member_role'] not in ('owner','admin'))):return jsonify(ok=False,message='No tienes permisos.'),403
 target_mem=q('SELECT * FROM room_members WHERE room_id=? AND user_id=?',(rid,target),one=True)
 if not target_mem or target_mem['member_role']=='owner':return jsonify(ok=False,message='No puedes retirar a este miembro.'),400
 x('DELETE FROM room_members WHERE room_id=? AND user_id=?',(rid,target));return jsonify(ok=True,message='Miembro retirado.')

@bp.post('/api/rooms/<int:rid>/visibility')
def room_visibility(rid):
 uid=auth();r,mem=room_access(uid,rid);vis=str((request.get_json() or {}).get('visibility','private')).lower()
 if not r or (not is_owner(uid) and (not mem or mem['member_role'] not in ('owner','admin'))):return jsonify(ok=False,message='Solo el creador o Owner puede cambiar la visibilidad.'),403
 if vis not in ('public','private'):return jsonify(ok=False,message='Visibilidad inválida.'),400
 x('UPDATE rooms SET visibility=? WHERE id=?',(vis,rid));return jsonify(ok=True,message=f'La sala ahora es {vis}.')

@bp.post('/api/rooms/<int:rid>/close')
def room_close(rid):
 uid=auth(); r,mem=room_access(uid,rid)
 if not r:return jsonify(ok=False,message='Sala no encontrada.'),404
 if not is_owner(uid) and (not mem or mem['member_role']!='owner'):return jsonify(ok=False,message='Solo el creador o Owner puede cerrar la sala.'),403
 x("UPDATE rooms SET status='closed' WHERE id=?",(rid,)); log(uid,'room.closed','room',rid); return jsonify(ok=True,message='Sala cerrada.')

@bp.delete('/api/rooms/<int:rid>')
def room_delete(rid):
 uid=auth();r,mem=room_access(uid,rid)
 if not r or (not is_owner(uid) and (not mem or mem['member_role']!='owner')):return jsonify(ok=False,message='Solo el creador o Owner puede eliminar la sala.'),403
 x("UPDATE rooms SET status='deleted' WHERE id=?",(rid,));log(uid,'room.deleted','room',rid);return jsonify(ok=True,message='Sala eliminada.')

@bp.get('/api/notifications')
def notifications():
    uid=auth();return jsonify(ok=True,notifications=[dict(r) for r in q('SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC',(uid,))],unread=q('SELECT COUNT(*) c FROM notifications WHERE user_id=? AND read_at IS NULL',(uid,),one=True)['c'])
@bp.post('/api/notifications/read')
def read_notifications():
    uid=auth();d=request.get_json() or {};x('UPDATE notifications SET read_at=CURRENT_TIMESTAMP WHERE user_id=?'+(' AND id=?' if d.get('id') else ''),(uid,d['id']) if d.get('id') else (uid,));return jsonify(ok=True)
