/* Deterministic collision-aware force integrator, shared by browser and tests. */
const VRPhysics = (() => {
 function step(nodes,links,{alpha=1,radius=()=>12,stage=false}={}) {
  for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
   const a=nodes[i],b=nodes[j];let dx=b.x-a.x,dy=b.y-a.y,d=Math.hypot(dx,dy);
   if(d<.001){const angle=(i*31+j*17)*2.399;dx=Math.cos(angle)*.01;dy=Math.sin(angle)*.01;d=.01;}
   const min=radius(a)+radius(b)+12,force=Math.min(4,460/Math.max(100,d*d))*alpha;
   a.vx-=dx/d*force;a.vy-=dy/d*force;b.vx+=dx/d*force;b.vy+=dy/d*force;
   if(d<min){const push=(min-d)*.5,weight=a.pinned||b.pinned?1: .5;
    if(!a.pinned){a.x-=dx/d*push*weight;a.y-=dy/d*push*weight;}
    if(!b.pinned){b.x+=dx/d*push*weight;b.y+=dy/d*push*weight;}
   }
  }
  for(const e of links){const a=e.source,b=e.target,dx=b.x-a.x,dy=b.y-a.y,d=Math.max(1,Math.hypot(dx,dy));const f=(d-115)*.018*alpha;a.vx+=dx/d*f;a.vy+=dy/d*f;b.vx-=dx/d*f;b.vy-=dy/d*f;}
  let energy=0;
  for(const n of nodes){const ax=stage?n.anchorX:0,ay=stage?n.anchorY:0,k=stage?.04:.0015;
   n.vx=(n.vx+(ax-n.x)*k*alpha)*.72;n.vy=(n.vy+(ay-n.y)*k*alpha)*.72;
   if(n.pinned){n.vx=n.vy=0;continue;}
   n.x+=Math.max(-8,Math.min(8,n.vx));n.y+=Math.max(-8,Math.min(8,n.vy));energy+=n.vx*n.vx+n.vy*n.vy;
  }return energy;
 }
 return {step};
})();
if(typeof module!=='undefined')module.exports=VRPhysics;
