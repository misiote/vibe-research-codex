/* Shared, project-scoped navigation. It never changes project mode or ownership. */
(()=>{
 const mounted=new WeakMap();
 function mount(host,options){
  mounted.get(host)?.();
  const {project,mode='engineering',board,title='',beforeNavigate}=options;
  if(!/^p[a-f0-9]{12}$/.test(project)||!['brainstorming','engineering'].includes(mode))throw Error('项目导航上下文无效');
  const prefix='/p/'+project,modeUrl=mode==='brainstorming'?'/brainstorming?space='+encodeURIComponent(board):prefix+'/engineering';
  const items=[['overview','概览',prefix+'/#work'],['map','研究地图',prefix+'/#map'],['library','文献',prefix+'/#library'],['history','研究历史',prefix+'/explore#history'],['direction','方向决策',prefix+'/explore#direction'],['mode',mode==='brainstorming'?'Brainstorming':'Engineering',modeUrl],['settings','设置',prefix+'/#settings']];
  const name=document.createElement('p');name.className='project-navigation-title';name.textContent=title;name.hidden=Boolean(document.getElementById('question'));
  const nav=document.createElement('nav');nav.className='project-navigation';nav.setAttribute('aria-label','项目导航');
  const anchors=[];
  for(const [key,label,url] of items){
   const a=document.createElement('a');a.textContent=label;a.href=url;a.dataset.projectView=key;
   a.addEventListener('click',async e=>{
    if(!beforeNavigate||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
    e.preventDefault();if(await beforeNavigate())location.assign(a.href);
   });nav.append(a);anchors.push(a);
  }
  function sync(){
   let view=options.view;
   if(!view){
    if(location.pathname.endsWith('/explore'))view=location.hash==='#direction'?'direction':'history';
    else if(location.pathname.endsWith('/engineering'))view='mode';
    else view=({map:'map',library:'library',settings:'settings'})[location.hash.slice(1)]||'overview';
   }
   for(const a of anchors)if(a.dataset.projectView===view)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');
  }
  host.replaceChildren(name,nav);host.hidden=false;sync();
  for(const id of ['legacy-workbench-tabs','legacy-project-tools']){const legacy=document.getElementById(id);if(legacy)legacy.hidden=true;}
  addEventListener('hashchange',sync);mounted.set(host,()=>removeEventListener('hashchange',sync));
  return {project,items:items.map(([view,label,url])=>({view,label,url})),sync};
 }
 window.VRProjectNav={mount};
 addEventListener('DOMContentLoaded',async()=>{
  const host=document.getElementById('project-navigation'),match=location.pathname.match(/^\/p\/(p[a-f0-9]{12})(?:\/|$)/);
  if(!host||!match)return;
  try{
   const response=await fetch('/api/projects');if(!response.ok)throw Error('项目导航读取失败');
   const data=await response.json(),p=data.projects.find(p=>p.id===match[1]);if(!p)throw Error('项目未登记');
   mount(host,{project:p.id,mode:p.mode||'engineering',board:p.board,title:p.name});
  }catch(e){host.hidden=false;host.textContent='项目导航暂不可用，请刷新。';host.setAttribute('role','status');}
 });
})();
