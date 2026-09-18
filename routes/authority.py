from flask import Blueprint,request,jsonify,session,render_template,current_app,send_file
from database import q,x
from services.permission_service import require_permission
from services.audit_service import log
from services.notification_service import notify
from services.file_service import save_upload
from pathlib import Path
bp=Blueprint('authority',__name__)
@bp.get('/authorities')
def page():return render_template('authorities.html')
@bp.get('/authority/channel')
def channel():
    uid=session.get('user_id');u=q('SELECT r.name role FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=?',(uid,),one=True)
    if not u or u['role'] not in ('OWNER','STAFF','AUTHORITY'):return render_template('403.html'),403
    return render_template('authority_channel.html')
@bp.post('/api/authority/request')
def request_():
    uid=session.get('user_id')
    if not uid:return jsonify(ok=False,message='No autenticado.'),401
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        d=request.form;evidence=request.files.get('document')
    else:d=request.get_json() or {};evidence=None
    required=['institution','authority_type','position','reason']
    if any(not str(d.get(k,'')).strip() for k in required):return jsonify(ok=False,message='Completa institución, tipo, cargo y motivo.'),400
    rid=x('INSERT INTO authority_requests(user_id,institution,authority_type,position,area,institutional_code,institutional_email,reason) VALUES(?,?,?,?,?,?,?,?)',(uid,d.get('institution',''),d.get('authority_type',''),d.get('position',''),d.get('area',''),d.get('institutional_code',''),d.get('institutional_email',''),d.get('reason','')))
    if evidence:
        saved,err=save_upload(evidence,current_app.config['UPLOAD_ROOT']/'authority',max_bytes=8*1024*1024)
        if err:return jsonify(ok=False,message=err),400
        x('INSERT INTO authority_documents(request_id,file_path,original_name,mime,size) VALUES(?,?,?,?,?)',(rid,saved['path'],saved['name'],saved['mime'],saved['size']))
    log(uid,'authority.request','authority_request',rid);return jsonify(ok=True,message='Solicitud enviada.')
@bp.get('/api/authority/requests')
@require_permission('authority.review')
def requests_():return jsonify(ok=True,requests=[dict(r) for r in q('SELECT a.*,u.username FROM authority_requests a JOIN users u ON u.id=a.user_id ORDER BY a.created_at DESC')])
@bp.get('/api/authority/documents/<int:doc_id>')
@require_permission('authority.review')
def document(doc_id):
    d=q('SELECT * FROM authority_documents WHERE id=?',(doc_id,),one=True)
    if not d:return jsonify(ok=False,message='Documento no encontrado.'),404
    return send_file(d['file_path'],download_name=d['original_name'],mimetype=d['mime'])
@bp.post('/api/authority/requests/<int:rid>/decision')
@require_permission('authority.review')
def decision(rid):
    d=request.get_json() or {};st=d.get('status');a=q('SELECT * FROM authority_requests WHERE id=?',(rid,),one=True)
    if not a:return jsonify(ok=False,message='No encontrada.'),404
    if st not in ('approved','rejected','revoked'):return jsonify(ok=False,message='Estado inválido.'),400
    x('UPDATE authority_requests SET status=?,reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?',(st,session['user_id'],rid))
    if st=='approved':
        x("UPDATE users SET role_id=(SELECT id FROM roles WHERE name='AUTHORITY'),authority_type=? WHERE id=?",(a['authority_type'],a['user_id']))
        notify(a['user_id'],'Autoridad verificada','Tu solicitud fue aprobada dentro de FerreñafeX.','authority','/authority/channel')
    if st=='revoked':x("UPDATE users SET role_id=(SELECT id FROM roles WHERE name='CITIZEN'),authority_type=NULL WHERE id=?",(a['user_id'],))
    log(session['user_id'],'authority.decision','authority_request',rid,{'status':st});return jsonify(ok=True,message='Solicitud actualizada.')
@bp.post('/api/authority/reinforcement')
@require_permission('authority.reinforcement')
def reinforcement():
    d=request.get_json() or {};rid=x('INSERT INTO authority_reinforcements(requester_id,target_authority_type,reason,priority,description,latitude,longitude) VALUES(?,?,?,?,?,?,?)',(session['user_id'],d.get('target_authority_type',''),d.get('reason',''),d.get('priority','normal'),d.get('description',''),d.get('latitude'),d.get('longitude')));log(session['user_id'],'authority.reinforcement','reinforcement',rid);return jsonify(ok=True,message='Solicitud interna registrada.')
