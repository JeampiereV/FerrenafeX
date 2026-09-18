from database import q, x
from services.permission_service import has_permission
from services.audit_service import log
from services.notification_service import notify

def commands(uid, context='general'):
    rows = q('SELECT name,description,syntax,example,permission_code FROM commands ORDER BY id')
    out=[]
    for r in rows:
        if r['permission_code']=='basic' or has_permission(uid,r['permission_code']):
            if context=='room' and (r['name'].startswith('/party') or r['name']=='/help'):
                out.append(dict(r))
            elif context=='authority' and (r['name'].startswith('/rango') or r['name']=='/help'):
                out.append(dict(r))
            elif context not in ('room','authority') and not r['name'].startswith('/party'):
                out.append(dict(r))
    return out

def run(uid,text,room=None,context='general'):
    p=(text or '').strip().split()
    if not p or not p[0].startswith('/'):
        return {'ok':False,'message':'Los comandos deben comenzar con /'}
    cmd=p[0].lower()
    if cmd=='/help':
        return {'ok':True,'commands':commands(uid,context)}
    if cmd=='/rango':
        if len(p)<2:return {'ok':False,'message':'Sintaxis: /rango list | /rango set RANGO DNI | /rango remove DNI'}
        if p[1]=='list':
            if not has_permission(uid,'admin.ranks.read'):return {'ok':False,'message':'No tienes permisos para ejecutar este comando.'}
            return {'ok':True,'ranks':[dict(r) for r in q('SELECT id,name,min_points,description FROM social_ranks ORDER BY min_points')]}
        if p[1]=='set':
            if len(p)<4:return {'ok':False,'message':'Sintaxis: /rango set RANGO DNI'}
            if not has_permission(uid,'admin.ranks.write'):return {'ok':False,'message':'No tienes permisos para ejecutar este comando.'}
            target=q('SELECT id FROM users WHERE dni=?',(p[-1],),one=True)
            if not target:return {'ok':False,'message':'No se encontró un usuario con ese DNI.'}
            target=target['id']
            name=' '.join(p[2:-1]);r=q('SELECT id,name FROM social_ranks WHERE lower(name)=lower(?)',(name,),one=True)
            if not q('SELECT id FROM users WHERE id=?',(target,),one=True):return {'ok':False,'message':'No se encontró el usuario indicado.'}
            if not r:return {'ok':False,'message':'Rango no válido.'}
            x('UPDATE users SET social_rank_id=? WHERE id=?',(r['id'],target));log(uid,'rank.set','user',target,{'rank':r['name']});notify(target,'Tu rango fue actualizado',f'Ahora tienes el rango social {r["name"]}.','profile','/profile');return {'ok':True,'message':'✓ Rango actualizado correctamente.'}
        if p[1]=='remove':
            if len(p)!=3:return {'ok':False,'message':'Sintaxis: /rango remove DNI'}
            if not has_permission(uid,'admin.ranks.write'):return {'ok':False,'message':'No tienes permisos para ejecutar este comando.'}
            target=q('SELECT id FROM users WHERE dni=?',(p[2],),one=True)
            if not target:return {'ok':False,'message':'No se encontró un usuario con ese DNI.'}
            target=target['id']
            if not q('SELECT id FROM users WHERE id=?',(target,),one=True):return {'ok':False,'message':'No se encontró el usuario indicado.'}
            x('UPDATE users SET social_rank_id=NULL WHERE id=?',(target,));log(uid,'rank.remove','user',target);return {'ok':True,'message':'✓ Rango retirado correctamente.'}
    if cmd.startswith('/party'):
        if not room:return {'ok':False,'message':'Este comando debe ejecutarse dentro de una sala.'}
        mem=q('SELECT * FROM room_members WHERE room_id=? AND user_id=?',(room,uid),one=True)
        r=q('SELECT * FROM rooms WHERE id=? AND status=\'active\'',(room,),one=True)
        if not mem or not r:return {'ok':False,'message':'No tienes acceso a esta sala.'}
        if cmd=='/party members':
            return {'ok':True,'members':[dict(m) for m in q('SELECT rm.user_id,rm.member_role,u.username,u.names,u.last_names FROM room_members rm JOIN users u ON u.id=rm.user_id WHERE rm.room_id=?',(room,))]}
        if cmd=='/party info':return {'ok':True,'room':dict(r)}
        if cmd=='/party leave':
            if mem['member_role']=='owner':return {'ok':False,'message':'El creador no puede salir sin cerrar o transferir la sala.'}
            x('DELETE FROM room_members WHERE room_id=? AND user_id=?',(room,uid));log(uid,'room.leave','room',room);return {'ok':True,'message':'Has salido de la sala.'}
        if cmd in ('/party add','/party invite'):
            if not has_permission(uid,'room.manage') or mem['member_role'] not in ('owner','admin'):
                return {'ok':False,'message':'No tienes permisos para administrar esta sala.'}
            if len(p)!=3:return {'ok':False,'message':f'Sintaxis: {cmd} ID'}
            target=q('SELECT id FROM users WHERE dni=?',(p[2],),one=True)
            if not target:return {'ok':False,'message':'No se encontró un usuario con ese DNI.'}
            target=target['id']
            if not q("SELECT id FROM users WHERE id=? AND status='approved'",(target,),one=True):return {'ok':False,'message':'No se encontró el usuario.'}
            x('INSERT OR IGNORE INTO room_members(room_id,user_id,member_role) VALUES(?,?,\'member\')',(room,target));notify(target,'Invitación a sala',f'Has sido invitado a {r["name"]}.','room',f'/rooms/{room}');log(uid,'room.add','room',room,{'target_user':target});return {'ok':True,'message':'Usuario agregado/invitado.'}
        if cmd=='/party remove':
            if not has_permission(uid,'room.manage') or mem['member_role'] not in ('owner','admin'):return {'ok':False,'message':'No tienes permisos para administrar esta sala.'}
            if len(p)!=3:return {'ok':False,'message':'Sintaxis: /party remove DNI'}
            target=q('SELECT id FROM users WHERE dni=?',(p[2],),one=True)
            if not target:return {'ok':False,'message':'No se encontró un usuario con ese DNI.'}
            target=target['id']
            target_mem=q('SELECT * FROM room_members WHERE room_id=? AND user_id=?',(room,target),one=True)
            if not target_mem:return {'ok':False,'message':'Ese usuario no pertenece a la sala.'}
            if target_mem['member_role']=='owner':return {'ok':False,'message':'No puedes remover al creador.'}
            x('DELETE FROM room_members WHERE room_id=? AND user_id=?',(room,target));log(uid,'room.remove','room',room,{'target_user':target});return {'ok':True,'message':'Miembro removido.'}
    return {'ok':False,'message':'Comando no reconocido. Escribe /help para ver los comandos disponibles.'}
