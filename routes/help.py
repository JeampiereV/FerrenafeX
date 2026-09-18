from flask import Blueprint,request,jsonify,session,render_template
from database import q,x
from services.help_service import nearby
from services.notification_service import notify
from services.audit_service import log
from services.gamification_service import award,badge
bp=Blueprint('help',__name__)
@bp.get('/help')
def page():return render_template('help.html')
@bp.get('/map')
def map_page():return render_template('map.html')
@bp.post('/api/help')
def create():
 uid=session.get('user_id');d=request.get_json() or {}
 if not uid:return jsonify(ok=False,message='Debes iniciar sesión.'),401
 try:lat=float(d['latitude']);lon=float(d['longitude']);radius=int(d.get('radius_m',1000))
 except:return jsonify(ok=False,message='Debes aceptar la ubicación.'),400
 if radius not in (500,1000,2000,5000):radius=1000
 hid=x('INSERT INTO help_requests(user_id,help_type,description,priority,latitude,longitude,radius_m) VALUES(?,?,?,?,?,?,?)',(uid,d.get('help_type','Otro'),str(d.get('description',''))[:3000],d.get('priority','normal'),lat,lon,radius));log(uid,'help.created','help',hid)
 for u in q("SELECT id FROM users WHERE status='approved' AND id<>?",(uid,)):notify(u['id'],'Solicitud de ayuda cercana','Hay una solicitud comunitaria cerca de ti.','help','/map')
 return jsonify(ok=True,id=hid,message='Solicitud de ayuda creada.')
@bp.get('/api/help/mine')
def mine():
 uid=session.get('user_id')
 if not uid:return jsonify(ok=False,message='No autenticado.'),401
 return jsonify(ok=True,requests=[dict(r) for r in q('SELECT * FROM help_requests WHERE user_id=? ORDER BY created_at DESC',(uid,))],offers=[dict(r) for r in q('SELECT o.*,h.help_type,h.description FROM help_offers o JOIN help_requests h ON h.id=o.help_id WHERE o.helper_id=? ORDER BY o.created_at DESC',(uid,))])
@bp.get('/api/help/nearby')
def near():
 uid=session.get('user_id');lat=request.args.get('lat',type=float);lon=request.args.get('lon',type=float);radius=request.args.get('radius',1000,type=int)
 if not uid or lat is None or lon is None:return jsonify(ok=False,message='Ubicación requerida.'),400
 return jsonify(ok=True,requests=nearby(lat,lon,radius))
@bp.post('/api/help/<int:hid>/offer')
def offer(hid):
 uid=session.get('user_id');h=q("SELECT * FROM help_requests WHERE id=? AND status='active'",(hid,),one=True)
 if not uid or not h:return jsonify(ok=False,message='Solicitud no disponible.'),404
 if h['user_id']==uid:return jsonify(ok=False,message='No puedes ofrecerte a tu propia solicitud.'),400
 existing=q('SELECT id,status FROM help_offers WHERE help_id=? AND helper_id=?',(hid,uid),one=True)
 if existing:return jsonify(ok=False,message='Ya ofreciste ayuda para esta solicitud.'),400
 oid=x('INSERT INTO help_offers(help_id,helper_id) VALUES(?,?)',(hid,uid));notify(h['user_id'],'Alguien se ofreció a ayudar','Un colaborador aceptó apoyar tu solicitud.','help','/help');log(uid,'help.offer','help',hid);return jsonify(ok=True,id=oid,message='Tu oferta fue enviada.')
