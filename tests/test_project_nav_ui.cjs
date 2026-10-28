const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.attrs={};this.events={};this.hidden=true;}
 append(x){this.children.push(x)}replaceChildren(...xs){this.children=xs}setAttribute(k,v){this.attrs[k]=v}removeAttribute(k){delete this.attrs[k]}addEventListener(k,fn){this.events[k]=fn}
}
const events={},legacy=new Element('nav'),location={pathname:'/brainstorming',hash:'',assign(url){this.assigned=url}};
const context={window:{},document:{createElement:t=>new Element(t),getElementById:id=>id==='legacy-workbench-tabs'?legacy:null},location,WeakMap,Error,encodeURIComponent,addEventListener:(k,fn)=>events[k]=fn,removeEventListener:()=>{}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../plugins/vibe-research/runtime/vr/static/project_nav.js'),'utf8'),context);
const host=new Element('div'),a='p111111111111',b='p222222222222';
let api=context.window.VRProjectNav.mount(host,{project:a,mode:'brainstorming',board:'Baaaaaaaaaaaa',title:'Ideas',view:'mode'});
assert.equal(api.items.find(i=>i.view==='mode').url,'/brainstorming?space=Baaaaaaaaaaaa');
assert.equal(api.items.find(i=>i.view==='map').url,'/p/'+a+'/#map');
assert.equal(host.children[1].children.find(e=>e.attrs['aria-current']==='page').textContent,'Brainstorming');
api=context.window.VRProjectNav.mount(host,{project:b,mode:'brainstorming',board:'Bbbbbbbbbbbbb',title:'Other ideas',view:'mode'});
assert(api.items.filter(i=>i.view!=='mode').every(i=>i.url.startsWith('/p/'+b+'/')));
assert.equal(api.items.find(i=>i.view==='mode').url,'/brainstorming?space=Bbbbbbbbbbbbb');
location.pathname='/p/'+b+'/';location.hash='#map';
context.window.VRProjectNav.mount(host,{project:b,mode:'brainstorming',board:'Bbbbbbbbbbbb'});
assert.equal(host.children[1].children.find(e=>e.attrs['aria-current']==='page').textContent,'研究地图');
location.hash='#library';events.hashchange();
assert.equal(host.children[1].children.find(e=>e.attrs['aria-current']==='page').textContent,'文献');
assert.equal(legacy.hidden,true);
assert.throws(()=>context.window.VRProjectNav.mount(host,{project:'../other',mode:'brainstorming'}));
(async()=>{
 let allowed=false,prevented=false;
 context.window.VRProjectNav.mount(host,{project:a,mode:'engineering',beforeNavigate:async()=>allowed});
 const link=host.children[1].children.find(e=>e.dataset.projectView==='map');
 const event={button:0,preventDefault(){prevented=true}};
 await link.events.click(event);assert(prevented);assert.equal(location.assigned,undefined);
 allowed=true;await link.events.click(event);assert.equal(location.assigned,'/p/'+a+'/#map');
 console.log('Project navigation: scoped links, board changes, return paths, hash selection and unsaved edit guard passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
