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
    if cmd=='/say':
        if not has_permission(uid,'admin.dashboard'):
            return {'ok':False,'message':'Solo el Owner puede utilizar /say.'}
        if len(p)<3 or p[1] not in ('1','2','3'):
            return {'ok':False,'message':'Sintaxis: /say 1|2|3 MENSAJE'}
        raw=' '.join(p[2:]).strip()
        if not raw:return {'ok':False,'message':'Escribe un mensaje.'}
        import html,re
        raw=raw[:500]
        parts=re.split(r'(&l)',html.escape(raw,quote=False),flags=re.IGNORECASE)
        out=[]
        bold=False
        for part in parts:
            if part.lower()=='&l':
                bold=True
            elif part:
                out.append(f'<strong>{part}</strong>' if bold else part)
                bold=False
        colors={'1':'green','2':'red','3':'white'}
        from database import x
        aid=x('INSERT INTO announcements(created_by,message,color,bold) VALUES(?,?,?,?)',(uid,' '.join(out),colors[p[1]],1 if '<strong>' in ' '.join(out) else 0))
        x('UPDATE announcements SET active=0 WHERE id<>? AND active=1',(aid,))
        log(uid,'announcement.created','announcement',aid,{'source':'/say','color':colors[p[1]]})
        for u in q("SELECT id FROM users WHERE status='approved' AND id<>?",(uid,)):
            notify(u['id'],'Nuevo anuncio global',raw,'announcement','/dashboard')
        return {'ok':True,'message':'Anuncio global publicado.','announcement':{'id':aid,'message':' '.join(out),'color':colors[p[1]]}}
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
            target=q('SELECT id FROM users WHERE id=? OR dni=?',(p[2],p[2]),one=True)
            if not target:return {'ok':False,'message':'No se encontró un usuario con ese DNI.'}
            target=target['id']
            if not q('SELECT id FROM users WHERE id=?',(target,),one=True):return {'ok':False,'message':'No se encontró el usuario indicado.'}
            x('UPDATE users SET social_rank_id=NULL WHERE id=?',(target,));log(uid,'rank.remove','user',target);return {'ok':True,'message':'✓ Rango retirado correctamente.'}
    if cmd.startswith('/party'):
        if not room:return {'ok':False,'message':'Este comando debe ejecutarse dentro de una sala.'}
        mem=q('SELECT * FROM room_members WHERE room_id=? AND user_id=?',(room,uid),one=True)
        r=q("SELECT * FROM rooms WHERE id=? AND status='active'",(room,),one=True)
        if not r or (not mem and r['visibility']!='public'):return {'ok':False,'message':'No tienes acceso a esta sala.'}
        if not mem: mem={'member_role':'guest'}
        if cmd=='/party members':
            return {'ok':True,'members':[dict(m) for m in q('SELECT rm.user_id,rm.member_role,u.username,u.names,u.last_names FROM room_members rm JOIN users u ON u.id=rm.user_id WHERE rm.room_id=?',(room,))]}
        if cmd=='/party info':return {'ok':True,'room':dict(r)}
        if cmd in ('/party public','/party priv'):
            if not has_permission(uid,'room.manage') or mem['member_role'] not in ('owner','admin'):
                return {'ok':False,'message':'No tienes permisos para cambiar la privacidad.'}
            vis='public' if cmd=='/party public' else 'private'
            x('UPDATE rooms SET visibility=? WHERE id=?',(vis,room));log(uid,'room.visibility','room',room,{'visibility':vis})
            return {'ok':True,'message':f'La sala ahora es {vis}.'}
        if cmd=='/party leave':
            if mem['member_role']=='owner':return {'ok':False,'message':'El creador no puede salir sin cerrar o transferir la sala.'}
            x('DELETE FROM room_members WHERE room_id=? AND user_id=?',(room,uid));log(uid,'room.leave','room',room);return {'ok':True,'message':'Has salido de la sala.'}
        if cmd in ('/party add','/party invite'):
            if not has_permission(uid,'room.manage') or mem['member_role'] not in ('owner','admin'):
                return {'ok':False,'message':'No tienes permisos para administrar esta sala.'}
            if len(p)!=3:return {'ok':False,'message':f'Sintaxis: {cmd} ID'}
            target=q('SELECT id FROM users WHERE id=? OR dni=?',(p[2],p[2]),one=True)
            if not target:return {'ok':False,'message':'No se encontró un usuario con ese DNI.'}
            target=target['id']
            if not q("SELECT id FROM users WHERE id=? AND status='approved'",(target,),one=True):return {'ok':False,'message':'No se encontró el usuario.'}
            x('INSERT OR IGNORE INTO room_members(room_id,user_id,member_role) VALUES(?,?,\'member\')',(room,target));notify(target,'Invitación a sala',f'Has sido invitado a {r["name"]}.','room',f'/rooms/{room}');log(uid,'room.add','room',room,{'target_user':target});return {'ok':True,'message':'Usuario agregado/invitado.'}
        if cmd=='/party remove':
            if not has_permission(uid,'room.manage') or mem['member_role'] not in ('owner','admin'):return {'ok':False,'message':'No tienes permisos para administrar esta sala.'}
            if len(p)!=3:return {'ok':False,'message':'Sintaxis: /party remove DNI'}
            target=q('SELECT id FROM users WHERE id=? OR dni=?',(p[2],p[2]),one=True)
            if not target:return {'ok':False,'message':'No se encontró un usuario con ese DNI.'}
            target=target['id']
            target_mem=q('SELECT * FROM room_members WHERE room_id=? AND user_id=?',(room,target),one=True)
            if not target_mem:return {'ok':False,'message':'Ese usuario no pertenece a la sala.'}
            if target_mem['member_role']=='owner':return {'ok':False,'message':'No puedes remover al creador.'}
            x('DELETE FROM room_members WHERE room_id=? AND user_id=?',(room,target));log(uid,'room.remove','room',room,{'target_user':target});return {'ok':True,'message':'Miembro removido.'}
    return {'ok':False,'message':'Comando no reconocido. Escribe /help para ver los comandos disponibles.'}
