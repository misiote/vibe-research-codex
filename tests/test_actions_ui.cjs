// Exercise embedded-WebView failure cases without browser confirm or clipboard permissions.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class E{
 constructor(tag,doc){Object.assign(this,{tag,doc,children:[],attrs:{},dataset:{},disabled:false,text:'',value:''})}
 append(...items){for(const c of items){c.parent=this;this.children.push(c)}}
 set textContent(v){this.text=v;this.children=[]}get textContent(){return this.text+this.children.map(c=>c.textContent).join('')}
 setAttribute(k,v){this.attrs[k]=v}remove(){this.parent.children=this.parent.children.filter(c=>c!==this)}
 focus(){this.doc.activeElement=this}select(){this.selected=true}scrollIntoView(){}
 querySelector(selector){return this.children.flatMap(c=>[c,c.querySelector(selector)]).find(c=>c&&c.className===selector.slice(1))||null}
}
const doc={activeElement:null,querySelectorAll:()=>[]};doc.body=new E('body',doc);doc.createElement=tag=>new E(tag,doc);
const ctx={window:{},document:doc,navigator:{clipboard:{writeText:async()=>{throw Error('Denied')}}},setTimeout:(fn,ms)=>setTimeout(fn,Math.min(ms,10)),clearTimeout,AbortController,Error,fetch:async()=>({ok:true,json:async()=>({ok:true})})};
vm.runInNewContext(fs.readFileSync('plugins/vibe-research/runtime/vr/static/actions.js','utf8'),ctx);
const UI=ctx.window.VRUI,find=(e,tag)=>e.children.flatMap(c=>[...(c.tag===tag?[c]:[]),...find(c,tag)]);
(async()=>{
 let p=UI.confirm('Keep files?',{accept:'Archive'});assert.equal(find(doc.body,'section')[0].attrs.role,'dialog');assert.equal(await UI.confirm('Duplicate?'),false);find(doc.body,'button').find(b=>b.textContent==='取消').onclick();assert.equal(await p,false);
 p=UI.confirm('Archive?',{accept:'Archive'});find(doc.body,'button').find(b=>b.textContent==='Archive').onclick();assert.equal(await p,true);
 p=UI.confirm('Escape?');doc.body.children.find(c=>c.className==='action-overlay').onkeydown({key:'Escape',preventDefault(){}});assert.equal(await p,false);
 const host=new E('div',doc);doc.body.append(host);let card=UI.handoff(host,'Known task');assert.equal(find(card,'textarea')[0].value,'Known task');await find(card,'button').find(b=>b.textContent==='复制任务').onclick();assert.match(card.textContent,/无法自动复制/);assert.equal(find(card,'textarea')[0].selected,true);
 ctx.navigator.clipboard.writeText=()=>new Promise(()=>{});card=UI.handoff(host,'Second task');assert.equal(host.children.length,1);await find(card,'button').find(b=>b.textContent==='复制任务').onclick();assert.match(card.textContent,/无法自动复制/);assert.equal(find(card,'button')[0].disabled,false);
 const button=new E('button',doc);button.textContent='Run';let resolve,calls=0;const work=UI.run(button,'Pending',()=>{calls++;return new Promise(r=>resolve=r)});await UI.run(button,'Pending',()=>calls++);assert.equal(calls,1);resolve();await work;assert.equal(button.disabled,false);assert.equal(button.textContent,'Run');
 console.log('Actions UI: cancel, accept, Escape, duplicate confirmation, denied/hanging clipboard fallback, task replacement and duplicate click prevention passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
