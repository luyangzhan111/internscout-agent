# InternScout Agent — Stage 11 Review

## 1. Stage Overview

### Stage

~~~text
Stage 11 — Deterministic Candidate / Job Matching & Agent Intelligence
~~~

Stage 11 的核心目标是：

> 在现有 SQLite 岗位、JobQueryPort、Agent Runtime 与 DeepSeek Provider 边界之上，加入确定性、可测试、可解释的候选人 / 岗位匹配能力，并让 Agent 通过 match_jobs Tool 消费应用代码生成的匹配证据与分数。

Stage 11 完成后的主链路是：

~~~text
CandidateProfile
↓
JobMatchingService
↓
JobQueryPort
↓
persisted JobRead
↓
JobSkillExtractor
↓
CandidateMatcher
↓
JobMatchResult
↓
MatchJobsTool
↓
AgentOrchestrator
↓
DeepSeek explanation
~~~

本阶段冻结的职责分工是：

~~~text
LLM:
intent recognition + tool selection + explanation

Application code:
skill evidence + score + ranking + reason
~~~

Stage 11 没有把匹配能力实现为 LLM 打分，也没有引入 embedding、Vector DB、RAG pipeline、候选人持久化或新的公开 HTTP matching endpoint。

---

# 2. Repository Reality

本 Review 核对的当前 branch：

~~~text
feat/stage-11-candidate-job-matching
~~~

当前实现 HEAD：

~~~text
d21271a
feat: integrate matching tool into agent runtime
~~~

最新 commit：

~~~text
d21271a
feat: integrate matching tool into agent runtime
~~~

Stage 11 base：

~~~text
30f3d97
docs: update project state after stage 10
~~~

Stage 11 相对 base 的 committed touch set：

~~~text
app/agent/tools/matching_tool.py
app/api/dependencies.py
app/matching/__init__.py
app/matching/contracts.py
app/matching/matcher.py
app/matching/service.py
app/matching/skill_extractor.py
app/services/cleaner.py
app/services/skill_vocabulary.py
docs/tasks/stage-11-task.md
tests/agent/test_matching_tool.py
tests/matching/__init__.py
tests/matching/test_contracts.py
tests/matching/test_matcher.py
tests/matching/test_service.py
tests/matching/test_skill_extractor.py
tests/test_agent_api.py
~~~

文档收尾时，Stage 11G 验证脚本：

~~~text
stage11g_agent_verify.py
~~~

仍是 untracked verification artifact，不属于上述 committed implementation touch set。

以下 repository identity 没有从当前 feature branch 事实中推断：

~~~text
Stage 11 PR number:
UNKNOWN

Stage 11 merge SHA:
UNKNOWN

main branch status:
UNKNOWN

post-merge regression:
UNKNOWN
~~~

---

# 3. Stage 11 Final Status

截至本 Review：

~~~text
Stage 11A — Contracts & Skill Vocabulary:
COMPLETE

Stage 11B — Deterministic Skill Extraction:
COMPLETE

Stage 11C — Candidate Matcher:
COMPLETE

Stage 11D — Job Matching Service:
COMPLETE

Stage 11E — MatchJobsTool:
COMPLETE

Stage 11F — Agent Runtime Integration:
COMPLETE

Stage 11G — Real Matching E2E:
PASS

Targeted automated tests:
164 passed

Full automated regression:
503 passed

Warnings:
0

Formal Final Review record:
UNKNOWN

MUST FIX:
UNKNOWN

SHOULD FIX:
UNKNOWN
~~~

因此当前状态必须区分为：

~~~text
Implementation / current verification:
COMPLETE

Documentation:
COMPLETE IN WORKING TREE

Formal review / Git closeout:
INCOMPLETE
~~~

没有把测试通过或本 Review 的创建自动等同于已经发生 PR、merge 或 post-merge verification。

---

# 4. Commit History

已验证的 Stage 11 feature commits：

~~~text
a5e5028
docs: add stage 11 task specification

024dc24
feat: add candidate matching contracts

928caed
feat: add deterministic job skill extraction

f40e62a
feat: add deterministic candidate matcher

b1f939b
feat: add job matching service

935c5df
feat: add match jobs agent tool

