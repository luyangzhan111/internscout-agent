# Stage 12 — Agent Evaluation Architecture & CI Demo

## 1. Background

InternScout Agent 当前已经具备 provider-neutral Agent Runtime、顺序 Tool Calling、DeepSeek Provider、Job Tools、确定性岗位匹配以及离线集成测试。

当前 Agent Runtime 的关键观测结果已经存在于 `AgentResult` 和 `ToolExecution` trace 中，但项目还没有独立的 Evaluation 层来批量运行场景、验证 Tool 行为、检查最终答案是否基于结构化结果，并在 CI 中报告回归。

Stage 12 的第一阶段建立一个独立、可重复、可离线运行的 Agent Evaluation 架构，并提供 CI 可执行的 Evaluation Demo。

核心架构原则：

```text
Evaluation 层消费 Agent Runtime 的结果。
Evaluation 层不进入 Agent Runtime 的核心控制逻辑。
```

## 2. Goals

Stage 12 必须实现以下目标：

- 建立独立的 Agent Evaluation 目录和数据模型。
- 使用 `AgentOrchestrator` 作为评测执行入口。
- 使用 `AgentResult.tool_executions` 作为主要评测 trace。
- 支持确定性、离线、无 API Key 的 Evaluation Demo。
- 能够验证用户输入、Tool 选择、Tool 调用顺序、Tool 参数和 Tool 结果。
- 能够验证 `match_jobs` 返回的 score、matched skills、missing skills、reason 等结构化证据。
- 能够检查最终答案是否使用并遵守 Tool 返回的数据。
- 输出机器可读的 Evaluation Report。
- 将离线 Evaluation 接入 CI，并与真实 Provider Smoke Test 分离。
- 保持现有 Agent Runtime、Provider、Tool 和数据库边界稳定。

## 3. Scope

### 3.1 Evaluation 执行边界

评测应直接调用 `AgentOrchestrator.run()`，不以 `/api/agent/query` 作为核心评测入口。

原因是 HTTP response 只暴露 `answer`、`steps` 和 `tool_execution_count`，而 Evaluation 需要完整的 Tool trace。

评测运行链路为：

```text
EvalCase
    |
    v
Evaluation Runner
    |
    v
AgentOrchestrator
    |
    v
AgentResult + ToolExecution trace
    |
    v
Deterministic Scorers
    |
    v
Evaluation Report
```

### 3.2 评测数据

每个 EvalCase 至少应包含：

- 稳定的 case ID；
- 用户输入；
- 运行模式或 ModelClient 类型；
- 可选的确定性岗位 fixture；
- 预期 Tool sequence；
- 预期 Tool 参数或参数约束；
- 预期 Tool 成功/失败状态；
- 可选的结构化结果断言；
- 最终答案的稳定事实或 grounding 断言。

最终自然语言不应默认采用完整字符串 exact match。应优先使用结构化字段、关键事实、Tool trace 和禁止错误事实进行评分。

### 3.3 评测模式

Stage 12 至少支持：

1. Offline deterministic mode：使用 FakeModelClient、临时 SQLite 或确定性 JobQuery fixture，不访问网络。
2. Live provider mode 的架构预留：允许未来注入真实 `DeepSeekModelClient`，但不作为普通 PR CI 的默认模式。

### 3.4 评分维度

第一版至少覆盖：

- Agent 是否完成任务；
- Tool 是否选择正确；
- Tool 调用顺序是否正确；
- Tool 参数是否满足预期；
- Tool 是否成功执行；
- Tool 结果是否包含正确的结构化证据；
- `match_jobs` 是否保持应用代码生成的 score 和 ranking；
- 最终答案是否与 Tool 结果一致；
- steps 和 tool execution 数量是否在合理范围内；
- 非法参数、Unknown Tool 和 Tool failure 是否按既有 Runtime 语义处理。

### 3.5 推荐目录

推荐新增非生产目录：

```text
evals/
├── __init__.py
├── contracts.py
├── dataset.py
├── runner.py
├── scorers.py
├── reports.py
├── cases/
│   ├── agent_cases.jsonl
│   └── jobs.json
└── README.md

tests/evaluation/
├── __init__.py
├── test_contracts.py
├── test_dataset.py
├── test_runner.py
└── test_scorers.py
```

