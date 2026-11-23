# InternScout Agent — Current Project Snapshot

> 本文件是 InternScout Agent 当前状态的唯一项目快照（Current Project Snapshot）。它只保留当前仍然有效的项目身份、能力、架构、provider、Agent tools、retrieval、evaluation、deployment、testing、限制、下一阶段与长期工程约束；它不是 development log、changelog、debug transcript、commit history、tutorial 或 interview review document。

## 1. Project Identity and Release Status

InternScout Agent 是一个面向软件工程、AI 与 Agent 实习岗位的信息采集、处理、存储、查询与智能分析的 AI Agent / AI application portfolio project。

核心闭环：

```text
job ingestion
→ normalization
→ persistence
→ structured query
→ deterministic candidate-job matching
→ semantic job knowledge retrieval
→ Agent tool orchestration
→ FastAPI
→ Streamlit Demo
→ deterministic evaluation / CI
→ local Docker Compose
```

- Previous released baseline: `v1.0.0`（tag 已存在并保持冻结）。
- Current portfolio / product version: `v1.1.0`。
- Current release line: `main` / `v1.1.0`。
- PR #14 已 merge into `main`；PR merge commit 为 `16313c1`，merged feature head 为 `bfc3fd5`，merge tree 与 reviewed feature tree 一致。
- FastAPI application metadata version 仍为 `0.1.0`；当前工作区包含 Stage 14–24，尚未发布新版本。

## 2. Current Stage Status

- Stage 0–13: complete。
- Stage 13.5: complete / release-ready。
- PR #14: merged into `main`。
- Release validation: complete。
- Stage 14: 当前工作区实现真实岗位导入与更新；任务、验收和本轮验证见 `docs/tasks/stage-14-real-job-ingestion.md`，使用说明见 `docs/job-imports.md`。
- Stage 15: 当前工作区实现五类投递条件检查；任务与验收见 `docs/tasks/stage-15-application-eligibility.md`，使用说明见 `docs/application-eligibility.md`。
- Stage 16: 当前工作区实现结合技能与条件的 Agent 推荐；任务见 `docs/tasks/stage-16-agent-eligibility-recommendations.md`，使用说明见 `docs/agent-recommendations.md`。
- Stage 17: 当前工作区实现可信推荐基础版，推荐层跨来源分组、默认样例隔离、待确认原因分类和技能匹配分母；任务与验收见 `docs/tasks/stage-17-trustworthy-recommendations.md`。
- Stage 18: 当前工作区增加目标方向、按原文区分核心／加分／未分类技能及确定性排序，方向不符与资格不符分别计数和解释；任务与验收见 `docs/tasks/stage-18-recommendation-quality.md`。
- Stage 19: 当前工作区完成多公司真实岗位快照、AI 辅助盲标及项目内交叉复核、离线技能基线/当前推荐对照、安全导入；任务见 `docs/tasks/stage-19-real-data-evaluation.md`，结果见 `docs/evaluations/stage19-results.md`，限制及错误分析见 `docs/evaluations/stage19-analysis.md`。
- Stage20: 实现学历/在读条件合并和标题+本岗职责复合方向，版本`stage20-rules-v1`/`direction-core-v2`，旧v1客户端兼容。旧集四个目标方向漏筛恢复；24新岗/8档案新留出中学历阻断改善、方向漏筛增加，未据结果再调规则。任务与真实边界见`docs/tasks/stage-20-eligibility-compound-directions.md`、`docs/evaluations/stage20-analysis.md`。
- Stage21: 方向逐目标正证据/明确无关/证据不足三态，任一匹配则整体匹配，全部明确无关才硬排。版本`direction-evidence-v3`，兼容v1/v2。原两批54岗保留作开发回归，另收26岗/17公司/10档案/260标签盲标新留出；任务见`docs/tasks/stage-21-direction-evidence.md`，收益与退步见`docs/evaluations/stage21-analysis.md`。
- Stage22: 学历研究生/硕博/并列集合及共同在读范围修复，规则`stage22-rules-v1`；待确认排序支持独立理由/目标/技能/原文，版本`direction-support-v4`兼容v1/v2/v3。三批80岗转回归，新28岗/15主体/280标签先盲标全量复核后四组比较，见`docs/tasks/stage-22-degree-uncertain-ranking.md`及`docs/evaluations/stage22-analysis.md`。
- Stage23: 学历分支能力与申请人门槛分离，明确学生身份、更高学历及证书状态保守核对；本岗混合/远程形式细化city，范围不明待确认、明确到岗与地域限制仍严格。资格`stage23-rules-v1`，排序继续v4；原108岗/912对转回归，新33岗/16主体/330对先盲标全量复核再四组比较。见`docs/tasks/stage-23-education-work-location.md`及`docs/evaluations/stage23-analysis.md`。

