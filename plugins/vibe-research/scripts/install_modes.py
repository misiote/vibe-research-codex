#!/usr/bin/env python3
"""Register short, explicit native skill aliases without changing Codex private state."""
import argparse
import json
from pathlib import Path
import shutil
import sys


NAMES=('lightning','brainstorming','engineering','giver','vrpet')


def install(plugin_root, skills_dir, apply=False):
    plugin_root=Path(plugin_root).expanduser().resolve()
    skills_dir=Path(skills_dir).expanduser().resolve()
    for name in NAMES:
        src=plugin_root/'skills'/name
        if not (src/'SKILL.md').is_file(): raise ValueError('Missing mode skill: '+name)
        target=skills_dir/name
        marker=target/'.vibe-research-mode-alias.json'
        if target.exists():
            try: owned=json.loads(marker.read_text(encoding='utf8')).get('owner')=='vibe-research'
            except (OSError,ValueError): owned=False
            if not owned: raise ValueError('Existing unrelated skill, left unchanged: '+str(target))
    if apply:
        skills_dir.mkdir(parents=True,exist_ok=True)
        for name in NAMES:
            src=plugin_root/'skills'/name;target=skills_dir/name;target.mkdir(exist_ok=True)
            # The alias routes directly to its explicit native plugin skill. No keyword classifier.
            description={'lightning':'即时探索与轻量创作','brainstorming':'研究构想与方案规划','engineering':'研究实施与开发协同','giver':'研究分支与版本管理','vrpet':'唤起悬浮研究伴侣'}[name]
            body='---\nname: '+name+'\ndescription: Vibe Research 显式命令入口，'+description+'。\n---\n\n'
            body+='读取固定插件入口 `'+str(src/'SKILL.md')+'` 并执行该模式。插件根为 `'+str(plugin_root)+'`；按该原生命令入口执行，不分类匹配自由文本。\n'
            (target/'SKILL.md').write_text(body,encoding='utf8')
            (target/'agents').mkdir(exist_ok=True)
            shutil.copy2(src/'agents/openai.yaml',target/'agents/openai.yaml')
            (target/'.vibe-research-mode-alias.json').write_text(json.dumps({'owner':'vibe-research','plugin_root':str(plugin_root)},ensure_ascii=False)+'\n',encoding='utf8')
    return {'installed':apply,'aliases':list(NAMES),'skills_dir':str(skills_dir),'plugin_root':str(plugin_root),
            'note':'Native explicit skills; reload the skill menu or start a new chat. Existing unrelated skills are never overwritten.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plugin-root',default=str(Path(__file__).resolve().parents[1]))
    p.add_argument('--skills-dir',default=str(Path.home()/'.codex/skills'))
    p.add_argument('--install',action='store_true',help='Without this flag, only check for conflicts')
    a=p.parse_args()
    try: print(json.dumps(install(a.plugin_root,a.skills_dir,a.install),ensure_ascii=False,indent=2))
    except (OSError,ValueError) as exc: print(str(exc),file=sys.stderr);return 1
    return 0


if __name__=='__main__':sys.exit(main())
