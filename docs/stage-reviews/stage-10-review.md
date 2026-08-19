# InternScout Agent — Stage 10 Review

## 1. Stage Overview

### Stage

```text
Stage 10 — Real Recruitment Source Integration & Source Abstraction
```

Stage 10 的核心目标是：

> 在不重新设计 Stage 3～9 既有采集、清洗、去重、持久化、Jobs API 与 Agent 架构的前提下，将 OPPO Careers 作为第一个真实招聘数据源接入 InternScout Agent。

Stage 10 完成后的主链路是：

```text
OPPO Careers
↓
OppoJobSourceClient
↓
OppoJobCrawler
↓
JobCreate
↓
existing ingest_jobs
↓
existing process_jobs
↓
Cleaner / Deduplicator
↓
Repository
↓
SQLite
↓
Jobs API
↓
Agent Tools
↓
DeepSeek Agent
```

Stage 10 的重点不是“再做一套爬虫系统”，而是完成：

```text
Real Source Feasibility
+
External Source Adapter Boundary
+
Defensive Response Validation
+
Crawler Policy / Mapping
+
Existing ETL Reuse
+
Offline Contract Tests
+
Real End-to-End Smoke
```

---

# 2. Repository Reality

本 Review 创建前验证的 feature branch：

```text
feat/stage-10-oppo-source-integration
```

当前实现 HEAD：

```text
bff25e47c493ff5067e9ccfb70220bbfcf0bcfbb
```

最新 commit：

```text
bff25e4
fix: reject incomplete oppo pagination metadata
```

Stage 10 base：

```text
21d33b0
docs: update project state after stage 9
```

Stage 10 相对 base 的实现 touch set 只有：

```text
app/crawlers/oppo_source_client.py
app/crawlers/oppo_crawler.py
docs/tasks/stage-10-task.md
tests/test_oppo_source_client.py
tests/test_oppo_crawler.py
tests/test_oppo_ingestion.py
```

生产处理、持久化、API、Agent 与 dependency 文件均未因 Stage 10 被修改。

---

# 3. Stage 10 Final Status

截至本 Review：

```text
Source feasibility and selection:
COMPLETE

Task contract:
COMPLETE

Source HTTP boundary:
COMPLETE

Crawler boundary:
COMPLETE

Existing ingestion integration:
COMPLETE

Automated regression:
PASS

Real OPPO smoke:
PASS

Jobs API smoke:
PASS

Real DeepSeek Agent smoke:
PASS

Final Review #2:
PASS
```

最终 Review 结论：

```text
MUST FIX = 0
SHOULD FIX = 0

READY FOR STAGE 10 CLOSEOUT
```

但 Stage 10 尚未 merge 到 `main`。

因此当前状态必须区分为：

```text
Implementation / verification:
COMPLETE

Merge / post-merge closeout:
PENDING

Stage 10 Merge Identity:
UNKNOWN
```

`Stage 10 Merge Identity` 只能在真实 PR merge 完成后，以真实 Git merge identity 填写或确认。本 Review 不预先发明 documentation commit、PR identity 或 merge commit。

---

# 4. Stage 10 Commit History

已验证的 Stage 10 feature commits：

```text
7abd814
docs: add stage 10 task specification

4722eee
feat: add oppo source client boundary

534cbec
feat: add oppo job crawler

1f8cfdd
test: add oppo ingestion integration

bf6f347
fix: support oppo string total count

bff25e4
fix: reject incomplete oppo pagination metadata
```

该列表只记录当前 repository 中已经存在并经过验证的 feature commits。

尚未发生的以下事项不在 commit history 中伪造：

```text
Stage 10 documentation commit
PR identity
merge identity
post-merge main verification commit
```

---

# 5. Source Feasibility History

## 5.1 为什么先评估 ByteDance

Stage 10A 首先评估了 ByteDance 招聘数据源。

实际观察结果是：

```text
Detail endpoint:
plain HTTP usable

Discovery flow:
depends on browser-side signing / _signature

Ordinary unsigned HTTP:
not suitable for the selected integration path
```

这意味着“能访问一个 detail endpoint”并不等于“已经拥有可持续、可测试、符合当前边界的 discovery → detail 采集链路”。

Stage 10 明确拒绝：

```text
signature reverse engineering
anti-bot bypass
CAPTCHA bypass
browser automation as crawler architecture
```

