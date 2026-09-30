from flask import Flask,session,jsonify,render_template,redirect,url_for,request,send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix
from pathlib import Path
from config import Config
from database import init_db,close_db,q,x
from services.csrf_service import get_token, validate_request
from extensions import socketio

def seed_base():
    for r in ['MEMBER','OWNER'] : x('INSERT OR IGNORE INTO roles(name) VALUES(?)',(r,))
    for r in [('Vecino solidario',0,'Participación inicial'),('Colaborador',50,'Ayudas confirmadas'),('Comunidad activa',150,'Participación constante'),('Colaborador destacado',400,'Aportes destacados'),('Embajador comunitario',1000,'Referente social por participación')]:x('INSERT OR IGNORE INTO social_ranks(name,min_points,description) VALUES(?,?,?)',r)
    perms={'admin.dashboard':'Owner panel','admin.users.read':'Consultar usuarios','admin.users.write':'Modificar usuarios','admin.roles.write':'Cambiar roles','admin.ranks.read':'Consultar rangos','admin.ranks.write':'Modificar rangos','admin.stats.read':'Estadísticas','admin.audit.read':'Auditoría','moderation.review':'Moderación','authority.review':'Revisión de autoridades','authority.reinforcement':'Refuerzo interno','support.manage':'Gestionar tickets','room.manage':'Administrar salas','room.read':'Comandos de sala'}
    for c,d in perms.items():x('INSERT OR IGNORE INTO permissions(code,description) VALUES(?,?)',(c,d))
    rolemap={'OWNER':list(perms),'MEMBER':['room.read']}
    for role,codes in rolemap.items():
        rid=q('SELECT id FROM roles WHERE name=?',(role,),one=True)['id']
        for c in codes:
            pid=q('SELECT id FROM permissions WHERE code=?',(c,),one=True)['id'];x('INSERT OR IGNORE INTO role_permissions(role_id,permission_id) VALUES(?,?)',(rid,pid))
    for b in [('Primera ayuda','Primera ayuda confirmada','✦'),('Buen vecino','Participación comunitaria','◎'),('Protector del entorno','Actividad ambiental','◈'),('Comunidad activa','Participación recurrente','◇'),('Gran colaborador','Ayudas confirmadas','★'),('Aprendiz de prevención','Aprendizaje','△'),('Pixel Rojo','Insignia de propietario','■'),('Pixel Verde','Ciudadanía comunitaria','■')]:x('INSERT OR IGNORE INTO badges(name,description,icon) VALUES(?,?,?)',b)
    x("INSERT OR IGNORE INTO user_badges(user_id,badge_id) SELECT u.id,b.id FROM users u JOIN roles r ON r.id=u.role_id JOIN badges b ON b.name='Pixel Rojo' WHERE r.name='OWNER'")
    x("INSERT OR IGNORE INTO user_badges(user_id,badge_id) SELECT u.id,b.id FROM users u JOIN roles r ON r.id=u.role_id JOIN badges b ON b.name='Pixel Verde' WHERE r.name='MEMBER' AND u.status='approved'")
    for c in [('/help','Muestra comandos disponibles','/help','/help','basic'),('/party add ID','Agrega usuario por ID','/party add ID','/party add 12345678','room.manage'),('/party remove ID','Retira usuario','/party remove ID','/party remove 12345678','room.manage'),('/party public','Hace pública la sala','/party public','/party public','room.manage'),('/party priv','Hace privada la sala','/party priv','/party priv','room.manage'),('/party members','Lista miembros','/party members','/party members','room.read'),('/party info','Info sala','/party info','/party info','room.read'),('/party leave','Salir','/party leave','/party leave','room.read'),('/say COLOR MENSAJE','Publica un anuncio global (solo Owner)','/say 1 MENSAJE','/say 1 &l IMPORTANTE: Nuevo aviso','admin.dashboard')]:x('INSERT OR IGNORE INTO commands(name,description,syntax,example,permission_code) VALUES(?,?,?,?,?)',c)
    for m in [('Inundaciones','inundaciones','Cómo actuar sin exponerse a corrientes o estructuras inestables.','Evita cruzar corrientes, aléjate de puentes o estructuras dañadas, corta la electricidad solo si hacerlo es seguro y sigue las indicaciones oficiales.'),('Cables eléctricos caídos','electricidad','No tocar ni acercarse; aislar y comunicar a los canales oficiales.','Mantén distancia, evita charcos cercanos y comunica la ubicación a los servicios correspondientes. Nunca intentes mover el cable.'),('Kit de emergencia','prevención','Agua segura, linterna, radio, botiquín y documentos protegidos.','Prepara agua, alimentos no perecibles, linterna, radio, botiquín, documentos y contactos de emergencia en un lugar accesible.')]:x('INSERT OR IGNORE INTO learning_modules(title,topic,body,details,points) VALUES(?,?,?,?,0)',m)

