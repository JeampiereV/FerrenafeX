from datetime import date

from flask import Blueprint, request, jsonify, session, render_template

from database import q, x
from services.permission_service import require_permission
from services.audit_service import log
from services.auth_service import role_id
from services.notification_service import notify
from services.email_service import send_account_approved, send_account_rejected
import html,re

bp = Blueprint("admin", __name__)

def is_owner(uid):
    return bool(uid and q("SELECT 1 FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=? AND r.name='OWNER'", (uid,), one=True))

def is_vip(uid):
    return bool(uid and q("SELECT 1 FROM users WHERE id=? AND vip_expires_at IS NOT NULL AND vip_expires_at > CURRENT_TIMESTAMP", (uid,), one=True))

def can_announce(uid):
    return is_owner(uid) or is_vip(uid)


def _age(birth_date):
    if not birth_date:
        return None
    try:
        b = date.fromisoformat(birth_date)
        t = date.today()
        return t.year - b.year - ((t.month, t.day) < (b.month, b.day))
    except ValueError:
        return None


def _user_row(row):
    d = dict(row)
    d["age"] = _age(d.get("birth_date"))
    d["full_name"] = f"{d.get('names','')} {d.get('last_names','')}".strip()
    return d


@bp.get("/owner")
@require_permission("admin.dashboard")
def owner():
    return render_template("owner.html")


@bp.get("/staff")
@require_permission("moderation.review")
def staff():
    return render_template("staff.html")


@bp.get("/api/admin/users")
@require_permission("admin.users.read")
def users():
    rows = q(
        """
        SELECT
            u.id, u.dni, u.names, u.last_names, u.username, u.email, u.phone,
            u.birth_date, u.status, u.profile_photo, u.bio, u.authority_type,
            u.created_at, u.updated_at,
            r.name AS role_name,
            sr.name AS social_rank_name,
            COALESCE((SELECT SUM(p.amount) FROM points p WHERE p.user_id=u.id),0) AS points
        FROM users u
        JOIN roles r ON r.id=u.role_id
        LEFT JOIN social_ranks sr ON sr.id=u.social_rank_id
        ORDER BY CASE u.status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END, u.created_at DESC
        """
    )
    return jsonify(ok=True, users=[_user_row(r) for r in rows])


@bp.get("/api/admin/users/<int:uid>")
@require_permission("admin.users.read")
def user_detail(uid):
    user = q(
        """
        SELECT
            u.id, u.dni, u.names, u.last_names, u.username, u.email, u.phone,
            u.birth_date, u.status, u.profile_photo, u.bio, u.authority_type,
            u.created_at, u.updated_at,
            r.name AS role_name,
            sr.name AS social_rank_name,
            COALESCE((SELECT SUM(p.amount) FROM points p WHERE p.user_id=u.id),0) AS points,
            (SELECT COUNT(*) FROM reports rp WHERE rp.user_id=u.id) AS report_count,
            (SELECT COUNT(*) FROM help_requests hr WHERE hr.user_id=u.id) AS help_requests,
            (SELECT COUNT(*) FROM help_offers ho WHERE ho.helper_id=u.id AND ho.status='completed') AS help_completed
        FROM users u
        JOIN roles r ON r.id=u.role_id
        LEFT JOIN social_ranks sr ON sr.id=u.social_rank_id
        WHERE u.id=?
        """, (uid,), one=True
    )
    if not user:
        return jsonify(ok=False, message="No se encontró el usuario."), 404
    return jsonify(ok=True, user=_user_row(user))


@bp.get('/api/admin/authorities')
@require_permission('admin.users.read')
def admin_authorities():
    rows=q("SELECT u.id,u.names,u.last_names,u.username,u.email,u.phone,u.authority_type,r.name role_name,u.status FROM users u JOIN roles r ON r.id=u.role_id WHERE u.status='approved' AND (u.authority_type IS NOT NULL OR r.name='OWNER') ORDER BY CASE WHEN r.name='OWNER' THEN 0 ELSE 1 END,u.names,u.last_names")
    return jsonify(ok=True,users=[dict(r) for r in rows])

