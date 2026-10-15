"""Credential discovery and an interactive, non-logging setup guide."""
import getpass
import json
import os
import stat
import tempfile
from pathlib import Path
from .store import ResearchError

PROVIDERS = {
 'openalex': ('OpenAlex', 'OPENALEX_API_KEY', 'https://openalex.org/settings/api'),
 's2': ('Semantic Scholar', 'S2_API_KEY', 'https://www.semanticscholar.org/product/api#api-key-form'),
 'wos': ('Web of Science Starter', 'WOS_API_KEY', 'https://developer.clarivate.com/apis/wos-starter'),
 'scopus': ('Scopus', 'SCOPUS_API_KEY', 'https://dev.elsevier.com/'),
 'scopus_insttoken': ('Scopus Institutional Token', 'SCOPUS_INSTTOKEN', 'https://dev.elsevier.com/support.html'),
 'unpaywall': ('Unpaywall 联系邮箱', 'UNPAYWALL_EMAIL', 'https://unpaywall.org/products/api'),
}

def default_backend():
    import sys
    return 'keychain' if sys.platform == 'darwin' else 'file'

def backend_info():
    import sys
    backend=default_backend()
    return {
        'platform':'macOS' if sys.platform=='darwin' else 'Windows' if sys.platform=='win32' else 'Linux',
        'backend':backend,
        'description':'macOS 系统钥匙串；研究项目和诊断报告不保存密钥。' if backend=='keychain' else '当前用户目录中的权限受限配置文件；不会进入研究项目或迁移包。',
        'encrypted':backend=='keychain',
    }

def credential_path():
    return Path.home() / '.config' / 'vibe-research' / 'credentials.json'

def read_saved():
    p = credential_path()
    if not p.exists(): return {}
    if p.is_symlink() or not stat.S_ISREG(p.stat().st_mode):
        raise ResearchError('凭据必须为用户私有的普通文件')
    if os.name != 'nt' and (p.stat().st_mode & 0o077 or p.stat().st_uid != os.getuid()):
        raise ResearchError('凭据文件应仅属于当前用户且权限为 600')
    try:
        data = json.loads(p.read_text(encoding="utf8"))
        if not isinstance(data, dict) or any(k not in PROVIDERS or not isinstance(v,str) for k,v in data.items()):
            raise ValueError()
        return data
    except (ValueError, OSError):
        raise ResearchError('凭据文件无法读取或格式无效；请重新运行 integrations setup') from None

def keychain_refs():
    p=credential_path().with_name('keychain-providers.json')
    if not p.exists():return []
    try:
        refs=json.loads(p.read_text(encoding="utf8"))
        if not isinstance(refs,list) or any(p not in PROVIDERS for p in refs):raise ValueError()
        return refs
    except (OSError,ValueError):raise ResearchError('钥匙串引用配置无效')

def credential(provider):
    env = PROVIDERS.get(provider, ('','',''))[1]
    if not env: return None, 'not_required'
    value = os.environ.get(env, '').strip()
    if value: return value, 'environment'
    if provider in keychain_refs():
        from .keychain import Keychain
        value=Keychain().read(provider)
        if not value:raise ResearchError('钥匙串中未找到此来源凭据；请重新配置')
        return value,'keychain'
    value = read_saved().get(provider, '').strip()
    return (value or None), ('saved' if value else 'anonymous')

def save(provider, value, backend="file"):
    if provider not in PROVIDERS or not value.strip() or any(c.isspace() for c in value):
        raise ResearchError('API key 无效；请输入单行且无空白的 key')
    if provider=='unpaywall' and ('@' not in value or '.' not in value.rsplit('@',1)[-1]):raise ResearchError('请填写有效的本人联系邮箱')
    if backend=='keychain':
        from .keychain import Keychain
        from .store import atomic
        Keychain().save(provider,value)
        p=credential_path();p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        atomic(p.with_name('keychain-providers.json'),json.dumps(sorted(set(keychain_refs()+[provider]))))
        return
    if backend!='file':raise ResearchError('未知凭据存储方式')
    if provider in keychain_refs():raise ResearchError('此来源已使用钥匙串；请继续以钥匙串保存，避免明文副本')
    data = read_saved(); data[provider] = value
    p = credential_path(); p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.credentials-', dir=p.parent)
    try:
        if os.name != 'nt':
            os.fchmod(fd, 0o600)
        with os.fdopen(fd,'w') as f:
            json.dump(data,f); f.flush(); os.fsync(f.fileno())
        os.replace(name,p)
    finally:
        if os.path.exists(name): os.unlink(name)

