"""Non-secret institutional network profiles and per-provider request routing."""
import hashlib
import json
import os
import re
import socket
import stat
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from .store import ResearchError, now


INSTITUTIONS = {
    "casia": {
        "title": "中国科学院自动化研究所",
        "portal_url": "https://webvpn.ia.ac.cn/",
        "portal_kind": "browser_reverse_proxy",
        "official_hosts": ("webvpn.ia.ac.cn", "ia.ac.cn"),
        "note": "图书馆电子资源远程访问云系统适合浏览器访问；它不会把 Python API 请求自动变成机构 IP 请求。",
    },
}

METHODS = {
    "auto": "自动判断",
    "campus_vpn": "校内网络或校园 VPN",
    "browser_portal": "机构网页入口",
    "institutional_token": "Elsevier Institutional Token",
    "public_only": "仅使用公开/基础 API 权限",
}


def runtime_root():
    if os.name == "nt":
        default = Path(os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming"))) / "VibeResearch/runtime"
    else:
        default = Path.home() / ".config/vibe-research"
    return Path(os.environ.get("VR_RUNTIME_DIR", str(default)))


def profile_path():
    return runtime_root() / "network-profiles.json"


def _private_file(path):
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise ResearchError("网络配置必须是当前用户的普通文件")
    if os.name != "nt" and (path.stat().st_mode & 0o077 or path.stat().st_uid != os.getuid()):
        raise ResearchError("网络配置文件应仅属于当前用户且权限为 600")


def _valid_portal(value):
    if not value:
        return ""
    if len(value) > 500:
        raise ResearchError("机构入口地址过长")
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ResearchError("机构入口必须是不含账号信息的 HTTPS 地址")
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        raise ResearchError("机构入口不能指向本机地址")
    return urllib.parse.urlunsplit(("https", parsed.netloc, parsed.path or "/", parsed.query, ""))


def _validate(data):
    if not isinstance(data, dict) or set(data) - {"version", "routes"}:
        raise ResearchError("网络配置格式无效")
    routes = data.get("routes", {})
    if not isinstance(routes, dict) or set(routes) - {"scopus", "wos"}:
        raise ResearchError("数据库路由配置无效")
    clean = {"version": 1, "routes": {}}
    for provider, route in routes.items():
        if not isinstance(route, dict):
            raise ResearchError("数据库路由项无效")
        method = route.get("method", "auto")
        declared_network = route.get("declared_network", "unknown")
        institution_id = route.get("institution_id", "custom")
        name = route.get("institution_name", "").strip()
        if method not in METHODS or declared_network not in {"campus", "off_campus", "unknown"} or institution_id not in {*INSTITUTIONS, "custom", "none"}:
            raise ResearchError("机构或接入方式无效")
        if institution_id in INSTITUTIONS:
            preset = INSTITUTIONS[institution_id]
            name, portal = preset["title"], preset["portal_url"]
        else:
            portal = _valid_portal(route.get("portal_url", ""))
            if institution_id == "custom" and not name:
                raise ResearchError("请填写机构名称")
        clean["routes"][provider] = {
            "institution_id": institution_id,
            "institution_name": name[:160],
            "portal_url": portal,
            "method": method,
            "declared_network": declared_network,
            "updated_at": str(route.get("updated_at", ""))[:64],
        }
    return clean


def load():
    path = profile_path()
    if not path.exists():
        return {"version": 1, "routes": {}}
    _private_file(path)
    try:
        return _validate(json.loads(path.read_text(encoding="utf8")))
    except (OSError, ValueError, json.JSONDecodeError):
        raise ResearchError("网络配置无法读取，请重新运行接入向导") from None


def _write(data):
    path = profile_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".network-profiles-", dir=path.parent)
    try:
        if os.name != "nt":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def configure(provider, institution_id, institution_name, portal_url, method, declared_network="unknown"):
    if provider not in {"scopus", "wos"} or method not in METHODS:
        raise ResearchError("数据库或接入方式无效")
    data = load()
    candidate = {
        "institution_id": institution_id,
        "institution_name": institution_name,
        "portal_url": portal_url,
        "method": method,
        "declared_network": declared_network,
        "updated_at": now(),
    }
    data["routes"][provider] = candidate
    clean = _validate(data)
    _write(clean)
    return {"saved": True, "route": clean["routes"][provider], "environment": environment_snapshot(),
            "decision": decision(provider, "https://api.elsevier.com/" if provider == "scopus" else "https://api.clarivate.com/")}


