---
name: research-engineering-expert
description: 关联 Git、GitHub、W&B、MLflow 与 SSH 开发环境，跟进科研工作包、版本与实验运行；用于工程实施、可复现记录和跨环境进度核对。
---

# Engineering

用当前对话的 mode status 取得明确项目，不复用全局活动项目。所有正式修改通过 vr CLI。`engineering show` 返回环境关联、工作包、进度快照和实验结果；既有研究库可直接使用，不重复初始化。

`engineering link spec.json` 关联已有环境：title、repo（本地 Git 目录，可省略而使用 SSH）、tools（github/wandb/mlflow/gitlab 项目 URL）、ssh（host 为已有 SSH Host 别名，repo 为远程绝对目录）、mlflow_experiments（明确实验 ID 列表）、metric_keys（需要的数值指标键）。不在 JSON/聊天存认证；GitHub 用本机 gh 认证，W&B 用本机 WANDB_API_KEY，MLflow 可用 MLFLOW_TRACKING_TOKEN。GitLab 当前仅支持地址跳转，其他服务支持按需状态采集。

`engineering sync A编号` 只观察本地 Git；加 --network 才读 GitHub 提交/PR/CI、W&B/MLflow 运行状态与指定指标、SSH 远端 Git。适配器彼此独立，某个失败不能阻止其他结果；快照含逐来源时间与错误边界。根据 commit_groups 关联版本，再核对配置、数据、种子、评估协议；SHA 一致不证明实验等价。只需查看服务原始细节时优先已有连接器。

SSH 使用已存在的配置、认证与已知主机信任，不传私钥，不改 SSH 配置或放宽主机校验，不执行任意远程命令。VS Code Remote 链接可交给用户打开；远程 MLflow 可关联用户已有 SSH 隧道的本机地址。无明确连接信息先完成本地部分，再请求 Host 别名和仓库路径。不会自行部署 agent 或创建持续轮询。

`engineering task spec.json` 规划细粒度工作包：title/question/acceptance/protocol/stop_rule/refs。refs 可引用假设、实验、环境关联；以验收标准和研究问题切分。更新同命令使用 id/state/note/evidence，state 为 planned/working/blocked/completed/abandoned；完成需要验收产物编号。工程状态不自动提升科学假设状态。

实验通过 experiment plan/ingest 记录配置、种子、Git SHA 和实际结果；默认 MARL 协议与通用协议区分。代码变动、外部 run id 与工作包之间显式关联，不因名字相似合并。按任务授权执行必要实现和验证，方向、历史、阅读模块作为独立输入按需使用；不要让工程细节反向约束方向探索。

这是按需快照跟进，不能称持续监控。用户明确要求定期跟进时再使用宿主自动化并保留失败和通知条件。

## 双向衔接

用 `bridge preview --workspace ... --input spec.json` 核对来源和目标，再按用户任务执行 `bridge transfer`。direction=promote 用 board 与可选 target（活动工程项目 ID，省略新建），可带选定 idea、验收/协议/停止条件与 environment；direction=abstract 用 project 与可选 board/topic，形成进展回顾。request_id 为 UUID，失败重试沿用原编号与相同参数；用户改变任务时重新预览并用新编号。expected_updated_at/source_revision 用于检查输入版本。返回两端链接后用当前对话的 mode enter 关联返回的 board 或目标工程目录，不改变其他对话。

保留原项目、全部构想模块、来源快照与附件引用；不删除源数据，不把跨模式衔接当作科学证据成立。已有进展回顾更新前会归档包括用户编辑的前一版本。转化仅建立计划与快照，实验运行按任务授权另行执行。
