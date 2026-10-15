# 数据库连接与首次配置

在固定工作台打开项目，进入「设置 → 数据库连接与首次配置」。这里可以直接保存凭据、查看最近一次实际 API 检查并处理 PDF 环境；时间戳代表检查时刻，并非持续监测。新建项目时，三步向导会自动对所选来源做一次不导入文献的只读预检。

## 最省事的入口

在本工作区双击 `outputs/配置研究数据库.command`，按提示打开官方页面申请 key，并在终端内粘贴。输入不回显，留空可跳过。完成后自动逐源检查当前研究项目。

通用 CLI（替换项目路径）：

```sh
vr --project <项目目录> integrations setup
vr --project <项目目录> integrations status
vr --project <项目目录> integrations check --network
```

未安装全局 `vr` 时使用 `python3 outputs/vibe-research/bin/vr` 替代。可用 `setup --provider openalex` 或 `--provider s2` 单独配置。

凭据不在研究项目目录内，跨项目自动读取，也不进入迁移包。macOS 默认使用系统钥匙串；Windows 和 Linux 使用当前用户目录中的权限受限配置文件。已有 `OPENALEX_API_KEY`、`S2_API_KEY`、`WOS_API_KEY`、`SCOPUS_API_KEY`、`SCOPUS_INSTTOKEN` 或 `UNPAYWALL_EMAIL` 环境变量时优先使用。设置页面、诊断报告和研究图都不展示凭据。不要把 key 发给助手或写在命令参数里。

## 各来源如何连接

| 来源 | 连接方式 | 受阻时处理 |
| --- | --- | --- |
| OpenAlex | 自动读取 key；未配置则匿名尝试 | 429 时遵循 Retry-After；剩余额度为 0 时等待重置，申请免费 key 后重新检测 |
| Semantic Scholar | 自动读取 key；未配置则匿名尝试 | 429 时降低请求频率并申请 key；申请可能需要审核，配置不保证立即解除所有限流 |
| arXiv | 无需登录，自动连接 | 临时网络故障或限流时稍后重试；仍遵循请求间隔 |
| Crossref | 无需登录，自动连接 | 作为 DOI 元数据来源分页检索 |
| CORE | 匿名基础访问 | 保守限速；服务端等待会保留到检索任务 |
| Hugging Face Papers | 无需登录 | 只用于发现线索，不计作完整覆盖 |
| Web of Science Starter | 本机保存本人 key | 已进入分页检索；字段与范围仍取决于官方套餐和机构权益 |
| Scopus | 本机保存本人 key；按需使用机构网络或 Institutional Token | 已进入分页检索；网页登录、API 身份、机构 entitlement 和实际出口分别验证 |
| Unpaywall | 本机保存本人联系邮箱 | 在候选出现 DOI 后自动加入开放全文定位任务；不做关键词检索 |
| Zotero | 已运行的本机应用，允许本机 API 读取 | 应用高级设置开启本机 API；验收必须查询文献，不能只检查 Connector |
| SQLite 研究库 | 按项目自动打开 | `vr doctor` 检查一致性；修复或恢复遵循项目指南 |

注册、验证码、服务方审核需本人完成。网页登录不会自动变成 API 授权。Zotero 本机读取无需云端登录；本次支持验证的是读取，不代表已经验收写入或全部检索工作流。

## 机构网络与 Scopus

Scopus 接入向导把网页访问和代理检索分开处理：

1. 用户选择机构和官方接入方式。已内置“中国科学院自动化研究所”案例，其公开远程入口是 `https://webvpn.ia.ac.cn/`。
2. 机构网页入口只在系统浏览器打开，用户名、密码和验证码由用户在机构页面输入。Vibe Research 不读取浏览器 Cookie，也不保存机构密码。
3. Scopus API 请求默认绕过 `HTTP_PROXY`、`HTTPS_PROXY` 等应用层全局代理，交给操作系统路由。这样校园 VPN 可以通过分流或全隧道承载 `api.elsevier.com`，其他公开数据库仍可沿用用户代理。
4. 检测到 VPN/隧道接口只说明存在候选通道。系统仍会用单条 Scopus API 查询确认；401 归为 API key 问题，403 归为机构 entitlement、网络出口或 Institutional Token 问题。
5. 如果机构只提供网页反向代理，不能把该入口拼接成 API 地址。校外自动检索应请馆员或 Elsevier API Support 核对可用的校园 VPN，或申请和 API key 配套的 Institutional Token。

命令行可查看和配置同一套网络策略：

```sh
vr --project <项目目录> integrations network
vr --project <项目目录> integrations route scopus --institution casia --method auto
vr --project <项目目录> integrations setup --provider scopus
vr --project <项目目录> integrations setup --provider scopus_insttoken
vr --project <项目目录> integrations verify scopus --query "machine learning"
```

机构名称、官方入口和路由偏好保存在当前用户配置目录，供所有研究项目复用。诊断只输出“是否检测到隧道”“是否存在应用代理”和所选方式，不输出接口名、IP、代理地址或凭据。

正式检索保留缓存、逐源分页和覆盖记录。429、认证/权限错误、服务故障、网络异常分别记录；429 不在一次请求里隐藏重试，避免原始配额信息被本地冷却提示覆盖。新手向导的预检由用户进入来源步骤或改变选择时触发；普通页面刷新不会触发学术 API 请求。

PDF 精读运行时也在同一向导中检查。工作台启动器优先选择 Codex bundled runtime 或已经准备好的用户运行时；仍缺 `pypdf` 时，可在设置页点击“一键准备 PDF 环境”，完成后从固定入口重启工作台。独立运行时位于用户配置目录，不写入研究项目。

若助手运行环境阻止网络，请在允许联网的执行环境或本机终端复测；网络权限失败不能作为数据库服务宕机证据。

官方入口：[OpenAlex 认证说明](https://help.openalex.org/api/authentication/)、[OpenAlex key](https://openalex.org/settings/api)、[Semantic Scholar API](https://www.semanticscholar.org/product/api)、[Elsevier API Support](https://dev.elsevier.com/support.html)、[中科院自动化所图书馆远程入口](https://webvpn.ia.ac.cn/)、[Zotero API](https://www.zotero.org/support/dev/web_api/v3/basics)。