- Stage 24 P0: 本地试用候选。空库提供真实 JD 手动导入和显式演示数据入口，规则推荐默认关闭模型说明，干净数据库上手流程进入 CI。发布范围和验收记录见 `docs/tasks/stage-24-local-pilot.md`。

## 3. Current Capabilities

### Job ingestion

- `BaseJobCrawler`、`MockJobCrawler` 与本地 sample fixture。
- OPPO explicit real-source adapter：`OppoJobSourceClient` / `OppoJobCrawler`。
- cleaning、normalization、deduplication 与 SQLite persistence。
- `POST /api/crawl` 保留 Mock；新增 `POST /api/imports/manual` 手动 JD 导入与 `POST /api/imports/oppo` 限量手动刷新，以及导入运行历史查询。
- OPPO 使用来源 ID；手动岗位使用规范化 URL（来源 ID 仅作元数据）。upsert 返回新增／更新／未变化，保存状态和观察／更新时间，数据修订号与内容变化同事务提交。
- 旧 SQLite 首次升级先备份、事务迁移并保留编号；旧观察时间保持未知，身份冲突行保留供核对。
- OPPO 按页数／岗位数／请求时间预算限量获取，支持有限重试与部分成功；上限提示和失败分开。缺失岗位不自动下架。

### Query and API

- FastAPI health、crawl、job list/filter/pagination、job detail 与 Agent query。
- 当前 HTTP endpoints：`GET /`、`GET /api/health`、`POST /api/crawl`、`GET /api/jobs`、`GET /api/jobs/{job_id}`、`POST /api/agent/query`、`POST /api/imports/manual`、`POST /api/imports/oppo`、`GET /api/imports`、`GET /api/imports/{run_id}`。岗位列表支持来源／状态筛选。
- `/api/agent/query` 每次请求触发一个独立的 request-scoped Agent run，不提供持久会话。
- `POST /api/eligibility/evaluate`：无需模型，根据当前岗位原文检查 1–50 个指定岗位，不持久化候选人输入。
- `POST /api/agent/recommend`：结构化技能与条件输入，全集规则判断后按符合／待确认及组内技能排序，返回推荐及排除依据；模型说明可关闭或失败降级。旧 `/api/agent/query` 协议保留。

### Candidate matching

- `CandidateProfile`、`JobSkillExtractor`、`CandidateMatcher` 与 `JobMatchingService`。
- deterministic skill extraction、deterministic scoring、match reasons、city filtering 与 stable ranking。
- 推荐卡片显示匹配项数／已识别项数；分母为已识别技能集合，零分母明确提示证据不足，原技能分数公式不变。
- 推荐支持八类目标方向多选，空列表不限。每个目标独立判断并绑定原文；另一技术方向有正证据不代表目标无关。全部目标明确无关才排除；缺证据或正负冲突待确认保留。明确图像生成/图文理解Agent职责可支持CV，仅多模态不推断视觉；已识别的产品/公关/营销/视觉设计职能仍受保护，不代表覆盖所有非技术标题。
- 基于同一份已识别技能全集及精确原文划分核心／加分／未分类；否定、任选组或证据不足不臆定必备。先资格与方向，方向待确认内再按目标相关线索/不足/已有他方向线索，然后原核心/加分/总覆盖和稳定编号。排序支持不改方向或删候选，技能分数和分母保持；旧`match_jobs`协议不变。
- `MatchJobsTool` 委托 matching service；deterministic matching score 不由 LLM 拥有或替代。

### Application eligibility

- `app/eligibility/`：独立规则提取、证据校验和三态比较，不修改技能匹配分数。
- 毕业届次、学历与在读／取得状态、正式工作经验、城市和可实习时长；固定五项“符合／不符合／待确认”，每项显示原文依据及原因。
- 偏好不变硬门槛；缺失、含糊、冲突或未支持表达待确认；明确关闭岗位独立阻断。实习可提供时长超过岗位期限上界时需确认能否缩短，不直接拒绝。
- Stage 17 对待确认返回结构化原因与下一步：个人信息缺失、原文未说明、无法可靠判断、要求冲突；Stage23进一步修复复杂学历分支与混合工作地点，当前版本`stage23-rules-v1`。真实分支、证书状态、远程范围与到岗安排仍只有限解析，不能称全部资格已可靠识别。
- 每次读取岗位当前快照，返回原文字段、字符范围、内容指纹和规则版本；不调用模型或外部招聘网站。页面以会话保存草稿，条件／岗位变化后清除旧结果。
- `app/recommendations/` 将同一资格检查接入 Agent 推荐，技能分数与资格独立。明确不符合／关闭不推荐、待确认保留；最终才按展示上限截取，摘要说明遗漏数量，排除样例最多 10 条。
- 推荐默认隔离 mock 与 example.com／example.org／example.net（含子域）示例链接，可显式 `include_samples=true` 体验。随后按规范化 URL、公司和标题跨来源分组；优先已接入官网，保留路径／查询参数／非空网址片段，选取一份主快照判断，不拼接冲突原文。来源差异、各记录时间和读取／隔离／合并／实际判断数量可追溯；岗位库与导入历史不删除或改写记录。

