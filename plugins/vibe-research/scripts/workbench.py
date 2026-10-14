#!/usr/bin/env python3
"""Portable plugin launcher; writes user data only to an explicitly selected workspace."""
import argparse,json,os,subprocess,sys,time,urllib.request,urllib.error,webbrowser
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--port',type=int,default=8766);p.add_argument('--no-open',action='store_true');a=p.parse_args()
root=Path(a.workspace).expanduser().resolve();plugin=Path(__file__).resolve().parents[1]
if plugin==root or plugin in root.parents:sys.exit('研究数据不能放在插件目录中；升级会替换插件。')
root.mkdir(parents=True,exist_ok=True);registry=root/'projects.json';url='http://127.0.0.1:'+str(a.port)
for proxy_key in ('NO_PROXY','no_proxy'):
 entries=[part.strip() for part in os.environ.get(proxy_key,'').split(',') if part.strip()]
 for local_host in ('127.0.0.1','localhost'):
  if local_host not in entries:entries.append(local_host)
 os.environ[proxy_key]=','.join(entries)
local_opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def runtime_python():
 explicit=os.environ.get('VR_PYTHON');candidates=[Path(explicit).expanduser()] if explicit else []
 base=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/python';prepared=Path.home()/'.config/vibe-research/python-runtime'
 candidates += [prepared/'bin/python',prepared/'Scripts/python.exe',base/'bin/python3',base/'bin/python',base/'python.exe',base/'Scripts/python.exe',Path(sys.executable)]
 fallback=Path(sys.executable)
 for candidate in candidates:
  if not candidate.is_file():continue
  if explicit:return str(candidate)
  try:
   if subprocess.run([str(candidate),'-c','import pypdf'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5).returncode==0:return str(candidate)
  except (OSError,subprocess.TimeoutExpired):pass
  fallback=candidate
 return str(fallback)
python=runtime_python()
def probe():
 try:
  with local_opener.open(url+'/api/workspace',timeout=2) as r:data=json.load(r)
  if data.get('registry')!=str(registry):raise RuntimeError('此端口属于另一工作区；请选择其他 --port，不会接管它。')
  return True
 except urllib.error.HTTPError:raise RuntimeError('此端口不是兼容工作台，请先更新服务或选择其他端口。')
 except (urllib.error.URLError,TimeoutError):return False
try:
 if not probe():
  with open(root/'workbench-server.log','ab') as log:
   detach={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS} if os.name=='nt' else {'start_new_session':True}
   child=subprocess.Popen([python,str(plugin/'runtime/bin/vr'),'hub','serve','--registry',str(registry),'--port',str(a.port)],cwd=root,stdout=log,stderr=log,**detach)
  for _ in range(40):
   if child.poll() is not None:raise RuntimeError('工作台启动失败，请查看本工作区日志。')
   if probe():break
   time.sleep(.15)
  else:raise RuntimeError('服务未确认启动。')
 if not a.no_open:webbrowser.open(url)
 print(url)
except (OSError,ValueError,RuntimeError) as exc:sys.exit(str(exc))
