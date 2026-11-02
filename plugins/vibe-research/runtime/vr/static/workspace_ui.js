/* Workspace chrome, icons and the optional configuration prompt. No research writes. */
(()=>{
 const paths={tree:'M6 4v12a3 3 0 0 0 3 3h9M6 9h7a4 4 0 0 0 4-4M3 4a3 3 0 1 0 6 0 3 3 0 0 0-6 0ZM14 4a3 3 0 1 0 6 0 3 3 0 0 0-6 0ZM16 19a3 3 0 1 0 6 0 3 3 0 0 0-6 0Z',database:'M20 6c0 2-4 3-8 3S4 8 4 6s4-3 8-3 8 1 8 3ZM4 6v6c0 2 4 3 8 3s8-1 8-3V6M4 12v6c0 2 4 3 8 3s8-1 8-3v-6',display:'M4 4h16v12H4zM8 21h8M12 16v5M7 8h4M7 11h8',capabilities:'m12 3 2.3 6.7L21 12l-6.7 2.3L12 21l-2.3-6.7L3 12l6.7-2.3L12 3ZM19 3v4M17 5h4',lightning:'m13 2-10 12h8l-1 8 11-12h-8l1-8Z',brainstorming:'m12 3 2.3 6.7L21 12l-6.7 2.3L12 21l-2.3-6.7L3 12l6.7-2.3L12 3Z',engineering:'m8 6-6 6 6 6m8-12 6 6-6 6M14 4l-4 16',settings:'M19.39 8.94L19.79 10.20L21.85 10.26L21.85 13.74L19.79 13.80L19.39 15.06L18.78 16.24L20.19 17.74L17.74 20.19L16.24 18.78L15.06 19.39L13.80 19.79L13.74 21.85L10.26 21.85L10.20 19.79L8.94 19.39L7.76 18.78L6.26 20.19L3.81 17.74L5.22 16.24L4.61 15.06L4.21 13.80L2.15 13.74L2.15 10.26L4.21 10.20L4.61 8.94L5.22 7.76L3.81 6.26L6.26 3.81L7.76 5.22L8.94 4.61L10.20 4.21L10.26 2.15L13.74 2.15L13.80 4.21L15.06 4.61L16.24 5.22L17.74 3.81L20.19 6.26L18.78 7.76ZM12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z'};
 function icon(name){return '<svg class="vr-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="'+paths[name]+'"/></svg>'}
 function link(name,url,label){const a=document.createElement('a');a.href=url;a.className=name==='tree'?'giver-entry':'icon-link';a.innerHTML=icon(name);a.title=label;a.setAttribute('aria-label',label);if(name==='settings')a.dataset.globalSettings='true';return a}
 const prompted=new Set();
 async function checkProject(project){
  try{
   const response=await fetch('/api/settings');if(!response.ok)return;const data=await response.json();
   const attention=data.providers.filter(p=>['needs_auth','blocked','waiting'].includes(p.status));
   if(!attention.length)return;
   const fingerprint=project+JSON.stringify(attention.map(p=>[p.provider,p.status,p.checked_at]));
   if(prompted.has(fingerprint))return;prompted.add(fingerprint);
   let previous;try{previous=sessionStorage.getItem('vr-config-prompt:'+project)}catch(_){}
   if(previous===fingerprint)return;
   if(!window.VRUI)return;
   const configure=await VRUI.confirm(attention.map(p=>p.title).join('、')+' 缺少配置或最近检测受阻。现在补充配置吗？也可以稍后使用其他可用来源继续。',{title:'项目开始前 · 数据库检查',accept:'配置来源',cancelLabel:'稍后'});
   try{sessionStorage.setItem('vr-config-prompt:'+project,fingerprint)}catch(_){}
   if(configure)location.assign('/settings?setup=1&project='+encodeURIComponent(project));
  }catch(_){/* The project remains usable when workspace configuration cannot be read. */}
 }
 function preferences(){try{document.body.classList.toggle('reduce-motion',localStorage.getItem('vr.motion')==='off')}catch(_){}}
 window.VRWorkspace={icon,link,checkProject,preferences};
 addEventListener('DOMContentLoaded',()=>{
  preferences();
  for(const a of document.querySelectorAll('.mode-nav a'))if(!a.querySelector('svg')){const name=a.getAttribute('href').slice(1);if(paths[name])a.insertAdjacentHTML('afterbegin',icon(name));}
  for(const a of document.querySelectorAll('.giver-entry')){
   a.innerHTML=icon('tree');a.setAttribute('aria-label','研究版本树');a.title='研究版本树';
   if(!a.closest('.workspace-tools')){const tools=document.createElement('div');tools.className='workspace-tools';a.before(tools);tools.append(a,link('settings','/settings','全局设置'));}
  }
 });
})();