如生产环境和 Evaluation 需要共享 Agent 对象图，可以在后续实现中增加 `app/agent/composition.py`，抽取当前 `get_agent_orchestrator` 的组装逻辑；该重构必须保持行为兼容。

## 4. Non-goals

Stage 12 不包含以下内容：

- 修改 AgentOrchestrator 的核心控制流程；
- 引入 parallel Tool Calling、Multi-Agent、Memory 或 Persistent Conversation；
- 将 Evaluation 逻辑写入 `ModelClient`、`ToolRegistry` 或具体 Tool；
- 默认在 PR CI 中调用真实 DeepSeek 或其他外部模型；
- 建立 LLM Judge 作为第一版唯一评分标准；
- 精确匹配所有自然语言答案；
- 新增公开 Evaluation HTTP API；
- 生产级 trace persistence、token accounting 或 cost accounting；
- 引入 Embedding、Vector DB、RAG 或新的推荐算法；
- 修改岗位数据库 schema 或新增 Evaluation 数据库表；
- 修改 OPPO crawler 或新增真实招聘源；
- 修改现有业务代码以迎合单个评测 case；
- 修改 `requirements.txt`，除非经过单独评审证明必要。

## 5. Task Breakdown

### Stage 12A — Evaluation Contracts and Dataset

- 定义 `EvalCase`、`EvalRunRecord`、`EvalScore`、`EvalReport` 等结构化模型。
- 定义 JSONL case 格式和版本字段。
- 定义预期 Tool sequence、参数断言和结构化结果断言。
- 为 malformed case、缺少必填字段和未知字段增加校验。

### Stage 12B — Offline Evaluation Runner

- 实现批量读取 EvalCase 的 runner。
- 直接调用 `AgentOrchestrator`。
- 支持 FakeModelClient 和确定性数据库 fixture。
- 捕获 Agent 正常结果、Tool failure、max steps 和 Model boundary exception。
- 为每次运行记录 case ID、模式、steps、trace、状态和错误分类。

### Stage 12C — Deterministic Scoring

- 实现 Tool sequence scorer。
- 实现 Tool argument scorer。
- 实现 Tool result / matching oracle scorer。
- 实现 final answer grounding scorer。
- 实现 overall pass/fail 和分项分数。
- 对自然语言评分保持宽松、可解释和稳定。

### Stage 12D — Evaluation Fixtures and Demo Cases

- 提供隔离的岗位 fixture 数据。
- 覆盖 direct final answer、search、detail、match、invalid tool arguments 和 zero-result 场景。
- 至少包含一个 `match_jobs` case，验证 score、matched skills、missing skills 和排序。
- 至少包含一个 Tool failure 后恢复的 case。

### Stage 12E — Report Output

- 输出 JSON Evaluation Report。
- 报告包含总 case 数、通过数、失败数、分项分数和失败原因。
- 报告不得写入 API key 或不必要的敏感岗位数据。
- 生成目录应作为测试产物处理，不应污染源码目录或提交到仓库。

### Stage 12F — CI Demo

- 增加离线 Evaluation CI workflow 或等价 CI 命令。
- PR CI 不访问网络，不需要 DeepSeek API Key。
- Evaluation 失败时返回非零退出码。
- CI 输出简短摘要，并保留机器可读报告作为 artifact。
- Live Provider Evaluation 单独设计为手动或定时任务。

### Stage 12G — Final Review

- 执行现有完整 pytest 回归。
- 执行离线 Evaluation Demo。
- 检查生产代码和 Evaluation 代码的依赖方向。
- 检查 CI 在无 API Key、无外网条件下的行为。
- 完成 Read-Only Review 并记录遗留风险。

## 6. Acceptance Criteria

### 架构

- Evaluation 代码位于独立的 `evals/` 层，不进入 `app/agent` Runtime 核心循环。
- Runner 直接使用 `AgentOrchestrator`，能够访问完整 `AgentResult` 和 Tool trace。
- `ModelClient`、`ToolRegistry`、`BaseTool` 和 `DeepSeekModelClient` 的既有职责不被重写。
- 现有生产 Agent composition 与 HTTP contract 保持兼容。

### 数据与运行

- 至少有一组版本化、可审查的 EvalCase 数据。
- Evaluation 使用独立 fixture，不依赖仓库现有 `internscout.db` 的偶然状态。
- Offline mode 可重复运行，结果稳定。
- Offline mode 不访问 OPPO、DeepSeek 或其他网络服务。

