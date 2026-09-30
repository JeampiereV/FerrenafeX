window.Chat={
  timer:null, socket:null, seen:new Set(),
  setStatus(text){const e=document.getElementById('chatSyncStatus');if(e)e.textContent=text},
  renderMessage(m){
    const box=document.getElementById('chatMessages'); if(!box || m?.id==null || this.seen.has(String(m.id)))return;
    const empty=box.querySelector('.muted'); if(empty)empty.remove();
    this.seen.add(String(m.id));
    const div=document.createElement('div'); div.className=`bubble ${Number(m.sender_id)===Number(CURRENT_USER_ID)?'mine':''}`;
    const p=document.createElement('p'); p.textContent=m.content??'';
    const small=document.createElement('small'); small.textContent=m.created_at??'';
    div.append(p,small); box.appendChild(div); box.scrollTop=box.scrollHeight;
  },
  renderAll(messages){
    const box=document.getElementById('chatMessages');if(!box)return;
    this.seen.clear();box.innerHTML='';
    (messages||[]).forEach(m=>this.renderMessage(m));
    if(!(messages||[]).length)box.innerHTML='<p class="muted">Aún no hay mensajes.</p>';
    box.scrollTop=box.scrollHeight;
  },
  async load(){
    const d=await FA.api(`/api/chat/${CHAT_USER_ID}`,{method:'GET'});
    if(!d.ok){this.setStatus('No disponible');return}
    this.renderAll(d.messages||[]); this.setStatus('Conectado · '+new Date().toLocaleTimeString());
  },
  connect(){
    if(typeof io!=='function')return;
    this.socket=io({transports:['websocket','polling']});
    this.socket.on('connect',()=>{this.setStatus('Conectado · tiempo real');});
    this.socket.on('disconnect',()=>{this.setStatus('Conexión perdida · recuperando…');});
    this.socket.on('connect_error',()=>{this.setStatus('Conexión perdida · respaldo activo');});
    this.socket.on('private_message',m=>{
      if(Number(m.sender_id)===Number(CURRENT_USER_ID)||Number(m.receiver_id)===Number(CURRENT_USER_ID))this.renderMessage(m);
    });
  },
  async send(){
    const e=document.getElementById('chatInput'),value=e?.value.trim();if(!value)return;
    const d=await FA.api(`/api/chat/${CHAT_USER_ID}`,{method:'POST',body:JSON.stringify({content:value})});
    FA.toast(d.message,d.ok?'ok':'err'); if(d.ok){e.value=''; if(d.message_data)this.renderMessage(d.message_data);}
  }
};
async function deleteWholeChat(){if(!confirm('¿Eliminar TODO el historial de este chat? Esta acción no se puede deshacer.'))return;const d=await FA.api(`/api/chat/${CHAT_USER_ID}/delete-all`,{method:'POST',body:'{}'});FA.toast(d.message,d.ok?'ok':'err');if(d.ok)Chat.load()}
async function deleteLatestChat(){const modal=document.getElementById('deleteLatestModal');if(modal){modal.classList.remove('hidden');modal.setAttribute('aria-hidden','false');document.getElementById('deleteLatestAmount')?.focus()}}
async function confirmLatestDelete(){const input=document.getElementById('deleteLatestAmount');let amount=Math.max(1,Math.min(200,Number(input?.value||10)));if(!confirm(`¿Eliminar los últimos ${amount} mensajes?`))return;const d=await FA.api(`/api/chat/${CHAT_USER_ID}/delete-latest`,{method:'POST',body:JSON.stringify({amount})});FA.toast(d.message,d.ok?'ok':'err');if(d.ok){closeLatestModal();Chat.load()}}
function closeLatestModal(){const m=document.getElementById('deleteLatestModal');if(!m)return;m.classList.add('hidden');m.setAttribute('aria-hidden','true')}
document.getElementById('chatSendBtn')?.addEventListener('click',()=>Chat.send());document.getElementById('chatInput')?.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();Chat.send()}});document.getElementById('deleteChatAllBtn')?.addEventListener('click',deleteWholeChat);document.getElementById('deleteChatLatestBtn')?.addEventListener('click',deleteLatestChat);document.getElementById('confirmDeleteLatest')?.addEventListener('click',confirmLatestDelete);document.getElementById('closeDeleteLatest')?.addEventListener('click',closeLatestModal);document.getElementById('cancelDeleteLatest')?.addEventListener('click',closeLatestModal);document.getElementById('deleteLatestModal')?.addEventListener('click',e=>{if(e.target.id==='deleteLatestModal')closeLatestModal()});document.addEventListener('keydown',e=>{if(e.key==='Escape')closeLatestModal()});
window.addEventListener('DOMContentLoaded',()=>{Chat.load();Chat.connect()});
Chat.timer=setInterval(()=>Chat.load(),10000);
window.addEventListener('beforeunload',()=>clearInterval(Chat.timer));