### Agent runtime

- provider-neutral `AgentOrchestrator`、`ToolRegistry`、显式 tool contracts 与 sequential tool execution。
- `DeepSeekModelClient` 作为真实 provider adapter。
- `FakeModelClient` 用于 deterministic、offline tests/evaluations。
- 新结构化推荐入口使用独立绑定 `recommend_jobs` 工具及预先执行结果，模型无法改写档案、分数或排序；最多 3 轮，8 秒 HTTP 阶段超时，无自动重试。模型仅提供补充说明，规则结果独立返回；数据版本变化重算并舍弃旧说明。

### Semantic job retrieval

- `JobDocument`、`EmbeddingProvider`、`FakeEmbeddingProvider` 与 `OpenAICompatibleEmbeddingProvider`。
- `VectorStore`、`InMemoryVectorStore`、`JobKnowledgeRetriever` 与 `RetrievalRuntime`。
- `RetrieveJobKnowledgeTool` 将岗位知识检索接入 Agent。
- Semantic retrieval 为非结构化岗位描述增加 evidence/retrieval，和 deterministic matching score 互补，不替代 deterministic matching。

### Evaluation

- Stage 12 Agent evaluation。
- Stage 13.5 direct retrieval evaluation。
- Stage 13.5 Agent retrieval integration evaluation。
- Stage 19 real-job holdout：五家公司30条官网岗位，六组合成条件、180对标签，先冻结后运行；标签由AI辅助和项目内复核，不是独立真人验证。离线比较简单技能与未修改的Stage18规则，P@5为8/30→12/30、明确错误21/30→16/30，当前误排除4/30个正相关候选对（涉及3个独立岗位）；不将改善归因于LLM。全金标无整体met，不能评价该类别。
- 新CLI `python -m evals.recommendation_runner` 输出完整JSON/Markdown；`python -m evals.real_job_snapshot` 提供准备、冻结和先预览/备份的本地导入。2026-11-18本地库新增30条，原17条与历史保留，最终47条；该数据库范围与30条评测池分开。
- Stage 19最终完整离线回归：`1626 passed in 66.88s`（2026-11-18）。冻结数据保留字节、算法源码仅允许LF/CRLF换行等价；80文件LF检出模拟及内容改动拒绝通过，未宣称真实Linux运行或公开生产部署。
- Stage20：封存80文件旧实现并隔离回放，原Stage19数据/金标/报告不改。旧集180对作开发回归，新集24岗/12公司（10新公司）/8档案/192标签先盲标复核冻结后比较；21/24仍同一招聘系统模板，未经真人验证。
- 新集简单技能/旧推荐/修复推荐前五相关分别19/40、25/40、27/40；旧→修复学历阻断21/30→30/30、整体阻断37/61→50/61，未知资格误阻断0/131；相关漏筛2/49→5/49（新增3对集中一个商汤多模态Agent岗）。不能称方向泛化已稳定或经验/完全符合类别已验证；经验全unknown、overall无met。
- Stage20完整离线回归`1809 passed in 66.12s`，最终回放/评测专项51项为子集。新增24条备份后导入，原47条与历史不改，本地共71岗位；该范围不同于两个评测池。新集出结果后未改规则/标签，下一步优先目标方向的独立证据与未知边界，后续另收留出验证。
- Stage21保留两批54岗作开发回归，另收26岗/17公司/10档案/260标签，独立盲标及全量项目内复核1320处引文后冻结；最终目录`recommendation_quality_stage21_holdout26`，原25准备稿未运行推荐。25/26仍同系统模板，非真人标注。
- 旧24岗漏筛5/49→0/49、前五相关27/40→29/40；旧30岗前五20/30→17/30。新26岗相关漏筛9/61→5/61、前五34/50→33/50、明确错误14/50→16/50；方向误硬排17/93→5/93，待确认弱/无关66/95→119/151。收益是少硬排，不能概括为排序总体变准；剩4对学历枚举误挡及1对产品/工程边界，分析见`docs/evaluations/stage21-analysis.md`。
- Stage21完整离线回归`1925 passed in 82.50s`，后续原文展开专项`196 passed in 7.53s`为重叠子集。首次新集JSON/Markdown复跑字节一致，80应用源码/冻结输入未改。新增26备份后导入、ID72–97，原71记录/8历史不改；本地现97记录/9次历史，仍含保留的旧样例和重复。未调用真实模型评测；后续优先学历替代关系和待确认精排，需另收新留出。
- Stage22：封存Stage21及仅学历中间80文件版本，四组隔离比较分开归因。旧80岗前五相关79/120→87/120、方向无关24→15；旧26岗已知4个有用学历误挡恢复，原632对其余四维2528项完整检查相同。排序相对仅学历版资格、方向和保留集合完全相同。
- 新28岗留出：简单技能/Stage21/仅学历/完整版前五相关21/50、29/50、29/50、33/50，错误并集27/50、20/50、20/50、15/50；完整版方向无关12/50，nDCG0.784，有用漏筛4/47→2/47。整体误资格挡15/176→9/176，逐维学历误挡10/205→4/205，学历阻断55/75不变。唯一新集nDCG退步及旧回归3处局部退步保留；剩余学生身份/条件分支、城市、届次和未知池噪声见分析。
- Stage22最终完整离线回归`2191 passed in 90.37s`，新集主报告复跑逐字一致；旧299文件、新冻结输入及80源码指纹保持。新28岗备份后追加ID98–125，原97记录/9历史保留，该阶段导入后为125记录/10次历史（含旧样例/重复）。15主体全部同类飞书门户，9/28同院，标签为AI辅助项目内复核、未真人验证，未证明真实模型/市场泛化收益。
- Stage23最终完整离线回归`2428 passed`。原108岗/912对全部回归，521历史文件保持；旧28岗学历误挡4/205→0/205、明确学历阻断55/75→75/75，6混合地点误挡消除，总误挡9/176→0/176，有用漏筛2/47→0/47。旧28岗两份硕士档案nDCG下降保留。
- Stage23新33岗/16主体/330对先盲标全量复核后四组比较：前五相关37/50→38/50，总误挡4/236→1/236，学历阻断37/63→43/63，仍20学历漏判和1/78有用漏筛；地点阶段暴露时长漏判使总体阻断61→60/94，未根据新结果继续修改。两个官网模板，但4主混合岗全同院，AI辅助标签未真人验证。
- Stage23冻结29输入文件、170采集文件、81应用源码与报告复跑字节保持；方向/技能/排序源码不改，毕业/经验/时长旧2736项检查相同。33岗副本验证、备份后追加ID126–158，原125记录/10历史保留，当前158记录/11次历史（含旧样例/重复）。见`docs/evaluations/stage23-analysis.md`及交付/导入验收JSON。

