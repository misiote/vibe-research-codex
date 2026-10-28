---
name: research-history-expert
description: 按 global/local 尺度梳理研究方向或局部路线的历史，建立有来源的时间轴、演化关系和覆盖边界；用于学术发展史、术语演变、方法谱系和转折点分析，不用于查询助手工作日志。
---

# 研究历史

Global 是给定研究主题的已检方向全景；Local 是该主题下明确子题的方法谱系或争议演化。节点只用作来源，不作研究方向或检索索引。不要把 global 理解为跨项目操作日志，也不要把有限书目叫作完整领域史。用户不指定时，方向发展史用 global，围绕特定方法或争议子题的演化用 local。

项目内先用 `vr history packet --topic '方向' --scope global`；local 另加 `--subtopic 子题`，需要时用 `--aliases "英文术语,同义词"`。这会提供本地图时间轴与输入结构。`vr history show --scope global|local --topic ... [--subtopic ...] [--aliases ...] [--since YYYY] [--until YYYY]` 与工作台“研究历史”共用数据。

先建立主题、子主题、同义词和时间范围。`vr history search --topic ... --scope global|local [--subtopic ...] [--aliases ...] [--background]` 建立 Crossref/arXiv 逐来源持久查询；未启用 background 仅排队。联网前按工作区约定检查 integrations；扩展其他数据库可用 --provider。候选不自动导入或变成历史事件，阅读筛选后再保存事件。需要补语义别名时由助手真实检索确认，不伪称字符串匹配实现了语义搜索。再用研究关系 skill 建立来源、查询、时间区间、术语与引用追踪覆盖。兼顾奠基工作、同期竞争路线、关键数据/基准、复现、负结果和相邻领域。阅读先概要筛选，再粗读重建事件；转折点、优先权争议和因果解释升级精读。年份/被引量不能单独证明历史地位。

区分事件发生/首次公开/正式发表日期；只知道年就填 YYYY，不虚构月日。每个事件写“发生什么、改变什么、依据在哪里、仍未知什么”；关系写为何是继承、反驳或迁移，而非仅时间相邻。来源节点存在仅证明可追踪，不证明解释成立。

用 `vr history add history.json` 保存为 A 产物。输入结构由 packet 提供：title/topic/coverage、events、relations；事件含 id/date/kind/title/description/sources/topics；kind 为 origin/method/dataset/result/debate/replication/turning_point。sources 引用 P/V/R/A 节点，topics 记录事件的子主题；旧 local_nodes 仅保留兼容，不参与筛选；relations 的 source/target 是同批事件 id，reason 为具体关系依据。不修改论文发表时间或把历史解释写成已验证假设。

产物包括可视时间轴、主要分叉/转折、争议和覆盖缺口；用方向决策 skill 把未决问题转成候选路线，用阅读 skill 回查关键论据，再交写作编辑定稿。

Lightning 中不建项目、不调用 history add：在草稿 output 保存带出处和时间精度的事件表及可用可视化文件。Brainstorming 用独立空间的 history 模块保存事件与来源，并以主题/子题检索，不借用工程节点索引。已有项目仅在用户任务需要时只读其时间轴，不导入草稿到正式图。
