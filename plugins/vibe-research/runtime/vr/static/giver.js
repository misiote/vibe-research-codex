(()=>{
 const $=id=>document.getElementById(id),make=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e};
 let workspace=null,groups=[],family=null,data=null,selected=null,view='tree',inspected=null,inspection=0;
 const branchNodes=new Map(),commitNodes=new Map();
 const fmt=v=>v===undefined?'∅':typeof v==='string'?v:v?.content!==undefined?v.content+(v.sources?.length?'\n\n来源：'+v.sources.join('\n'):''):JSON.stringify(v,null,2);
 async function post(action,spec){const token=(await VRUI.request('/api/session')).token;return VRUI.request('/api/giver',{method:'POST',headers:{'Content-Type':'application/json','X-VR-Token':token},body:JSON.stringify({action,spec})})}
 async function act(button,fn){try{await VRUI.run(button,'处理中…',fn)}catch(e){$('status').textContent=e.message}}
 function svg(tag,attrs,text){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs||{}))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e}
 function address(){const u=new URL(location.href);u.search='';if(family){u.searchParams.set('project',family.id);if(selected)u.searchParams.set('branch',selected.name);u.searchParams.set('view',view);if(inspected)u.searchParams.set('commit',inspected)}history.replaceState(null,'',u)}
 function clearInspection(){inspection++;inspected=null;$('commit-info').hidden=true;$('commit-info').replaceChildren()}
 function locate(node){if(node)requestAnimationFrame(()=>{node.scrollIntoView({block:'nearest',inline:'center',behavior:'smooth'});node.focus({preventScroll:true})})}
 function catalog(){
  $('catalog').hidden=false;$('family-workspace').hidden=true;family=null;data=null;selected=null;clearInspection();address();catalogRows();$('status').textContent=groups.length+' 个项目谱系';
 }
 function catalogRows(){
  const q=$('project-search').value,rows=VRGiverView.search(groups,q);$('families').replaceChildren();$('catalog-empty').hidden=rows.length>0;
  if(!groups.length)$('catalog-empty').textContent='尚无项目。可以从下方新建项目。';else $('catalog-empty').textContent='没有匹配的项目。';
  for(const g of rows){const button=make('button');button.className='giver-family-card';button.append(make('strong',g.title),make('span',g.branches.length+' 个独立项目 · '+g.commits.length+' 个版本'),make('code',g.origin.name+' · '+g.id));
   const matches=q.trim()?g.branches.filter(b=>[b.title,b.name,b.project,b.mode].some(x=>String(x||'').toLowerCase().includes(q.trim().toLowerCase()))):g.branches;
   button.append(make('small',matches.map(b=>b.title+' / '+b.name+(b.lifecycle!=='active'?' · '+b.lifecycle:'')).join(' · ')));button.onclick=()=>openFamily(g,q.trim()?matches[0]?.name:g.origin.name,'tree',true);$('families').append(button)}
 }
 function branches(){
  $('family-branches').replaceChildren();for(const b of data.branches){const button=make('button');button.setAttribute('aria-pressed',String(b.name===selected?.name));button.append(make('strong',b.title),make('code',b.name),make('span',(b.mode==='brainstorming'?'Brainstorming':'Engineering')+(b.lifecycle!=='active'?' · '+b.lifecycle:'')));button.onclick=()=>select(b,true);$('family-branches').append(button)}
 }
 function select(b,focus=false){
  selected=b;if(focus)$('version-search').value='';clearInspection();$('selection').hidden=false;$('branch-info').replaceChildren(make('span',b.mode==='brainstorming'?'Brainstorming':'Engineering'),make('h2',b.title),make('code',b.name),make('p',b.head?'HEAD · '+b.head.slice(0,8):'尚未提交'));
  $('open-project').href=b.url;$('branch-mode').value=b.mode==='brainstorming'?'engineering':'brainstorming';branches();tree();log();address();if(focus)locate(view==='log'?commitNodes.get(b.head):branchNodes.get(b.name));
 }
 function setView(name){view=['tree','log','diff','reflog'].includes(name)?name:'tree';for(const b of document.querySelectorAll('[data-view]'))b.setAttribute('aria-selected',String(b.dataset.view===view));for(const n of ['tree','log','diff','reflog'])$(n+'-view').hidden=n!==view;address()}
 function openFamily(g,branch,tab='tree',focus=false){
  clearInspection();family=g;data=VRGiverView.scope(workspace,g);$('catalog').hidden=true;$('family-workspace').hidden=false;$('family-title').textContent=g.title;$('family-meta').textContent=g.branches.length+' 个独立项目 · '+g.commits.length+' 个版本 · '+g.id;
  $('version-search').value='';$('diff').replaceChildren();$('status').textContent='当前谱系：'+g.title;setView(tab);compareOptions();records();select(data.branches.find(b=>b.name===branch)||g.origin,focus);
 }
 function tree(){
  branchNodes.clear();$('tree').replaceChildren();const rows=[],seen=new Set(),walk=(b,depth)=>{if(seen.has(b.name))return;seen.add(b.name);rows.push({b,depth,y:22+rows.length*110});for(const child of data.branches.filter(c=>c.parent===b.name))walk(child,depth+1)};
  for(const b of data.branches.filter(b=>!data.branches.some(p=>p.name===b.parent)))walk(b,0);for(const b of data.branches)walk(b,0);
  if(!rows.length)return;const w=380+Math.max(...rows.map(r=>r.depth))*250,h=Math.max(240,rows.length*110+22),canvas=svg('svg',{viewBox:`0 0 ${w} ${h}`,width:w,height:h,role:'group','aria-label':'当前项目谱系'}),by=new Map(rows.map(r=>[r.b.name,r]));
  for(const r of rows){const p=by.get(r.b.parent);if(!p)continue;const x1=28+p.depth*250+145,y1=p.y+44,x2=28+r.depth*250,y2=r.y+44;canvas.append(svg('path',{d:`M${x1},${y1} C${x1+75},${y1} ${x2-70},${y2} ${x2},${y2}`,fill:'none',stroke:'#b4c8b5','stroke-width':2}))}
  for(const r of rows){const b=r.b,g=svg('g',{tabindex:0,role:'button','aria-label':b.title+' · '+b.name,transform:`translate(${28+r.depth*250},${r.y})`});const trim=(s,n)=>s.length>n?s.slice(0,n-1)+'…':s;
   g.append(svg('title',{},b.title+' · '+b.name+' · '+b.project),svg('rect',{width:300,height:94,rx:10,fill:b.mode==='brainstorming'?'#edf3e8':'#edf1f6',stroke:b.name===selected?.name?'#3e7050':'#b5c7af','stroke-width':b.name===selected?.name?2.5:1}),svg('text',{x:14,y:22,class:'giver-svg-mode'},b.mode==='brainstorming'?'Brainstorming':'Engineering'),svg('text',{x:14,y:44,class:'giver-svg-title'},trim(b.title,28)),svg('text',{x:14,y:64,class:'giver-svg-meta'},trim(b.name,38)),svg('text',{x:14,y:82,class:'giver-svg-meta'},(b.head?b.head.slice(0,8):'尚未提交')+(b.lifecycle!=='active'?' · '+b.lifecycle:'')));
   g.onclick=()=>select(b);g.onkeydown=e=>{if(e.key==='Enter')select(b)};canvas.append(g);branchNodes.set(b.name,g)}$('tree').append(canvas);
 }
 function log(){
  commitNodes.clear();$('log').replaceChildren();$('version-results').replaceChildren();const query=$('version-search').value,commits=VRGiverView.versions(data,query).sort((a,b)=>a.at.localeCompare(b.at));$('version-count').textContent='显示 '+commits.length+' / '+data.commits.length+' 个版本';
  if(!commits.length){$('version-results').append(make('p',query?'没有匹配的版本。':'尚无已保存的版本。'));return}
  const lanes=new Map(data.branches.map((b,i)=>[b.name,i])),positions=new Map(commits.map((c,i)=>[c.id,{x:35+(lanes.get(c.branch)||0)*145,y:55+i*83}])),w=Math.max(600,data.branches.length*145+330),h=Math.max(200,commits.length*83+40),canvas=svg('svg',{viewBox:`0 0 ${w} ${h}`,width:w,height:h,role:'group','aria-label':'当前谱系的提交及父版本关系'});
  for(const b of data.branches)canvas.append(svg('text',{x:20+lanes.get(b.name)*145,y:21,class:'giver-svg-meta'},b.name.length>19?b.name.slice(0,17)+'…':b.name));
  for(const c of commits){const p=positions.get(c.id);for(const parent of c.parents){const q=positions.get(parent);if(q)canvas.append(svg('path',{d:`M${q.x},${q.y} C${q.x},${p.y-35} ${p.x},${p.y-35} ${p.x},${p.y}`,fill:'none',stroke:'#b1c3b4','stroke-width':2}))}}
  for(const c of commits){const p=positions.get(c.id),g=svg('g',{tabindex:0,role:'button','aria-label':c.message+' · '+c.id});g.append(svg('circle',{cx:p.x,cy:p.y,r:c.id===selected?.head?9:7,fill:c.id===inspected?'#aa813d':'#4d735a'}),svg('text',{x:p.x+16,y:p.y-4,class:'giver-svg-title'},c.message.length>46?c.message.slice(0,44)+'…':c.message),svg('text',{x:p.x+16,y:p.y+16,class:'giver-svg-meta'},c.id.slice(0,8)+' · '+new Date(c.at).toLocaleString()));g.onclick=()=>inspect(c);g.onkeydown=e=>{if(e.key==='Enter')inspect(c)};canvas.append(g);commitNodes.set(c.id,g);
   if(query.trim()){const button=make('button');button.append(make('strong',c.message),make('small',c.id.slice(0,8)+' · '+c.branch+' · '+new Date(c.at).toLocaleString()));button.onclick=async()=>{await inspect(c);locate(commitNodes.get(c.id))};$('version-results').prepend(button)}}$('log').append(canvas);
 }
 async function inspect(c){
  const stamp=++inspection,group=family.id;
  try{const snapshot=await post('show',{ref:c.id});if(stamp!==inspection||group!==family?.id)return;inspected=c.id;address();$('commit-info').hidden=false;$('commit-info').replaceChildren(make('h2',c.message),make('code',c.id),make('p',c.branch+' · '+new Date(c.at).toLocaleString()),make('p','父版本：'+(c.parents.map(p=>p.slice(0,8)).join(', ')||'初始提交')));
   const labels=Object.entries(data.tags).filter(([,id])=>id===c.id).map(([label])=>label);if(labels.length)$('commit-info').append(make('p','标签：'+labels.join(' · ')));
   for(const [k,v] of Object.entries(snapshot)){const details=make('details');details.append(make('summary',k+(v?.title?' · '+v.title:'')),make('pre',fmt(v)));$('commit-info').append(details)}log();
  }catch(e){if(stamp===inspection)VRUI.toast(e.message,true)}
 }
 function compareOptions(){for(const id of ['diff-source','diff-target']){const prior=$(id).value;$(id).replaceChildren();for(const b of data.branches){const o=make('option',b.title+' · '+b.name);o.value=b.name;$(id).append(o)}for(const [label] of Object.entries(data.tags)){const o=make('option','tag · '+label);o.value=label;$(id).append(o)}for(const c of [...data.commits].reverse()){const o=make('option',c.id.slice(0,8)+' · '+c.message);o.value=c.id;$(id).append(o)}if([...$(id).options].some(o=>o.value===prior))$(id).value=prior}if($('diff-source').options.length>1&&$('diff-source').value===$('diff-target').value)$('diff-target').selectedIndex=1}
 function records(){$('reflog').replaceChildren();for(const e of [...data.reflog].reverse()){const row=make('article');row.append(make('strong',e.action),make('span',(e.branch||e.tag||'')+' · '+new Date(e.at).toLocaleString()));$('reflog').append(row)}}
 async function refresh(){
  const was=family?.id,branch=selected?.name,tab=view,commit=inspected;workspace=await VRUI.request('/api/giver');groups=VRGiverView.families(workspace);
  if(was&&family?.id===was){const g=groups.find(g=>g.id===was);if(g){openFamily(g,branch,tab);if(commit){const c=data.commits.find(c=>c.id===commit);if(c)await inspect(c)}return}}
  const params=new URLSearchParams(location.search),requested=params.get('branch'),project=params.get('project');
  const g=groups.find(g=>(!project||g.id===project||g.branches.some(b=>b.project===project))&&(!requested||g.branches.some(b=>b.name===requested)));
  if((requested||project)&&g){openFamily(g,requested,params.get('view')||'tree',['tree','log'].includes(params.get('view')||'tree'));const c=data.commits.find(c=>c.id===params.get('commit'));if(c){setView('log');await inspect(c);locate(commitNodes.get(c.id))}}
  else{catalog();if(requested||project)VRUI.toast('未找到指定项目或分支，请重新选择项目谱系。',true)}
 }
 function diffRows(rows){$('diff').replaceChildren();if(!rows.length)$('diff').append(make('p','所选版本没有差异。'));for(const item of rows){const d=make('details'),grid=make('div');grid.className='giver-diff-grid';grid.append(make('pre',fmt(item.before)),make('pre',fmt(item.after)));d.append(make('summary',item.change+' · '+item.path),grid);$('diff').append(d)}}
 $('project-search').oninput=catalogRows;$('version-search').oninput=()=>{clearInspection();log();address()};$('back-catalog').onclick=catalog;
 $('init-form').onsubmit=e=>{e.preventDefault();act(e.submitter,async()=>{const result=await post('init',{title:$('init-title').value,mode:$('init-mode').value});$('init-title').value='';await refresh();openFamily(groups.find(g=>g.branches.some(b=>b.project===result.project)),result.branch);VRUI.toast('独立项目与初始快照已创建')})};
 $('commit-form').onsubmit=e=>{e.preventDefault();act(e.submitter,async()=>{await post('commit',{branch:selected.name,message:$('commit-message').value});$('commit-message').value='';await refresh();VRUI.toast('研究版本已提交')})};
 $('branch-form').onsubmit=e=>{e.preventDefault();act(e.submitter,async()=>{const branch=$('branch-name').value,mode=$('branch-mode').value;if(!await VRUI.confirm('保存当前分叉点并创建独立 '+(mode==='brainstorming'?'Brainstorming':'Engineering')+' 项目？原项目继续保留。',{title:'创建分支',accept:'创建'}))return;const result=await post('branch',{source:selected.name,branch,mode,request_id:crypto.randomUUID()});await refresh();select(data.branches.find(b=>b.name===result.branch),true);$('branch-name').value='';VRUI.toast('新分支已创建 · '+result.branch)})};
 $('tag-form').onsubmit=e=>{e.preventDefault();act(e.submitter,async()=>{await post('tag',{label:$('tag-name').value,ref:selected.name});await refresh();VRUI.toast('里程碑标签已保存')})};
 $('compare').onclick=()=>act($('compare'),async()=>{const stamp=family.id,result=await post('diff',{left:$('diff-source').value,right:$('diff-target').value});if(family?.id===stamp)diffRows(result.changes)});
 for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>setView(b.dataset.view);$('refresh').onclick=()=>act($('refresh'),refresh);refresh().catch(e=>VRUI.toast(e.message,true));
})();
