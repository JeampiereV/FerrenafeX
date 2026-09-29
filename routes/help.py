from flask import Blueprint, request, jsonify, session, render_template
from services.help_service import nearby
from services.notification_service import notify
from services.audit_service import log
from services.gamification_service import award, badge
from database import q, x
from datetime import datetime, timedelta

bp = Blueprint('help', __name__)

ALLOWED_RADII = (500, 1000, 2000, 5000)
ALLOWED_MINUTES = (15, 30, 60, 120)
LIVE_MINUTES = (5, 10, 15, 30, 60)


def _coords(lat_value, lon_value):
    if lat_value in (None, '') or lon_value in (None, ''):
        return None, None
    try:
        lat = float(lat_value)
        lon = float(lon_value)
    except (TypeError, ValueError):
        raise ValueError('La ubicación no es válida.')
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('La ubicación está fuera de rango.')
    return lat, lon


def _minutes(value, allowed, default):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return value if value in allowed else default


def _active_help_participant(hid, uid):
    h = q("SELECT * FROM help_requests WHERE id=? AND status='active'", (hid,), one=True)
    if not h:
        return None, None
    if h['user_id'] == uid:
        return h, None
    offer = q(
        """SELECT * FROM help_offers
           WHERE help_id=? AND helper_id=? AND status IN ('accepted','on_way','nearby','arrived','finished')
           ORDER BY id DESC LIMIT 1""",
        (hid, uid), one=True
    )
    return (h, offer) if offer else (None, None)


@bp.get('/help')
def page():
    return render_template('help.html')


@bp.get('/map')
def map_page():
    return render_template('help.html', focus_map=True)


