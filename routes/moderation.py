from flask import Blueprint, request, jsonify, session
from database import q, x
from services.permission_service import require_permission
from services.audit_service import log
from services.notification_service import notify

bp = Blueprint('moderation', __name__)

@bp.post('/api/moderation/report')
def create_case():
    uid = session.get('user_id')
    if not uid:
        return jsonify(ok=False, message='Debes iniciar sesión.'), 401
    d = request.get_json() or {}
    target_type = str(d.get('target_type', 'content'))[:30]
    try:
        target_id = int(d.get('target_id'))
    except Exception:
        target_id = None
    reason = str(d.get('reason', '')).strip()[:500]
    if not reason:
        return jsonify(ok=False, message='Indica el motivo.'), 400
    cid = x('INSERT INTO moderation_cases(reporter_id,target_type,target_id,reason) VALUES(?,?,?,?)', (uid, target_type, target_id, reason))
    log(uid, 'moderation.reported', target_type, target_id, {'case_id': cid, 'reason': reason})
    return jsonify(ok=True, id=cid, message='El contenido fue enviado a moderación.')

@bp.get('/api/moderation')
@require_permission('moderation.review')
def cases():
    rows = q('''SELECT m.*, u.username reporter_username
                FROM moderation_cases m JOIN users u ON u.id=m.reporter_id
                ORDER BY m.created_at DESC LIMIT 300''')
    return jsonify(ok=True, cases=[dict(r) for r in rows])

@bp.post('/api/moderation/<int:cid>')
@require_permission('moderation.review')
def review(cid):
    d = request.get_json() or {}
    status = d.get('status')
    resolution = str(d.get('resolution', '')).strip()[:1000]
    if status not in ('valid', 'correction', 'false_confirmed', 'insufficient', 'closed'):
        return jsonify(ok=False, message='Estado de moderación inválido.'), 400
    row = q('SELECT * FROM moderation_cases WHERE id=?', (cid,), one=True)
    if not row:
        return jsonify(ok=False, message='Caso no encontrado.'), 404
    x('UPDATE moderation_cases SET status=?,resolution=?,reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?', (status, resolution, session['user_id'], cid))
    notify(row['reporter_id'], 'Moderación actualizada', f'El caso #{cid} fue revisado.', 'moderation', '/staff')
    log(session['user_id'], 'moderation.reviewed', 'moderation_case', cid, {'status': status})
    return jsonify(ok=True, message='Caso actualizado.')
