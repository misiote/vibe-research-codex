/* Cross-mode transfer: visible entry, explicit progress and durable destination receipt. */
window.VRBridge=(()=>{
 const make=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e};
 async function get(url){const r=await fetch(url),d=await r.json();if(!r.ok)throw Error(d.error||'读取未完成');return d}
 async function post(action,spec){const token=(await get('/api/session')).token,r=await fetch('/api/bridge',{method:'POST',headers:{'Content-Type':'application/json','X-VR-Token':token},body:JSON.stringify({action,spec})}),d=await r.json();if(!r.ok)throw Error(d.error||'转化未完成');return d}
 function mount(host,options){
  const promote=options.direction==='promote',destination=promote?'Engineering':'Brainstorming';
  const card=make('section'),heading=make('div'),copy=make('div'),title=make('h2','继续到 '+destination),intro=make('p',promote?'让选定方向进入实施，保留主题与研究依据。':'将工程进展带回讨论，继续整理与规划。'),open=make('button',promote?'转为 Engineering ↗':'转为 Brainstorming ↗');
  card.className='transfer-card';card.setAttribute('aria-label','模式转化');heading.className='transfer-heading';intro.className='hintline';open.className='primary';open.type='button';open.setAttribute('aria-expanded','false');copy.append(title,intro);heading.append(copy,open);
  const form=make('div'),target=make('p'),label=make('label','派生方式');form.className='transfer-form';form.hidden=true;target.setAttribute('aria-label',promote?'目标工程项目':'目标主题空间');label.append(target);form.append(label);
  let targets=[],prepared=null,requestId=null,busy=false,boardId=null,loading=false;
  const fields={};function field(key,title,area=false,parent=form){const label=make('label',title),input=make(area?'textarea':'input');input.setAttribute('aria-label',title);if(area)input.rows=3;label.append(input);parent.append(label);fields[key]=input;return input}
  if(promote){field('idea','选定构想',true);field('acceptance','验收标准（可稍后完善）');const more=make('details'),summary=make('summary','关联开发环境（可选）');more.className='transfer-environment';more.append(summary);form.append(more);field('repo','本地仓库',false,more);field('sshHost','SSH Host',false,more);field('sshRepo','远程仓库',false,more);}
  else field('topic','新项目名称（可选）');
  field('branch','新分支名称（可选）');
  const bar=make('div'),preview=make('button','预览转化'),confirm=make('button','确认转化'),cancel=make('button','收起'),note=make('p'),error=make('p'),result=make('div'),receipt=make('section');
  bar.className='transfer-actions';preview.className='quiet';confirm.className='primary';cancel.className='quiet';confirm.disabled=true;note.className='transfer-status';note.setAttribute('role','status');note.setAttribute('aria-live','polite');error.className='transfer-error';error.setAttribute('role','alert');result.className='transfer-preview';result.hidden=true;receipt.className='transfer-receipt';receipt.setAttribute('role','status');receipt.hidden=true;bar.append(preview,confirm,cancel);form.append(result,bar);card.append(heading,form,note,error,receipt);host.append(card);
  function state(text,phase=''){note.textContent=text;card.dataset.state=phase;card.setAttribute('aria-busy',phase==='pending'?'true':'false')}
  function lock(value){busy=value;open.disabled=value;for(const e of form.querySelectorAll('input,textarea,select,button'))e.disabled=value;confirm.disabled=value||!prepared;}
  function showReceipt(data,persisted=false){
   const name=data.targetName||(promote?(targets.find(t=>t.id===data.project)?.name):targets.find(t=>t.id===data.board)?.topic)||(promote?data.project:data.board);
   receipt.replaceChildren();receipt.hidden=false;receipt.append(make('strong',persisted?'已关联 '+destination:'✓ 已转化到 '+destination));
   receipt.append(make('p',(promote?'目标项目：':'主题空间：')+name));
   if(data.branch)receipt.append(make('p','分支：'+data.branch));if(data.base)receipt.append(make('p','分叉点：'+data.base.slice(0,8)));if(data.task)receipt.append(make('p','已建立工作包 '+data.task));
   receipt.append(make('p',persisted?'项目独立保存，派生关系由 giver 管理。':'已建立独立项目；来源版本保留，两个分支后续各自演进。'));
   const link=make('a','进入 '+destination+' ↗');link.className='transfer-destination';link.href=data.url||(promote?'/p/'+data.project+'/engineering':'/brainstorming?space='+data.board);receipt.append(link);const tree=make('a','在 giver 查看分支 ↗');tree.className='transfer-destination';tree.href='/giver'+(data.branch?'?branch='+encodeURIComponent(data.branch):'');receipt.append(document.createTextNode(' '),tree);
  }
  function sync(){
   if(busy)return;const board=options.getBoard?.(),scope=promote?board?.id:options.project,source=promote?board?.project:options.project;if(boardId===scope)return;boardId=scope;prepared=null;requestId=null;form.hidden=true;open.setAttribute('aria-expanded','false');confirm.disabled=true;receipt.hidden=true;result.hidden=true;error.textContent='';state('');
   if(source)get('/api/giver').then(d=>{if(boardId!==scope||busy)return;const parent=d.branches.find(b=>b.project===source);const child=d.branches.filter(b=>b.parent===parent?.name&&b.mode===(promote?'engineering':'brainstorming')).sort((a,b)=>b.created_at.localeCompare(a.created_at))[0];if(child)showReceipt({...child,branch:child.name,targetName:child.title},true)}).catch(()=>{});
  }
  form.addEventListener('input',()=>{prepared=null;requestId=null;confirm.disabled=true;result.hidden=true;error.textContent='';state('填写完成后，先预览目标与将要建立的关联。')});
  cancel.onclick=()=>{form.hidden=true;open.setAttribute('aria-expanded','false');state('')};
  open.onclick=async()=>{
   if(busy||loading)return;sync();if(!form.hidden){form.hidden=true;open.setAttribute('aria-expanded','false');return}
   loading=true;form.hidden=false;open.setAttribute('aria-expanded','true');prepared=null;confirm.disabled=true;error.textContent='';state('正在读取可关联的空间…','pending');lock(true);
   try{targets=[];target.textContent='新建独立 '+destination+' 项目与 giver 分支';
    if(promote){const board=options.getBoard();fields.idea.value=board?.modules?.directions?.content||board?.modules?.proposal?.content||board?.context||'';}
    state('预览分叉点，确认后创建独立项目；来源保持独立。');
   }catch(e){error.textContent=e.message;state('读取失败，请重新打开重试。','error')}finally{loading=false;lock(false)}
  };
  preview.onclick=async()=>{
   if(busy)return;error.textContent='';state('正在保存来源并生成预览…','pending');lock(true);
   try{await options.beforePreview?.();let spec={direction:options.direction,request_id:requestId||crypto.randomUUID()};requestId=spec.request_id;if(fields.branch.value.trim())spec.branch=fields.branch.value.trim();
    if(promote){const board=options.getBoard();if(!board)throw Error('先选择主题空间');spec={...spec,board:board.id,expected_updated_at:board.updated_at,idea:fields.idea.value};if(fields.acceptance.value)spec.acceptance=fields.acceptance.value;if(fields.repo.value||fields.sshHost.value){spec.environment={};if(fields.repo.value)spec.environment.repo=fields.repo.value;if(fields.sshHost.value)spec.environment.ssh={host:fields.sshHost.value,repo:fields.sshRepo.value};}}
    else{spec.project=options.project;if(fields.topic.value)spec.topic=fields.topic.value;}
    const d=await post('preview',spec);if(!promote)spec.source_revision=d.packet.revision;prepared=spec;result.hidden=false;result.textContent=promote?'目标：'+(targets.find(t=>t.id===spec.target)?.name||'新建项目 · '+d.topic)+'\n从当前快照创建独立项目与分支，保留来源；后续更改互不覆盖。':d.packet.markdown;state('预览已就绪，点击「确认转化」完成。');confirm.textContent='确认转化';
   }catch(e){prepared=null;error.textContent=e.message;state('预览未完成，请检查后重试。','error')}finally{lock(false)}
  };
  confirm.onclick=async()=>{
   if(!prepared||busy)return;error.textContent='';state('正在转化到 '+destination+'，请稍候…','pending');confirm.textContent='转化中…';lock(true);
   let d;try{d=await post('transfer',prepared)}catch(e){error.textContent=e.message;state('暂未确认转化结果。可点击重试，系统会复用本次请求以避免重复创建。','error');confirm.textContent='重试转化';lock(false);return}
   const targetName=d.title||(promote?(targets.find(t=>t.id===d.project)?.name||options.getBoard()?.topic):(targets.find(t=>t.id===d.board)?.topic||fields.topic.value));
   prepared=null;requestId=null;form.hidden=true;open.setAttribute('aria-expanded','false');showReceipt({...d,targetName});state('转化成功 · '+new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}),'success');confirm.textContent='确认转化';
   try{await options.refresh?.()}catch(e){error.textContent='转化已成功，当前视图刷新未完成。可通过下方入口继续。'}finally{lock(false)}
  };
  sync();
  return {sync,restore:data=>{if(!busy&&receipt.hidden)showReceipt(data,true)}};
 }
 return {mount};
})();
