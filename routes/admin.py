from datetime import date

from flask import Blueprint, request, jsonify, session, render_template

from database import q, x
from services.permission_service import require_permission
from services.audit_service import log
from services.auth_service import role_id
from services.notification_service import notify

bp = Blueprint("admin", __name__)


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

    x("UPDATE users SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (st, uid))
    log(session["user_id"], "user.status", "user", uid, {"status": st})
    if st == "approved":
        notify(uid, "Cuenta aprobada", "Tu cuenta ya está activa. Puedes iniciar sesión.", "account", "/login")
    elif st in ("rejected", "suspended", "blocked"):
        notify(uid, "Estado de cuenta actualizado", f"Tu cuenta ahora está: {st}.", "account", "/login")
    return jsonify(ok=True, message="Estado actualizado correctamente.")


@bp.post("/api/admin/users/<int:uid>/role")
@require_permission("admin.roles.write")
def role(uid):
    d = request.get_json() or {}
    name = str(d.get("role", "")).upper()
    if name not in ("CITIZEN", "COLLABORATOR", "STAFF"):
        return jsonify(ok=False, message="Ese rol no se puede asignar desde administración general. Las autoridades requieren verificación y Owner es único."), 400

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


@bp.post("/api/commands")
def command():
    uid = session.get("user_id")
    if not uid:
        return jsonify(ok=False, message="Debes iniciar sesión."), 401
    from services.command_service import run
    d = request.get_json() or {}
    return jsonify(run(uid, str(d.get("command", "")), d.get("room_id"), d.get("context", "general")))