因此 ByteDance 被拒绝为第一个真实招聘源。

这个决定不是说明 ByteDance 永远不能集成，而是说明其当时可观察的 discovery 条件不符合 Stage 10 的窄范围、安全边界与普通 HTTP 架构。

## 5.2 为什么选择 OPPO Careers

随后评估 OPPO Careers。

OPPO 招聘静态 HTML 页面主要是 frontend shell，实际岗位数据不直接存在于可稳定解析的服务端 HTML 中，因此没有选择 HTML scraping。

网站运行时使用的 JSON endpoints 可以通过普通 synchronous HTTP 访问，并且实际验证不需要：

```text
Cookie
Authorization
token
signature
Selenium
Playwright
browser automation
```

因此 Stage 10 选择：

```text
Observed website JSON endpoints
↓
injected synchronous httpx.Client
↓
narrow source adapter
```

重要边界：

> 这些 endpoint 是从 OPPO 招聘网站观察到的网站内部 JSON endpoints，不是被本项目声明为 OPPO 官方支持的 public developer API。

---

# 6. OPPO Source Endpoints

## Discovery

```text
POST
https://career.oppo.com/ats-candidate-api/open-api/position/queryPositionList
```

Discovery 用于获得分页 metadata 与 `positionId`。

## Detail

```text
GET
https://career.oppo.com/ats-candidate-api/open-api/position/queryPosition
```

Detail query：

```text
positionId={position_id}
```

## Human Source URL

```text
https://career.oppo.com/official/oppo/recruitment/post/{position_id}?recruitType={recruit_type}
```

持久化到 `JobCreate.source_url` 的是 human-readable OPPO recruitment page，而不是内部 discovery/detail JSON endpoint。

这一区分保证用户、Jobs API 与 Agent 最终获得的是可以打开的岗位页面，而不是网站内部数据接口地址。

---

# 7. Source Client Architecture

新增：

```text
app/crawlers/oppo_source_client.py
```

主要 symbols：

```text
OppoJobSourceClient
OppoPositionSummary
OppoPositionPage
OppoPositionDetail
```

架构：

```text
OppoJobSourceClient
↓
injected caller-owned synchronous httpx.Client
↓
observed OPPO website JSON endpoints
```

`OppoJobSourceClient` 负责：

```text
endpoint ownership
request serialization
source timeout policy
HTTP transport / status boundary
JSON decoding
response envelope validation
pagination source-shape validation
positionId validation
detail field validation
typed source data construction
```

它不认识：

```text
JobCreate
Cleaner
Deduplicator
Repository
SQLAlchemy Session
SQLite
FastAPI
Agent Runtime
Agent Tools
DeepSeek
```

因此 OPPO website response shape 被限制在 source adapter 内，没有泄漏到 domain、persistence、API 或 Agent layer。

## 7.1 HTTP Client Lifecycle

Client lifecycle 保持 caller-owned：

```text
with httpx.Client(...) as http_client:
    source_client = OppoJobSourceClient(http_client)
    crawler = OppoJobCrawler(source_client)
    ingest_jobs(crawler, session)
```

`OppoJobSourceClient` 不会：

```text
create a hidden long-lived client
close a caller-owned client
use module-level httpx.get/post
```

这使连接池、关闭时机和测试 transport 都由 composition caller 明确控制。

## 7.2 Failure Policy

Source client 使用 fail-fast：

```text
transport error
→ propagate

HTTP non-2xx
→ raise_for_status() / propagate

invalid JSON
→ contextual ValueError

invalid envelope / source shape
→ contextual ValueError
```

Stage 10 没有实现 retry、backoff 或 malformed item silent skipping。

---

# 8. Source Response Contract

真实外部 source 的 serialization 不应由离线 fixture 猜测决定。

Stage 10 的真实 smoke 暴露了两个重要 compatibility facts。

## 8.1 OPPO Success Code

真实观察：

```text
code = "0"
```

Production 接受且只接受：

```text
0
"0"
```

拒绝：

```text
bool
"00"
" 0"
0.0
None
other strings / containers
```

Python 中 `bool` 是 `int` 的 subclass，因此必须显式先拒绝 bool，不能只写简单的 `isinstance(value, int)`。

## 8.2 data.total

真实观察：

```text
total = "1"
```

Production 支持：

```text
non-negative Python int
```

或：

