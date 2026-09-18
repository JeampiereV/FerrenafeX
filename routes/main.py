from flask import Blueprint,render_template,session,redirect,url_for,jsonify,request,current_app
from database import q,x
from services.auth_service import role_id
from services.file_service import save_upload
from pathlib import Path
bp=Blueprint('main',__name__)
@bp.get('/')
def landing():return render_template('landing.html')
@bp.get('/dashboard')
def dashboard():
 uid=session.get('user_id')
 if not uid:return redirect(url_for('auth.login_page'))
 u=q('SELECT u.*,r.name role_name,sr.name social_rank_name,(SELECT COALESCE(SUM(amount),0) FROM points WHERE user_id=u.id) points FROM users u JOIN roles r ON r.id=u.role_id LEFT JOIN social_ranks sr ON sr.id=u.social_rank_id WHERE u.id=?',(uid,),one=True)
 return render_template('dashboard.html',user=u)
@bp.get('/profile')
def profile():
 uid=session.get('user_id')
 if not uid:return redirect('/login')
 target=request.args.get('user',type=int) or uid
 u=q('SELECT u.*,r.name role_name,sr.name social_rank_name,(SELECT COALESCE(SUM(amount),0) FROM points WHERE user_id=u.id) points FROM users u JOIN roles r ON r.id=u.role_id LEFT JOIN social_ranks sr ON sr.id=u.social_rank_id WHERE u.id=? AND u.status=\'approved\'',(target,),one=True)
 if not u:return render_template('404.html'),404
 b=q('SELECT b.* FROM badges b JOIN user_badges ub ON ub.badge_id=b.id WHERE ub.user_id=?',(target,))
 return render_template('profile.html',user=u,badges=b,own=(target==uid))
@bp.post('/api/profile')
def profile_update():
 uid=session.get('user_id')
 if not uid:return jsonify(ok=False,message='No autenticado.'),401
 d=request.get_json() or {};x('UPDATE users SET bio=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(str(d.get('bio',''))[:500],uid));return jsonify(ok=True,message='Perfil actualizado.')
@bp.post('/api/profile/photo')
def profile_photo():
 uid=session.get('user_id')
 if not uid:return jsonify(ok=False,message='No autenticado.'),401
 f=request.files.get('photo');saved,err=save_upload(f,current_app.config['UPLOAD_ROOT']/'profiles')
 if err:return jsonify(ok=False,message=err),400
 rel=Path(saved['path']).name
 x('UPDATE users SET profile_photo=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(rel,uid));return jsonify(ok=True,message='Foto actualizada.')
@bp.get('/learning')
def learning():return render_template('learning.html')
@bp.get('/api/learning')
def learning_api():return jsonify(ok=True,modules=[dict(r) for r in q('SELECT id,title,topic,body FROM learning_modules WHERE active=1')])
@bp.post('/api/learning/<int:mid>/complete')
def learning_complete(mid):
 from services.gamification_service import award,badge
 uid=session.get('user_id');m=q('SELECT * FROM learning_modules WHERE id=?',(mid,),one=True)
 if not uid or not m:return jsonify(ok=False,message='No disponible.'),400
 if not q('SELECT 1 FROM learning_results WHERE module_id=? AND user_id=?',(mid,uid),one=True):x('INSERT INTO learning_results(module_id,user_id,score,points_awarded) VALUES(?,?,?,?)',(mid,100,m['points']));award(uid,m['points'],'Módulo de aprendizaje completado','learning',mid);badge(uid,'Aprendiz de prevención')
 return jsonify(ok=True,message='Módulo completado.')
