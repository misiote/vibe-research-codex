/* Fixed 3D stage coordinates and camera projection. No force simulation. */
const VRStage=(()=>{
 const stages={RQ:0,P:1,V:2,C:3,G:3,I:4,H:4,X:5,Q:5,R:6,F:6,D:6,A:6};
 const titles=['研究问题','文献线索','证据阅读','洞察与缺口','构想与假设','实施与实验','结果与决策'];
 function reset(nodes){nodes.forEach((n,i)=>{const a=i*2.39996;n.x=Math.cos(a)*30*Math.sqrt(i+1);n.y=Math.sin(a)*30*Math.sqrt(i+1);n.vx=n.vy=0;n.pinned=false;});}
 function layout(nodes){const buckets=titles.map(()=>[]);nodes.forEach(n=>buckets[stages[n.kind]??6].push(n));let span=340;
  const layers=buckets.map((rows,level)=>{rows.sort((a,b)=>a.id.localeCompare(b.id));const cols=Math.max(1,Math.ceil(Math.sqrt(rows.length))),count=Math.ceil(rows.length/cols);span=Math.max(span,cols*90,count*90);rows.forEach((n,i)=>{n.world={x:(i%cols-(cols-1)/2)*90,y:(level-3)*115,z:(Math.floor(i/cols)-(count-1)/2)*90};n.vx=n.vy=0;n.pinned=false;});return {level,title:titles[level],count:rows.length};});
  return {layers,span:span+70};
 }
 function project(p,yaw=-.45,pitch=.48){const x=p.x*Math.cos(yaw)+p.z*Math.sin(yaw),z=p.z*Math.cos(yaw)-p.x*Math.sin(yaw),y=p.y*Math.cos(pitch)-z*Math.sin(pitch),depth=p.y*Math.sin(pitch)+z*Math.cos(pitch),k=1800/(1800+depth);return {x:x*k,y:y*k,depth};}
 return {reset,layout,project};
})();
if(typeof module!=='undefined')module.exports=VRStage;