d21271a
feat: integrate matching tool into agent runtime
~~~

该列表只记录当前 repository 已存在的 Stage 11 commits。

以下事项没有被预先写入 commit history：

~~~text
Stage 11 documentation commit:
UNKNOWN

PR number:
UNKNOWN

merge SHA:
UNKNOWN

post-merge documentation / state commit:
UNKNOWN
~~~

---

# 5. Matching Architecture

Stage 11 的 application path：

~~~text
CandidateProfile
        |
        v
JobMatchingService
        |
        +-----------------------------+
        |                             |
        v                             v
JobQueryPort                  JobSkillExtractor
        |                             |
        v                             v
RepositoryJobQueryAdapter     JobSkillEvidence
        |                             |
        v                             v
Repository                    CandidateMatcher
        |                             |
        v                             v
SQLAlchemy / SQLite           JobMatchResult
~~~

Agent path：

~~~text
POST /api/agent/query
↓
request-scoped AgentOrchestrator
↓
DeepSeekModelClient
↓
DeepSeek requests match_jobs
↓
MatchJobsTool
↓
JobMatchingService
↓
deterministic ranked results
↓
DeepSeek final explanation
~~~

核心 boundary：

~~~text
AgentOrchestrator
!= matching business logic

DeepSeek
!= scoring engine

MatchJobsTool
!= database adapter

JobMatchingService
!= SQLAlchemy repository
~~~

匹配结果按请求即时计算，没有写入数据库。

---

# 6. Candidate Contracts

新增：

~~~text
app/matching/contracts.py
~~~

主要 contracts：

~~~text
CandidateProfile
JobSkillEvidence
JobMatchResult
MatchReason
~~~

CandidateProfile 规则：

~~~text
skills:
required non-empty list[StrictStr]

preferred_cities:
optional list[StrictStr]
default = []

extra fields:
forbidden
~~~

候选人技能会：

~~~text
trim / collapse whitespace
↓
shared canonical alias normalization
↓
case-insensitive identity deduplication
↓
first occurrence order preservation
~~~

空技能列表、blank skill、非字符串元素都会被拒绝。

preferred_cities 复用现有城市 normalization：

~~~text
东莞市
↓
东莞
~~~

城市同样拒绝 blank / non-string element，并在保持顺序的情况下去重。空城市偏好表示不启用城市过滤。

JobSkillEvidence 允许：

~~~text
skills = []
~~~

因为“岗位没有被当前 vocabulary 检测到技能证据”是正常业务状态。

JobMatchResult 包含：

~~~text
job
match_score
matched_skills
missing_skills
detected_job_skills
reason
~~~

match_score 是 strict integer，范围为 0..100。Contract 还验证：

~~~text
matched_skills ∩ missing_skills = empty

matched_skills ⊆ detected_job_skills

missing_skills ⊆ detected_job_skills

matched_skills ∪ missing_skills
= detected_job_skills
~~~

稳定 reason values：

~~~text
full_match
partial_match
no_skill_match
insufficient_evidence
~~~

---

# 7. Shared Skill Vocabulary

新增：

~~~text
app/services/skill_vocabulary.py
~~~

Stage 11 没有复制 Cleaner 的技能规则，而是将 canonical skill normalization 抽为 shared boundary，并让：

~~~text
Cleaner
Candidate contracts
JobSkillExtractor
~~~

共同使用。

当前 canonical display vocabulary：

~~~text
Python
FastAPI
SQL
Git
pytest
HTTP
HTML
Requests
Beautiful Soup
Docker
Linux
Shell
Postman
LLM
RAG
~~~

Beautiful Soup 支持：

~~~text
beautifulsoup
beautiful soup
beautifulsoup4
bs4
~~~

Identity 使用 casefold，因此 alias / case variation 可以稳定映射和去重。

未知技能不会被丢弃；normalize_skill 会保留清理空白后的原值。这允许结构化候选人 / 岗位技能继续表达 vocabulary 之外的明确技能，但 free-text extractor 只检测冻结的 lexical whitelist。

Cleaner 的职责保持不变：

~~~text
shared skill normalization
+ company normalization
+ city normalization
~~~

没有引入 taxonomy database、knowledge graph 或 semantic ontology。