### Deployment

- FastAPI Backend。
- Streamlit Product Demo。
- 四页统一浅色主题、胶囊导航与岗位卡片；窄屏适配，页面淡入／卡片悬停／展开反馈遵循系统减少动态效果偏好。主题资源随 Demo 镜像打包。
- 新增中文“岗位库”“导入与更新”“投递条件”，无需模型；保留“Agent 推荐”。时间显示为北京时间，样例／待确认／在招／关闭分开标注。
- Docker Compose local topology。
- Backend `backend_data:/data` named volume 持久化 SQLite。

## 4. Architecture

项目保持分层：

```text
Streamlit Demo → FastAPI → Agent Runtime → Tools + Matching → Database
```

岗位 ingestion 的共享下游为：

```text
Crawler → cleaning / normalization / deduplication → SQLite
                                                        ↓
                                      Jobs API / Agent tools / retrieval snapshot
```

Deterministic matching 与 semantic retrieval 是互补的两层能力。项目的 retrieval 是 semantic job knowledge retrieval，不是 generic PDF RAG。

### Retrieval architecture

```text
JobRead
→ build_job_document()
→ EmbeddingProvider
→ VectorStore
→ JobKnowledgeRetriever
→ RetrieveJobKnowledgeTool
→ AgentOrchestrator
```

`JobDocument` searchable content 包含：`title`、`company`、`city`、`skills`、`description`。当前 metadata 仅包含 `job_id`、`company`、`city`；不把 `salary`、`published_at`、`source` 或 `source_url` 当作 searchable content 或 metadata。

`InMemoryVectorStore` 是 process-local in-memory store，使用 cosine similarity，按 score descending 排序；相同分数保持 deterministic insertion-order tie behavior。它不是 persistent vector DB、external vector database 或 distributed index。

### Agent tool registry

Default / no retriever 时固定为 3 个工具：

1. `search_jobs`
2. `get_job_detail`
3. `match_jobs`

