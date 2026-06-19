"""Dependency-free browser UI served by Trinity's HTTP bridge."""


def render_web_ui(auth_enabled=False):
    """Render the browser client for legacy token or account based access."""
    auth_controls = (
        '<input id="username" placeholder="Benutzername">'
        '<input id="password" type="password" placeholder="Passwort">'
        '<button class="secondary" id="login">Anmelden</button>'
    ) if auth_enabled else (
        '<input id="token" type="password" placeholder="Bearer Token">'
        '<button class="secondary" id="saveToken">Token speichern</button>'
    )
    page = r"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trinity Web</title><style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#0c1017;color:#edf3fb;font:15px system-ui,sans-serif}
header{position:sticky;top:0;z-index:2;display:flex;gap:10px;align-items:center;padding:13px 18px;background:#121923;border-bottom:1px solid #263448}
h1{margin:0;font-size:19px}.status{color:#8aa0bc;font-size:13px;margin-right:auto}button,input,textarea{font:inherit}button{border:0;border-radius:10px;padding:9px 13px;background:#168cf4;color:white;cursor:pointer}button.secondary{background:#263448}input,textarea{background:#111923;color:#edf3fb;border:1px solid #31425a;border-radius:10px;padding:10px}
#token{width:180px}.layout{max-width:1180px;margin:auto;padding:22px}.composer{display:grid;grid-template-columns:1fr auto;gap:10px;margin-bottom:18px}.composer textarea{min-height:86px;resize:vertical}.actions{display:flex;gap:9px;align-items:center;flex-wrap:wrap}.actions input{max-width:260px}.event{margin:12px 0;padding:14px 16px;border-radius:14px;background:#141d29;border:1px solid #243247}.event.user{margin-left:12%;background:#10335b}.event .meta{font-size:12px;color:#87a0c0;margin-bottom:7px}.event .text{white-space:pre-wrap;line-height:1.45}.event img,.event video{max-width:100%;max-height:560px;border-radius:10px;margin-top:12px}.event audio{width:100%;margin-top:12px}.attachment{margin-top:8px;color:#8bd1ff;font-size:13px}.empty{color:#89a0b9;text-align:center;padding:60px}.payload{margin-top:12px;border-radius:10px;overflow:auto;background:#0b1119}.payload iframe{display:block;width:100%;height:480px;border:0;background:white}@media(max-width:720px){header{flex-wrap:wrap}.layout{padding:12px}.event.user{margin-left:0}.composer{grid-template-columns:1fr}#token{width:100%}}
</style></head><body><header><h1>Trinity Web</h1><span class="status" id="status">Verbinde...</span>__AUTH_CONTROLS__</header>
<main class="layout"><section class="composer"><textarea id="prompt" placeholder="Schreibe Trinity eine Nachricht oder ziehe eine Datei in die Auswahl..."></textarea><div class="actions"><input id="files" type="file" multiple accept=".txt,.md,.markdown,.csv,.tsv,.json,.yaml,.yml,.log,.py,.js,.html,.css,.pdf,.png,.jpg,.jpeg,.webp,.gif,.xlsx,.xlsm"><button id="send">Senden</button></div></section><section id="events"><div class="empty">Noch keine Nachrichten.</div></section></main>
<script>
const authEnabled=__AUTH_ENABLED__;const state={after:0,token:localStorage.getItem('trinity.web.token')||''};const token=document.querySelector('#token');if(token)token.value=state.token;
const status=document.querySelector('#status'),events=document.querySelector('#events'),prompt=document.querySelector('#prompt'),files=document.querySelector('#files');
function headers(){return state.token?{'Authorization':'Bearer '+state.token,'Content-Type':'application/json'}:{'Content-Type':'application/json'}}
function escapeHtml(value){const d=document.createElement('div');d.textContent=value||'';return d.innerHTML}
function media(event){let html='';for(const item of(event.attachments||[])){const url=item.media_url||'';const mime=item.mime||'';if(url&&mime.startsWith('image/'))html+=`<img src="${url}">`;else if(url&&mime.startsWith('audio/'))html+=`<audio controls src="${url}"></audio>`;else if(url&&mime.startsWith('video/'))html+=`<video controls src="${url}"></video>`;else html+=`<div class="attachment">Anlage: ${escapeHtml(item.name||'Datei')}</div>`}if(event.payload_html)html+=`<div class="payload"><iframe sandbox="allow-scripts allow-same-origin" srcdoc="${escapeHtml(event.payload_html)}"></iframe></div>`;return html}
function render(list){if(!list.length)return;events.innerHTML=list.map(event=>`<article class="event ${event.role==='user'?'user':''}"><div class="meta">${event.role==='user'?'Du':'Trinity'} · ${new Date((event.timestamp||0)*1000).toLocaleTimeString()}</div><div class="text">${escapeHtml(event.text||'')}</div>${media(event)}</article>`).join('');window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'})}
async function poll(){try{const response=await fetch('/events?after='+state.after,{headers:state.token?{'Authorization':'Bearer '+state.token}:{}});if(!response.ok)throw new Error(response.status);const data=await response.json();const list=data.events||[];if(list.length){state.after=Math.max(...list.map(item=>item.timestamp||0));render(list)}status.textContent='Verbunden'}catch(error){status.textContent='Verbindung oder Token pruefen'}setTimeout(poll,1200)}
async function encode(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve({name:file.name,mime:file.type||'application/octet-stream',data_base64:String(reader.result).split(',')[1]||''});reader.onerror=reject;reader.readAsDataURL(file)})}
const saveToken=document.querySelector('#saveToken');if(saveToken)saveToken.onclick=()=>{state.token=token.value.trim();localStorage.setItem('trinity.web.token',state.token);state.after=0;events.innerHTML='';};
const login=document.querySelector('#login');if(login){async function authStatus(){const response=await fetch('/auth/status');const data=await response.json();login.textContent=data.bootstrap_required?'Admin anlegen':'Anmelden';status.textContent=data.bootstrap_required?'Bitte ersten Admin-Account anlegen':'Anmelden';}login.onclick=async()=>{const isBootstrap=login.textContent.includes('anlegen');try{const response=await fetch(isBootstrap?'/auth/register':'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:document.querySelector('#username').value.trim(),password:document.querySelector('#password').value})});const data=await response.json();if(!response.ok)throw new Error(data.error||response.status);state.token=data.token;localStorage.setItem('trinity.web.token',state.token);document.querySelector('#password').value='';state.after=0;events.innerHTML='';status.textContent='Angemeldet';}catch(error){status.textContent=error.message||'Anmeldung fehlgeschlagen';}};authStatus().catch(()=>status.textContent='Serverstatus nicht erreichbar');}
document.querySelector('#send').onclick=async()=>{const text=prompt.value.trim();const attachments=await Promise.all([...files.files].map(encode));if(!text&&!attachments.length)return;try{const response=await fetch('/message',{method:'POST',headers:headers(),body:JSON.stringify({text,attachments,source:'web',speak:false})});if(!response.ok)throw new Error(await response.text());prompt.value='';files.value='';status.textContent='Auftrag gesendet'}catch(error){status.textContent='Senden fehlgeschlagen'}};poll();
</script></body></html>"""
    return page.replace("__AUTH_CONTROLS__", auth_controls).replace(
        "__AUTH_ENABLED__", "true" if auth_enabled else "false"
    )