---

# 8. Deterministic Skill Extraction

新增：

~~~text
app/matching/skill_extractor.py
~~~

主要 symbol：

~~~text
JobSkillExtractor
~~~

输入 evidence source 按固定优先级组合：

~~~text
1. job.skills
2. job.title
3. job.description
~~~

输出：

~~~text
JobSkillEvidence
~~~

structured job.skills 会经过 shared normalization，可以保留明确提供的 unknown skill。

free-text detection 使用冻结的 TEXT_SKILL_ALIASES、escaped regex 与 ASCII identifier boundary。它：

~~~text
case-insensitive
deterministic
network-free
LLM-free
preserves first textual occurrence
removes duplicate canonical evidence
~~~

以下 false-positive boundaries 已被测试：

~~~text
NoSQL
SQLAlchemy
github
digital
HTTPServer
HTML5
python3
ragged
storage
shellscript
my_python_module
~~~

Requests 虽存在于 shared structured vocabulary，但故意不在 free-text whitelist 中，避免普通英文 prose 中的 “requests” 被误判为 Python Requests library。

OPPO 真实岗位 persisted skills 为：

~~~text
[]
~~~

Stage 11G 仍能从 description 中确定性提取：

~~~text
RAG
LLM
~~~

如果 title / description 也没有支持的 lexical evidence，则返回空 evidence，不进行猜测。

---

# 9. Candidate Matcher

新增：

~~~text
app/matching/matcher.py
~~~

主要 symbol：

~~~text
CandidateMatcher
~~~

Matcher 是 pure deterministic calculation boundary。它只消费：

~~~text
CandidateProfile
JobRead
JobSkillEvidence
~~~

它不访问：

~~~text
database
network
Agent
DeepSeek
~~~

matched / missing 的定义：

~~~text
matched_skills:
detected job skills possessed by candidate

missing_skills:
detected job skills not possessed by candidate
~~~

对非空 evidence：

~~~text
raw ratio =
matched_count / detected_count

score =
round-half-up(raw ratio * 100)
~~~

当前 integer implementation：

~~~text
(200 * matched_count + detected_count)
// (2 * detected_count)
~~~

因此 score 没有 floating-point nondeterminism。

Reason 由 counts 决定，而不是由 rounded score 推断：

~~~text
all detected matched:
full_match

some detected matched:
partial_match

none matched:
no_skill_match

no detected evidence:
insufficient_evidence
score = 0
~~~

即使很小的 partial ratio 四舍五入为 0，reason 仍是 partial_match；即使很高的 partial ratio 四舍五入为 100，也不会误写为 full_match。

---

# 10. Job Matching Service

新增：

~~~text
app/matching/service.py
~~~

主要 symbol：

~~~text
JobMatchingService
~~~

Service 依赖：

~~~text
JobQueryPort
JobSkillExtractor
CandidateMatcher
~~~

不依赖 SQLAlchemy Session 或 Repository implementation。

完整查询策略：

~~~text
page 1 with page_size = 100
↓
freeze page_count from first total
↓
request page 2 ... page N
↓
combine pages
↓
deduplicate by numeric job ID
~~~

这保证最强岗位位于第一页之后时仍可参与 global ranking。重复 job ID 采用第一次出现的 JobRead。

城市 eligibility：

~~~text
preferred_cities = []
→ all cities eligible

preferred_cities non-empty
→ exact normalized, case-insensitive city membership
~~~

城市只决定岗位是否进入匹配集合，不改变 skill score。

稳定 ranking：

~~~text
1. match_score descending
2. matched skill count descending
3. numeric job ID ascending
~~~

top_k 当前只要求：

~~~text
type(top_k) is int
top_k > 0
~~~

当前 service 没有 maximum top_k；这是 repository reality，记录在 limitations 中。

no jobs 返回空 list。JobQueryPort、extractor 或 matcher 的异常使用 fail-fast propagation。

---

# 11. MatchJobsTool

新增：

~~~text
app/agent/tools/matching_tool.py
~~~

主要 symbols：

~~~text
MatchJobsArguments
MatchJobsTool
~~~

Tool identity：

~~~text
name:
match_jobs

default top_k:
5
~~~

