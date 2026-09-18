let adminState={users:[],ranks:[]};

function statusLabel(s){return {pending:'Pendiente',approved:'Aprobada',rejected:'Rechazada',suspended:'Suspendida',blocked:'Bloqueada'}[s]||s}
function roleLabel(s){return {CITIZEN:'Ciudadano',COLLABORATOR:'Colaborador',STAFF:'Staff',AUTHORITY:'Autoridad',OWNER:'Owner'}[s]||s}
function setTabActive(t){document.querySelectorAll('.owner-tabs button').forEach(b=>b.classList.toggle('active',b.dataset.tab===t))}

async function tab(t){
  setTabActive(t);
  const e=document.getElementById('admin');
  if(t==='stats'){
    const d=await FA.api('/api/admin/stats');
    if(!d.ok){FA.toast(d.message,'err');return}
    const labels={users:'Miembros',pending_users:'Pendientes',approved_users:'Aprobados',reports:'Reportes',active_reports:'Reportes activos',helps:'Ayudas',completed_help:'Ayudas completadas',authorities:'Autoridades verificadas',posts:'Publicaciones',tickets:'Tickets abiertos',moderation:'Moderación abierta'};
    e.innerHTML='<div class="admin-summary">'+Object.entries(d.stats).map(([k,v])=>`<div class="admin-metric"><small>${FA.escape(labels[k]||k)}</small><strong>${v}</strong></div>`).join('')+'</div><div class="card admin-note"><strong>Ruta operativa recomendada</strong><p>Miembros → aprobar cuenta → revisar ficha → asignar rol si corresponde → administrar rango social → continuar supervisando desde Auditoría.</p></div>';
    return;
  }
  if(t==='users') return loadUsers();
  if(t==='authorities'){
    let d=await FA.api('/api/authority/requests');
    e.innerHTML='<div class="list">'+(d.requests||[]).map(a=>`<div class="row"><div><b>#${a.id} · ${FA.escape(a.authority_type)}</b><span>${FA.escape(a.institution)} · @${FA.escape(a.username)} · ${FA.escape(a.status)}</span></div><div class="actions"><button class="btn dark" onclick="decide(${a.id},'approved')">Aprobar</button><button class="btn dark" onclick="decide(${a.id},'rejected')">Rechazar</button></div></div>`).join('')+'</div>';
    return;
  }
  if(t==='tickets'){
    let d=await FA.api('/api/tickets');
    e.innerHTML='<div class="list">'+(d.tickets||[]).map(a=>`<div class="row"><div><b>${FA.escape(a.public_id)} · ${FA.escape(a.subject)}</b><span>@${FA.escape(a.username)} · ${FA.escape(a.status)}</span></div><button class="btn dark" onclick="ticketStatus(${a.id},'resolved')">Resolver</button></div>`).join('')+'</div>';
    return;
  }
  if(t==='audit'){
    let d=await FA.api('/api/admin/audit');
    e.innerHTML='<div class="list">'+(d.logs||[]).map(a=>`<div class="row"><div><b>${FA.escape(a.action)}</b><span>${FA.escape(a.actor_username||'sistema')} · ${FA.escape(a.created_at)}</span></div></div>`).join('')+'</div>';
  }
}

async function loadUsers(){
  const e=document.getElementById('admin');
  const [du,dr]=await Promise.all([FA.api('/api/admin/users'),FA.api('/api/admin/ranks')]);
  if(!du.ok){FA.toast(du.message,'err');return}
  adminState.users=du.users||[]; adminState.ranks=dr.ranks||[];
  const pending=adminState.users.filter(u=>u.status==='pending').length;
  e.innerHTML=`<div class="member-toolbar"><div><strong>Miembros de FerreñafeX</strong><span>${pending} cuenta(s) pendiente(s) de aprobación.</span></div><div class="member-filters"><input id="memberSearch" placeholder="Buscar por nombre, usuario o DNI..." oninput="renderUsers()"><select id="memberStatus" onchange="renderUsers()"><option value="">Todos los estados</option><option value="pending">Pendientes</option><option value="approved">Aprobados</option><option value="rejected">Rechazados</option><option value="suspended">Suspendidos</option><option value="blocked">Bloqueados</option></select></div></div><div id="memberList" class="list"></div>`;
  renderUsers();
}