Retrieval ready 时在上述工具之后增加：

4. `retrieve_job_knowledge`

因此 Agent 不固定拥有 4 tools；retrieval 不可用时保留三工具 fallback。运行时仍为 sequential tool execution，不实现 parallel tool execution 或 Multi-Agent runtime。

## 5. Retrieval Runtime and Provider Configuration

### RetrievalRuntime semantics

- Initial state：`dirty=True`，没有 retriever。
- `mark_dirty()`：只标记当前 index stale，不执行 embedding 或 rebuild。
- `rebuild()`：创建新的 vector store 与 retriever；完整构建成功后才 build-then-swap 当前 retriever。
- Refresh failure：同版本刷新可保留旧 retriever；数据库版本已变化时本次停用旧语义索引，避免引入已关闭岗位。
- First rebuild failure：没有可用 retriever；Agent 仍可使用默认三工具。
- FastAPI startup 只构造 optional runtime/provider，不 eager embedding 或 indexing 全部岗位。
- Agent request 遇到 dirty / not-ready runtime 时，通过完整 job snapshot 惰性 rebuild。
- 成功 crawl ingestion 之后调用 `mark_dirty()`；crawl 本身不做 embedding。
- 数据库修订号使独立进程写入也能被下次 Agent 请求发现；结构化 Agent 查询和语义快照排除 closed，详情接口保留历史记录。

### Embedding provider

Production abstraction 为 `OpenAICompatibleEmbeddingProvider`，当前目标兼容 Alibaba Cloud Bailian / Model Studio 的 OpenAI-compatible embeddings endpoint（Bailian-compatible endpoint）。

配置接口：

- `INTERNSCOUT_EMBEDDING_API_KEY`
- `INTERNSCOUT_EMBEDDING_BASE_URL`
- optional `INTERNSCOUT_EMBEDDING_MODEL`，default `text-embedding-v4`
- optional `INTERNSCOUT_EMBEDDING_DIMENSIONS`，default `1024`

缺少 API key 或 base URL 时 retrieval disabled，FastAPI 与默认 Agent tools 仍可工作。当前 CI 不对真实 Bailian embedding quality 做 benchmark。

### DeepSeek provider decision

- Real LLM provider：DeepSeek。
- API：DeepSeek Responses API。
- Request reasoning：`{"effort": "none"}`。
- Provider 返回多个 function calls 时采用 provider-order first-call projection，执行一个 selected call，再由下一轮 model turn replans。
- Agent runtime 保持 sequential；不执行 parallel tool runtime，也不引入 multi-agent。

## 6. Evaluation and CI

### Stage 12 Agent Evaluation

使用 9 个 deterministic cases，metrics 为：

- `execution_outcome`
- `tool_selection`
- `tool_sequence`
- `tool_arguments`
- `tool_results`
- `answer_facts`

### Stage 13.5 Direct Retrieval Evaluation

使用 6 个 cases，采用 `ControlledEmbeddingProvider` 与 production `JobKnowledgeRetriever`，metrics 仅为：

- Hit@K
- Top-1

### Stage 13.5 Agent Retrieval Evaluation

使用 2 个 cases，通过 `FakeModelClient` scripted `ToolCall`、真实 Agent loop 与 production retrieval tool path 验证 Agent/retrieval integration。

`ControlledEmbeddingProvider` 是 evaluation-only deterministic semantic fixture，用于证明 controlled semantic retrieval pipeline 与 ranking regression；它不证明 Bailian general embedding quality。

Blocking CI evaluation 保持 offline、deterministic、secret-free、network-free，不使用真实 embedding provider call、DeepSeek API key、LLM judge、MRR 或 real embedding benchmark。

GitHub Actions 当前使用 Python 3.12，至少执行：

- `python -m pytest -q`
- `docker compose config --quiet`
- `docker compose build`

Retrieval evaluation gates 通过 normal pytest collection 进入现有 CI gate；没有独立 real-provider CI。

## 7. Deployment and Demo State

Docker Compose 当前真实状态：

- Backend：host port `8000`。
- Streamlit Demo：host port `8501`。
- SQLite URL：`sqlite:////data/internscout.db`。
- volume：`backend_data:/data`。
- Demo backend URL：`http://backend:8000`。
- DeepSeek env 与 embedding env 只传给 Backend。
- Embedding Compose defaults：model `text-embedding-v4`、dimensions `1024`。
- 缺少 embedding API key/base URL 时 retrieval disabled，FastAPI 仍可工作。

这代表 local Docker Compose reproducibility，不代表 public production deployment。

默认数据与 Demo：

