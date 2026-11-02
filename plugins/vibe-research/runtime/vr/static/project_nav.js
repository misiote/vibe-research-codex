/* Navigation owns links only. Research services and mode ownership remain independent. */
(()=>{
 const mounted=new WeakMap();
 function mount(host,options){
  mounted.get(host)?.();
  const {project,mode='engineering',board,title='',beforeNavigate}=options;
  if(!/^p[a-f0-9]{12}$/.test(project)||!['brainstorming','engineering'].includes(mode))throw Error('项目导航上下文无效');
  const prefix='/p/'+project,notes=mode==='brainstorming'?'/brainstorming?space='+encodeURIComponent(board):prefix+'/explore#notes';
  const items=[['overview','概览',prefix+'/#work'],['map','研究地图',prefix+'/#map'],['library','文献',prefix+'/#library']];
  if(mode==='engineering')items.push(['engineering','Engineering',prefix+'/engineering']);
  const research=[['notes','研究笔记',notes],['history','研究历史',prefix+'/explore#history'],['direction','方向决策',prefix+'/explore#direction']];
  const context=document.createElement('div');context.className='project-context';
  const name=document.createElement('p');name.className='project-navigation-title';name.textContent=title;name.hidden=Boolean(document.getElementById('page-title')||document.getElementById('question'));
  const menu=document.createElement('details');menu.className='project-research';
  const summary=document.createElement('summary');summary.textContent='Brainstorming';
  const sub=document.createElement('nav');sub.className='research-subnav';sub.setAttribute('aria-label','Brainstorming');menu.append(summary,sub);context.append(name,menu);
  if(window.VRWorkspace)context.append(VRWorkspace.link('tree','/giver?project='+project,'研究版本树'),VRWorkspace.link('settings','/settings','全局设置'));
  const nav=document.createElement('nav');nav.className='project-navigation';nav.setAttribute('aria-label','项目导航');const anchors=[];
  function add(items,target){for(const [key,label,url] of items){const a=document.createElement('a');a.textContent=label;a.href=url;a.dataset.projectView=key;a.addEventListener('click',async e=>{if(!beforeNavigate||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;e.preventDefault();if(await beforeNavigate())location.assign(a.href)});target.append(a);anchors.push(a)}}
  add(items,nav);add(research,sub);
  function sync(){let view=options.view;if(view==='mode')view=mode==='brainstorming'?'notes':'engineering';if(!view){if(location.pathname.endsWith('/explore'))view=location.hash==='#direction'?'direction':location.hash==='#notes'?'notes':'history';else if(location.pathname.endsWith('/engineering'))view='engineering';else view=({map:'map',library:'library'})[location.hash.slice(1)]||'overview'}for(const a of anchors)if(a.dataset.projectView===view)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');summary.dataset.active=String(research.some(([k])=>k===view));}
  host.replaceChildren(context,nav);host.hidden=false;sync();
  for(const id of ['legacy-workbench-tabs','legacy-project-tools']){const legacy=document.getElementById(id);if(legacy)legacy.hidden=true}
  addEventListener('hashchange',sync);mounted.set(host,()=>removeEventListener('hashchange',sync));window.VRWorkspace?.checkProject(project);
  return {project,items:[...items,...research].map(([view,label,url])=>({view,label,url})),sync};
 }
 window.VRProjectNav={mount};
 addEventListener('DOMContentLoaded',async()=>{const host=document.getElementById('project-navigation'),match=location.pathname.match(/^\/p\/(p[a-f0-9]{12})(?:\/|$)/);if(!host||!match)return;try{const response=await fetch('/api/projects');if(!response.ok)throw Error();const data=await response.json(),p=data.projects.find(p=>p.id===match[1]);if(!p)throw Error();mount(host,{project:p.id,mode:p.mode||'engineering',board:p.board,title:p.name})}catch(e){host.hidden=false;host.textContent='项目导航暂不可用，请刷新。';host.setAttribute('role','status')}});
})();