function renderUsers(){
  const e=document.getElementById('memberList');if(!e)return;
  const search=(document.getElementById('memberSearch')?.value||'').trim().toLowerCase();
  const st=document.getElementById('memberStatus')?.value||'';
  const rows=adminState.users.filter(u=>{
    const hay=`${u.id} ${u.dni||''} ${u.names} ${u.last_names} ${u.username} ${u.email||''}`.toLowerCase();
    return (!search||hay.includes(search))&&(!st||u.status===st);
  });
  if(!rows.length){e.innerHTML='<div class="empty-state">No hay miembros que coincidan con el filtro.</div>';return}
  e.innerHTML=rows.map(u=>{
    const pending=u.status==='pending';
    const owner=u.role_name==='OWNER';
    return `<div class="member-row ${pending?'is-pending':''}">
      <div class="member-main"><div class="member-avatar">${FA.escape((u.names||'?').charAt(0).toUpperCase())}</div><div><div class="member-name"><b>#${FA.escape(u.dni||'—')} · ${FA.escape(u.names)} ${FA.escape(u.last_names)}</b>${pending?'<span class="pending-badge">PENDIENTE</span>':''}</div><div class="member-meta">@${FA.escape(u.username)} · ${FA.escape(roleLabel(u.role_name))} · ${FA.escape(u.social_rank_name||'Sin rango')} · ${statusLabel(u.status)}</div><div class="member-meta">DNI ${FA.escape(u.dni||'—')} · ${u.age??'—'} años · ${FA.escape(u.phone||'Sin teléfono')}</div></div></div>
      <div class="member-actions"><button class="btn dark" onclick="openMember(${u.id})">Ver ficha</button>${!owner&&pending?`<button class="btn light" onclick="setStatus(${u.id},'approved')">Aprobar</button><button class="btn dark" onclick="setStatus(${u.id},'rejected')">Rechazar</button>`:''}</div>
    </div>`;
  }).join('');
}