- 默认 `POST /api/crawl` 使用 `MockJobCrawler` 与本地 sample fixture，sample fixture 为 6 jobs，不是 live recruitment feed。
- OPPO real-source adapter 已存在，但不是默认 `/api/crawl` 来源。
- Streamlit Demo 仅通过 HTTP client 调用 FastAPI；不直接访问 SQLite、Agent internals 或 provider secrets。
- 当前没有 dedicated retrieval UI；retrieval 通过 Agent tool 提供。

## 8. Security and Data Boundaries

- Provider secrets 通过 environment variables 注入。
- `.env` 被忽略，不提交真实密钥或 secret value。
- `DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL` 与 embedding credentials 均为 Backend-only configuration。
- Demo 不接收 provider key。
- 当前 SQLite persistence 使用本地数据库与 Compose named volume；默认 fixture 数据不代表实时招聘数据。

## 9. Current Test Baseline

Stage 18 目标方向与核心技能验收（2026-11-17，未发布）：

- 新增八类目标方向多选、明确方向不符单列、核心／加分／未分类技能原文证据及确定性排序。开发任务与完整结果见 `docs/tasks/stage-18-recommendation-quality.md`。
- 本轮完整离线回归 `1571 passed in 41.95s`。其中质量模块62项含29条方向与25条技能人工标注开发案例；不作为独立留出或通用准确率评测。核心优先、方向待确认保留、否定／任选组、伙伴职责、核心与加分作用域均有回归。
- 当前17条库内记录默认隔离6条演示并合并1条，判断10个独立岗位。完整虚构档案不限方向时6条待确认推荐；选择AI应用／后端／计算机视觉后仅保留CV岗7，5条方向不符与4条资格不符分开。仅后端时无推荐，方向6、资格4，明确提示补充相关岗位。
- CV岗Python／PyTorch为核心、匹配2／2，并展示精确引用；没有识别到加分要求时明确说明。去重与原始17条岗位／6条导入记录全表校验值不变。本轮关闭AI的真实服务／浏览器验收完成，模型新上下文通过离线模拟验证，没有新增真实模型或embedding调用。
- 推荐排序版本为 `direction-core-v1`；先资格，再方向、核心比率、加分比率、原总技能分数／匹配数／编号。缺核心只影响推荐排序，不改五维资格；旧 `match_jobs` 与自由问答契约保持。方向与技能词表仍有限，不能证明全部招聘要求或录用概率。

Stage 17 可信推荐基础版验收（2026-11-17 收尾，未发布）：

- 跨来源重复只占一个推荐名额、保留来源与差异；默认隔离 mock 和示例链接、可显式演示；四类待确认说明下一步；技能同时展示匹配数／识别数。任务、具体边界与完整证据见 `docs/tasks/stage-17-trustworthy-recommendations.md`。
- 2026-11-14 完整离线回归 `1435 passed in 46.31s`；2026-11-17 中断后继续完成代码复核、服务恢复、双模式运行验收和页面展示，没有将此前完整回归重标为本日新测试。
- 当前 17 条记录默认隔离 6 条演示、合并 1 条重复，实际判断 10 个独立岗位；使用虚构的 2027 本科在读／0 月正式经验／北京深圳／6 月实习档案，得到 6 待确认、4 不符合、0 整体符合。显式演示时判断 16 个独立岗位，9 待确认、7 不符合。
- CV 岗位 7／17 合并后采用官网快照；显示两来源与时间、状态差异。CV 技能显示 2／2，安全研发 1／1，未识别技能为 0／0 并提示证据不足。原库 17 岗与 6 条导入记录全表校验值保持一致；来源网站本轮未刷新。
- 返回前重新比对稳定规则／来源快照，覆盖只更新时间但未增加内容修订号的主来源变化；旧说明不会与新来源并存。本轮真实服务与浏览器验收关闭 AI，没有新增真实模型或 embedding 请求。
- 后续按用户明确要求于 2026-11-17 08:27（北京时间）使用同一完整虚构档案新请求一次真实模型推荐，默认隔离模式下 5 个岗位全部显示新生成的逐岗 AI 理由；范围、去重、三态、分母和规则顺序保持一致。此为真实模型展示链路验证，不代表推荐质量准确率评测；截图见本机可视化根目录 `stage17-live-model-20261117/model-recommendation.jpg`。

AI 说明按岗位展示验证（2026-11-14，未发布）：