Arguments 继承 CandidateProfile，并增加 strict integer top_k。Candidate / city validation 发生在 Tool boundary，extra fields 继续被拒绝。

Tool flow：

~~~text
provider arguments
↓
MatchJobsArguments validation
↓
CandidateProfile
↓
JobMatchingService.match_jobs
↓
JobMatchResult list
↓
JSON-compatible dictionaries
~~~

MatchJobsTool 不包含：

~~~text
skill extraction rules
score formula
ranking rules
SQLAlchemy queries
DeepSeek SDK calls
~~~

它是 provider-neutral、read-only application adapter。

---

# 12. Agent Runtime Integration

修改：

~~~text
app/api/dependencies.py
~~~

Production composition 为每个 Agent HTTP request 使用同一个 request-scoped SQLAlchemy Session 构造：

~~~text
RepositoryJobQueryAdapter
↓
JobMatchingService
↓
MatchJobsTool
↓
ToolRegistry
~~~

Registry 当前注册：

~~~text
search_jobs
get_job_detail
match_jobs
~~~

现有 sequential Tool-Calling loop 没有改动。

Stage 11 相对 base 没有修改：

~~~text
app/agent/orchestrator.py
app/agent/model_client.py
app/agent/providers/deepseek_client.py
~~~

Fake model HTTP integration test 验证：

~~~text
user request
↓
model requests match_jobs
↓
real production composition executes Tool
↓
structured result reaches next ModelRequest
↓
model returns final answer
~~~

公共 endpoint 保持：

~~~text
POST /api/agent/query
~~~

没有新增 standalone /api/match endpoint。

---

# 13. Stage 11G Real Verification Evidence

验证脚本：

~~~text
stage11g_agent_verify.py
~~~

该脚本当前是 untracked artifact。2026-08-21 文档收尾期间对当前 HEAD 执行了显式 live verification。

Provider / model：

~~~text
Provider:
DeepSeek

Model:
deepseek-v4-flash
~~~

API key 只从 environment 读取，未输出具体值。

## 13.1 Real OPPO Ingestion

脚本使用 real OPPO source、isolated temporary SQLite 与现有 ingestion：

~~~text
OppoJobSourceClient
↓
OppoJobCrawler
↓
ingest_jobs
↓
temporary SQLite
~~~

实际 persisted record：

~~~text
count:
1

job_id:
1

title:
AI产品实习生

company:
OPPO

city:
东莞

skills:
[]

source:
oppo

published_at:
2026-06-01

source position identity:
2061649545671430146
~~~

## 13.2 Deterministic Oracle

Candidate：

~~~text
skills:
[RAG]

preferred_cities:
[东莞市]

top_k:
1
~~~

Direct JobMatchingService result：

~~~text
detected_job_skills:
[RAG, LLM]

matched_skills:
[RAG]

missing_skills:
[LLM]

match_score:
50

reason:
partial_match
~~~

这证明 OPPO persisted skills 为空时，title / description evidence 仍可驱动 deterministic matching。

## 13.3 Real HTTP Agent

~~~text
POST /api/agent/query:
HTTP 200

steps:
2

tool_execution_count:
1
~~~

最终 answer 使用：

~~~text
job:
AI产品实习生 / OPPO / 东莞

score:
50

matched:
RAG

missing:
LLM
~~~

## 13.4 Direct Agent Trace

~~~text
steps:
2

tool_count:
1

tool:
match_jobs

arguments:
skills = [RAG]
preferred_cities = [东莞市]
top_k = 1

success:
True
~~~

Tool data 与 deterministic oracle 一致：

~~~text
detected = [RAG, LLM]
matched = [RAG]
missing = [LLM]
score = 50
reason = partial_match
~~~

因此 final response 中的 50 分来自 application matcher，不是 DeepSeek 自行生成的隐藏分数。

## 13.5 Verification Harness Note

第一次执行在 HTTP 已返回 200 后，因为 Windows GBK console 无法打印 answer 中的 emoji 而触发 UnicodeEncodeError。

随后使用 UTF-8 Python console 重跑同一脚本，完整流程 exit code 0。该问题属于 verification script output encoding，不是 application、HTTP、Tool 或 matching failure。