def create_app(test_config=None):
    app=Flask(__name__);app.config.from_object(Config);app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1,x_host=1)
    if test_config:app.config.update(test_config)
    for d in ['reports','profiles','authority']:Path(app.config['UPLOAD_ROOT'],d).mkdir(parents=True,exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context():init_db();seed_base()
    from routes.auth import bp as auth
    from routes.main import bp as main
    from routes.reports import bp as reports
    from routes.help import bp as helpbp
    from routes.community import bp as comm
    from routes.admin import bp as admin
    from routes.authority import bp as authority
    from routes.tickets import bp as tickets
    from routes.moderation import bp as moderation
    from routes.search import bp as search
    from routes.tools import bp as tools
    for bp in [auth,main,reports,helpbp,comm,admin,authority,tickets,moderation,search,tools]:app.register_blueprint(bp)
    socketio.init_app(app)

    @app.before_request
    def expire_access():
        uid=session.get('user_id')
        if uid:
            try:
                owner=q("SELECT r.name, u.owner_expires_at FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=?",(uid,),one=True)
                if owner and owner['name']=='OWNER' and owner['owner_expires_at'] and q("SELECT datetime(?) <= datetime('now') AS expired",(owner['owner_expires_at'],),one=True)['expired']:
                    rid=q("SELECT id FROM roles WHERE name='MEMBER'",one=True)['id']
                    x("UPDATE users SET role_id=?,owner_expires_at=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",(rid,uid))
                    pb=q("SELECT id FROM badges WHERE name='Pixel Rojo'",one=True)
                    if pb: x("DELETE FROM user_badges WHERE user_id=? AND badge_id=?",(uid,pb['id']))
                vip=q("SELECT vip_expires_at FROM users WHERE id=?",(uid,),one=True)
                if vip and vip['vip_expires_at'] and q("SELECT datetime(?) <= datetime('now') AS expired",(vip['vip_expires_at'],),one=True)['expired']:
                    vb=q("SELECT id FROM badges WHERE name='VIP'",one=True)
                    if vb: x("DELETE FROM user_badges WHERE user_id=? AND badge_id=?",(uid,vb['id']))
                    x("UPDATE users SET vip_expires_at=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",(uid,))
            except Exception:
                pass

    @app.before_request
    def csrf_guard():
        if request.method in ('POST','PUT','PATCH','DELETE') and request.path.startswith('/api/'):
            if not validate_request():
                return jsonify(ok=False, message='Tu sesión cambió o quedó desactualizada. Recarga la página e inténtalo nuevamente.'), 400
    @app.context_processor
    def globals_():
        uid=session.get('user_id');u=None;n=0
        if uid:
            u=q('SELECT u.id,u.username,u.names,u.last_names,u.vip_expires_at,r.name role_name,sr.name social_rank_name FROM users u JOIN roles r ON r.id=u.role_id LEFT JOIN social_ranks sr ON sr.id=u.social_rank_id WHERE u.id=?',(uid,),one=True)
            n=q('SELECT COUNT(*) c FROM notifications WHERE user_id=? AND read_at IS NULL',(uid,),one=True)['c']
        announcement=None
        if uid:
            try:
                announcement=q("SELECT a.id,a.message,a.color,a.bold,a.animation,a.animation_duration_ms,a.font,a.kind,u.names,u.last_names,u.username FROM announcements a JOIN users u ON u.id=a.created_by WHERE a.active=1 AND (a.expires_at IS NULL OR a.expires_at > CURRENT_TIMESTAMP) ORDER BY a.created_at DESC LIMIT 1",one=True)
                if announcement:
                    announcement=dict(announcement); announcement['display_message']=f"{announcement['kind']} ({announcement['names']} {announcement['last_names']}) DICE: {announcement['message']}"
            except Exception:
                announcement=None
        return {'nav_user':u,'notification_count':n,'csrf_token':get_token(),'global_announcement':announcement,'is_vip': bool(u and u['vip_expires_at'] and u['vip_expires_at'] > __import__('datetime').datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))}
    @app.get('/media/profile/<path:filename>')
    def profile_media(filename):
        return send_from_directory(Path(app.config['UPLOAD_ROOT'])/'profiles', filename)

    @app.get('/api/announcement/current')
    def current_announcement():
        if not session.get('user_id'): return jsonify(ok=False,message='No autenticado.'),401
        a=q("SELECT a.id,a.message,a.color,a.bold,a.animation,a.animation_duration_ms,a.font,a.kind,u.names,u.last_names FROM announcements a JOIN users u ON u.id=a.created_by WHERE a.active=1 AND (a.expires_at IS NULL OR a.expires_at > CURRENT_TIMESTAMP) ORDER BY a.created_at DESC LIMIT 1",one=True)
        if not a:return jsonify(ok=True,announcement=None)
        d=dict(a);d['display_message']=f"{d['kind']} ({d['names']} {d['last_names']}) DICE: {d['message']}";return jsonify(ok=True,announcement=d)

    @app.get('/logout')
    def logout():
        session.clear()
        return redirect(url_for('auth.login'))

    @app.errorhandler(413)
    def too_big(_):
        return jsonify(ok=False,message='El archivo es demasiado grande.'),413

    @app.errorhandler(403)
    def e403(_):
        return render_template('403.html'),403

    @app.errorhandler(404)
    def e404(_):
        return render_template('404.html'),404

    @app.errorhandler(500)
    def e500(_):
        # Never expose Flask/Python internals to citizens.
        try:
            from services.audit_service import log
            log(session.get('user_id'), 'server.error', 'system', None)
        except Exception:
            pass
        return render_template('500.html'),500

    @app.after_request
    def security_headers(response):
        response.headers.setdefault('X-Content-Type-Options','nosniff')
        response.headers.setdefault('X-Frame-Options','SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy','strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy','geolocation=(self),camera=(),microphone=()')
        if request.path.startswith(('/dashboard','/profile','/owner','/staff','/authority','/notifications','/friends','/chat','/rooms','/tickets','/reports','/map','/help','/learning','/local','/forum','/search')):
            response.headers['Cache-Control']='no-store'
        return response

    from flask_socketio import emit, join_room

    @socketio.on('connect')
    def socket_connect():
        uid=session.get('user_id')
        if not uid:
            return False
        join_room(f'user:{uid}')
        emit('socket_ready', {'user_id': uid})

    @socketio.on('join_room')
    def socket_join_room(data):
        uid=session.get('user_id')
        try:
            rid=int((data or {}).get('room_id', 0))
        except (TypeError, ValueError):
            return
        if not uid or not rid:
            return
        room=q("SELECT * FROM rooms WHERE id=? AND status='active'", (rid,), one=True)
        member=q('SELECT * FROM room_members WHERE room_id=? AND user_id=?', (rid,uid), one=True)
        owner=q("SELECT 1 FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=? AND r.name='OWNER'", (uid,), one=True)
        if not room or (not member and not owner and room['visibility'] != 'public'):
            return
        join_room(f'room:{rid}')
        emit('room_joined', {'room_id': rid})

    return app
app=create_app()

if __name__=='__main__':
    socketio.run(app,host='0.0.0.0',port=int(__import__('os').getenv('PORT','5000')),debug=__import__('os').getenv('FLASK_DEBUG','0')=='1')