@bp.get("/api/admin/ranks")
@require_permission("admin.ranks.read")
def ranks():
    return jsonify(ok=True, ranks=[dict(r) for r in q("SELECT id,name,min_points,description FROM social_ranks ORDER BY min_points")])


@bp.post("/api/admin/users/<int:uid>/status")
@require_permission("admin.users.write")
def status(uid):
    d = request.get_json() or {}
    st = d.get("status")
    if st not in ("pending", "approved", "rejected", "suspended", "blocked"):
        return jsonify(ok=False, message="Estado inválido."), 400

    target = q("SELECT u.id,r.name role_name FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=?", (uid,), one=True)
    if not target:
        return jsonify(ok=False, message="Usuario no encontrado."), 404
    if target["role_name"] == "OWNER":
        return jsonify(ok=False, message="La cuenta Owner no puede administrarse desde esta acción."), 403

    if st == "approved":
        member_id=role_id("MEMBER")
        x("UPDATE users SET status=?, role_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (st, member_id, uid)); x("INSERT OR IGNORE INTO user_badges(user_id,badge_id) SELECT ?,id FROM badges WHERE name='Pixel Verde'", (uid,))
    else:
        x("UPDATE users SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (st, uid))
    log(session["user_id"], "user.status", "user", uid, {"status": st})
    if st == "approved":
        user=q("SELECT id,names,last_names,email FROM users WHERE id=?",(uid,),one=True)
        notify(uid, "Cuenta aprobada", "Tu cuenta ya está activa. Puedes iniciar sesión.", "account", "/login")
        email_sent=send_account_approved(user) if user and user["email"] else False
        log(session["user_id"], "user.approval_email", "user", uid, {"sent": bool(email_sent)})
        return jsonify(ok=True, message="Cuenta aprobada. Se asignó el rango MIEMBRO y se intentó enviar el correo de confirmación.", email_sent=bool(email_sent))
    elif st in ("rejected", "suspended", "blocked"):
        user=q("SELECT id,names,last_names,email FROM users WHERE id=?",(uid,),one=True)
        notify(uid, "Estado de cuenta actualizado", f"Tu cuenta ahora está: {st}.", "account", "/login")
        email_sent=False
        if st=="rejected" and user and user["email"]:
            email_sent=send_account_rejected(user)
        log(session["user_id"], "user.status_email", "user", uid, {"sent": bool(email_sent), "status": st})
        return jsonify(ok=True, message="Estado actualizado correctamente.", email_sent=bool(email_sent))
    return jsonify(ok=True, message="Estado actualizado correctamente.")


@bp.put("/api/admin/users/<int:uid>")
@require_permission("admin.users.write")
def edit_user(uid):
    d=request.get_json() or {}; target=q('SELECT id FROM users WHERE id=?',(uid,),one=True)
    if not target:return jsonify(ok=False,message='Usuario no encontrado.'),404
    fields=[]; vals=[]
    for key,maxlen in [('names',100),('last_names',120),('username',40),('phone',30),('bio',500)]:
        if key in d:
            val=str(d[key]).strip()[:maxlen]
            if key=='username' and not val:return jsonify(ok=False,message='El usuario no puede quedar vacío.'),400
            fields.append(f'{key}=?');vals.append(val)
    if not fields:return jsonify(ok=False,message='No hay cambios para guardar.'),400
    if 'username' in d and q('SELECT id FROM users WHERE username=? AND id<>?',(str(d['username']).strip(),uid),one=True): return jsonify(ok=False,message='Ese nombre de usuario ya está ocupado.'),409
    vals.append(uid)
    try: x(f"UPDATE users SET {', '.join(fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=?",tuple(vals))
    except Exception: return jsonify(ok=False,message='No se pudieron guardar los datos del miembro.'),400
    log(session['user_id'],'user.edited','user',uid); notify(uid,'Perfil actualizado','Un Owner actualizó datos administrativos de tu cuenta.','account','/profile'); return jsonify(ok=True,message='Miembro actualizado correctamente.')

@bp.post('/api/admin/users/<int:uid>/password')
@require_permission('admin.users.write')
def admin_password_reset(uid):
    d=request.get_json() or {}
    new_password=str(d.get('new_password',''))
    if len(new_password)<8:
        return jsonify(ok=False,message='La nueva contraseña debe tener al menos 8 caracteres.'),400
    target=q('SELECT id,username FROM users WHERE id=?',(uid,),one=True)
    if not target:
        return jsonify(ok=False,message='Usuario no encontrado.'),404
    from services.auth_service import hash_password
    x('UPDATE users SET password_hash=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(hash_password(new_password),uid))
    log(session['user_id'],'admin.password_reset','user',uid)
    notify(uid,'Contraseña actualizada','Un Owner estableció una nueva contraseña para tu cuenta.','account','/login')
    return jsonify(ok=True,message='Contraseña reemplazada correctamente.')

@bp.post("/api/admin/me/password")
@require_permission("admin.users.write")
def admin_self_password():
    uid = session.get("user_id")
    owner = q(
        "SELECT u.id, r.name AS role_name FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=?",
        (uid,), one=True
    )
    if not owner or owner["role_name"] != "OWNER":
        return jsonify(ok=False, message="Solo el Owner puede cambiar su propia contraseña desde este panel."), 403

    d = request.get_json() or {}
    new_password = str(d.get("new_password", ""))
    if len(new_password) < 8:
        return jsonify(ok=False, message="La nueva contraseña debe tener al menos 8 caracteres."), 400

    from services.auth_service import hash_password
    x(
        "UPDATE users SET password_hash=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (hash_password(new_password), uid)
    )
    log(uid, "owner.password_changed", "user", uid)
    return jsonify(ok=True, message="Contraseña del Owner actualizada correctamente.")


@bp.post("/api/admin/users/<int:uid>/role")
@require_permission("admin.roles.write")
def role(uid):
    d = request.get_json() or {}
    name = str(d.get("role", "")).upper()
    if name != "MEMBER":
        return jsonify(ok=False, message="FerreñafeX solo admite los rangos OWNER y MIEMBRO."), 400

    target = q("SELECT r.name role_name FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=?", (uid,), one=True)
    if not target:
        return jsonify(ok=False, message="Usuario no encontrado."), 404
    if target["role_name"] == "OWNER":
        return jsonify(ok=False, message="El Owner es único y no puede modificarse desde aquí."), 403

    rid = role_id(name)
    if not rid:
        return jsonify(ok=False, message="Rol inválido."), 400
    x("UPDATE users SET role_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (rid, uid))
    log(session["user_id"], "role.change", "user", uid, {"role": name})
    notify(uid, "Rol actualizado", f"Tu rol ahora es {name}.", "account", "/profile")
    return jsonify(ok=True, message="Rol actualizado correctamente.")


@bp.post("/api/admin/users/<int:uid>/social-rank")
@require_permission("admin.ranks.write")
def social_rank(uid):
    d = request.get_json() or {}
    rank_id = d.get("rank_id")
    try:
        rank_id = int(rank_id)
    except (TypeError, ValueError):
        return jsonify(ok=False, message="Rango inválido."), 400

    target = q("SELECT r.name role_name FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=?", (uid,), one=True)
    rank = q("SELECT id,name FROM social_ranks WHERE id=?", (rank_id,), one=True)
    if not target:
        return jsonify(ok=False, message="Usuario no encontrado."), 404
    if not rank:
        return jsonify(ok=False, message="Rango social no encontrado."), 404
    if target["role_name"] == "OWNER":
        return jsonify(ok=False, message="El rango social del Owner no se modifica desde esta herramienta."), 403

    x("UPDATE users SET social_rank_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (rank_id, uid))
    log(session["user_id"], "social_rank.change", "user", uid, {"rank_id": rank_id, "rank": rank["name"]})
    notify(uid, "Rango social actualizado", f"Tu rango ahora es: {rank['name']}.", "rank", "/profile")
    return jsonify(ok=True, message="Rango social actualizado correctamente.")


@bp.get("/api/admin/stats")
@require_permission("admin.stats.read")
def stats():
    return jsonify(ok=True, stats={k:q(sql,one=True)["c"] for k,sql in {
        "users":"SELECT COUNT(*) c FROM users",
        "pending_users":"SELECT COUNT(*) c FROM users WHERE status='pending'",
        "approved_users":"SELECT COUNT(*) c FROM users WHERE status='approved'",
        "reports":"SELECT COUNT(*) c FROM reports",
        "active_reports":"SELECT COUNT(*) c FROM reports WHERE status NOT IN ('resolved','closed','rejected')",
        "helps":"SELECT COUNT(*) c FROM help_requests",
        "completed_help":"SELECT COUNT(*) c FROM help_requests WHERE status='completed'",
        "authorities":"SELECT COUNT(*) c FROM authority_requests WHERE status='approved'",
        "posts":"SELECT COUNT(*) c FROM posts",
        "tickets":"SELECT COUNT(*) c FROM support_tickets WHERE status NOT IN ('closed','resolved')",
        "moderation":"SELECT COUNT(*) c FROM moderation_cases WHERE status='open'"
    }.items()})


@bp.get("/api/admin/audit")
@require_permission("admin.audit.read")
def audit():
    return jsonify(ok=True, logs=[dict(r) for r in q("SELECT a.*,u.username actor_username FROM audit_logs a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.created_at DESC LIMIT 200")])


@bp.get("/api/admin/announcements")
@require_permission("admin.dashboard")
def announcements():
    rows=q("SELECT a.*,u.username,u.names,u.last_names FROM announcements a LEFT JOIN users u ON u.id=a.created_by ORDER BY a.created_at DESC LIMIT 100")
    return jsonify(ok=True, announcements=[dict(r) for r in rows])

@bp.post("/api/admin/announcements")
def announcement_create():
    if not can_announce(session.get("user_id")):
        return jsonify(ok=False, message="Solo Owner o VIP puede publicar anuncios."), 403
    d=request.get_json() or {}
    message=html.escape(str(d.get("message","")).strip(), quote=False)[:500]
    color=str(d.get("color","green")).lower()
    animation=str(d.get("animation","fade")).lower()
    font=str(d.get("font","DM Sans"))[:40]
    try: duration=max(120, min(2000, int(d.get("animation_duration_ms",300))))
    except: duration=300
    expires=str(d.get("expires_at","")).strip() or None
    bold=1 if d.get("bold") else 0
    if not message:return jsonify(ok=False,message="Escribe un anuncio."),400
    if color not in ("green","red","white","dark"):return jsonify(ok=False,message="Color inválido."),400
    if animation not in ("fade","slide","soft"):return jsonify(ok=False,message="Animación inválida."),400
    if font not in ("DM Sans","Manrope","Georgia","system-ui","monospace"):return jsonify(ok=False,message="Fuente inválida."),400
    kind="OWNER" if is_owner(session["user_id"]) else "VIP"
    aid=x("INSERT INTO announcements(created_by,message,color,bold,animation,animation_duration_ms,font,expires_at,kind) VALUES(?,?,?,?,?,?,?,?,?)",(session["user_id"],message,color,bold,animation,duration,font,expires,kind))
    x("UPDATE announcements SET active=0 WHERE id<>? AND active=1",(aid,))
    log(session["user_id"],"announcement.created","announcement",aid,{"color":color,"animation":animation,"font":font,"expires_at":expires})
    users=q("SELECT id FROM users WHERE status='approved' AND id<>?",(session["user_id"],))
    for u in users: notify(u["id"],"Nuevo anuncio global",html.unescape(message),"announcement","/dashboard")
    return jsonify(ok=True,id=aid,message="Anuncio publicado para toda la comunidad.")

@bp.put("/api/admin/announcements/<int:aid>")
def announcement_edit(aid):
    if not can_announce(session.get("user_id")): return jsonify(ok=False,message="No tienes permiso para editar anuncios."),403
    d=request.get_json() or {}; row=q("SELECT id FROM announcements WHERE id=?",(aid,),one=True)
    if not row:return jsonify(ok=False,message="Anuncio no encontrado."),404
    message=html.escape(str(d.get("message","")).strip(),quote=False)[:500]
    color=str(d.get("color","green")).lower(); animation=str(d.get("animation","fade")).lower(); font=str(d.get("font","DM Sans"))[:40]
    try: duration=max(120,min(2000,int(d.get("animation_duration_ms",300))))
    except: duration=300
    expires=str(d.get("expires_at","")).strip() or None; bold=1 if d.get("bold") else 0
    if not message:return jsonify(ok=False,message="Escribe un anuncio."),400
    if color not in ("green","red","white","dark") or animation not in ("fade","slide","soft") or font not in ("DM Sans","Manrope","Georgia","system-ui","monospace"):return jsonify(ok=False,message="Configuración inválida."),400
    x("UPDATE announcements SET message=?,color=?,bold=?,animation=?,animation_duration_ms=?,font=?,expires_at=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(message,color,bold,animation,duration,font,expires,aid))
    log(session["user_id"],"announcement.edited","announcement",aid)
    return jsonify(ok=True,message="Anuncio actualizado.")

@bp.post("/api/admin/announcements/<int:aid>/deactivate")
def announcement_deactivate(aid):
    if not can_announce(session.get("user_id")): return jsonify(ok=False,message="No tienes permiso."),403
    if not q("SELECT id FROM announcements WHERE id=?",(aid,),one=True):return jsonify(ok=False,message="Anuncio no encontrado."),404
    x("UPDATE announcements SET active=0,updated_at=CURRENT_TIMESTAMP WHERE id=?",(aid,))
    log(session["user_id"],"announcement.deactivated","announcement",aid)
    return jsonify(ok=True,message="Anuncio desactivado.")

@bp.delete("/api/admin/announcements/<int:aid>")
def announcement_delete(aid):
    if not can_announce(session.get("user_id")): return jsonify(ok=False,message="No tienes permiso."),403
    if not q("SELECT id FROM announcements WHERE id=?",(aid,),one=True):return jsonify(ok=False,message="Anuncio no encontrado."),404
    x("DELETE FROM announcements WHERE id=?",(aid,)); log(session["user_id"],"announcement.deleted","announcement",aid)
    return jsonify(ok=True,message="Anuncio eliminado.")

@bp.get('/api/admin/tickets/archive')
@require_permission('admin.dashboard')
def tickets_archive():
    rows=q("SELECT t.*,u.username,u.names,u.last_names,u.dni FROM support_tickets t JOIN users u ON u.id=t.user_id WHERE t.status IN ('closed','resolved') ORDER BY t.updated_at DESC")
    return jsonify(ok=True,tickets=[dict(r) for r in rows])

@bp.get('/api/admin/badges')
@require_permission("admin.dashboard")
def badges_list():
    return jsonify(ok=True,badges=[dict(r) for r in q("SELECT id,name,description,icon,color FROM badges ORDER BY id")])

@bp.post('/api/admin/badges')
@require_permission("admin.dashboard")
def badge_create():
    d=request.get_json() or {}; name=str(d.get('name','')).strip()[:80]; desc=str(d.get('description','')).strip()[:200]; icon=str(d.get('icon','■'))[:4]; color=str(d.get('color','#22c55e'))[:20]
    if not name or not desc:return jsonify(ok=False,message='Completa nombre y descripción.'),400
    try: bid=x('INSERT INTO badges(name,description,icon,color) VALUES(?,?,?,?)',(name,desc,icon,color))
    except Exception:return jsonify(ok=False,message='Ya existe una insignia con ese nombre.'),400
    log(session['user_id'],'badge.created','badge',bid,{'name':name});return jsonify(ok=True,id=bid,message='Insignia creada.')

@bp.put('/api/admin/badges/<int:bid>')
@require_permission("admin.dashboard")
def badge_edit(bid):
    d=request.get_json() or {}; name=str(d.get('name','')).strip()[:80]; desc=str(d.get('description','')).strip()[:200]; icon=str(d.get('icon','■'))[:4]; color=str(d.get('color','#22c55e'))[:20]
    if not q('SELECT id FROM badges WHERE id=?',(bid,),one=True):return jsonify(ok=False,message='Insignia no encontrada.'),404
    if not name or not desc:return jsonify(ok=False,message='Completa nombre y descripción.'),400
    try:x('UPDATE badges SET name=?,description=?,icon=?,color=? WHERE id=?',(name,desc,icon,color,bid))
    except Exception:return jsonify(ok=False,message='El nombre ya está en uso.'),400
    log(session['user_id'],'badge.edited','badge',bid);return jsonify(ok=True,message='Insignia actualizada.')

@bp.delete('/api/admin/badges/<int:bid>')
@require_permission("admin.dashboard")
def badge_delete(bid):
    if not q('SELECT id FROM badges WHERE id=?',(bid,),one=True):return jsonify(ok=False,message='Insignia no encontrada.'),404
    x('DELETE FROM user_badges WHERE badge_id=?',(bid,));x('DELETE FROM badges WHERE id=?',(bid,));log(session['user_id'],'badge.deleted','badge',bid);return jsonify(ok=True,message='Insignia eliminada.')

@bp.post('/api/admin/users/<int:uid>/badge')
@require_permission("admin.dashboard")
def badge_assign(uid):
    d=request.get_json() or {}
    try:bid=int(d.get('badge_id'))
    except:return jsonify(ok=False,message='Insignia inválida.'),400
    if not q('SELECT id FROM users WHERE id=?',(uid,),one=True) or not q('SELECT id FROM badges WHERE id=?',(bid,),one=True):return jsonify(ok=False,message='Usuario o insignia no encontrada.'),404
    x('INSERT OR IGNORE INTO user_badges(user_id,badge_id) VALUES(?,?)',(uid,bid));log(session['user_id'],'badge.assigned','user',uid,{'badge_id':bid});notify(uid,'Nueva insignia','Se te asignó una insignia.','profile','/profile');return jsonify(ok=True,message='Insignia asignada.')

@bp.delete('/api/admin/users/<int:uid>/badge/<int:bid>')
@require_permission("admin.dashboard")
def badge_unassign(uid,bid):
    x('DELETE FROM user_badges WHERE user_id=? AND badge_id=?',(uid,bid));log(session['user_id'],'badge.removed','user',uid,{'badge_id':bid});return jsonify(ok=True,message='Insignia retirada.')

@bp.get('/api/admin/learning')
@require_permission('admin.dashboard')
def admin_learning():
    return jsonify(ok=True, modules=[dict(r) for r in q('SELECT * FROM learning_modules ORDER BY id DESC')])

@bp.put('/api/admin/learning/<int:mid>')
@require_permission('admin.dashboard')
def admin_learning_edit(mid):
    d=request.get_json() or {}; title=str(d.get('title','')).strip()[:120]; topic=str(d.get('topic','')).strip()[:80]; body=str(d.get('body','')).strip()[:500]; details=str(d.get('details','')).strip()[:4000]
    if not q('SELECT id FROM learning_modules WHERE id=?',(mid,),one=True): return jsonify(ok=False,message='Contenido no encontrado.'),404
    if not title or not topic or not body or not details: return jsonify(ok=False,message='Completa todos los campos.'),400
    x('UPDATE learning_modules SET title=?,topic=?,body=?,details=?,active=1 WHERE id=?',(title,topic,body,details,mid)); log(session['user_id'],'learning.edited','learning',mid); return jsonify(ok=True,message='Contenido actualizado.')

@bp.delete('/api/admin/learning/<int:mid>')
@require_permission('admin.dashboard')
def admin_learning_delete(mid):
    if not q('SELECT id FROM learning_modules WHERE id=?',(mid,),one=True): return jsonify(ok=False,message='Contenido no encontrado.'),404
    x('UPDATE learning_modules SET active=0 WHERE id=?',(mid,)); log(session['user_id'],'learning.deleted','learning',mid); return jsonify(ok=True,message='Contenido eliminado.')

@bp.get('/api/admin/owner-codes')
@require_permission("admin.dashboard")
def owner_codes():
    rows=q("SELECT c.*,u.username used_username FROM owner_codes c LEFT JOIN users u ON u.id=c.used_by ORDER BY c.created_at DESC LIMIT 200")
    return jsonify(ok=True,codes=[dict(r) for r in rows])

@bp.post('/api/admin/owner-codes')
@require_permission("admin.dashboard")
def owner_code_create():
    import secrets
    d=request.get_json() or {}; code_type=str(d.get('type','OWNER')).upper(); expires=str(d.get('expires_at','')).strip() or None
    if code_type not in ('OWNER','VIP'):return jsonify(ok=False,message='Tipo de código inválido.'),400
    if not d.get('permanent') and not expires:return jsonify(ok=False,message='Elige una fecha de expiración o marca permanente.'),400
    prefix='FX-OWNER' if code_type=='OWNER' else 'FX-VIP'
    code=prefix+'-'+secrets.token_hex(5).upper()
    cid=x("INSERT INTO owner_codes(code,role_name,created_by,expires_at) VALUES(?,?,?,?)",(code,code_type,session['user_id'],expires))
    log(session['user_id'],'access_code.created','owner_code',cid,{'type':code_type,'expires_at':expires})
    return jsonify(ok=True,code=code,message=f'Código {code_type} creado.')

@bp.put('/api/admin/owner-codes/<int:cid>')
@require_permission("admin.dashboard")
def owner_code_edit(cid):
    d=request.get_json() or {}; active=1 if d.get('active',True) else 0; expires=str(d.get('expires_at','')).strip() or None
    c=q('SELECT id FROM owner_codes WHERE id=?',(cid,),one=True)
    if not c:return jsonify(ok=False,message='Código no encontrado.'),404
    x('UPDATE owner_codes SET expires_at=?,active=? WHERE id=?',(expires,active,cid));log(session['user_id'],'access_code.edited','owner_code',cid);return jsonify(ok=True,message='Código actualizado.')

@bp.delete('/api/admin/owner-codes/<int:cid>')
@require_permission("admin.dashboard")
def owner_code_delete(cid):
    if not q('SELECT id FROM owner_codes WHERE id=?',(cid,),one=True):return jsonify(ok=False,message='Código no encontrado.'),404
    x('DELETE FROM owner_codes WHERE id=?',(cid,));log(session['user_id'],'access_code.deleted','owner_code',cid);return jsonify(ok=True,message='Código eliminado.')

@bp.post('/api/owner-code/redeem')
def owner_code_redeem():
    uid=session.get('user_id');d=request.get_json() or {};code=str(d.get('code','')).strip().upper()
    if not uid or not code:return jsonify(ok=False,message='Ingresa un código.'),400
    c=q("SELECT * FROM owner_codes WHERE code=? AND active=1 AND used_by IS NULL AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)",(code,),one=True)
    if not c:return jsonify(ok=False,message='Código inválido, usado o vencido.'),400
    if c['role_name']=='VIP':
        badge=q("SELECT id FROM badges WHERE name='VIP'",one=True)
        if not badge:
            bid=x("INSERT INTO badges(name,description,icon,color) VALUES('VIP','Acceso especial temporal','■','#d8b46a')")
        else: bid=badge['id']
        x('INSERT OR IGNORE INTO user_badges(user_id,badge_id) VALUES(?,?)',(uid,bid));x('UPDATE users SET vip_expires_at=? WHERE id=?',(c['expires_at'],uid));message='Código VIP aceptado.'
    else:
        rid=role_id('OWNER');x('UPDATE users SET role_id=?,owner_expires_at=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(rid,c['expires_at'],uid));x("INSERT OR IGNORE INTO user_badges(user_id,badge_id) SELECT ?,id FROM badges WHERE name='Pixel Rojo'",(uid,));message='Código aceptado. Tu rol de sistema ahora es OWNER.'
    x('UPDATE owner_codes SET used_by=?,used_at=CURRENT_TIMESTAMP,active=0 WHERE id=?',(uid,c['id']));log(uid,'access_code.redeemed','user',uid,{'code_id':c['id'],'type':c['role_name']});return jsonify(ok=True,message=message)
