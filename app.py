from flask import Flask,session,jsonify,render_template,redirect,url_for,request,send_from_directory
from pathlib import Path
from config import Config
from database import init_db,close_db,q,x
from services.csrf_service import get_token, validate_request

def seed_base():
    for r in ['CITIZEN','COLLABORATOR','STAFF','AUTHORITY','OWNER'] : x('INSERT OR IGNORE INTO roles(name) VALUES(?)',(r,))
    for r in [('Vecino solidario',0,'Participación inicial'),('Colaborador',50,'Ayudas confirmadas'),('Comunidad activa',150,'Participación constante'),('Colaborador destacado',400,'Aportes destacados'),('Embajador comunitario',1000,'Referente social por participación')]:x('INSERT OR IGNORE INTO social_ranks(name,min_points,description) VALUES(?,?,?)',r)
    perms={'admin.dashboard':'Owner panel','admin.users.read':'Consultar usuarios','admin.users.write':'Modificar usuarios','admin.roles.write':'Cambiar roles','admin.ranks.read':'Consultar rangos','admin.ranks.write':'Modificar rangos','admin.stats.read':'Estadísticas','admin.audit.read':'Auditoría','moderation.review':'Moderación','authority.review':'Revisión de autoridades','authority.reinforcement':'Refuerzo interno','support.manage':'Gestionar tickets','room.manage':'Administrar salas','room.read':'Comandos de sala'}
    for c,d in perms.items():x('INSERT OR IGNORE INTO permissions(code,description) VALUES(?,?)',(c,d))
    rolemap={'OWNER':list(perms),'STAFF':['admin.users.read','admin.users.write','moderation.review','authority.review','support.manage','admin.stats.read','room.manage','room.read'],'AUTHORITY':['authority.reinforcement','room.manage','room.read'],'COLLABORATOR':['room.read'],'CITIZEN':['room.read']}
    for role,codes in rolemap.items():
        rid=q('SELECT id FROM roles WHERE name=?',(role,),one=True)['id']
        for c in codes:
            pid=q('SELECT id FROM permissions WHERE code=?',(c,),one=True)['id'];x('INSERT OR IGNORE INTO role_permissions(role_id,permission_id) VALUES(?,?)',(rid,pid))
    for b in [('Primera ayuda','Primera ayuda confirmada','✦'),('Buen vecino','Participación comunitaria','◎'),('Protector del entorno','Actividad ambiental','◈'),('Comunidad activa','Participación recurrente','◇'),('Gran colaborador','Ayudas confirmadas','★'),('Aprendiz de prevención','Aprendizaje','△')]:x('INSERT OR IGNORE INTO badges(name,description,icon) VALUES(?,?,?)',b)
    for c in [('/help','Muestra comandos disponibles','/help','/help','basic'),('/rango list','Lista rangos','/rango list','/rango list','admin.ranks.read'),('/rango set RANGO DNI','Asigna rango social','/rango set RANGO DNI','/rango set Colaborador 12345678','admin.ranks.write'),('/rango remove DNI','Retira rango','/rango remove DNI','/rango remove 12345678','admin.ranks.write'),('/party add DNI','Agrega usuario','/party add DNI','/party add 12345678','room.manage'),('/party remove DNI','Retira usuario','/party remove DNI','/party remove 12345678','room.manage'),('/party members','Lista miembros','/party members','/party members','room.read'),('/party info','Info sala','/party info','/party info','room.read'),('/party leave','Salir','/party leave','/party leave','room.read')]:x('INSERT OR IGNORE INTO commands(name,description,syntax,example,permission_code) VALUES(?,?,?,?,?)',c)
    for m in [('Inundaciones','inundaciones','Cómo actuar sin exponerse a corrientes o estructuras inestables.',20),('Cables eléctricos caídos','electricidad','No tocar ni acercarse; aislar y comunicar a los canales oficiales.',20),('Kit de emergencia','prevención','Agua segura, linterna, radio, botiquín y documentos protegidos.',20)]:x('INSERT OR IGNORE INTO learning_modules(title,topic,body,points) VALUES(?,?,?,?)',m)

def create_app(test_config=None):
    app=Flask(__name__);app.config.from_object(Config)
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
    for bp in [auth,main,reports,helpbp,comm,admin,authority,tickets,moderation,search]:app.register_blueprint(bp)

    @app.before_request
    def csrf_guard():
        if request.method in ('POST','PUT','PATCH','DELETE') and request.path.startswith('/api/'):
            if not validate_request():
                return jsonify(ok=False, message='Solicitud no válida. Actualiza la página e inténtalo nuevamente.'), 400
    @app.context_processor
    def globals_():
        uid=session.get('user_id');u=None;n=0
        if uid:
            u=q('SELECT u.id,u.username,u.names,r.name role_name,sr.name social_rank_name FROM users u JOIN roles r ON r.id=u.role_id LEFT JOIN social_ranks sr ON sr.id=u.social_rank_id WHERE u.id=?',(uid,),one=True)
            n=q('SELECT COUNT(*) c FROM notifications WHERE user_id=? AND read_at IS NULL',(uid,),one=True)['c']
        return {'nav_user':u,'notification_count':n,'csrf_token':get_token()}
    @app.get('/media/profile/<path:filename>')
    def profile_media(filename):
        return send_from_directory(Path(app.config['UPLOAD_ROOT'])/'profiles', filename)

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

    return app
app=create_app()

if __name__=='__main__':
    app.run(host='0.0.0.0',port=int(__import__('os').getenv('PORT','5000')),debug=__import__('os').getenv('FLASK_DEBUG','0')=='1')