---

# 14. Automated Tests

Stage 11 automated tests保持：

~~~text
network-free
real-OPPO-free
real-DeepSeek-free
API-key-free
deterministic
repeatable
~~~

## 14.1 Targeted Collection

~~~text
tests/matching/test_contracts.py:
38

tests/matching/test_skill_extractor.py:
36

tests/matching/test_matcher.py:
22

tests/matching/test_service.py:
37

tests/agent/test_matching_tool.py:
19

tests/test_agent_api.py:
12

Total targeted:
164 passed
~~~

Targeted test result：

~~~text
164 passed in 6.55s
~~~

## 14.2 Full Regression

当前 full-project result：

~~~text
503 passed in 14.05s

Warnings:
0
~~~

Stage 10 authoritative baseline 是 350 passed, 0 warnings；当前实际 full regression 增长到 503 passed，且未出现 failed test 或 warning。

## 14.3 Coverage Boundaries

测试覆盖：

~~~text
candidate validation and normalization
shared aliases
structured and text extraction
false-positive lexical boundaries
zero evidence
full / partial / zero matching
half-up integer score
stable reason
city eligibility
pagination beyond first page
ranking and tie-breaks
top_k validation
Tool validation / delegation / serialization
production Agent composition
Tool observation reaching model
HTTP error regressions
~~~

pytest 不证明真实 OPPO / DeepSeek compatibility，因此 Stage 11G 与 automated regression 保持分离。

---

# 15. Final Review History

当前 repository 能验证：

~~~text
Stage 11 task specification:
PRESENT

Implementation commits:
PRESENT

Targeted regression:
PASS

Full regression:
PASS

Real Stage 11G:
PASS
~~~

但当前 repository 中没有独立、已提交的 Stage 11 Final Codex Read-Only Review execution record，也没有可核对的 finding-resolution history。

因此：

~~~text
Stage 11A-F Review:
PASS

Stage 11G Real Verification:
PASS

Formal Final Review:
PENDING

MUST FIX:
PENDING

SHOULD FIX:
PENDING

READY FOR STAGE 11 CLOSEOUT:
UNKNOWN
~~~

本 Review 不把“文档生成”伪装成已经发生的 formal review，也不发明 review number 或 review conclusion。

一个可直接从 implementation / tests 观察到的 contract difference 是：

~~~text
Stage 11 task specification:
top_k should be bounded

Current implementation:
any positive strict int, no maximum
~~~

其最终 review classification 与是否接受为 limitation：

~~~text
UNKNOWN
~~~

---

# 16. Architecture Boundaries

Stage 11 保持：

~~~text
Matching domain:
independent of SQLAlchemy

Database access:
behind JobQueryPort

Tool:
delegates to application service

AgentOrchestrator:
provider-neutral and unchanged

DeepSeek adapter:
provider-specific and unchanged

Tool execution:
sequential and unchanged

Candidate / match state:
request-scoped, not persisted
~~~

相对 Stage 11 base 没有修改：

~~~text
app/database/models.py
app/database/session.py
app/crawlers/oppo_source_client.py
app/crawlers/oppo_crawler.py
app/workflows/job_ingestion.py
app/agent/orchestrator.py
app/agent/model_client.py
app/agent/providers/deepseek_client.py
requirements.txt
~~~

因此没有：

~~~text
database migration
new dependency
candidate table
match table
embedding table
source identity redesign
Agent loop redesign
provider contract redesign
~~~

Cleaner 的修改仅用于复用 shared skill vocabulary，不把 matching score 或 Agent logic 放入 cleaning layer。

---

# 17. Engineering Lessons

## 17.1 LLM Explanation Is Not Matching Logic

LLM 适合：

~~~text
understand user intent
select match_jobs
explain structured result
~~~

但 score / ranking 必须由可测试代码产生，避免同一 candidate / job 在不同调用中获得漂移分数。

## 17.2 Shared Canonicalization Prevents Split Identity

如果 Cleaner、candidate input 与 extractor 各维护一套 alias：

~~~text
rag
RAG
Rag
~~~

可能在不同 layer 形成不同 identity。Shared vocabulary 让 ingestion 与 matching 使用同一 canonical display boundary。