### 评分

- 能验证 Tool 名称、顺序、参数和执行结果。
- 能验证 `match_jobs` 的确定性匹配结果不会被模型改写。
- 能识别最终答案与结构化 Tool 结果不一致的情况。
- 能区分正常通过、受控 Tool failure、Agent runtime failure 和 Provider failure。
- 评测失败能输出具体 case ID 和失败原因。

### CI

- CI 能执行离线 Evaluation 命令。
- 任意必需 case 失败都会使 CI 失败。
- CI 不依赖本机代理、API Key 或外部服务状态。
- 报告以 JSON 或等价机器可读格式输出。

### 回归

- 现有 pytest 测试全部通过。
- 现有 `/api/agent/query` 行为不发生非预期变化。
- 既有 `search_jobs`、`get_job_detail` 和 `match_jobs` Tool 测试不回归。

## 7. Testing Strategy

测试分为三层：

### 7.1 Evaluation Framework Unit Tests

测试 `evals/` 自身：

- case schema 校验；
- dataset 加载；
- runner 状态记录；
- scorer 规则；
- report 序列化；
- malformed input；
- 空数据集和重复 case ID。

### 7.2 Offline Agent Evaluation

使用 FakeModelClient 和临时数据库运行真实 AgentOrchestrator、ToolRegistry、Job Tools 和 matching service。

重点验证：

```text
user input
-> model decision
-> tool call
-> tool result
-> next model decision
-> final answer
```

该层是 Stage 12 CI 的主要验证对象。

### 7.3 Live Provider Verification

真实 DeepSeek Evaluation 仅作为独立验证：

- 不进入普通 pytest；
- 不作为默认 PR 阻塞项；
- 使用显式 API Key 和 provider/model metadata；
- 记录外部服务失败与评分失败的区别；
- 对非确定性结果采用阈值、趋势或人工审查，而不是简单 exact match。

## 8. Risks

### 模型非确定性

同一输入可能产生不同的答案、Tool 参数或 steps。应优先评测结构化行为和关键事实，避免过度依赖全文 exact match。

### Provider 漂移

DeepSeek 模型版本、Tool Calling 行为和网络状态可能变化。Live Evaluation 必须与离线 CI 分离。

### 评测污染

如果 Evaluation 使用真实数据库、当前环境变量或共享缓存，结果会受到本机状态影响。必须使用隔离 fixture 和明确的 composition。

### HTTP 信息不足

直接评测 HTTP response 会丢失完整 trace。核心 Evaluation 不应只依赖 `/api/agent/query` 的摘要字段。

### 全局缓存与测试隔离

当前 ModelClient 存在 application-level lazy cache。Evaluation 切换 Fake/Live provider 时必须使用明确的依赖注入、独立进程或安全的 cache lifecycle，避免 case 之间串状态。

### Tool 注册顺序变化

ToolRegistry 的注册顺序会影响模型可见定义。新增 Tool 或重排 Tool 可能改变模型行为，应保留相关回归断言。

### 诊断信息不足

当前 Runtime 没有统一的 run ID、耗时、token、成本和 provider metadata。第一版由 Evaluation wrapper 记录必要元数据，不应为了评测而把这些字段强行塞入核心 Runtime。

### 敏感数据泄露

Evaluation report 可能包含 prompt、岗位内容和 Tool data。报告必须避免保存 API key，并按需要脱敏或限制 artifact 的保留范围。

### CI 环境差异

Windows、Unicode 输出、临时目录和文件路径可能造成假失败。Runner 和报告输出应使用稳定编码，并将环境错误与业务断言失败区分开。

## 9. Final Architecture Decision

Stage 12 的 Evaluation 采用以下冻结边界：

```text
Production Agent Runtime
    |
    | AgentResult / ToolExecution
    v
Independent Evaluation Layer
    |
    +--> deterministic scoring
    +--> JSON report
    +--> offline CI
```

第一版以离线 deterministic evaluation 为核心，真实 Provider Evaluation 作为独立的手动或定时验证。任何未来的 LLM Judge、trace persistence、token/cost accounting 或 online evaluation，都必须作为独立设计审查，不在本 Stage 默认范围内。