@bp.post('/api/help/<int:hid>/offer/<int:oid>/accept')
def accept_offer(hid,oid):
 uid=session.get('user_id');h=q('SELECT * FROM help_requests WHERE id=? AND user_id=? AND status=\'active\'',(hid,uid),one=True);o=q('SELECT * FROM help_offers WHERE id=? AND help_id=?',(oid,hid),one=True)
 if not h or not o:return jsonify(ok=False,message='Oferta no encontrada.'),404
 x("UPDATE help_offers SET status='accepted',updated_at=CURRENT_TIMESTAMP WHERE id=?",(oid,));notify(o['helper_id'],'Oferta aceptada','La persona solicitante aceptó tu ayuda.','help','/help');log(uid,'help.offer.accepted','help',hid,{'offer_id':oid});return jsonify(ok=True,message='Colaborador aceptado.')
@bp.post('/api/help/<int:hid>/status')
def status(hid):
 uid=session.get('user_id');d=request.get_json() or {};st=d.get('status');o=q("SELECT * FROM help_offers WHERE help_id=? AND helper_id=? AND status IN ('offered','accepted','on_way','nearby','arrived','finished') ORDER BY id DESC LIMIT 1",(hid,uid),one=True)
 if not o:return jsonify(ok=False,message='No existe tu oferta de ayuda.'),403
 if st not in ('accepted','on_way','nearby','arrived','finished','cancelled'):return jsonify(ok=False,message='Estado inválido.'),400
 x('UPDATE help_offers SET status=?,updated_at=CURRENT_TIMESTAMP,helper_latitude=?,helper_longitude=? WHERE id=?',(st,d.get('latitude'),d.get('longitude'),o['id']))
 if d.get('latitude') is not None and d.get('longitude') is not None and st in ('on_way','nearby','arrived'):
  x('INSERT INTO help_locations(help_id,helper_id,latitude,longitude,expires_at) VALUES(?,?,?,?,datetime(\'now\',\'+20 minutes\'))',(hid,uid,float(d['latitude']),float(d['longitude'])))
 if st=='finished':
  h=q('SELECT user_id FROM help_requests WHERE id=?',(hid,),one=True);notify(h['user_id'],'Ayuda finalizada','Confirma si recibiste la ayuda.','help','/help');x("UPDATE help_requests SET updated_at=CURRENT_TIMESTAMP,sharing_location=0 WHERE id=?",(hid,))
 log(uid,'help.status','help',hid,{'status':st});return jsonify(ok=True,message='Estado actualizado.')
@bp.get('/api/help/<int:hid>/tracking')
def tracking(hid):
 uid=session.get('user_id');h=q('SELECT * FROM help_requests WHERE id=?',(hid,),one=True);o=q('SELECT * FROM help_offers WHERE help_id=? ORDER BY updated_at DESC LIMIT 1',(hid,),one=True)
 if not h or uid not in (h['user_id'], o['helper_id'] if o else -1):return jsonify(ok=False,message='No permitido.'),403
 loc=q('SELECT latitude,longitude,shared_at,expires_at FROM help_locations WHERE help_id=? AND expires_at>CURRENT_TIMESTAMP ORDER BY shared_at DESC LIMIT 1',(hid,),one=True)
 return jsonify(ok=True,location=dict(loc) if loc else None,offer=dict(o) if o else None)
@bp.post('/api/help/<int:hid>/confirm')
def confirm(hid):
 uid=session.get('user_id');h=q('SELECT * FROM help_requests WHERE id=? AND user_id=?',(hid,uid),one=True);o=q("SELECT * FROM help_offers WHERE help_id=? AND status='finished' ORDER BY id DESC LIMIT 1",(hid,),one=True)
 if not h or not o:return jsonify(ok=False,message='No hay una ayuda finalizada.'),400
 x("UPDATE help_requests SET status='completed',sharing_location=0,completed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?",(hid,));award(o['helper_id'],50,'Ayuda confirmada','help',hid);badge(o['helper_id'],'Primera ayuda');x('UPDATE help_locations SET expires_at=CURRENT_TIMESTAMP WHERE help_id=?',(hid,));log(uid,'help.confirmed','help',hid);return jsonify(ok=True,message='Ayuda confirmada. +50 puntos para el colaborador.')