```text
canonical non-negative ASCII decimal string
```

合法例子：

```text
0
1
12

"0"
"1"
"12"
```

字符串 `total` 在 source boundary 内被 normalize 为 `int`，因此 `OppoPositionPage.total` 始终是稳定的 integer contract。

明确拒绝：

```text
""
" "
"01"
"00"
"+1"
"-1"
" 1"
"1 "
"1.0"
"1e3"
Unicode digits
bool
None
float
list
dict
```

同时：

```text
pageNum
pageSize
pages
```

继续保持 strict int-only，不因为 `total` 的真实兼容需求而放宽。

## 8.3 Narrow Compatibility Principle

Stage 10 没有使用：

```text
int(value)
```

作为 broad coercion。

原因是 `int(value)` 会接受超出已知 source contract 的 representation，并可能把 source schema drift 悄悄隐藏为“正常数据”。

Stage 10 采用的原则是：

> External compatibility 只根据已观察、已验证、已写入测试的 source evidence 扩展；未知 representation 继续 defensive fail。

---

# 9. Pagination Completeness Fix

## 9.1 Final Review #1 发现的问题

第一次 Stage 10 Final Review 发现：现有测试全部为绿色，但 pagination metadata 仍可能保证 silent incomplete ingestion。

例如：

```text
pages = 1
pageSize = 20
total = 21
len(list) = 20
```

Crawler 使用第一页 `pages=1` 作为有限边界，因此永远不会请求 page 2。

但 response 又声称总共有 21 条，而唯一可请求页面只返回 20 条。这不是普通的“页没有填满”，而是 metadata 已经证明至少一条岗位不可能被当前有限 page range 表示。

另一个例子：

```text
pages = 1
pageSize = 20
total = 1
len(list) = 0
```

`total` 声称存在岗位，但没有任何 later page 可以容纳这条岗位。

如果接受这些 response，系统会：

```text
HTTP success
↓
partial discovery accepted
↓
missing position never fetched
↓
incomplete ingestion appears successful
```

这是 data-integrity blocker，而不是 style issue。

## 9.2 Narrow Per-Response Invariant

修复加入：

```text
for pages > 0:

maximum_representable_total =
    (pages - 1) * returned_page_size
    + len(raw_positions)
```

仅当以下条件成立时拒绝：

```text
total > maximum_representable_total
```

该检查使用的 `total` 已经经过 integer normalization，因此同样覆盖：

```text
total = 41
total = "41"
```

## 9.3 为什么这个检查不属于过度验证

它不要求：

```text
every page is full
total == maximum capacity
later page total == first-page total
later page pages == first-page pages
returned pageSize == requested page_size
```

它也没有加入：

```text
crawler-level accumulated count
cross-page source state
cross-page metadata equality model
```

合法的 non-full response 仍然可以通过，例如：

```text
pages = 2
pageSize = 20
total = 21
len(current list) = 1

maximum capacity = 21
```

核心语义是：

> 当前 response 自己声明的有限页面容量，至少必须有可能表示它自己声明的 total。

因此这是 source-response self-consistency boundary，不是严格的 cross-page pagination model。

---

# 10. Crawler Architecture

新增：

```text
app/crawlers/oppo_crawler.py
```

主要 symbol：

```text
OppoJobCrawler
```

它继承：

```text
BaseJobCrawler
```

并继续满足：

```text
fetch_jobs() -> list[JobCreate]
```

## 10.1 Default Source Policy

默认配置：

```text
recruit_types = ("OFFEN-RECRUITMENT",)
keyword = ""
page_size = 20
```

`OFFEN-RECRUITMENT` 是真实 OPPO daily internship result 使用的 recruitment code。

Stage 10 故意没有设置默认：

```text
keyword = "AI"
```

原因是 production 默认 scope 应覆盖 daily internship recruitment，而不是把一次 smoke 使用的窄 AI filter 固化为业务默认。

Caller 提供的 sequence filters 会在 crawler construction 时 snapshot 为 tuple，避免外部 mutable list 在 crawl 前后改变 query policy。

## 10.2 Pagination and Ordering

Crawler flow：

```text
page 1 discovery
↓
page 1 establishes finite pages bound
↓
page 2 ... page N discovery
↓
all discovery complete
↓
sequential detail calls
↓
JobCreate mapping in discovery order
```

关键保证：