async function openMember(id){
  const d=await FA.api('/api/admin/users/'+id);
  if(!d.ok){FA.toast(d.message,'err');return}
  const u=d.user; const rankOptions=adminState.ranks.map(r=>`<option value="${r.id}" ${String(r.id)===String((adminState.ranks.find(x=>x.name===u.social_rank_name)||{}).id)?'selected':''}>${FA.escape(r.name)}</option>`).join('');
  const canManage=u.role_name!=='OWNER';
  document.getElementById('memberModalTitle').textContent=`#${FA.escape(u.dni||'—')} · ${u.names} ${u.last_names}`;
  document.getElementById('memberDetail').innerHTML=`
    <div class="profile-head admin-profile-head"><div class="avatar">${FA.escape((u.names||'?').charAt(0).toUpperCase())}</div><div><h3>${FA.escape(u.names)} ${FA.escape(u.last_names)}</h3><div class="member-meta">@${FA.escape(u.username)} · ${FA.escape(roleLabel(u.role_name))} · ${FA.escape(u.social_rank_name||'Sin rango')}</div></div></div>
    <div class="detail-grid"><div><small>DNI</small><strong>${FA.escape(u.dni||'No registrado')}</strong></div><div><small>Edad</small><strong>${u.age==null?'No registrada':u.age+' años'}</strong></div><div><small>Teléfono</small><strong>${FA.escape(u.phone||'No registrado')}</strong></div><div><small>Correo</small><strong>${FA.escape(u.email||'No registrado')}</strong></div><div><small>Estado</small><strong>${FA.escape(statusLabel(u.status))}</strong></div><div><small>Registro</small><strong>${FA.escape(u.created_at||'—')}</strong></div><div><small>Puntos</small><strong>${u.points||0}</strong></div><div><small>Reportes creados</small><strong>${u.report_count||0}</strong></div><div><small>Solicitudes de ayuda</small><strong>${u.help_requests||0}</strong></div><div><small>Ayudas completadas</small><strong>${u.help_completed||0}</strong></div></div>
    <div class="card detail-block"><small>Biografía</small><p>${FA.escape(u.bio||'Sin biografía registrada.')}</p></div>
    ${canManage?`<div class="admin-controls"><div><label>Estado<select id="editStatus"><option value="pending" ${u.status==='pending'?'selected':''}>Pendiente</option><option value="approved" ${u.status==='approved'?'selected':''}>Aprobada</option><option value="rejected" ${u.status==='rejected'?'selected':''}>Rechazada</option><option value="suspended" ${u.status==='suspended'?'selected':''}>Suspendida</option><option value="blocked" ${u.status==='blocked'?'selected':''}>Bloqueada</option></select></label><button class="btn light" onclick="saveStatus(${u.id})">Guardar estado</button></div><div><label>Rol<select id="editRole"><option value="CITIZEN" ${u.role_name==='CITIZEN'?'selected':''}>Ciudadano</option><option value="COLLABORATOR" ${u.role_name==='COLLABORATOR'?'selected':''}>Colaborador</option><option value="STAFF" ${u.role_name==='STAFF'?'selected':''}>Staff</option></select></label><button class="btn dark" onclick="saveRole(${u.id})">Guardar rol</button></div><div><label>Rango social<select id="editRank">${rankOptions}</select></label><button class="btn dark" onclick="saveRank(${u.id})">Guardar rango</button></div></div>`:`<div class="warning">Esta es la cuenta Owner. No se permite modificar su rol ni rango desde este panel.</div>`}
    <div class="actions"><a class="btn dark" href="/profile?user=${u.id}" target="_blank">Ver perfil</a>${canManage&&u.status!=='approved'?`<button class="btn light" onclick="setStatus(${u.id},'approved');openMember(${u.id})">Aprobar cuenta</button>`:''}</div>`;
  const modal=document.getElementById('memberModal');
  modal.classList.remove('hidden');
  modal.setAttribute('aria-hidden','false');
  document.body.classList.add('modal-open');
  document.getElementById('memberModalClose')?.focus();
}
function closeMember(){
  const m=document.getElementById('memberModal');
  if(!m)return;
  m.classList.add('hidden');
  m.setAttribute('aria-hidden','true');
  document.body.classList.remove('modal-open');
}

function bindMemberModal(){
  const modal=document.getElementById('memberModal');
  const close=document.getElementById('memberModalClose');
  if(close){
    close.addEventListener('click', closeMember);
  }
  if(modal){
    modal.addEventListener('click', event=>{
      if(event.target===modal) closeMember();
    });
  }
  document.addEventListener('keydown', event=>{
    if(event.key==='Escape') closeMember();
  });
}

async function setStatus(id,s){let d=await FA.api('/api/admin/users/'+id+'/status',{method:'POST',body:JSON.stringify({status:s})});FA.toast(d.message,d.ok?'ok':'err');if(d.ok){await loadUsers();closeMember()}}
async function saveStatus(id){const s=document.getElementById('editStatus').value;await setStatus(id,s)}
async function saveRole(id){const role=document.getElementById('editRole').value;const d=await FA.api('/api/admin/users/'+id+'/role',{method:'POST',body:JSON.stringify({role})});FA.toast(d.message,d.ok?'ok':'err');if(d.ok){await loadUsers();openMember(id)}}
async function saveRank(id){const rank_id=document.getElementById('editRank').value;const d=await FA.api('/api/admin/users/'+id+'/social-rank',{method:'POST',body:JSON.stringify({rank_id})});FA.toast(d.message,d.ok?'ok':'err');if(d.ok){await loadUsers();openMember(id)}}
async function decide(id,s){let d=await FA.api('/api/authority/requests/'+id+'/decision',{method:'POST',body:JSON.stringify({status:s})});FA.toast(d.message,d.ok?'ok':'err');tab('authorities')}
async function ticketStatus(id,s){let d=await FA.api('/api/tickets/'+id+'/status',{method:'POST',body:JSON.stringify({status:s})});FA.toast(d.ok?'Ticket actualizado.':d.message,d.ok?'ok':'err');tab('tickets')}
bindMemberModal();
tab('stats');
