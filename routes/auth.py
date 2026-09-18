from flask import Blueprint,request,jsonify,session,render_template,url_for,current_app
from database import q,x
from services.auth_service import hash_password,verify_password,role_id,user_by_username
from services.audit_service import log
from services.gamification_service import refresh_rank
import re
bp=Blueprint('auth',__name__)
@bp.get('/login')
def login_page():return render_template('login.html')
@bp.get('/register')
def register_page():return render_template('register.html')
@bp.get('/forgot-password')
def forgot_page():return render_template('forgot.html')
@bp.get('/pending')
def pending_page():return render_template('pending.html')
@bp.get('/owner-access')
def owner_page():return render_template('owner_access.html')
@bp.post('/api/register')
def register():
 d=request.get_json() or {};need=['dni','names','last_names','username','phone','password','confirm_password']
 if any(not str(d.get(k,'')).strip() for k in need):return jsonify(ok=False,message='Completa los campos obligatorios.'),400
 if d['password']!=d['confirm_password'] or len(d['password'])<8:return jsonify(ok=False,message='Contraseña inválida o no coincidente.'),400
 if not re.fullmatch(r'\d{8}',str(d['dni'])):return jsonify(ok=False,message='El DNI debe contener 8 dígitos.'),400
 if q('SELECT 1 FROM users WHERE dni=? OR lower(username)=lower(?)',(d['dni'],d['username']),one=True):return jsonify(ok=False,message='DNI o usuario ya registrado.'),409
 uid=x('INSERT INTO users(dni,names,last_names,username,email,phone,birth_date,password_hash,role_id,status) VALUES(?,?,?,?,?,?,?,?,?,?)',(d['dni'],d['names'],d['last_names'],d['username'],d.get('email') or None,d['phone'],d.get('birth_date') or None,hash_password(d['password']),role_id('CITIZEN'),'pending'));refresh_rank(uid);log(uid,'user.created','user',uid,{'status':'pending'});return jsonify(ok=True,message='Registro enviado. Tu cuenta queda pendiente de aprobación.')
@bp.post('/api/login')
def login():
 d=request.get_json() or {}
 identifier=str(d.get('username',d.get('identifier',''))).strip()
 u=user_by_username(identifier)
 if not u and re.fullmatch(r'\d{8}',identifier):
  u=q("SELECT u.*,r.name role_name FROM users u JOIN roles r ON r.id=u.role_id WHERE u.dni=?",(identifier,),one=True)
 if not u or not verify_password(str(d.get('password','')),u['password_hash']):return jsonify(ok=False,message='Usuario o contraseña incorrectos.'),401
 if u['status']!='approved':
  if u['status']=='pending': return jsonify(ok=False,message='Tu cuenta está pendiente de aprobación.',redirect='/pending'),403
  return jsonify(ok=False,message=f'Tu cuenta está {u["status"]}.'),403
 session.clear();session['user_id']=u['id'];session['role']=u['role_name'];log(u['id'],'auth.login');return jsonify(ok=True,redirect=url_for('main.dashboard'))
@bp.post('/api/logout')
def logout():session.clear();return jsonify(ok=True,redirect='/login')
@bp.post('/api/forgot-password')
def forgot():
 d=request.get_json() or {};u=q('SELECT id FROM users WHERE dni=? AND phone=?',(d.get('dni'),d.get('phone')),one=True)
 if not u:return jsonify(ok=False,message='No encontramos una cuenta con esos datos.'),404
 if not d.get('new_password'):return jsonify(ok=True,message='Identidad validada. Define una nueva contraseña.')
 if len(d['new_password'])<8:return jsonify(ok=False,message='La nueva contraseña debe tener al menos 8 caracteres.'),400
 x('UPDATE users SET password_hash=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(hash_password(d['new_password']),u['id']));log(u['id'],'auth.password_reset','user',u['id']);return jsonify(ok=True,message='Contraseña actualizada.')
@bp.post('/api/owner/access')
def owner_access():
 d=request.get_json() or {}
 code=str(d.get('code','')).strip()
 if not code:return jsonify(ok=False,message='Ingresa el código de propietario.'),400
 if code!=current_app.config['OWNER_CODE']:return jsonify(ok=False,message='Código Owner incorrecto.'),401
 owner=q("SELECT u.id,u.status,r.name role_name FROM users u JOIN roles r ON r.id=u.role_id WHERE r.name='OWNER' LIMIT 1",one=True)
 if not owner:
  uid=x("INSERT INTO users(names,last_names,username,email,password_hash,role_id,status) VALUES(?,?,?,?,?,?,?)",('Propietario','Principal','owner','owner@local',hash_password(code),role_id('OWNER'),'approved'));refresh_rank(uid);owner_id=uid;log(uid,'owner.bootstrap','user',uid,{'method':'owner_code'})
 else:
  owner_id=owner['id']
  if owner['status']!='approved':return jsonify(ok=False,message=f"La cuenta Owner está {owner['status']}.") ,403
  log(owner_id,'owner.login','user',owner_id,{'method':'owner_code'})
 session.clear();session['user_id']=owner_id;session['role']='OWNER';return jsonify(ok=True,redirect=url_for('main.dashboard'),message='Acceso Owner autorizado correctamente.')