```text
all discovery before any detail
sequential discovery
sequential detail fetch
discovery ordering preserved
finite page-one bound
```

Crawler 不比较 later page 与 first page 的 `total/pages` 是否完全一致，也不维护跨页 accumulated count。

## 10.3 Crawler Failure Boundary

Crawler 使用 fail-fast：

```text
page discovery failure
→ stop before detail calls

detail failure
→ stop immediately
→ no later detail calls
→ no partial list returned

JobCreate validation failure
→ propagate
```

Stage 10 没有 retry，也没有 partial-success collection。

Crawler 只认识 typed source objects 和 `JobCreate`，不认识：

```text
HTTP request implementation
httpx.Response
Repository
SQLite
FastAPI
Agent
```

---

# 11. OPPO to JobCreate Mapping

精确 mapping：

```text
publishName
→ title

"OPPO"
→ company

workCityName
→ city

None
→ salary

岗位职责：
{jobDuty}

任职要求：
{workRequire}
→ description

[]
→ skills

"oppo"
→ source

human OPPO recruitment page
→ source_url

publishDate
→ published_at
```

`source_url` 使用真实 detail 返回的：

```text
positionId
recruitType
```

构造 human-readable URL。

## 11.1 Source Mapping 与 Domain Cleaning 分离

Crawler 故意保留 source 原值：

```text
东莞市
```

而不是在 `OppoJobCrawler` 内改为：

```text
东莞
```

随后 existing Cleaner 负责：

```text
东莞市
↓
东莞
```

因此：

```text
OppoJobCrawler
= source-specific mapping

Cleaner
= project-wide domain normalization
```

如果把城市 normalization 放入每个 source crawler，未来不同 crawler 会复制并漂移同一套 domain rule。

---

# 12. Existing Ingestion Integration

新增 network-free integration test：

```text
tests/test_oppo_ingestion.py
```

它验证的不是 isolated mapping function，而是真实现有 pipeline：

```text
Fake typed OPPO source
↓
OppoJobCrawler
↓
real ingest_jobs
↓
real process_jobs
↓
Cleaner
↓
Deduplicator
↓
Repository
↓
isolated temporary SQLite
```

验证的 source-shaped position：

```text
title:
AI产品实习生

company:
OPPO

raw city:
东莞市

persisted city:
东莞

salary:
None

skills:
[]

source:
oppo

published_at:
2026-06-01

source_url:
canonical human OPPO recruitment URL
```

测试还对同一个 crawler 执行第二次 ingestion，并确认：

```text
same logical database record
same database id
stored row count = 1
```

因此 re-ingestion 在当前 identity rule 下保持 idempotent。

测试使用显式 temporary SQLite engine/session，normal development database 没有参与。

---

# 13. Identity Limitation

现有 job identity 是：

```text
normalized company
+
normalized title
+
normalized city
```

因此已知 limitation：

> 两个不同 OPPO `positionId`，如果 normalized company/title/city 相同，可能被视为同一个 logical database job。

当前 database identity 不包含 external source position ID。

这属于 Stage 10 之前已经存在的 project/domain identity limitation，不是 Stage 10 新增 regression。

Stage 10 明确没有为了第一个 real source 修改：

```text
database schema
identity key
Repository uniqueness behavior
deduplication semantics
```

是否引入 source ID identity，需要单独的 domain migration 与兼容性设计，不能作为本阶段“顺手修改”。

---

# 14. Automated Test Architecture

Stage 10 automated tests 全部保持 network-free。

## 14.1 Source Client

```text
tests/test_oppo_source_client.py
```

使用：

```text
httpx.MockTransport
+
injected httpx.Client
```

覆盖 endpoint、payload、query、timeout use、HTTP failure、invalid JSON、envelope、code、pagination、total normalization、position ID、detail fields、publication date 与 no-retry behavior。

最终结果：

```text
117 passed
```

## 14.2 Crawler

```text
tests/test_oppo_crawler.py
```

使用：

```text
fake typed source client
```

不经过 HTTP，专门验证 defaults、filter snapshot、pagination ownership、ordering、mapping 与 fail-fast behavior。

最终结果：

```text
13 passed
```

## 14.3 Ingestion

```text
tests/test_oppo_ingestion.py
```

使用：

```text
fake real-source-shaped typed data
+
temporary SQLite
```

最终结果：

```text
1 passed
```

