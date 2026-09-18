"""Carga datos de DEMOSTRACIÓN de forma explícita.
No se ejecuta al iniciar la aplicación. Para volver al estado vacío, elimina database/ferre_alerta.db y ejecuta python app.py.
"""
from pathlib import Path
import sqlite3, hashlib, secrets, uuid
ROOT=Path(__file__).resolve().parents[1]; DB=ROOT/'database'/'ferre_alerta.db'

def hash_password(p):
    salt=secrets.token_bytes(16); h=hashlib.scrypt(p.encode(),salt=salt,n=2**14,r=8,p=1,dklen=64); return f'scrypt${salt.hex()}${h.hex()}'

def add_user(c,dni,names,last,username,email,phone,password,role,authority_type=None):
    rid=c.execute('SELECT id FROM roles WHERE name=?',(role,)).fetchone()[0]
    sr=c.execute("SELECT id FROM social_ranks ORDER BY min_points LIMIT 1").fetchone()[0]
    cur=c.execute('INSERT INTO users(dni,names,last_names,username,email,phone,password_hash,role_id,social_rank_id,status,demo_flag,authority_type) VALUES(?,?,?,?,?,?,?,?,?,?,1,?)',(dni,names,last,username,email,phone,hash_password(password),rid,sr,'approved',authority_type))
    return cur.lastrowid

con=sqlite3.connect(DB);con.row_factory=sqlite3.Row
with con:
    # Base rows are seeded by app.py, but make seed independently usable.
    for r in ['CITIZEN','COLLABORATOR','STAFF','AUTHORITY','OWNER']:con.execute('INSERT OR IGNORE INTO roles(name) VALUES(?)',(r,))
    for r in [('Vecino solidario',0,'Participación inicial'),('Colaborador',50,'Ayudas confirmadas'),('Comunidad activa',150,'Participación constante'),('Colaborador destacado',400,'Aportes destacados'),('Embajador comunitario',1000,'Referente social por participación')]:con.execute('INSERT OR IGNORE INTO social_ranks(name,min_points,description) VALUES(?,?,?)',r)
    if con.execute("SELECT COUNT(*) FROM users WHERE demo_flag=1").fetchone()[0]:
        raise SystemExit('Los datos de demostración ya existen. Elimina la base de datos para reconstruir el entorno demo.')
    ids={}
    ids['citizen']=add_user(con,'11111111','María','Demo','maria_demo','maria.demo@demo.local','900000001','Demo12345!','CITIZEN')
    ids['collab']=add_user(con,'22222222','Carlos','Demo','carlos_demo','carlos.demo@demo.local','900000002','Demo12345!','COLLABORATOR')
    ids['staff']=add_user(con,'33333333','Staff','Demo','staff_demo','staff.demo@demo.local','900000003','Demo12345!','STAFF')
    ids['police']=add_user(con,'44444444','Policía','Demo','policia_demo','policia.demo@demo.local','900000004','Demo12345!','AUTHORITY','Policía')
    ids['fire']=add_user(con,'55555555','Bomberos','Demo','bomberos_demo','bomberos.demo@demo.local','900000005','Demo12345!','AUTHORITY','Bomberos')
    ids['health']=add_user(con,'66666666','Salud','Demo','salud_demo','salud.demo@demo.local','900000006','Demo12345!','AUTHORITY','Salud')
    ids['owner']=add_user(con,'77777777','Owner','Demo','owner_demo','owner.demo@demo.local','900000007','DemoOwner123!','OWNER')
    for u in (ids['citizen'],ids['collab'],ids['police']):
        con.execute('INSERT OR IGNORE INTO points(user_id,amount,reason) VALUES(?,?,?)',(u,100,'Datos de demostración'))
    con.execute('INSERT INTO posts(user_id,content) VALUES(?,?)',(ids['citizen'],'DATOS DE DEMOSTRACIÓN · Aviso comunitario ficticio.'))
    con.execute('INSERT INTO forums(category,title,content,user_id) VALUES(?,?,?,?)',('Comunidad','DATOS DE DEMOSTRACIÓN · Tema de prueba','Tema ficticio para demostración universitaria.',ids['citizen']))
    con.execute('INSERT INTO rooms(name,owner_id) VALUES(?,?)',('DATOS DE DEMOSTRACIÓN · Vecinos',ids['collab']))
    room=con.execute('SELECT last_insert_rowid()').fetchone()[0]
    con.execute('INSERT INTO room_members(room_id,user_id,member_role) VALUES(?,?,?)',(room,ids['collab'],'owner'))
    con.execute('INSERT OR IGNORE INTO friends(user_id,friend_id) VALUES(?,?),(?,?)',(ids['citizen'],ids['collab'],ids['collab'],ids['citizen']))
    con.execute('INSERT INTO reports(public_id,user_id,category,description,priority,latitude,longitude,status) VALUES(?,?,?,?,?,?,?,?)',('FX-DEMO001',ids['citizen'],'Ambiente','DATOS DE DEMOSTRACIÓN · Reporte ficticio.','normal',-6.639, -79.788,'received'))
    h=con.execute('INSERT INTO help_requests(user_id,help_type,description,priority,latitude,longitude,radius_m) VALUES(?,?,?,?,?,?,?)',(ids['citizen'],'Agua','DATOS DE DEMOSTRACIÓN · Solicitud ficticia.', 'normal',-6.640,-79.789,1000)).lastrowid
    con.execute('INSERT INTO help_offers(help_id,helper_id,status) VALUES(?,?,?)',(h,ids['collab'],'accepted'))
    con.execute('INSERT INTO support_tickets(public_id,user_id,subject,category,message,priority) VALUES(?,?,?,?,?,?)',('TKT-DEMO001',ids['citizen'],'DATOS DE DEMOSTRACIÓN · Ticket ficticio','Soporte','Ticket ficticio para probar atención.','normal'))
print('Datos de DEMOSTRACIÓN creados.')
print('Usuarios demo: contraseña general Demo12345! · owner_demo usa DemoOwner123!')
