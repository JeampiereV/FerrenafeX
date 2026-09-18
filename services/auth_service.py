import hashlib,secrets
from database import q,x
def hash_password(p):
    s=secrets.token_bytes(16); h=hashlib.scrypt(p.encode(),salt=s,n=2**14,r=8,p=1,dklen=64); return f'scrypt${s.hex()}${h.hex()}'
def verify_password(p,e):
    try:
        _,s,h=e.split('$',2); d=hashlib.scrypt(p.encode(),salt=bytes.fromhex(s),n=2**14,r=8,p=1,dklen=64); return secrets.compare_digest(d.hex(),h)
    except Exception:return False
def role_id(name):
    r=q('SELECT id FROM roles WHERE name=?',(name,),one=True); return r['id'] if r else None
def user_by_username(u): return q('SELECT u.*,r.name role_name,sr.name social_rank_name FROM users u JOIN roles r ON r.id=u.role_id LEFT JOIN social_ranks sr ON sr.id=u.social_rank_id WHERE lower(u.username)=lower(?)',(u,),one=True)
