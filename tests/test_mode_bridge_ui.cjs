const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class E{
 constructor(tag){Object.assign(this,{tag,children:[],attrs:{},value:'',hidden:false,disabled:false,dataset:{},listeners:{},text:''})}
 append(...x){this.children.push(...x)} replaceChildren(...x){this.children=x;this.text=''}
 set textContent(v){this.text=v;this.children=[]} get textContent(){return this.text+this.children.map(c=>c.textContent||'').join('')}
 setAttribute(k,v){this.attrs[k]=v} addEventListener(k,f){this.listeners[k]=f}
 querySelectorAll(s){return this.children.flatMap(c=>[...(s.split(',').includes(c.tag)?[c]:[]),...c.querySelectorAll(s)])}
}
function setup(){
 const host=new E('div');let board={id:'B1',updated_at:'v1',topic:'Topic',context:'Idea',connections:[]},handler,calls=[],lineage=[];
 const ctx={window:{},document:{createElement:t=>new E(t),createTextNode:t=>{const e=new E('text');e.textContent=t;return e}},crypto:require('node:crypto').webcrypto,Date,Error,fetch:async(url,opts)=>{
  if(url==='/api/giver')return {ok:true,json:async()=>({branches:lineage})};if(url==='/api/projects')return {ok:true,json:async()=>({projects:[]})};if(url==='/api/session')return {ok:true,json:async()=>({token:'test'})};
  const req=JSON.parse(opts.body);calls.push(req);return req.action==='transfer'?handler(req):{ok:true,json:async()=>({topic:board.topic})};
 }};
 vm.runInNewContext(fs.readFileSync('plugins/vibe-research/runtime/vr/static/mode_bridge.js','utf8'),ctx);
 const ui=ctx.window.VRBridge.mount(host,{direction:'promote',getBoard:()=>board,refresh:async()=>{throw Error('Refresh failed')}}),all=()=>host.querySelectorAll('section,div,p,strong,a,button');
 return {host,ui,calls,button:t=>all().find(e=>e.tag==='button'&&e.textContent===t),status:()=>all().find(e=>e.className==='transfer-status'),receipt:()=>all().find(e=>e.className==='transfer-receipt'),setBoard:b=>board=b,setLineage:rows=>lineage=rows,setHandler:f=>handler=f};
}
const ok={ok:true,json:async()=>({project:'p123',board:'B1',task:'A42',url:'/p/p123/engineering'})};
(async()=>{
 const t=setup();await t.button('转为 Engineering ↗').onclick();await t.button('预览转化').onclick();let resolve;t.setHandler(()=>new Promise(r=>resolve=r));
 const confirm=t.button('确认转化'),pending=confirm.onclick();await new Promise(setImmediate);assert.match(t.status().textContent,/正在转化/);assert.equal(confirm.disabled,true);await confirm.onclick();assert.equal(t.calls.filter(c=>c.action==='transfer').length,1);
 resolve(ok);await pending;assert.match(t.status().textContent,/转化成功/);assert.equal(t.receipt().hidden,false);assert.match(t.receipt().textContent,/A42/);assert.match(t.receipt().textContent,/进入 Engineering/);assert.equal(t.host.querySelectorAll('p').some(e=>/转化已成功.*刷新/.test(e.textContent)),true);
 const r=setup();await r.button('转为 Engineering ↗').onclick();await r.button('预览转化').onclick();r.setHandler(async()=>{throw Error('Connection lost')});await r.button('确认转化').onclick();assert.match(r.status().textContent,/暂未确认/);
 const id=r.calls.find(c=>c.action==='transfer').spec.request_id;r.setHandler(async()=>ok);await r.button('重试转化').onclick();assert.equal(r.calls.filter(c=>c.action==='transfer').at(-1).spec.request_id,id);
 r.setBoard({id:'B2',connections:[]});r.ui.sync();assert.equal(r.receipt().hidden,true);r.setLineage([{name:'ideas/main',project:'pSource'},{name:'engineering/new',parent:'ideas/main',project:'pExisting',mode:'engineering',created_at:'2026-10-25',title:'Independent project',url:'/p/pExisting/engineering'}]);r.setBoard({id:'B3',project:'pSource',connections:[]});r.ui.sync();await new Promise(setImmediate);assert.match(r.receipt().textContent,/已关联 Engineering/);assert.match(r.receipt().textContent,/engineering\/new/);
 console.log('Transfer UI: pending, duplicate clicks, committed refresh failure, retry identity, board switch and saved receipt passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
