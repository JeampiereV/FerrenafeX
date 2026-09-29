from flask import Blueprint,request,jsonify,session,render_template
from database import q,x
from services.notification_service import notify
from services.audit_service import log
import uuid
bp=Blueprint('tickets',__name__)

def can_manage(uid):
 return bool(q("SELECT 1 FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=? AND r.name='OWNER'",(uid,),one=True))

@bp.get('/tickets')
def page(): return render_template('tickets.html')

@bp.post('/api/tickets')
def create():
 uid=session.get('user_id');d=request.get_json() or {}
 if not uid:return jsonify(ok=False,message='No autenticado.'),401
 subject=str(d.get('subject','')).strip()[:180];message=str(d.get('message','')).strip()[:4000];priority=d.get('priority','normal')
 if not subject or not message:return jsonify(ok=False,message='Completa asunto y mensaje.'),400
 public='TKT-'+uuid.uuid4().hex[:8].upper()
 tid=x('INSERT INTO support_tickets(public_id,user_id,subject,category,message,priority) VALUES(?,?,?,?,?,?)',(public,uid,subject,d.get('category','Otro'),message,priority))
 x('INSERT INTO ticket_messages(ticket_id,sender_id,message) VALUES(?,?,?)',(tid,uid,message));log(uid,'ticket.created','ticket',tid,{'public_id':public})
 return jsonify(ok=True,id=tid,message=f'Ticket {public} creado.')

@bp.get('/api/tickets')
def list_():
 uid=session.get('user_id')
 if not uid:return jsonify(ok=False,message='No autenticado.'),401
 if can_manage(uid): rows=q("SELECT t.*,u.username,u.names,u.last_names,u.dni FROM support_tickets t JOIN users u ON u.id=t.user_id ORDER BY t.updated_at DESC")
 else: rows=q("SELECT t.*,u.username,u.names,u.last_names,u.dni FROM support_tickets t JOIN users u ON u.id=t.user_id WHERE t.user_id=? AND t.status NOT IN ('closed','resolved') ORDER BY t.updated_at DESC",(uid,))
 return jsonify(ok=True,tickets=[dict(r) for r in rows])

@bp.get('/api/tickets/<int:tid>')
def detail(tid):
 uid=session.get('user_id');t=q('SELECT t.*,u.username,u.names,u.last_names,u.dni FROM support_tickets t JOIN users u ON u.id=t.user_id WHERE t.id=?',(tid,),one=True)
 if not t:return jsonify(ok=False,message='Ticket no encontrado.'),404
 if t['user_id']!=uid and not can_manage(uid):return jsonify(ok=False,message='No tienes acceso a este canal privado.'),403
 msgs=q('SELECT tm.*,u.username,u.names,u.last_names,u.dni FROM ticket_messages tm JOIN users u ON u.id=tm.sender_id WHERE tm.ticket_id=? ORDER BY tm.created_at',(tid,))
 return jsonify(ok=True,ticket=dict(t),messages=[dict(m) for m in msgs])

@bp.post('/api/tickets/<int:tid>/message')
def msg(tid):
 uid=session.get('user_id');t=q('SELECT * FROM support_tickets WHERE id=?',(tid,),one=True);text=str((request.get_json() or {}).get('message','')).strip()[:4000]
 if not t:return jsonify(ok=False,message='Ticket no encontrado.'),404
 if t['user_id']!=uid and not can_manage(uid):return jsonify(ok=False,message='No tienes acceso a este ticket.'),403
 if t['status'] in ('closed','resolved'):return jsonify(ok=False,message='El ticket está cerrado.'),400
 if not text:return jsonify(ok=False,message='Escribe un mensaje.'),400
 x('INSERT INTO ticket_messages(ticket_id,sender_id,message) VALUES(?,?,?)',(tid,uid,text));x('UPDATE support_tickets SET updated_at=CURRENT_TIMESTAMP WHERE id=?',(tid,))
 if t['user_id']!=uid:notify(t['user_id'],'Tu ticket tiene una respuesta','Soporte respondió a tu ticket.','ticket','/tickets')
 return jsonify(ok=True,message='Mensaje enviado.')

@bp.post('/api/tickets/<int:tid>/status')
def status(tid):
 uid=session.get('user_id');d=request.get_json() or {};st=d.get('status')
 t=q('SELECT * FROM support_tickets WHERE id=?',(tid,),one=True)
 if not t:return jsonify(ok=False,message='Ticket no encontrado.'),404
 if not can_manage(uid):return jsonify(ok=False,message='Solo soporte autorizado puede cerrar tickets.'),403
 if st not in ('open','resolved','closed'):return jsonify(ok=False,message='Estado inválido.'),400
 x('UPDATE support_tickets SET status=?,assigned_to=COALESCE(assigned_to,?),updated_at=CURRENT_TIMESTAMP WHERE id=?',(st,uid,tid));log(uid,'ticket.status','ticket',tid,{'status':st});notify(t['user_id'],'Estado de ticket actualizado',f'El ticket {t["public_id"]} ahora está {st}.','ticket','/tickets')
 return jsonify(ok=True,message='Estado actualizado.')

@bp.delete('/api/tickets/<int:tid>')
def delete_ticket(tid):
 uid=session.get('user_id'); t=q('SELECT * FROM support_tickets WHERE id=?',(tid,),one=True)
 if not t:return jsonify(ok=False,message='Ticket no encontrado.'),404
 if not can_manage(uid):return jsonify(ok=False,message='Solo el Owner puede eliminar tickets.'),403
 x('DELETE FROM ticket_messages WHERE ticket_id=?',(tid,)); x('DELETE FROM support_tickets WHERE id=?',(tid,)); log(uid,'ticket.deleted','ticket',tid); return jsonify(ok=True,message='Ticket eliminado.')

@bp.post('/api/tickets/<int:tid>/command')
def command_removed(tid):
 return jsonify(ok=False,message='Los comandos de tickets fueron retirados. Usa el botón Cerrar ticket.') ,410