def status():
    rows=[]
    for provider,(title,env,url) in PROVIDERS.items():
        if provider == 'scopus_insttoken':
            continue
        try:
            if os.environ.get(env,'').strip():configured=True;source='environment'
            elif provider in keychain_refs():configured=True;source='keychain'
            else:configured=bool(read_saved().get(provider));source='saved' if configured else 'anonymous'
            error=None
        except ResearchError as exc:
            configured=False;source='invalid_configuration';error=str(exc)
        row=dict(provider=provider,title=title,configured=configured,source=source,error=error,url=url,
                 note='已配置不等于已验证连接；先检测 API。' if configured else '需要官方授权；请打开接入向导。' if provider in ('wos','scopus') else '免费使用；需填写愿意发送给服务方的本人联系邮箱。' if provider=='unpaywall' else '可先匿名尝试；需要更稳定访问时申请免费 API key。')
        if provider == 'scopus':
            try:
                token, token_source = credential('scopus_insttoken')
                row['institutional_token_configured'] = bool(token)
                row['institutional_token_source'] = token_source
            except ResearchError as exc:
                row['institutional_token_configured'] = False
                row['institutional_token_error'] = str(exc)
        rows.append(row)
    rows += [dict(provider='arxiv',title='arXiv',source='not_required',configured=True,note='无需登录；自动连接，仍受网络与限流影响。'),
             dict(provider='zotero',title='Zotero 本地文献库',source='local_app',configured=False,url='https://www.zotero.org/support/dev/web_api/v3/local',note='启动 Zotero 并在高级设置允许本机 API 读取；无需云端登录。')]
    rows += [dict(provider=p,title=t,source='not_required',configured=True,note=n) for p,t,n in [('crossref','Crossref','免费元数据查询；支持分页。'),('core','CORE','匿名基础访问；保守限速，不自动购买加速。'),('huggingface','Hugging Face Papers','论文发现；未验证完整分页，不能代替全覆盖检索。')]]
    return {'providers':rows,'credential_backend':backend_info(),'note':'环境变量优先，其次为已配置的系统钥匙串，最后为既有私有配置文件。密码、验证码和 API key 不进入研究库。'}

def setup(provider=None,backend=None):
    import sys
    if not sys.stdin.isatty(): raise ResearchError('请在本机交互终端运行 integrations setup；不要把 key 写入命令参数或聊天。')
    print('数据库配置引导：arXiv 无需登录；OpenAlex / Semantic Scholar 可匿名尝试。')
    backend=backend or default_backend()
    print('保存方式：'+('macOS 系统钥匙串，密钥不进入命令参数或研究备份。' if backend=='keychain' else '权限 600 明文文件（非加密），不进入研究备份。'))
    for p in ([provider] if provider else ('openalex','s2')):
        title,env,url=PROVIDERS[p]
        print('\n'+title+'：'+url)
        print('已有 '+env+' 时优先使用；留空跳过。账户注册、验证码和 key 申请需本人完成。')
        if p=='unpaywall':print('Unpaywall 会在 DOI 查询时接收这个联系邮箱；仅填写你愿意发送给服务方的本人邮箱。')
        prompt = '填写联系邮箱' if p=='unpaywall' else '粘贴 Institutional Token' if p=='scopus_insttoken' else '粘贴 API key'
        value=getpass.getpass(prompt+'（不回显，输入即同意保存在本机）：').strip()
        if value:
            save(p,value,backend)
            print('已保存；请返回此来源的接入引导验证一次连接。' if p in ('wos','scopus','unpaywall') else '已保存；请运行 integrations check --network 验证。')
    return status()
