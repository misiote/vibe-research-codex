# Vibe Research 0.12.1

在 Codex 中组织研究构想、文献证据、开发实验与版本历史。完整安装与使用指南见 [仓库 README](https://github.com/misiote/vibe-research-codex#readme)，平台依赖与更新见 [INSTALL.md](https://github.com/misiote/vibe-research-codex/blob/main/INSTALL.md)。

## 开始使用

通过仓库安装器安装后，完全退出并重启 ChatGPT/Codex，将研究工作区（默认 `~/VibeResearch`）添加为本地项目，在新聊天中选择插件并发送“打开 Vibe Research 工作台”。研究伴侣以收起的按钮出现，点击才展开工作台。终端入口为 `vr-workbench`。

| 模式 | 工作方式 |
| --- | --- |
| Lightning | 无需主题的单次探索与创作，本机草稿不登记研究项目 |
| Brainstorming | 独立主题项目，以研究笔记连接历史、方向与研究成果 |
| Engineering | 独立实施项目，连接代码、开发环境、工作包与实验记录 |

在源码仓库运行 `python3 plugins/vibe-research/scripts/install_modes.py --install` 可注册 `/lightning`、`/brainstorming`、`/engineering`、`/giver`、`/vrpet` 五个显式 skill 别名。若当前目录就是本插件目录，使用 `python3 scripts/install_modes.py --install`。Windows 将 `python3` 换为 `py -3`。重新载入技能菜单或新建聊天后选择入口；不会覆盖同名的其他技能。

## 研究能力

- 文献检索、初筛和概要 / 粗读 / 精读，保留来源覆盖与证据边界。`auto` 检索在首个来源成功后返回；多来源覆盖需逐源核对。
- 研究地图、文献排序与固定 3D 阶段分层；初筛未通过的文献默认隐藏，数据仍可追溯。
- 按研究主题组织 Global / Local 历史时间轴，连接研究版图与方向决策。
- 候选方向比较、可证伪假设、区分实验与停止条件；研究方案、阶段交流与学术材料组织。
- Engineering 关联本地 Git、GitHub、W&B、MLflow 和现有 SSH 配置。地址登记、授权验证、状态同步与运行实验分别处理。
- Brainstorming 与 Engineering 双向转化生成新的独立项目和 giver 分支，保留来源项目。

工作台负责组织与展示，分析和生成由 Codex agent 执行。选择阅读深度不等于完成阅读；没有全文不能声称全文精读。Slides 文件生成取决于宿主可用的演示文稿工具。机构数据库需要本人授权，登录、验证码和密钥配置由本人在官方页面或本机终端完成。

## 全局设置

工作台首页的齿轮入口管理数据库与全文、显示和研究能力。项目开始时读取本机配置与最近检查结果，遇到缺少授权或最近不可用的来源会询问是否补充，并提供逐项引导。可选择稍后；联网检查单独触发，不把未检测来源标记为可用。

## giver 与管理流程

打开 giver 后先选择项目谱系，再查看版本树、日志、变化、标签与引用历史；可按项目名、分支名或项目 ID 搜索。浏览历史不会切换 agent 当前分支。

giver 支持 `init`、`status`、`branch`、`switch` / `checkout`、`commit`、`log`、`tree`、`diff`、`show`、`tag`、`restore`、`reflog`。不提供合并操作，也不替代工程代码的 Git。模块恢复建立新版本；从历史项目继续可创建分支。

Agent 在恢复、目标变化、阶段完成或阻塞时评估转化、分支与检查点建议；记录暂缓或拒绝，减少重复询问。结构调整需具体建议或用户明确授权；没有后台模型持续研究。详见 [管理流程](runtime/docs/AGENT_WORKFLOW.md)。

## 本机入口与数据

```bash
python3 scripts/companion.py --workspace ~/VibeResearch --check
python3 scripts/companion.py --workspace ~/VibeResearch
python3 scripts/workbench.py --workspace ~/VibeResearch --no-open
python3 runtime/bin/vr --help
```

伴侣支持 `--status`、`--toggle`、`--stop`。macOS 在线安装自动准备专用 Python，随包通用伴侣无需编译或 clang；Windows 使用 WebView2，源码无预编译程序时需要 .NET 8 SDK；Linux 需要 GTK 3 / WebKitGTK 图形桌面，也可使用浏览器工作台。

研究数据与工具代码分开。单项目 bundle 包含研究库、工作历史、检索队列和已登记附件，不含外部工程代码、凭据或 Codex 对话；恢复到新目录并先做诊断。完整保留所有项目、Brainstorming 空间和 giver 谱系，请另备份整个工作区。更新或卸载插件不会删除独立工作区。

`SHA256SUMS.json` 校验工具载荷。社区技能许可见 [runtime/skills/LICENSE.md](runtime/skills/LICENSE.md)，来源见 [runtime/docs/COMMUNITY_SKILLS.md](runtime/docs/COMMUNITY_SKILLS.md)。