@bp.post('/api/help')
def create():
    uid = session.get('user_id')
    d = request.get_json() or {}
    if not uid:
        return jsonify(ok=False, message='Debes iniciar sesión.'), 401

    try:
        lat, lon = _coords(d.get('latitude'), d.get('longitude'))
        radius = _minutes(d.get('radius_m', 1000), ALLOWED_RADII, 1000)
        minutes = _minutes(d.get('location_minutes', 30), ALLOWED_MINUTES, 30)
    except ValueError as exc:
        return jsonify(ok=False, message=str(exc)), 400

    help_type = str(d.get('help_type', 'Otro')).strip()[:100] or 'Otro'
    description = str(d.get('description', '')).strip()[:3000]
    priority = str(d.get('priority', 'normal')).strip().lower()
    if priority not in ('normal', 'high'):
        priority = 'normal'
    if not description:
        return jsonify(ok=False, message='Escribe qué ayuda necesitas.'), 400

    expires = (datetime.utcnow() + timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S') if lat is not None else None
    hid = x(
        """INSERT INTO help_requests(
            user_id,help_type,description,priority,latitude,longitude,radius_m,
            location_expires_at,sharing_location
        ) VALUES(?,?,?,?,?,?,?,?,?)""",
        (uid, help_type, description, priority, lat, lon, radius, expires, 1 if lat is not None else 0)
    )

    log(uid, 'help.created', 'help', hid, {'live_location': bool(lat is not None)})
    for u in q("SELECT id FROM users WHERE status='approved' AND id<>?", (uid,)):
        notify(u['id'], 'Nueva solicitud de ayuda', 'Hay una solicitud comunitaria activa.', 'help', '/help')
    return jsonify(ok=True, id=hid, message='Solicitud de ayuda creada.')


@bp.put('/api/help/<int:hid>')
def edit_help(hid):
    uid = session.get('user_id')
    h = q('SELECT * FROM help_requests WHERE id=?', (hid,), one=True)
    if not uid or not h:
        return jsonify(ok=False, message='Solicitud no encontrada.'), 404
    if h['user_id'] != uid:
        return jsonify(ok=False, message='Solo quien creó la solicitud puede editarla.'), 403
    if h['status'] != 'active':
        return jsonify(ok=False, message='La solicitud ya fue finalizada.'), 400

    d = request.get_json() or {}
    desc = str(d.get('description', h['description'])).strip()[:3000]
    kind = str(d.get('help_type', h['help_type'])).strip()[:100]
    priority = str(d.get('priority', h['priority'])).lower()
    if priority not in ('normal', 'high'):
        priority = 'normal'
    minutes = _minutes(d.get('location_minutes', 30), ALLOWED_MINUTES, 30)
    has_location = h['latitude'] is not None and h['longitude'] is not None
    expires = (datetime.utcnow() + timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S') if has_location else None
    x(
        """UPDATE help_requests SET help_type=?,description=?,priority=?,location_expires_at=?,
           updated_at=CURRENT_TIMESTAMP,sharing_location=? WHERE id=?""",
        (kind, desc, priority, expires, 1 if has_location else 0, hid)
    )
    # Editar la solicitud no activa ni reactiva el seguimiento GPS exacto.
    # El seguimiento sólo comienza mediante el botón de ubicación en vivo.
    log(uid, 'help.edited', 'help', hid)
    return jsonify(ok=True, message='Solicitud actualizada.')


@bp.post('/api/help/<int:hid>/complete')
def complete_help(hid):
    uid = session.get('user_id')
    h = q('SELECT * FROM help_requests WHERE id=?', (hid,), one=True)
    if not uid or not h:
        return jsonify(ok=False, message='Solicitud no encontrada.'), 404
    if h['user_id'] != uid:
        return jsonify(ok=False, message='Solo quien creó la solicitud puede marcarla como solucionada.'), 403
    x("UPDATE help_requests SET status='completed',sharing_location=0,completed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?", (hid,))
    x('UPDATE help_locations SET expires_at=CURRENT_TIMESTAMP WHERE help_id=?', (hid,))
    x("UPDATE live_locations SET sharing=0,expires_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE user_id=? AND context=?", (uid, f'help:{hid}'))
    log(uid, 'help.completed', 'help', hid)
    return jsonify(ok=True, message='Solicitud marcada como solucionada.')


@bp.get('/api/help/mine')
def mine():
    uid = session.get('user_id')
    if not uid:
        return jsonify(ok=False, message='No autenticado.'), 401
    rows = q(
        """SELECT h.*,u.names,u.last_names,u.username,u.dni
           FROM help_requests h JOIN users u ON u.id=h.user_id
           WHERE h.user_id=? ORDER BY h.created_at DESC""",
        (uid,)
    )
    offers = q(
        """SELECT o.*,h.help_type,h.description,h.user_id request_user_id
           FROM help_offers o JOIN help_requests h ON h.id=o.help_id
           WHERE o.helper_id=? ORDER BY o.created_at DESC""",
        (uid,)
    )
    return jsonify(ok=True, requests=[dict(r) for r in rows], offers=[dict(r) for r in offers])


@bp.get('/api/help/nearby')
def near():
    uid = session.get('user_id')
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    radius = request.args.get('radius', 1000, type=int)
    if not uid or lat is None or lon is None:
        return jsonify(ok=False, message='Ubicación requerida.'), 400
    return jsonify(ok=True, requests=nearby(lat, lon, radius))


@bp.post('/api/help/<int:hid>/offer')
def offer(hid):
    uid = session.get('user_id')
    h = q("SELECT * FROM help_requests WHERE id=? AND status='active'", (hid,), one=True)
    if not uid or not h:
        return jsonify(ok=False, message='Solicitud no disponible.'), 404
    if h['user_id'] == uid:
        return jsonify(ok=False, message='No puedes ofrecerte a tu propia solicitud.'), 400
    existing = q('SELECT id,status FROM help_offers WHERE help_id=? AND helper_id=?', (hid, uid), one=True)
    if existing:
        return jsonify(ok=False, message='Ya ofreciste ayuda para esta solicitud.'), 400
    oid = x('INSERT INTO help_offers(help_id,helper_id) VALUES(?,?)', (hid, uid))
    notify(h['user_id'], 'Alguien se ofreció a ayudar', 'Un colaborador quiere apoyar tu solicitud.', 'help', '/help')
    log(uid, 'help.offer', 'help', hid)
    return jsonify(ok=True, id=oid, message='Tu oferta fue enviada.')


@bp.post('/api/help/<int:hid>/offer/<int:oid>/accept')
def accept_offer(hid, oid):
    uid = session.get('user_id')
    h = q("SELECT * FROM help_requests WHERE id=? AND user_id=? AND status='active'", (hid, uid), one=True)
    o = q('SELECT * FROM help_offers WHERE id=? AND help_id=?', (oid, hid), one=True)
    if not h or not o:
        return jsonify(ok=False, message='Oferta no encontrada.'), 404
    x("UPDATE help_offers SET status='accepted',updated_at=CURRENT_TIMESTAMP WHERE id=?", (oid,))
    notify(o['helper_id'], 'Oferta aceptada', 'La persona solicitante aceptó tu ayuda.', 'help', '/help')
    log(uid, 'help.offer.accepted', 'help', hid, {'offer_id': oid})
    return jsonify(ok=True, message='Colaborador aceptado.')


@bp.post('/api/help/<int:hid>/status')
def status(hid):
    uid = session.get('user_id')
    d = request.get_json() or {}
    st = d.get('status')
    o = q(
        """SELECT * FROM help_offers WHERE help_id=? AND helper_id=?
           AND status IN ('offered','accepted','on_way','nearby','arrived','finished')
           ORDER BY id DESC LIMIT 1""",
        (hid, uid), one=True
    )
    if not o:
        return jsonify(ok=False, message='No existe tu oferta de ayuda.'), 403
    if st not in ('accepted', 'on_way', 'nearby', 'arrived', 'finished', 'cancelled'):
        return jsonify(ok=False, message='Estado inválido.'), 400
    try:
        lat, lon = _coords(d.get('latitude'), d.get('longitude'))
    except ValueError as exc:
        return jsonify(ok=False, message=str(exc)), 400
    x(
        'UPDATE help_offers SET status=?,updated_at=CURRENT_TIMESTAMP,helper_latitude=?,helper_longitude=? WHERE id=?',
        (st, lat, lon, o['id'])
    )
    if lat is not None:
        expires = (datetime.utcnow() + timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')
        x(
            """INSERT INTO help_locations(help_id,helper_id,latitude,longitude,expires_at)
               VALUES(?,?,?,?,?)""",
            (hid, uid, lat, lon, expires)
        )
        x(
            """INSERT INTO live_locations(user_id,latitude,longitude,accuracy,context,sharing,expires_at)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
                 latitude=excluded.latitude,longitude=excluded.longitude,accuracy=excluded.accuracy,
                 context=excluded.context,sharing=excluded.sharing,expires_at=excluded.expires_at,
                 updated_at=CURRENT_TIMESTAMP""",
            (uid, lat, lon, d.get('accuracy'), f'help:{hid}', 1 if st not in ('finished','cancelled') else 0, expires)
        )
    if st == 'finished':
        h = q('SELECT user_id FROM help_requests WHERE id=?', (hid,), one=True)
        if h:
            notify(h['user_id'], 'Ayuda finalizada', 'Confirma si recibiste la ayuda.', 'help', '/help')
        x("UPDATE help_requests SET updated_at=CURRENT_TIMESTAMP,sharing_location=0 WHERE id=?", (hid,))
        x("UPDATE live_locations SET sharing=0,expires_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE user_id=? AND context=?", (uid, f'help:{hid}'))
    log(uid, 'help.status', 'help', hid, {'status': st})
    return jsonify(ok=True, message='Estado actualizado.')


@bp.get('/api/help/<int:hid>/tracking')
def tracking(hid):
    uid = session.get('user_id')
    h, participant_offer = _active_help_participant(hid, uid)
    owner = bool(q("SELECT 1 FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=? AND r.name='OWNER'", (uid,), one=True))
    if not h and not owner:
        return jsonify(ok=False, message='No permitido.'), 403
    if owner and not h:
        h = q('SELECT * FROM help_requests WHERE id=?', (hid,), one=True)
    requester_id = h['user_id']
    offer = q("SELECT * FROM help_offers WHERE help_id=? AND status IN ('accepted','on_way','nearby','arrived','finished') ORDER BY updated_at DESC LIMIT 1", (hid,), one=True)
    users = [requester_id]
    if offer:
        users.append(offer['helper_id'])
    live = q(
        """SELECT l.user_id,l.latitude,l.longitude,l.accuracy,l.context,l.updated_at,u.username,u.names,u.last_names
           FROM live_locations l JOIN users u ON u.id=l.user_id
           WHERE l.user_id IN (%s) AND l.sharing=1 AND l.expires_at>CURRENT_TIMESTAMP""" % ','.join('?'*len(users)),
        tuple(users)
    ) if users else []
    return jsonify(ok=True, live_locations=[dict(v) for v in live], offer=dict(offer) if offer else None)


@bp.post('/api/help/<int:hid>/live')
def help_live(hid):
    uid = session.get('user_id')
    h, offer = _active_help_participant(hid, uid)
    if not h:
        return jsonify(ok=False, message='Solo el solicitante y el colaborador aceptado pueden compartir ubicación exacta.'), 403
    try:
        lat, lon = _coords((request.get_json() or {}).get('latitude'), (request.get_json() or {}).get('longitude'))
    except ValueError as exc:
        return jsonify(ok=False, message=str(exc)), 400
    if lat is None:
        return jsonify(ok=False, message='Ubicación requerida.'), 400
    d = request.get_json() or {}
    existing = q("SELECT expires_at,context FROM live_locations WHERE user_id=?", (uid,), one=True)
    renew = bool(d.get('renew', False))
    if existing and existing['context'] == f'help:{hid}' and not renew:
        expires = existing['expires_at']
    else:
        minutes = _minutes(d.get('minutes', 10), LIVE_MINUTES, 10)
        expires = (datetime.utcnow() + timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
    x(
        """INSERT INTO live_locations(user_id,latitude,longitude,accuracy,context,sharing,expires_at)
           VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET
             latitude=excluded.latitude,longitude=excluded.longitude,accuracy=excluded.accuracy,
             context=excluded.context,sharing=1,expires_at=excluded.expires_at,updated_at=CURRENT_TIMESTAMP""",
        (uid, lat, lon, d.get('accuracy'), f'help:{hid}', 1, expires)
    )
    x('INSERT INTO help_locations(help_id,helper_id,latitude,longitude,expires_at) VALUES(?,?,?,?,?)', (hid, uid if offer else None, lat, lon, expires))
    return jsonify(ok=True, message='Ubicación en tiempo real actualizada.')


@bp.post('/api/location/live')
def location_live():
    uid = session.get('user_id')
    if not uid:
        return jsonify(ok=False, message='No autenticado.'), 401
    d = request.get_json() or {}
    try:
        lat, lon = _coords(d.get('latitude'), d.get('longitude'))
    except ValueError as exc:
        return jsonify(ok=False, message=str(exc)), 400
    if lat is None:
        return jsonify(ok=False, message='Ubicación requerida.'), 400
    context = str(d.get('context', 'self')).strip()[:80] or 'self'
    existing = q("SELECT expires_at,context FROM live_locations WHERE user_id=?", (uid,), one=True)
    renew = bool(d.get('renew', False))
    if existing and existing['context'] == context and not renew:
        expires = existing['expires_at']
    else:
        minutes = _minutes(d.get('minutes', 10), LIVE_MINUTES, 10)
        expires = (datetime.utcnow() + timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
    x(
        """INSERT INTO live_locations(user_id,latitude,longitude,accuracy,context,sharing,expires_at)
           VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET
             latitude=excluded.latitude,longitude=excluded.longitude,accuracy=excluded.accuracy,
             context=excluded.context,sharing=1,expires_at=excluded.expires_at,updated_at=CURRENT_TIMESTAMP""",
        (uid, lat, lon, d.get('accuracy'), context, 1, expires)
    )
    return jsonify(ok=True, message='Ubicación compartida en tiempo real.', expires_at=expires)


@bp.post('/api/location/stop')
def location_stop():
    uid = session.get('user_id')
    if not uid:
        return jsonify(ok=False, message='No autenticado.'), 401
    x("UPDATE live_locations SET sharing=0,expires_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (uid,))
    return jsonify(ok=True, message='Compartir ubicación detenido.')


@bp.get('/api/location/me')
def location_me():
    uid = session.get('user_id')
    if not uid:
        return jsonify(ok=False, message='No autenticado.'), 401
    loc = q("SELECT latitude,longitude,accuracy,context,updated_at,expires_at FROM live_locations WHERE user_id=? AND sharing=1 AND expires_at>CURRENT_TIMESTAMP", (uid,), one=True)
    return jsonify(ok=True, location=dict(loc) if loc else None)


@bp.post('/api/help/<int:hid>/confirm')
def confirm(hid):
    uid = session.get('user_id')
    h = q('SELECT * FROM help_requests WHERE id=? AND user_id=?', (hid, uid), one=True)
    o = q("SELECT * FROM help_offers WHERE help_id=? AND status='finished' ORDER BY id DESC LIMIT 1", (hid,), one=True)
    if not h or not o:
        return jsonify(ok=False, message='No hay una ayuda finalizada.'), 400
    x("UPDATE help_requests SET status='completed',sharing_location=0,completed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?", (hid,))
    award(o['helper_id'], 50, 'Ayuda confirmada', 'help', hid)
    badge(o['helper_id'], 'Primera ayuda')
    x('UPDATE help_locations SET expires_at=CURRENT_TIMESTAMP WHERE help_id=?', (hid,))
    x("UPDATE live_locations SET sharing=0,expires_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE user_id IN (?,?)", (uid, o['helper_id']))
    log(uid, 'help.confirmed', 'help', hid)
    return jsonify(ok=True, message='Ayuda confirmada.')
