/* Browser-independent confirmation and visible task handoff, including embedded WebViews. */
window.VRUI=(()=>{
 const make=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e};
 let notice=null,activeConfirm=null;
 function toast(text,error=false){if(!notice){notice=make('div');notice.className='action-notice';notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');document.body.append(notice)}notice.dataset.error=String(error);notice.textContent=text;notice.hidden=false;}
 function confirm(message,{title='确认操作',accept='确认',destructive=false}={}){
  if(activeConfirm)return Promise.resolve(false);
  return new Promise(resolve=>{
   const previous=document.activeElement,overlay=make('div'),panel=make('section'),heading=make('h2',title),text=make('p',message),bar=make('div'),cancel=make('button','取消'),yes=make('button',accept);
   overlay.className='action-overlay';panel.className='action-dialog';panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');heading.id='action-dialog-title';panel.setAttribute('aria-labelledby',heading.id);text.id='action-dialog-description';panel.setAttribute('aria-describedby',text.id);bar.className='action-buttons';cancel.type=yes.type='button';yes.className=destructive?'action-danger':'primary';cancel.className='quiet';bar.append(cancel,yes);panel.append(heading,text,bar);overlay.append(panel);document.body.append(overlay);
   const finish=value=>{overlay.remove();activeConfirm=null;previous?.focus();resolve(value)};activeConfirm=overlay;cancel.onclick=()=>finish(false);yes.onclick=()=>finish(true);overlay.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();finish(false)}else if(e.key==='Tab'){e.preventDefault();(document.activeElement===cancel?yes:cancel).focus()}};cancel.focus();
  });
 }
 async function run(button,pending,fn){if(button.disabled)return;button.disabled=true;const original=button.textContent;button.textContent=pending;toast(pending);try{return await fn()}catch(e){toast(e.message||'操作未完成，请重试。',true);throw e}finally{button.disabled=false;button.textContent=original;if(notice?.textContent===pending)notice.hidden=true}}
 async function request(url,options={}){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);try{const r=await fetch(url,{...options,signal:controller.signal});const d=await r.json();if(!r.ok)throw Error(d.error||'操作未完成');return d}catch(e){if(e.name==='AbortError')throw Error('请求超时，暂未确认结果。请刷新核对后重试。');throw e}finally{clearTimeout(timer)}}
 function handoff(host,text){
  host.querySelector('.handoff-card')?.remove();const card=make('section'),heading=make('h3','在 Codex 继续'),hint=make('p','任务已准备好。复制下方内容，粘贴到 Codex 对话即可继续。'),area=make('textarea'),bar=make('div'),copy=make('button','复制任务'),select=make('button','选中任务文字'),status=make('p');card.className='handoff-card';card.setAttribute('aria-label','Codex 任务');area.value=text;area.readOnly=true;area.rows=4;area.setAttribute('aria-label','Codex 任务内容');bar.className='action-buttons';copy.type=select.type='button';copy.className='primary';select.className='quiet';status.setAttribute('role','status');bar.append(copy,select);card.append(heading,hint,area,bar,status);host.append(card);card.scrollIntoView({block:'nearest',behavior:'smooth'});area.focus();
  select.onclick=()=>{area.focus();area.select();status.textContent='已选中，可按 ⌘C / Ctrl+C 复制。'};
  copy.onclick=async()=>{if(copy.disabled)return;copy.disabled=true;status.textContent='正在复制…';let timer;try{await Promise.race([navigator.clipboard.writeText(text),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Clipboard unavailable')),1500)})]);status.textContent='已复制，请粘贴到 Codex 对话。';toast('任务已复制，请粘贴到 Codex 对话。')}catch(e){area.focus();area.select();status.textContent='此窗口无法自动复制。文字已选中，请按 ⌘C / Ctrl+C 复制。'}finally{clearTimeout(timer);copy.disabled=false}};
  toast('Codex 任务已准备好，请在任务卡片中复制。');return card;
 }
 for(const input of document.querySelectorAll('input[type=date]')){const sync=()=>{input.dataset.empty=String(!input.value)};sync();input.addEventListener('input',sync);input.addEventListener('change',sync)}
 return {confirm,toast,run,request,handoff};
})();
