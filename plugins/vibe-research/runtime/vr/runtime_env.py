"""Per-user PDF runtime preparation; never installs into the research project."""
import os
import subprocess
import sys
from pathlib import Path
from .store import ResearchError


def root():
    return Path(os.environ.get('VR_RUNTIME_DIR', str(Path.home()/'.config/vibe-research'))) / 'python-runtime'


def executable():
    base=root()
    return base/'Scripts/python.exe' if os.name=='nt' else base/'bin/python'


def prepare():
    target=root();python=executable()
    try:
        if not python.is_file():
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            result=subprocess.run([sys.executable,'-m','venv',str(target)],capture_output=True,text=True,timeout=120)
            if result.returncode:raise ResearchError('无法建立独立 Python 环境；请检查 Python venv 支持')
        result=subprocess.run([str(python),'-m','pip','install','pypdf>=5,<7'],capture_output=True,text=True,timeout=300)
        if result.returncode:raise ResearchError('PDF 依赖安装未完成；请检查网络或 Python 包源')
        check=subprocess.run([str(python),'-c','import pypdf'],capture_output=True,timeout=20)
        if check.returncode:raise ResearchError('PDF 依赖安装后仍无法载入')
    except subprocess.TimeoutExpired:raise ResearchError('准备 PDF 环境超时；可稍后重试') from None
    except OSError:raise ResearchError('无法启动 Python 环境准备程序') from None
    return {'prepared':True,'python':str(python),'note':'PDF 环境已准备；请关闭并从固定入口重新打开工作台。'}
