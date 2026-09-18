from functools import wraps
from flask import session,jsonify
from database import q
def has_permission(uid,code):
    u=q('SELECT r.name role_name FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=?',(uid,),one=True)
    if not u:return False
    if u['role_name']=='OWNER':return True
    return bool(q('SELECT 1 FROM role_permissions rp JOIN permissions p ON p.id=rp.permission_id JOIN users u ON u.role_id=rp.role_id WHERE u.id=? AND p.code=?',(uid,code),one=True))
def require_permission(code):
    def deco(fn):
        @wraps(fn)
        def wrap(*a,**kw):
            uid=session.get('user_id')
            if not uid:return jsonify(ok=False,message='Debes iniciar sesión.'),401
            if not has_permission(uid,code):return jsonify(ok=False,message='No tienes permisos para realizar esta acción.'),403
            return fn(*a,**kw)
        return wrap
    return deco
