from flask import Blueprint,request,jsonify,session,render_template
from database import q,x
from services.permission_service import require_permission,has_permission
from services.audit_service import log
from services.notification_service import notify
import uuid
bp=Blueprint('tickets',__name__)

@bp.get('/tickets')
def page():return render_template('tickets.html')

@bp.post('/api/tickets')
def create():
    uid=session.get('user_id');d=request.get_json() or {}
    if not uid:return jsonify(ok=False,message='No autenticado.'),401
    subject=str(d.get('subject','')).strip()[:160];message=str(d.get('message','')).strip()[:4000]
    if not subject or not message:return jsonify(ok=False,message='Asunto y mensaje son obligatorios.'),400
    priority=d.get('priority','normal') if d.get('priority') in ('normal','high') else 'normal'
    public='TKT-'+uuid.uuid4().hex[:10].upper()
    tid=x('INSERT INTO support_tickets(public_id,user_id,subject,category,message,priority) VALUES(?,?,?,?,?,?)',(public,uid,subject,d.get('category','Otro'),message,priority))
    x('INSERT INTO ticket_messages(ticket_id,sender_id,message) VALUES(?,?,?)',(tid,uid,message))
    log(uid,'ticket.created','ticket',tid,{'public_id':public})
    return jsonify(ok=True,message=f'Ticket {public} creado.',id=tid)

@bp.get('/api/tickets')
def list_():
    uid=session.get('user_id')
    if not uid:return jsonify(ok=False,message='No autenticado.'),401
    manage=has_permission(uid,'support.manage')
    if manage:
        rows=q('SELECT t.*,u.username FROM support_tickets t JOIN users u ON u.id=t.user_id ORDER BY t.updated_at DESC')
    else:
        rows=q('SELECT t.*,u.username FROM support_tickets t JOIN users u ON u.id=t.user_id WHERE t.user_id=? ORDER BY t.updated_at DESC',(uid,))
    return jsonify(ok=True,tickets=[dict(r) for r in rows])

@bp.get('/api/tickets/<int:tid>')
def detail(tid):
    uid=session.get('user_id');t=q('SELECT t.*,u.username FROM support_tickets t JOIN users u ON u.id=t.user_id WHERE t.id=?',(tid,),one=True)
    if not t:return jsonify(ok=False,message='Ticket no encontrado.'),404
    if t['user_id']!=uid and not has_permission(uid,'support.manage'):return jsonify(ok=False,message='No permitido.'),403
    msgs=q('SELECT tm.*,u.username FROM ticket_messages tm JOIN users u ON u.id=tm.sender_id WHERE tm.ticket_id=? ORDER BY tm.created_at',(tid,))
    return jsonify(ok=True,ticket=dict(t),messages=[dict(m) for m in msgs])

@bp.post('/api/tickets/<int:tid>/message')
def msg(tid):
    uid=session.get('user_id');d=request.get_json() or {};text=str(d.get('message','')).strip()[:4000]
    t=q('SELECT * FROM support_tickets WHERE id=?',(tid,),one=True)
    if not t or (t['user_id']!=uid and not has_permission(uid,'support.manage')):return jsonify(ok=False,message='No permitido.'),403
    if not text:return jsonify(ok=False,message='Escribe una respuesta.'),400
    x('INSERT INTO ticket_messages(ticket_id,sender_id,message) VALUES(?,?,?)',(tid,uid,text));x('UPDATE support_tickets SET updated_at=CURRENT_TIMESTAMP WHERE id=?',(tid,))
    if t['user_id']!=uid:notify(t['user_id'],'Tu ticket tiene una respuesta','Soporte respondió a tu ticket.','ticket','/tickets')
    return jsonify(ok=True,message='Respuesta enviada.')

@bp.post('/api/tickets/<int:tid>/status')
@require_permission('support.manage')
def status(tid):
    st=(request.get_json() or {}).get('status','open')
    if st not in ('open','pending','in_progress','resolved','closed'):return jsonify(ok=False,message='Estado inválido.'),400
    t=q('SELECT * FROM support_tickets WHERE id=?',(tid,),one=True)
    if not t:return jsonify(ok=False,message='Ticket no encontrado.'),404
    x('UPDATE support_tickets SET status=?,assigned_to=COALESCE(assigned_to,?),updated_at=CURRENT_TIMESTAMP WHERE id=?',(st,session['user_id'],tid));log(session['user_id'],'ticket.status','ticket',tid,{'status':st});notify(t['user_id'],'Estado de ticket actualizado',f'El ticket {t["public_id"]} cambió a {st}.','ticket','/tickets');return jsonify(ok=True,message='Ticket actualizado.')
