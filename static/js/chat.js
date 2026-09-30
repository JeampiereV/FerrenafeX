window.Chat={
  timer:null,
  async load(){
    const status=document.getElementById('chatSyncStatus');
    const d=await FA.api(`/api/chat/${CHAT_USER_ID}`,{method:'GET'});
    if(!d.ok){if(status)status.textContent='No disponible';FA.toast(d.message,'err');return}
    const box=document.getElementById('chatMessages');
    if(!box)return;
    box.innerHTML=(d.messages||[]).map(m=>`<div class="bubble ${Number(m.sender_id)===Number(CURRENT_USER_ID)?'mine':''}"><p>${FA.escape(m.content)}</p><small>${FA.escape(m.created_at)}</small></div>`).join('')||'<p class="muted">Aún no hay mensajes.</p>';
    box.scrollTop=box.scrollHeight;
    if(status)status.textContent='Sincronizado · '+new Date().toLocaleTimeString();
  },
  async send(){
    const e=document.getElementById('chatInput');
    const value=e?.value.trim();
    if(!value)return;
    const d=await FA.api(`/api/chat/${CHAT_USER_ID}`,{method:'POST',body:JSON.stringify({content:value})});
    FA.toast(d.message,d.ok?'ok':'err');
    if(d.ok){e.value='';this.load()}
  }
};
async function deleteWholeChat(){
  if(!confirm('¿Eliminar TODO el historial de este chat? Esta acción no se puede deshacer.'))return;
  const d=await FA.api(`/api/chat/${CHAT_USER_ID}/delete-all`,{method:'POST',body:'{}'});
  FA.toast(d.message,d.ok?'ok':'err');if(d.ok)Chat.load();
}
async function deleteLatestChat(){
  const modal=document.getElementById('deleteLatestModal');if(modal){modal.classList.remove('hidden');modal.setAttribute('aria-hidden','false');document.getElementById('deleteLatestAmount')?.focus()}
}
async function confirmLatestDelete(){
  const input=document.getElementById('deleteLatestAmount');let amount=Math.max(1,Math.min(200,Number(input?.value||10)));
  if(!confirm(`¿Eliminar los últimos ${amount} mensajes?`))return;
  const d=await FA.api(`/api/chat/${CHAT_USER_ID}/delete-latest`,{method:'POST',body:JSON.stringify({amount})});
  FA.toast(d.message,d.ok?'ok':'err');if(d.ok){closeLatestModal();Chat.load()}
}
function closeLatestModal(){const m=document.getElementById('deleteLatestModal');if(!m)return;m.classList.add('hidden');m.setAttribute('aria-hidden','true')}
document.getElementById('chatSendBtn')?.addEventListener('click',()=>Chat.send());
document.getElementById('chatInput')?.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();Chat.send()}});
document.getElementById('deleteChatAllBtn')?.addEventListener('click',deleteWholeChat);
document.getElementById('deleteChatLatestBtn')?.addEventListener('click',deleteLatestChat);
document.getElementById('confirmDeleteLatest')?.addEventListener('click',confirmLatestDelete);
document.getElementById('closeDeleteLatest')?.addEventListener('click',closeLatestModal);
document.getElementById('cancelDeleteLatest')?.addEventListener('click',closeLatestModal);
document.getElementById('deleteLatestModal')?.addEventListener('click',e=>{if(e.target.id==='deleteLatestModal')closeLatestModal()});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeLatestModal()});
window.addEventListener('DOMContentLoaded',()=>Chat.load());
setInterval(()=>window.Chat?.load(),2500);
