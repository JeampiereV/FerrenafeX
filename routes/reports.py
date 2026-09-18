from flask import Blueprint,request,jsonify,session,render_template,current_app
from database import q,x
from services.audit_service import log
from services.file_service import save_upload
from services.permission_service import require_permission
import uuid
bp=Blueprint('reports',__name__)
@bp.get('/reports')
def page():return render_template('reports.html')
@bp.get('/report/new')
def new():return render_template('report_create.html')
@bp.post('/api/reports')
def create():
    uid=session.get('user_id')
    if not uid:return jsonify(ok=False,message='Debes iniciar sesión.'),401
    if request.content_type and request.content_type.startswith('multipart/form-data'):
        d=request.form; description=str(d.get('description','')).strip(); evidence=request.files.get('evidence')
    else:
        d=request.get_json() or {};description=str(d.get('description','')).strip();evidence=None
    if not d.get('category') or not description:return jsonify(ok=False,message='Completa categoría y descripción.'),400
    pid='FX-'+uuid.uuid4().hex[:10].upper();rid=x('INSERT INTO reports(public_id,user_id,category,subcategory,description,latitude,longitude,priority) VALUES(?,?,?,?,?,?,?,?)',(pid,uid,d.get('category'),d.get('subcategory'),description[:4000],d.get('latitude') or None,d.get('longitude') or None,d.get('priority','normal')))
    if evidence:
        saved,err=save_upload(evidence,current_app.config['UPLOAD_ROOT']/'reports')
        if err:return jsonify(ok=False,message=err),400
        x('INSERT INTO report_evidence(report_id,file_path,original_name,mime,size) VALUES(?,?,?,?,?)',(rid,saved['path'],saved['name'],saved['mime'],saved['size']))
    x('INSERT INTO report_history(report_id,status,actor_id,notes) VALUES(?,?,?,?)',(rid,'created',uid,'Reporte creado'))
    log(uid,'report.created','report',rid,{'public_id':pid});return jsonify(ok=True,message=f'Reporte {pid} creado.',id=rid)
@bp.get('/api/reports')
def list_():return jsonify(ok=True,reports=[dict(r) for r in q('SELECT r.*,u.username FROM reports r JOIN users u ON u.id=r.user_id ORDER BY r.created_at DESC')])
@bp.get('/api/reports/evidence/<int:eid>')
def evidence(eid):
    from flask import send_file
    row=q('SELECT e.*,r.user_id FROM report_evidence e JOIN reports r ON r.id=e.report_id WHERE e.id=?',(eid,),one=True)
    uid=session.get('user_id')
    allowed=bool(q("SELECT 1 FROM users u JOIN roles ro ON ro.id=u.role_id WHERE u.id=? AND ro.name IN ('OWNER','STAFF','AUTHORITY')",(uid,),one=True))
    if not row or (row['user_id']!=uid and not allowed):return jsonify(ok=False,message='No permitido.'),403
    return send_file(row['file_path'],download_name=row['original_name'],mimetype=row['mime'])
@bp.get('/api/reports/<int:rid>')
def detail(rid):
    uid=session.get('user_id');r=q('SELECT r.*,u.username FROM reports r JOIN users u ON u.id=r.user_id WHERE r.id=?',(rid,),one=True)
    if not r:return jsonify(ok=False,message='Reporte no encontrado.'),404
    if r['user_id']!=uid and not require_read_reports(uid):return jsonify(ok=False,message='No permitido.'),403
    return jsonify(ok=True,report=dict(r),timeline=[dict(t) for t in q('SELECT h.*,u.username FROM report_history h LEFT JOIN users u ON u.id=h.actor_id WHERE h.report_id=? ORDER BY h.created_at',(rid,))],evidence=[dict(e) for e in q('SELECT id,original_name,mime,size FROM report_evidence WHERE report_id=?',(rid,))])
def require_read_reports(uid):
    return bool(q("SELECT 1 FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=? AND r.name IN ('OWNER','STAFF','AUTHORITY')",(uid,),one=True))
@bp.post('/api/admin/reports/<int:rid>/status')
@require_permission('admin.users.read')
def admin_status(rid):
    d=request.get_json() or {};st=d.get('status')
    if st not in ('created','received','in_review','in_attention','referred','resolved','closed','rejected'):return jsonify(ok=False,message='Estado inválido.'),400
    if not q('SELECT id FROM reports WHERE id=?',(rid,),one=True):return jsonify(ok=False,message='Reporte no encontrado.'),404
    x('UPDATE reports SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(st,rid));x('INSERT INTO report_history(report_id,status,actor_id,notes) VALUES(?,?,?,?)',(rid,st,session['user_id'],str(d.get('notes',''))[:500]));log(session['user_id'],'report.status','report',rid,{'status':st});return jsonify(ok=True,message='Estado del reporte actualizado.')

@bp.get('/api/map/markers')
def map_markers():
    uid=session.get('user_id')
    if not uid:return jsonify(ok=False,message='Debes iniciar sesión.'),401
    reports=q("""SELECT id,public_id,category,priority,status,latitude,longitude,created_at FROM reports WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND status NOT IN ('closed','rejected') ORDER BY created_at DESC LIMIT 250""")
    helps=q("""SELECT id,help_type,priority,status,latitude,longitude,created_at,radius_m FROM help_requests WHERE status='active' AND sharing_location=1 ORDER BY created_at DESC LIMIT 250""")
    def approx(rows):
        out=[]
        for r in rows:
            d=dict(r); d['latitude']=round(float(d['latitude']),3); d['longitude']=round(float(d['longitude']),3); out.append(d)
        return out
    return jsonify(ok=True,reports=approx(reports),helps=approx(helps))