- 每个推荐岗位分为推荐理由、待确认条件和原文依据；理由按岗位身份关联，条件与引用保留规则结果，引用不做文字清理。新模型输出为逐岗位理由，旧会话按明确编号兼容整理。
- 后端相关回归 `123 passed`；Demo 全目录阶段回归 `153 passed`。随后补充旧标题关联与无旧文本降级边界，最终说明解析／客户端／推荐页回归 `104 passed`（与前述用例有重叠，不作总数相加）。
- 浏览器复用 00:03 已生成的真实模型结果，确认两条 OPPO 岗位说明分开、无星号／原始字段、原文引用保持一致，窄屏无横向溢出。本次没有额外请求真实模型；新的结构化生成格式已用离线模型与接口测试验证。
- 后端已重启加载新响应字段；模型配置保持启用。说明格式无效只影响 AI 展示，不丢弃规则卡片，也不自动重试模型。

真实模型推荐体验（2026-11-14，未发布）：

- 沿用本机 DeepSeek 密钥，官方模型列表鉴权成功；后端启用 `deepseek-flash`，从 Demo 完成一次启用 AI 说明的实际推荐。
- 示例技能为 Python、PyTorch、OpenCV，五项个人条件全部留空、展示上限 2。现有 17 个岗位均待确认；返回 OPPO 岗位 7、8，两者已识别技能覆盖率为 100，资格仍为待确认。
- UI 成功显示真实模型说明；已展开并对照两岗五项依据，第二岗“硕士及以上学历”“实习期至少三个月”等引文与模型说明一致。真实模型读取服务端预先执行的绑定工具结果，不代表模型自主选择了工具，也不代表所有场景可靠性已验证。
- 本次未修改判断算法或岗位数据、未调用 embedding；未重跑离线测试，之前测试记录仍按原日期区分。

Demo 界面优化验证（2026-11-13，未发布）：

- 页面回归：`102 passed in 5.47s`（`tests/demo`）；本次没有重跑完整后端测试或构建 Docker 镜像。
- 浏览器验证四页导航、方向键切换、来源筛选、关闭模型说明后的规则推荐及原文展开；390px 窄屏卡片单列，未出现横向溢出。验收后已清除测试输入。
- 本次仅调整展示、交互提示和镜像主题配置；未重新抓取、修改已有岗位或调用真实模型。

Stage 16 当前工作区验证（2026-11-12，未发布）：

- 最终完整离线回归：`1165 passed in 68.06s`，新增 114 项；覆盖联合排序、绑定 Agent、源变化重算、模型降级、页面与真实原文技能识别。
- 本地运行接口只读核验 17 条现有岗位（含 10 条 OPPO 快照）；虚构档案保留 7 条待确认、排除 10 条明确冲突，原文／排序／技能及资格同快照校验通过。PyTorch/OpenCV 漏识别已补齐；原数据与导入历史不变。
- 真实模型和 embedding 未调用；模拟模型测试不能表示真实解释效果。详见 `docs/tasks/stage-16-agent-eligibility-recommendations.md`。

Stage 15 当前工作区验证（2026-11-12，未发布）：

- 完整离线回归：`1051 passed in 33.72s`，新增 238 项；包含条件提取／比较、API、页面与既有回归。
- 本地服务只读核验 10 条已导入 OPPO 快照，逐项原文引用可复现；虚构测试档案结果不符合 6、待确认 4。判断前后 17 条岗位及导入记录不变，无模型调用，不代表通用准确率。
- 实现范围与剩余边界见 `docs/tasks/stage-15-application-eligibility.md`。

Stage 14 当前工作区验证（2026-11-12，未发布）：

- 完整离线回归：`813 passed in 32.50s`，覆盖新增岗位库／导入／更新和既有功能。
- OPPO 有限在线检查：获取并导入 2 条，失败 0；同批重导未变化 2。达到配置上限按 partial + warnings 表达。
- 当前默认数据库副本升级保留 6 条记录及其编号／原内容／创建时间；重复初始化仅一份备份，原数据库未修改。
- `git diff --check`、`docker compose config --quiet` 通过。Docker 引擎未运行，本轮未验证镜像构建或容器启动。
- 真实模型／embedding 本轮未调用；上述测试不代表模型效果验证。完整验收见 `docs/tasks/stage-14-real-job-ingestion.md`。

Verified Stage 13.5 product regression baseline（reviewed feature / pre-merge full regression）：

- `tests/evaluation`: 95 passed。
- `tests/agent`: 139 passed。
- `tests/rag`: 58 passed。
- `tests/test_agent_api.py`: 22 passed。
- Full suite: `710 passed in 16.64s`，0 failed，0 errors。

Post-merge `main` validation：

- PR #14 GitHub Actions: SUCCESS。
- Merge tree 与 reviewed feature head `bfc3fd5` 一致。
- `tests/evaluation`: 95 passed。
- `tests/agent` + `tests/rag`: 197 passed。
- `git diff --check`: PASS。
- `docker compose config --quiet`: PASS。
- Full local rerun collected 710 tests：618 passed，0 failed，92 errors；errors 来自 Windows temporary-directory / SQLite ACL，分类为 CLASS D local environment issue，不是 product regression。
- Local `docker compose build` 未取得新的成功 evidence；Docker Desktop Linux engine / buildx local access failure 分类为 CLASS D local environment issue，不是 product blocker。

