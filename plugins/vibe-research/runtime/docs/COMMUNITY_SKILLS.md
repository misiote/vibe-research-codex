# 社区技能接入记录

2026-09-07 审阅 K-Dense-AI/scientific-agent-skills，固定 commit `9cf7d9aea7d84754db4c167ab04b299d33c444bc`。GitHub 当次 API 返回 43,547 stars、3,964 forks、MIT 许可证。这些是采用和维护信号，不是效果评测。

采用 `citation-management` 和 `scientific-critical-thinking`，当前工作区 `.agents/skills` 已安装完整技能与参考文件；分发包的 `skills/` 保留对应副本。新一轮可由 Codex 发现工作区技能。跨项目迁移时将它们复制到目标工作区的 `.agents/skills/`。

来源：https://github.com/K-Dense-AI/scientific-agent-skills

## 实际接入

- **嗅探/检索**：使用查询变体、明确纳入标准、多来源和引用扩展的方法。`vr scout --query 'DanZero' --provider arxiv --include '与掼蛋表征有关' --limit 2` 保留每次查询、时间、失败、缓存和候选结果，并生成 A 检索节点，关联命中的 P 论文。默认未指定 provider 时逐一尝试三个来源；限流不视为覆盖成功。已有 `vr paper expand` 可继续前后向引用追踪。
- **精读**：`vr reading packet P0001` 增加批判性检查清单。阅读时加载 scientific-critical-thinking，围绕设计、证据、替代解释与局限进行核查。对掼蛋 RL 加入可见信息、动作合法集、预算、种子、对手池和规则一致性。研究记录继续用 `reading add/review`，不会因为加载 skill 自动判定通过。
- **归档/引用**：`vr bibliography` 实际调用社区 BibTeX 解析器和校验器，输出 `research/references.bib` 与 `research/BibliographyCheck.json`。通过离线检查只证明当前字段、年份与重复规则满足要求；DOI 在线验证、正式发表版本核对和引用语义审查仍需单独进行。

## 适配与未采用部分

`vr/community` 中保留 MIT 许可证、上游文件哈希和固定版本来源。`bib_common.py` 原样复制；`validator.py` 仅将导入改为包内相对导入，将 requests 改为可选，以支持现有零额外依赖的离线校验入口。没有自动运行付费 API、上传研究库、安装 Google Scholar 爬虫或生成宣传图片。

审阅过 literature-review，但没有启用其完整默认流程：它要求外部检索 CLI 和强制 AI 图片，不符合当前 free-first 范围。保留了已采用技能自身的多来源检索和记录要求。临床证据分级不机械套用到强化学习。

上游技能说明声称离线解析与校验无需额外依赖，但实际 validator 顶层导入 requests；本项目适配修复这一点，并用无 requests 的系统 Python 实测。

## 引用

Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*. https://doi.org/10.48550/arXiv.2609.00065

2026-09-07 核对 arXiv 最新记录为 v2。作者明确写明没有报告任务级评测；因此本项目不将社区关注度描述为掼蛋研究质量已被验证。