## 14.4 Final Regression Baseline

```text
Combined OPPO:
131 passed

Full project:
350 passed

Warnings:
0

git diff --check:
PASS
```

自动化测试不访问真实 OPPO，也不访问真实 DeepSeek。

验证策略是：

```text
Deterministic pytest contract tests
+
Explicit real external smoke
```

两者职责不同，不能互相替代。

---

# 15. Real Stage 10G OPPO Evidence

在 automated regression 全部通过后，Stage 10G 执行了显式 manual real-source smoke。

实际 position：

```text
position_id:
2061649545671430146

title:
AI产品实习生

raw city:
东莞市

publish_date:
2026-06-01

recruit_type:
OFFEN-RECRUITMENT
```

为保持真实 smoke 范围窄且可验证，使用 discovery filters：

```text
recruit_types = ("OFFEN-RECRUITMENT",)
keyword = "AI"
city_codes = ("44190X",)
page_size = 20
```

这里的 `keyword="AI"` 只是 explicit smoke filter，不是 production crawler default。

真实 human source URL：

```text
HTTP 200
```

真实 ingestion path：

```text
httpx.Client
↓
OppoJobSourceClient
↓
OppoJobCrawler
↓
ingest_jobs
↓
process_jobs
↓
Repository
↓
isolated SQLite
```

最终 persisted record：

```text
ID = 1
title = AI产品实习生
company = OPPO
city = 东莞
salary = None
skills = []
source = oppo
published_at = 2026-06-01
```

Normal development database 没有被该 smoke 使用。

---

# 16. Real Jobs API Evidence

同一份 isolated SQLite dataset 随后被接入 FastAPI。

验证结果：

```text
GET /api/jobs
→ HTTP 200

GET /api/jobs/1
→ HTTP 200
```

两个 endpoint 都返回真实 persisted OPPO position。

关键 same-database invariant：

```text
Real OPPO ingestion
↓
one temporary SQLite engine / session factory
↓
FastAPI app.state.database_engine
+
get_session dependency override
↓
Jobs API
```

为什么必须这样验证？

如果 ingestion 使用 database A，而 FastAPI dependency 使用 database B，那么：

```text
ingestion success
+
HTTP 200
```

仍然可能是 false smoke，因为 HTTP 查询到的不是刚刚写入的真实 OPPO data。

Stage 10G 通过共享同一个 isolated SQLite engine/session boundary 排除了这个问题。

---

# 17. Real Agent / DeepSeek Evidence

最终 real Agent smoke 使用：

```text
Provider:
DeepSeek

Model:
deepseek-v4-flash
```

HTTP 验证：

```text
POST /api/agent/query
→ HTTP 200
```

结果：

```text
answer:
nonblank

steps:
2

tool_execution_count:
1
```

Tool evidence：

```text
search_jobs
executed successfully
```

最终回答消费了同一 isolated SQLite 中真实持久化的 OPPO job，并报告了：

```text
OPPO internship
city
responsibilities
requirements
```

完整真实链路：

```text
Real OPPO source
↓
Source validation
↓
Crawler mapping
↓
Persistence
↓
Jobs database
↓
SearchJobsTool
↓
Real DeepSeek
↓
Natural-language answer
```

安全边界：

```text
DEEPSEEK_API_KEY
= environment configuration only
= never committed
```

本 Review 不包含也不推测任何 API key value。

---

# 18. Stage 10 Final Review History

## 18.1 Final Review #1

第一次 Final Review 结果：

```text
MUST FIX = 1
```

Finding：

```text
pagination metadata could guarantee
silent incomplete ingestion
```

该问题不是 request 是否成功的问题，而是成功 response 是否可能导致确定性 data loss 的问题。

修复 commit：

```text
bff25e4
fix: reject incomplete oppo pagination metadata
```

## 18.2 Final Review #2

Pagination fix 完成并经过 Human Review 后，再次执行完整 read-only code / architecture review。

结果：

```text
MUST FIX = 0
SHOULD FIX = 0
```

Verdict：

```text
READY FOR STAGE 10 CLOSEOUT
```

这段历史不应被隐藏。

它证明：

> 绿色测试 suite 不等于所有 data-integrity invariant 已经完整；Final Review 可以通过 architecture-level reasoning 发现 fixture 尚未表达的问题。

