---
name: vrpet
description: 显式唤起当前工作区的 Vibe Research 悬浮研究伴侣。
---

# vrpet

本目录 `../..` 是插件根。将本次显式调用视为唤起研究伴侣的请求，直接执行：

`python3 <插件根>/scripts/companion.py --workspace <工作区>`

工作区优先当前目录已有的 `outputs/projects.json` 父目录，否则当前目录下 `vibe-research-workspace`。只确保悬浮按钮存在，不主动展开工作台，不创建研究项目。检查返回的 running/started；若桌面启动受沙箱限制，按宿主权限流程申请运行同一条命令，不改用侧栏任务卡片。