当前稳定 product baseline 是 reviewed Stage 13.5 full regression 的 `710 passed`；不能把 post-merge 本机 environment-limited rerun 表述为 `710 passed`。旧的 `570 passed` 不再作为 current baseline。

## 10. Known Limitations and Explicit Non-goals

- `InMemoryVectorStore` 仅为 process-local index。
- 没有 persistent external vector DB、distributed index 或其他持久向量数据库。
- Retrieval rebuild 在 Agent dependency path 上惰性执行。
- Embedding configuration 是 optional；缺少配置时 retrieval disabled。
- 没有 persistent conversation memory。
- 没有 Multi-Agent runtime 或 parallel tool execution。
- 默认 crawler 使用本地 fixture；没有 live recruitment feed。
- `/api/crawl` 不触发 OPPO；`/api/imports/oppo` 提供个人本地使用的手动限量刷新入口，尚无鉴权与公开部署访问控制。
- OPPO 依赖 observed website/internal endpoints，source schema 可能变化。
- 当前没有 public production deployment。
- `ControlledEmbeddingProvider` 的 controlled semantic CI 不等于真实 provider benchmark，不提供 general embedding quality guarantee。
- SQLite 有本轮专用备份／事务升级，没有通用迁移框架；没有 scheduler。OPPO 有有限 retry 和 partial-success，暂无自动下架、进程中断后的运行恢复或历史冲突合并界面。
- 投递条件首版为有限规则覆盖；具体日期窗口、领域经验、未支持城市及复杂关联条件不作确定推断。“符合”只覆盖五项已识别条件，不代表录用或所有要求达标。已接入专用推荐 Agent 工具，未实现长期个人档案或自动投递；旧自由问答工具仍使用原技能匹配协议。

Semantic job retrieval 已实现，不应再把 RAG 或 retrieval 列为不存在的能力。

## 11. Repository Inventory

以下只列当前 snapshot 相关的真实 tracked paths，不列 `__pycache__`、pytest temporary directories、database files 或 secrets：

- `app/rag/`
  - `contracts.py`
  - `document.py`
  - `embedding.py`
  - `retriever.py`
  - `runtime.py`
  - `vector_store.py`
- `evals/`
  - `retrieval_contracts.py`
  - `retrieval_dataset.py`
  - `retrieval_runner.py`
  - `retrieval_scorers.py`
  - `cases/retrieval_cases.jsonl`
  - `cases/retrieval_case.schema.json`
- `tests/rag/`
  - `test_contracts.py`
  - `test_document.py`
  - `test_embedding.py`
  - `test_openai_embedding.py`
  - `test_retriever.py`
  - `test_runtime.py`
  - `test_vector_store.py`
- `tests/evaluation/`
  - `retrieval_fixtures.py`
  - `test_agent_retrieval_gate.py`
  - `test_retrieval_dataset.py`
  - `test_retrieval_evaluation_gate.py`
  - `test_retrieval_fixtures.py`
  - `test_retrieval_runner.py`
  - `test_retrieval_scorers.py`
- Agent retrieval integration：
  - `app/agent/tools/retrieval_tool.py`
  - `app/agent/composition.py`
  - `app/api/dependencies.py`
  - `app/main.py`
- `docs/tasks/stage-13.5-task.md`
- `docs/tasks/stage-13.5g-retrieval-evaluation-task.md`
- `docs/deployment.md`
- `docker-compose.yml`
- `.github/workflows/ci.yml`

Current documentation state：

- README Stage 13.5 updated。
- `docs/deployment.md` Stage 13.5 updated。
- `PROJECT_STATE.md` is the current snapshot。
- `docs/stage-reviews/stage-13.5-review.md` exists and is complete。
- `docs/development-log.md` has the Stage 13.5 milestone appended。

## 12. Long-term Engineering Constraints

- Deterministic business logic stays outside the LLM。
- Agent orchestrates tools; it does not own the database or business rules。
- `ModelClient` abstraction isolates real providers。
- Tool contracts remain explicit and provider-neutral。
- Real providers remain optional where possible; offline tests stay deterministic。
- Retrieval supplements deterministic matching and does not replace its score。
- Provider secrets stay Backend-only。
- CI uses deterministic offline tests and validation gates。
- Preserve backward compatibility, especially the retrieval-disabled three-tool path。
- Avoid framework inflation without a demonstrated requirement。