随后新增的 regression coverage 会在没有 capacity fix 时失败，从而把 review finding 转化为长期自动化保护。

---

# 19. Preserved Architecture Boundaries

Stage 10 没有修改或重新设计：

```text
BaseJobCrawler
MockJobCrawler
JobCrawlerProtocol
JobCreate
process_jobs
Cleaner
Deduplicator
ingest_jobs
Repository
database schema
/api/crawl
Jobs API
Agent Runtime
Agent Tools
requirements.txt
```

`POST /api/crawl` 继续保持 mock-specific。

Real OPPO ingestion 当前采用 explicit manual composition：

```text
httpx.Client
↓
OppoJobSourceClient
↓
OppoJobCrawler
↓
ingest_jobs
```

Stage 10 没有因为加入一个 real source 就强迫：

```text
Repository understand OPPO
Jobs API understand OPPO
Agent Tools understand OPPO
Agent Runtime understand OPPO
```

真实 OPPO data 一旦映射成现有 `JobCreate` 并持久化，后续 layer 自然复用原有 contract。

---

# 20. Important Engineering Lessons

## 20.1 External Source Adapter Boundary

招聘网站拥有自己的字段、envelope、pagination 与错误语义：

```text
publishName
workCityName
recruitType
positionId
code
data.total
```

这些不应该泄漏到：

```text
Repository
FastAPI
Agent Tools
Agent Runtime
```

`OppoJobSourceClient` 将不稳定 external contract 转换为窄的 typed source objects；`OppoJobCrawler` 再把 typed source data 映射为稳定的 `JobCreate`。

这是 Adapter Pattern 与 Port / Adapter architecture 在真实 source integration 中的具体价值。

## 20.2 Source Reality > Fixture Assumptions

初始 offline fixture 对 serialization 的假设与 live OPPO 不完全一致。

真实 source 返回：

```text
code = "0"
total = "1"
```

如果只相信 fixture，production 会拒绝真实合法 response。

因此 external integration contract 的形成过程应该是：

```text
safe real observation
↓
narrow contract decision
↓
production validation
↓
offline regression fixture
```

而不是反过来让真实世界服从最初的 fake data。

## 20.3 Narrow Compatibility vs Broad Coercion

简单写：

```text
int(value)
```

看似方便，但会把许多未验证 representation 一起接受。

Stage 10 只接受：

```text
non-negative int
or
canonical non-negative ASCII decimal string
```

这兼顾：

```text
real-source compatibility
+
schema drift visibility
+
defensive parsing
```

## 20.4 Fail Fast vs Silent Data Loss

在 recruitment ingestion 中，最危险的 failure 不一定是明显 exception，而可能是：

```text
request succeeded
pipeline completed
but some jobs were silently lost
```

Contradictory pagination metadata 应被拒绝，因为明确失败可以被发现、重试或调查；silent truncation 会产生看似正常但不完整的数据集。

## 20.5 Source Mapping vs Domain Cleaning

`OppoJobCrawler` 输出：

```text
东莞市
```

Cleaner 输出：

```text
东莞
```

这说明：

```text
source adapter / crawler
= preserve and map source meaning

domain cleaner
= apply project-wide normalization
```

Separation of Concerns 防止 source-specific code 重复 domain policy。

## 20.6 Offline Tests + Real Smoke

`httpx.MockTransport` 提供：

```text
deterministic
fast
network-free
precise malformed-response coverage
```

Real OPPO / DeepSeek smoke 提供：

```text
actual endpoint compatibility
actual serialization evidence
actual external behavior
```

Mock 无法证明 endpoint 当前真实可用；real smoke 也无法稳定覆盖几十种 malformed boundaries。两层验证都必要。

## 20.7 Same-Database End-to-End Verification

“ingestion PASS”和“API HTTP 200”分别成立，仍不足以证明 API 读到了同一批 data。

可靠 smoke 必须证明：

```text
one write database
=
one API read database
=
one Agent Tool query database
```

Stage 10G 使用同一个 isolated SQLite boundary，将 persistence、Jobs API 和 Agent consumption 连接成一条可验证的真实链路。

## 20.8 Architecture Preservation

加入 external source 时，容易把 source-specific condition 扩散到所有 layer。

Stage 10 证明更稳健的方法是：

```text
new source boundary
+
new crawler mapping
+
existing stable pipeline
```

而不是：