## 17.3 Zero Evidence Is a First-Class State

没有 evidence 不等于 candidate 完全不匹配，也不应该触发 LLM 猜测。

~~~text
detected = []
score = 0
reason = insufficient_evidence
~~~

比“自动补全岗位需要的技能”更可解释。

## 17.4 Stable Ranking Needs a Final Tie-Break

只按 score 排序不足以保证重复调用稳定。Stage 11 使用：

~~~text
score
matched count
job ID
~~~

形成 total ordering。

## 17.5 Pagination Is Part of Matching Correctness

如果 service 只取 database page 1，算法本身再正确也会漏掉全局最佳岗位。Application service 必须先完成有限 horizon collection，再 global rank。

## 17.6 Location Is Eligibility, Not Skill Evidence

城市偏好通过 filter 表达，不混入 skill ratio。这避免“同城”改变 candidate 对技术要求的掌握比例。

## 17.7 Offline Tests and Real E2E Have Different Jobs

Automated tests冻结 malformed inputs、ordering、score 和 architecture boundary；Stage 11G 证明真实 OPPO text、SQLite、DeepSeek Tool Calling 与 final explanation 确实能连接。

## 17.8 Verification Harnesses Also Need Environment Discipline

Stage 11G 的 GBK print failure 说明：业务 flow 已成功与“诊断输出可打印”是两个问题。真实验证脚本应显式考虑 Unicode console encoding，但不应把 harness output failure误诊为 application failure。

---

# 18. Interview Knowledge Points

## Domain Modeling

- Pydantic strict validation
- request-scoped CandidateProfile
- structured JobSkillEvidence
- stable MatchReason
- result partition invariant
- normal business state vs exception

## Deterministic Matching

- canonical skill identity
- case-insensitive deduplication
- lexical extraction
- regex boundary
- false-positive control
- integer half-up scoring
- explainable matched / missing skills
- deterministic tie-breaking

## Application Architecture

- Port / Adapter
- Dependency Inversion
- pure matcher
- application service orchestration
- Tool as thin adapter
- composition root
- request-scoped dependencies

## Data Access

- pagination horizon
- global ranking
- first-occurrence deduplication
- in-memory on-demand computation
- no match persistence

## Agent Engineering

- provider-neutral Tool contract
- sequential Tool Calling
- structured Tool observation
- LLM intent / explanation boundary
- application-owned score

## Testing

- fake JobQueryPort
- temporary SQLite
- fake ModelClient
- offline HTTP integration
- real external E2E
- environment vs assertion failure

### Q1：为什么不让 DeepSeek 直接打分？

因为 LLM score 不稳定、难以 regression test，也很难解释精确来源。Stage 11 由 CandidateMatcher 计算 score，DeepSeek 只解释 Tool 返回的结构化 evidence。

### Q2：为什么 extractor 不直接使用 embedding？

Stage 11 需要窄范围、确定性与可审计。冻结 vocabulary 与 lexical boundary 可以精确测试 false positive；semantic retrieval 属于后续独立 scope。

### Q3：为什么 score 的分母是岗位 evidence 数量？

当前 score 表示 candidate 覆盖了多少已检测岗位技能。它不是 candidate 全部技能的利用率，也不包含城市、薪资、学历或经验。

### Q4：为什么 zero evidence 仍返回结果？

因为 zero evidence 是“当前 vocabulary 无法判断”，不是 job 不存在。返回 insufficient_evidence 可以让上层明确说明信息不足，避免 hallucination。

### Q5：为什么 service 依赖 JobQueryPort？

Matching business logic 只需要读取 JobRead，不需要知道 SQLAlchemy。Port 让 unit test 使用 fake query，也让 Tool 不直接操作 database session。

### Q6：如何保证排名稳定？

先按 score 降序，再按 matched count 降序，最后按 numeric job ID 升序。最后一个 tie-break 让同一 dataset 重复调用得到相同 ordering。

### Q7：如何证明 50 分不是 DeepSeek 编的？

Stage 11G 先直接调用 JobMatchingService 得到 oracle 50，再捕获 Agent direct trace 中 match_jobs Tool data，二者 detected / matched / missing / score / reason 完全一致。

---