def _interfaces():
    try:
        return [str(name).lower() for _, name in socket.if_nameindex()]
    except (OSError, AttributeError):
        return []


def _system_proxy_present():
    try:
        if sys.platform == "darwin":
            result = subprocess.run(["/usr/sbin/scutil", "--proxy"], capture_output=True, text=True, timeout=3)
            return result.returncode == 0 and bool(re.search(r"(?:HTTP|HTTPS|SOCKS)Enable\s*:\s*1", result.stdout))
        if os.name == "nt":
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as key:
                return bool(winreg.QueryValueEx(key, "ProxyEnable")[0])
    except (OSError, subprocess.TimeoutExpired, ImportError):
        pass
    return False


def environment_snapshot():
    names = _interfaces()
    tunnel = any(re.search(r"(^|[-_ ])(utun|tun|tap|wintun|wireguard|tailscale|wg|ppp|vpn)(\d|[-_ ]|$)", name) or name.startswith(("utun", "tun", "tap", "wintun", "wireguard", "tailscale", "ppp", "wg")) for name in names)
    proxy_keys = ("http_proxy", "https_proxy", "all_proxy")
    environment_proxy = any(os.environ.get(key) or os.environ.get(key.upper()) for key in proxy_keys)
    system_proxy = _system_proxy_present()
    proxy = environment_proxy or system_proxy
    # The fingerprint invalidates old checks without storing interface names, IPs or proxy addresses.
    material = json.dumps({"platform": sys.platform, "tunnel": tunnel, "proxy": proxy, "interfaces": sorted(names)}, separators=(",", ":"))
    return {
        "platform": "macOS" if sys.platform == "darwin" else "Windows" if sys.platform == "win32" else "Linux",
        "tunnel_candidate": tunnel,
        "application_proxy": proxy,
        "environment_proxy": environment_proxy,
        "system_proxy": system_proxy,
        "fingerprint": hashlib.sha256(material.encode()).hexdigest(),
        "note": "隧道接口只表示可能存在 VPN；是否获得机构权限必须用目标 API 验证。",
    }


def route(provider):
    return load().get("routes", {}).get(provider, {
        "institution_id": "none", "institution_name": "", "portal_url": "", "method": "auto", "declared_network": "unknown", "updated_at": ""
    })


def decision(provider, url):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    environment = environment_snapshot()
    selected = route(provider)
    if host in {"localhost", "127.0.0.1", "::1"}:
        return {"route": "direct", "reason": "本机服务始终绕过代理", "institutional_api_expected": False}
    if provider == "scopus" or host == "api.elsevier.com":
        method = selected["method"]
        expected = method in {"campus_vpn", "institutional_token"} or (method == "auto" and selected.get("declared_network") == "campus")
        reasons = {
            "browser_portal": "机构网页入口仅供浏览器使用；API 直连并按实际 entitlement 返回",
            "institutional_token": "Institutional Token 由请求头授权；绕过应用层全局代理",
            "campus_vpn": "由操作系统校园 VPN/校内路由承载；绕过应用层全局代理",
            "public_only": "仅请求公开或基础 API 权限；绕过不受支持的应用代理",
            "auto": "Scopus API 不使用普通代理；由系统路由承载并以实测结果确认机构权限",
        }
        return {"route": "direct", "reason": reasons[method], "institutional_api_expected": expected,
                "method": method, "application_proxy_bypassed": environment["application_proxy"]}
    return {"route": "environment", "reason": "沿用当前用户的应用网络设置", "institutional_api_expected": False,
            "method": selected.get("method", "auto"), "application_proxy_bypassed": False}


def open_request(request, provider, timeout=20, handlers=()):
    selected = decision(provider, request.full_url)
    if selected["route"] == "direct":
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), *handlers)
        return opener.open(request, timeout=timeout)
    if handlers:
        return urllib.request.build_opener(*handlers).open(request, timeout=timeout)
    return urllib.request.urlopen(request, timeout=timeout)


def status():
    data = load()
    environment = environment_snapshot()
    return {
        "environment": environment,
        "routes": data["routes"],
        "known_institutions": [{"id": key, **value} for key, value in INSTITUTIONS.items()],
        "methods": [{"id": key, "title": value} for key, value in METHODS.items()],
        "scopus_decision": decision("scopus", "https://api.elsevier.com/content/search/scopus"),
        "note": "仅保存机构名称、官方入口和路由偏好；不保存账号、密码、IP、代理地址或浏览器会话。",
    }