```text
new source
→ redesign Repository
→ redesign API
→ redesign Agent
```

这降低 change surface，也让现有 full regression 真正发挥保护作用。

---

# 21. Interview Knowledge Points

## Architecture

- Adapter Pattern
- Port / Adapter architecture
- Dependency Inversion
- Separation of Concerns
- External contract vs internal stable contract
- Source boundary vs domain boundary
- Architecture preservation

## HTTP / Resource Lifecycle

- synchronous `httpx`
- injected HTTP client
- caller-owned client lifecycle
- connection pooling ownership
- timeout policy
- `raise_for_status()`
- transport failure propagation

## External Data Validation

- defensive parsing
- strict envelope validation
- bool-as-int pitfall
- canonical decimal string
- pagination metadata
- representational capacity
- fail-fast
- external schema volatility
- narrow compatibility
- data-integrity invariant

## Data Engineering

- source mapping
- data normalization
- ETL / ingestion pipeline
- cleaning
- deduplication
- idempotent ingestion
- database identity
- external source ID limitation

## Testing

- `httpx.MockTransport`
- fake typed source client
- temporary SQLite
- deterministic contract test
- integration test
- real external smoke test
- same-database invariant
- regression baseline
- test isolation

## Agent Integration

- persisted external data
- Jobs API consumption
- Agent Tool query
- DeepSeek Tool Calling
- real source → database → Agent answer

---

# 22. Potential Interview Questions

### Q1：为什么不直接让 `OppoJobCrawler` 使用 requests/httpx？

因为 crawler 的职责是 pagination policy、ordering 和 `JobCreate` mapping，而不是解析 HTTP response envelope。

Stage 10 将 HTTP 与 source schema 放在 `OppoJobSourceClient`：

```text
Source Client
= HTTP + source validation

Crawler
= orchestration + mapping
```

这样 crawler tests 可以使用 fake typed client，不需要构造 HTTP response。

### Q2：为什么 HTTP Client 要注入？

注入 caller-owned `httpx.Client` 可以明确：

```text
resource lifecycle
connection pooling
timeout use
MockTransport testing
```

Source client 不会隐藏创建或泄漏一个 long-lived client，调用方可以通过 `with httpx.Client(...)` 可靠关闭资源。

### Q3：为什么 Source Client 不直接返回 `JobCreate`？

因为 source client 应只负责 OPPO external contract。

如果它直接构造 `JobCreate`，HTTP adapter 就会同时承担 domain mapping，并开始认识 salary、skills、source URL 等项目语义。Stage 10 使用 typed OPPO dataclasses 保持 source validation 与 domain mapping 分离。

### Q4：为什么城市标准化不放在 `OppoJobCrawler`？

城市 normalization 是全项目 domain rule，existing Cleaner 已经统一负责。

Crawler 保留 `东莞市`，Cleaner 转换为 `东莞`，可以避免每个 source crawler 复制同一套 normalization logic。

### Q5：为什么自动化测试不能直接访问 OPPO？

真实网站会受到：

```text
network availability
source schema change
rate limiting
data change
service availability
```

影响。pytest 必须 deterministic、可重复且不依赖外部服务，因此 source tests 使用 `httpx.MockTransport`。

### Q6：为什么仍然需要真实 OPPO smoke？

MockTransport 只能证明“代码符合我们写下的 fixture contract”，不能证明 fixture 与真实 source 相同。

Stage 10 正是通过 real smoke 发现了 `code="0"` 与 `total="1"` 的真实 serialization，因此 real smoke 是 external compatibility evidence。

### Q7：`code="0"` / `total="1"` 如何安全兼容？

`code` 只接受：

```text
0
"0"
```

`total` 只接受 non-negative int 或 canonical non-negative ASCII decimal string，并在 boundary 内 normalize 为 int。

bool、sign、whitespace、leading zero、float、Unicode digits 与 containers 都继续拒绝。

### Q8：为什么不能直接 `int(value)`？

因为 broad coercion 会接受未经 source evidence 支持的 representation，并隐藏 schema drift。

Stage 10 先验证 exact accepted shape，再转换，从而保持 compatibility 是有依据且可审计的。

### Q9：pagination capacity invariant 解决什么问题？

它拒绝 response 声称的 `total` 超出有限 `pages`、returned `pageSize` 和当前 `list` 能表示的最大容量。