# 19. Resume Value

## Deterministic Matching 方向

> 为 InternScout Agent 设计候选人 / 岗位确定性匹配模块，通过共享技能词汇、结构化与文本证据抽取、整数化可解释评分、城市 eligibility、全量分页与稳定 tie-break，实现可重复的 ranked matching，并使用严格 Pydantic contracts 冻结输入与输出 invariant。

## Agent Engineering 方向

> 将 matching capability 封装为 provider-neutral match_jobs Tool，通过 FastAPI composition root 接入现有 sequential Agent Runtime，使 DeepSeek 负责意图理解和结果说明、应用代码负责 evidence / score / ranking；使用 Fake Model、临时 SQLite、503-test full regression 与真实 OPPO + DeepSeek E2E 验证完整链路。

这些描述不声称：

~~~text
semantic matching
resume parsing
production recommender system
candidate persistence
multi-agent
RAG platform
~~~

---

# 20. Non-goals and Limitations

## 20.1 Explicit Non-goals

Stage 11 没有实现：

~~~text
resume PDF parsing
resume upload
OCR
candidate accounts
candidate persistence
education / GPA / experience matching
salary expectation matching
embeddings
Vector DB
semantic search
RAG retrieval pipeline
LLM skill extraction
LLM scoring
LLM ranking
parallel Tool Calling
multi-agent
memory
streaming
new crawler trigger
scheduler
database migration
standalone matching HTTP endpoint
~~~

## 20.2 Vocabulary Limitation

当前 canonical vocabulary 只有 15 个 display skills。Free-text extraction 更窄，并故意不检测普通 prose 中的 Requests。

因此未进入 structured job.skills、且不在 lexical whitelist 中的技术不会从 title / description 自动识别。

## 20.3 Score Semantics

当前 score 只计算：

~~~text
matched detected job skills
/
all detected job skills
~~~

它不表达：

~~~text
candidate overall seniority
education
years of experience
salary fit
business-domain fit
skill proficiency
skill importance weighting
~~~

## 20.4 City Semantics

城市是 hard eligibility filter。没有距离、remote、城市层级或 relocation model。

## 20.5 Query / Memory Limitation

Service 使用 first-page total 冻结 page horizon，并把 eligible results 放入 memory 后排序。它没有 database snapshot transaction model，也没有 streaming top-k。

## 20.6 top_k Limitation

当前 top_k 只验证 strict positive integer，没有 upper bound。这与 task specification 中的 bounded top_k expectation 不一致；formal review disposition 是 UNKNOWN。

## 20.7 Persistence Limitation

CandidateProfile、evidence、score 与 matches 都是 request-scoped，不保留历史，也不能用于离线 evaluation 或 recommendation analytics。

## 20.8 Real Verification Artifact

stage11g_agent_verify.py 当前未跟踪。Live OPPO 与 DeepSeek 也可能随外部 endpoint、岗位数据或 provider behavior 变化。

---

# 21. Completion Boundary

截至本 Review：

~~~text
Implementation:
COMPLETE

Stage 11 targeted tests:
164 passed

Full project tests:
503 passed

Warnings:
0

Real OPPO ingestion:
PASS

Deterministic oracle:
PASS

Real DeepSeek HTTP Agent:
PASS

Direct match_jobs trace:
PASS

Documentation:
COMPLETE IN WORKING TREE

Stage 11A-F Review:
PASS

Stage 11G Real Verification:
PASS

Formal Final Review:
PENDING

MUST FIX:
PENDING

SHOULD FIX:
PENDING

PR number:
UNKNOWN

merge SHA:
UNKNOWN

main branch status:
UNKNOWN

post-merge regression:
UNKNOWN
~~~

本次文档任务明确没有更新：

~~~text
PROJECT_STATE.md
~~~

也没有修改 app/ 或 tests/。

当前可确认的 capability：

~~~text
persisted real job
↓
deterministic skill evidence
↓
candidate coverage score
↓
stable ranked result
↓
match_jobs Tool
↓
DeepSeek explanation
~~~

但完整 Stage 11 Git lifecycle closeout 不能在 PR、merge、post-merge regression 与 formal Final Review 都为 UNKNOWN 时被声明为完成。
