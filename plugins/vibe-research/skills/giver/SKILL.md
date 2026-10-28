---
name: giver
description: 使用 giver 管理独立科研项目的分支、快照、历史、差异、标签和恢复；用于显式 giver 命令与研究版本管理。
---

# giver — GIt VibE Research

插件根为本目录 `../..`，确定性 CLI 为 `<插件根>/runtime/bin/vr giver --workspace <工作区> <子命令>`。这是宿主注册的显式技能入口，接收本次命令参数，不分类匹配自由文本。

工作区优先当前目录已有的 `outputs/projects.json` 父目录，否则当前目录的 `vibe-research-workspace`。`/giver` 无参数时读取 `status` 并提供 `<固定工作台>/giver`。有命令参数时按下表直接调用 CLI 并核对结果。只读命令不创建项目。

| 命令 | 用途 |
| --- | --- |
| `init --title 名称 --mode brainstorming或engineering --branch ideas/main` | 新建独立项目和初始快照 |
| `status [--branch 分支]` | 分支与未提交差异 |
| `branch 新分支 --from 来源分支或提交 --mode brainstorming或engineering` | 从分叉点创建新的独立项目 |
| `switch 分支 --session 当前对话ID` / `checkout 分支` | 仅切换当前对话，使用 CODEX_THREAD_ID 时可省略 session |
| `commit --branch 分支 -m 说明` | 提交完整研究快照与附件 |
| `log` / `tree` / `reflog` | 提交图、派生关系和操作记录 |
| `diff 分支 [另一个分支或提交]` | 无第二项时与当前工作版本比较 |
| `show 提交或标签` | 读取版本内容 |
| `tag 名称 提交或分支` | 标记不可覆盖的里程碑 |
| `restore --branch 分支 --source 提交 --path modules/directions` | 以新版本恢复明确模块，保留此前快照 |

Brainstorming 和 Engineering 各有独立项目身份与研究库；转化永远新建项目和分支。分支派生复制已提交的研究数据和登记附件，不复制外部代码仓库或远端运行进程。当前版本会先保存分叉点；从指定历史提交派生时使用那个提交。

不提供 merge、cherry-pick、rebase、强制回退或远程 push/pull。不同研究路线通过比较、明确引用或新派生分支承接，不自动拼接科学结论。restore 当前仅恢复 Brainstorming 模块；完整历史通过 `branch --from 提交` 新建项目查看。这里的分支与研究地图内的路线分组是不同层次。

切换后依据返回分支的 project/mode 读取对应项目或主题；不要改变其他对话的选择。操作研究数据只通过 vr CLI。研究版本不等于结论被验证。

## 阶段管理

恢复项目、保存实质里程碑或目标改变时，主 agent 读取 [项目与分支管理流](../vibe-research/references/management-flow.md)，用 `vr workflow assess` 评估是否建议转换、派生、切换或保存版本；用 `workflow record` 保留用户选择与执行回执。用户已明确授权时直接执行，同一目标不重复询问；一次性报告不默认派生项目。普通问答和界面维护不启动此流程。