这样可以防止 crawler 按有限 pages 正常结束，却确定性漏掉 source 自己声称存在的岗位。

### Q10：为什么不检查每一页 `total/pages` 完全一致？

因为外部数据在分页期间可能变化，而且 Stage 10 没有证据证明 OPPO 保证 cross-page snapshot consistency。

当前 fix 只检查每个 response 自己是否可能成立，不引入没有 source evidence 的 cross-page equality contract。

### Q11：如何证明真实 OPPO 数据最终真的被 Agent 使用？

Stage 10G 将真实 OPPO job 写入一个 isolated SQLite，然后让 FastAPI `get_session` 和 `app.state.database_engine` 指向同一 database。

Jobs API 返回该 record，随后真实 DeepSeek Agent 执行 `search_jobs`，最终答案报告这条 OPPO internship 的城市、职责和要求。

### Q12：为什么 Stage 10 不修改 `/api/crawl`？

Stage 10 contract 将 `/api/crawl` 冻结为 mock-specific。

本阶段目标是证明 real source 可以通过 explicit composition 复用 existing ingestion path，而不是同时设计 production trigger、auth、scheduling、retry 与 operational policy。Real-source endpoint 应由后续独立 scope 决定。

---

# 23. Resume Value

## Source Integration / ETL 方向

> 为 InternScout Agent 接入真实 OPPO Careers 招聘数据源，设计基于 injected synchronous httpx Client 的 source adapter 与 typed response boundary，实现 discovery/detail、有限分页、defensive schema validation、fail-fast data-integrity checks，并将结果无侵入接入既有 cleaning、deduplication、Repository 与 SQLite ETL pipeline。

## End-to-End Agent 方向

> 完成真实 OPPO 岗位从外部 JSON source、typed crawler mapping、SQLite persistence、FastAPI Jobs API 到 DeepSeek Agent `search_jobs` Tool Calling 的端到端验证，使用 MockTransport、fake typed client、temporary SQLite 与 same-database smoke 同时保证自动化确定性和真实外部兼容性。

这些描述不声称：

```text
multi-source support
production scheduler
distributed crawling
anti-bot bypass
```

---

# 24. Explicit Stage 10 Non-Goals

Stage 10 故意没有实现：

```text
ByteDance integration
multi-source orchestration
universal crawler framework
generic provider factory
browser automation
CAPTCHA bypass
signature reverse engineering
retry
exponential backoff
partial success
scheduler
distributed crawler
real-source /api/crawl trigger
LLM skill extraction
RAG
Memory
Vector DB
Streaming
Multi-Agent
Parallel Tool Calling
database identity redesign
```

这些是明确的 scope boundary，不是 Stage 10 defects。

当前 external website schema 未来可能变化，也属于真实 source integration 必须接受并通过 boundary failure 暴露的 operational limitation。

---

# 25. Stage 10 Final Capability

Stage 10 implementation 完成后，feature branch 已经具备：

```text
Natural external recruitment data
↓
validated source boundary
↓
crawler pagination and mapping
↓
existing cleaning / dedup pipeline
↓
SQLite persistence
↓
Jobs API
↓
Agent Tool
↓
DeepSeek answer
```

项目能力从：

```text
mock recruitment ingestion
+
database-backed Agent query
```

扩展为：

```text
verified real recruitment source
↓
existing application and Agent stack
```

同时没有把一个 source-specific integration 误写成 multi-source platform。

---

# 26. Completion Boundary

截至本 Review：

```text
Implementation:
COMPLETE

Automated Tests:
350 passed

Warnings:
0

Real OPPO Discovery / Detail:
PASS

Real Ingestion:
PASS

Jobs API:
PASS

Real DeepSeek Agent:
PASS

Final Review #2:
PASS

MUST FIX:
0

SHOULD FIX:
0
```

仍待 procedural closeout：

```text
development-log.md update
documentation commit
push
PR
merge
post-merge main verification
PROJECT_STATE final snapshot
branch cleanup
```

特别注意：

```text
PROJECT_STATE.md
```

只能在真实 PR merge 与 post-merge `main` verification 后更新 Stage 10 final snapshot。

最终状态：

```text
Implementation / verification:
COMPLETE

Merge / post-merge closeout:
PENDING

Stage 10 Merge Identity:
UNKNOWN
```

该 identity 必须以未来真实 PR merge 后的 repository reality 为准。
