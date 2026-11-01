/* Read-only projections for the project-first giver browser. */
((root)=>{
 function families(data){
  const branches=data.branches||[],by=new Map(branches.map(b=>[b.name,b])),adj=new Map(branches.map(b=>[b.name,[]]));
  for(const b of branches)if(by.has(b.parent)){adj.get(b.name).push(b.parent);adj.get(b.parent).push(b.name)}
  const seen=new Set(),groups=[];
  for(const b of branches){
   if(seen.has(b.name))continue;const members=[],queue=[b.name];
   while(queue.length){const n=queue.pop();if(seen.has(n))continue;seen.add(n);members.push(by.get(n));queue.push(...adj.get(n))}
   const origin=members.find(m=>!by.has(m.parent))||[...members].sort((a,b)=>a.name.localeCompare(b.name))[0];
   const ordered=[],visited=new Set(),walk=m=>{if(visited.has(m.name))return;visited.add(m.name);ordered.push(m);for(const child of members.filter(b=>b.parent===m.name).sort((a,b)=>a.name.localeCompare(b.name)))walk(child)};walk(origin);for(const m of members)walk(m);
   const names=new Set(members.map(m=>m.name)),projects=new Set(members.map(m=>m.project));
   const commits=(data.commits||[]).filter(c=>projects.has(c.project)||names.has(c.branch));
   groups.push({id:origin.project,title:origin.title,origin,branches:ordered,commits});
  }
  return groups.sort((a,b)=>a.title.localeCompare(b.title)||a.id.localeCompare(b.id));
 }
 function matches(branch,q){return [branch.title,branch.name,branch.project,branch.mode].some(v=>String(v||'').toLocaleLowerCase().includes(q))}
 function search(groups,query){const q=query.trim().toLocaleLowerCase();return groups.filter(g=>!q||g.branches.some(b=>matches(b,q)))}
 function scope(data,group){
  const names=new Set(group.branches.map(b=>b.name)),ids=new Set(group.commits.map(c=>c.id));
  const tags=Object.fromEntries(Object.entries(data.tags||{}).filter(([,id])=>ids.has(id)));
  return {branches:group.branches,commits:group.commits,tags,reflog:(data.reflog||[]).filter(e=>names.has(e.branch)||names.has(e.source)||ids.has(e.commit)||Object.hasOwn(tags,e.tag))};
 }
 function versions(data,query){
  const q=query.trim().toLocaleLowerCase();return data.commits.filter(c=>!q||[c.id,c.message,c.branch,c.at,...Object.entries(data.tags).filter(([,id])=>id===c.id).map(([label])=>label)].some(v=>String(v).toLocaleLowerCase().includes(q)));
 }
 const api={families,search,scope,versions};root.VRGiverView=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
