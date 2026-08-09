# InternScout Agent 阶段6复习：FastAPI岗位服务闭环、筛选与分页

> 阶段名称：FastAPI岗位服务闭环、岗位查询、筛选、分页、详情、采集与健康检查  
> 项目：InternScout Agent  
> 最终测试：111 passed  
> Codex最终审查：必须修改为无  
> 阶段结论：完成“采集 → 清洗 → 去重 → SQLite → FastAPI查询”第一版完整服务闭环

---

## 目录

- [1. 阶段6完成了什么](#1-阶段6完成了什么)
- [2. 阶段6项目结构变化](#2-阶段6项目结构变化)
- [3. 完整HTTP服务闭环](#3-完整http服务闭环)
- [4. FastAPI路由分层](#4-fastapi路由分层)
- [5. API响应模型](#5-api响应模型)
- [6. 岗位列表查询](#6-岗位列表查询)
- [7. 城市公司技能筛选](#7-城市公司技能筛选)
- [8. 分页设计](#8-分页设计)
- [9. 岗位详情接口](#9-岗位详情接口)
- [10. 岗位采集接口](#10-岗位采集接口)
- [11. 数据库健康检查](#11-数据库健康检查)
- [12. FastAPI lifespan与自动建表](#12-fastapi-lifespan与自动建表)
- [13. FastAPI依赖覆盖与临时数据库测试](#13-fastapi依赖覆盖与临时数据库测试)
- [14. 阶段6完整自动化测试](#14-阶段6完整自动化测试)
- [15. Codex发现的关键问题](#15-codex发现的关键问题)
- [16. 本阶段实际遇到的问题](#16-本阶段实际遇到的问题)
- [17. 面试可能提问](#17-面试可能提问)
- [18. 一分钟阶段介绍](#18-一分钟阶段介绍)
- [19. 当前技术债](#19-当前技术债)
- [20. 阶段6验收清单](#20-阶段6验收清单)
- [21. 自测题](#21-自测题)

---

# 1. 阶段6完成了什么

阶段5结束时，项目已经能够：

```text
模拟招聘HTML
→ MockJobCrawler
→ JobCreate
→ 数据清洗
→ 岗位去重
→ SQLite持久化
```

但这些能力主要仍然通过Python函数调用。

阶段6的核心目标是：

> 将已经完成的爬虫、清洗、数据库和查询能力通过FastAPI组成一个真正可访问的Web服务。

最终提供接口：

```text
GET  /
GET  /api/health
POST /api/crawl
GET  /api/jobs
GET  /api/jobs/{job_id}
```

并实现：

- 应用启动自动创建数据库表
- 数据库健康检查
- 通过HTTP触发岗位采集
- 岗位列表查询
- 城市筛选
- 公司筛选
- 技能筛选
- 多条件组合查询
- 分页
- 岗位详情
- 404和422错误语义
- 重复采集幂等
- 临时数据库API测试
- 完整HTTP闭环测试

最终：

```text
111 passed
```

---

# 2. 阶段6项目结构变化

阶段6主要增加：

```text
app/
├── api/
│   ├── __init__.py
│   └── routes/
│       ├── __init__.py
│       ├── jobs.py
│       ├── crawl.py
│       └── health.py
│
├── schemas/
│   ├── job.py
│   ├── job_response.py
│   ├── crawl_response.py
│   └── health_response.py
│
├── database/
│   ├── models.py
│   ├── session.py
│   └── repository.py
│
├── services/
│   └── cleaner.py
│
└── main.py

tests/
├── test_job_response_schema.py
├── test_job_query_repository.py
├── test_job_api.py
├── test_job_detail_api.py
├── test_crawl_api.py
├── test_health.py
└── test_stage6_api_flow.py
```

职责：

| 文件 | 作用 |
|---|---|
| `jobs.py` | 岗位列表和岗位详情HTTP接口 |
| `crawl.py` | 触发岗位采集工作流 |
| `health.py` | 服务与数据库健康检查 |
| `job_response.py` | 岗位列表和详情响应模型 |
| `crawl_response.py` | 采集接口响应模型 |
| `health_response.py` | 健康检查响应模型 |
| `repository.py` | 筛选、分页、详情数据库查询 |
| `main.py` | 创建FastAPI应用、lifespan、注册路由 |

---

# 3. 完整HTTP服务闭环

阶段6结束后完整链路：

```text
                 HTTP Client
                      ↓
                   FastAPI
                      ↓
      ┌───────────────┼────────────────┐
      ↓               ↓                ↓
 /api/health      /api/crawl       /api/jobs
      ↓               ↓                ↓
  SELECT 1       ingest_jobs        query_jobs
                      ↓                ↓
               MockJobCrawler      Repository
                      ↓                ↓
                  JobCreate        SQLAlchemy
                      ↓                ↓
                 process_jobs       SQLite
                      ↓                ↑
                 清洗 + 去重 ─────────┘
```

从空数据库开始：

```text
FastAPI启动
→ lifespan自动创建jobs表
→ GET /api/health
→ POST /api/crawl
→ 保存6条岗位
→ GET /api/jobs
→ 筛选 / 分页
→ GET /api/jobs/{job_id}
→ 再次POST /api/crawl
→ 数据库仍然只有6条
```

这就是第一版服务闭环。

---

# 4. FastAPI路由分层

阶段1时接口直接写在：

```text
app/main.py
```

阶段6后拆分：

```text
app/api/routes/jobs.py
app/api/routes/crawl.py
app/api/routes/health.py
```

`main.py`只负责：

```text
创建FastAPI
配置lifespan
注册router
保留根路径
```

这样避免随着接口增加，`main.py`越来越大。

当前：

```text
jobs.py
→ 岗位读取

crawl.py
→ 岗位采集命令

health.py
→ 服务状态
```

这属于按业务领域拆分路由。

---

# 5. API响应模型

## 5.1 JobRead

数据库返回的是：

```text
JobModel
```

API不能直接把整个ORM对象暴露出去。

因此定义：

```python
class JobRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )
```

`from_attributes=True`允许Pydantic从：

```python
job.id
job.title
job.company
```

等ORM属性读取数据。

链路：

```text
JobModel
→ JobRead.model_validate()
→ JSON
```

---

## 5.2 为什么不返回identity_key

数据库：

```text
JobModel.identity_key
```

用于内部去重。

它不是API用户需要关心的信息。

所以：

```text
JobModel
包含identity_key

JobRead
不包含identity_key
```

实现：

> 数据库模型和API契约解耦。

---

## 5.3 JobListResponse

列表响应：

```text
items
total
page
page_size
pages
```

例如：

```json
{
  "items": [],
  "total": 21,
  "page": 2,
  "page_size": 10,
  "pages": 3
}
```

`total`表示全部符合条件的结果数量。

`len(items)`只表示当前页返回多少条。

两者不能混淆。

---

# 6. 岗位列表查询

接口：

```text
GET /api/jobs
```

调用：

```text
query_jobs()
```

Repository负责：

```text
构建筛选条件
→ count总数
→ 判断页码
→ offset
→ limit
→ 主键排序
→ 返回items和total
```

API负责：

```text
读取HTTP参数
→ 调用Repository
→ 计算pages
→ JobModel转换JobRead
→ 返回JobListResponse
```

这种职责划分避免路由中出现复杂SQL。

---

# 7. 城市公司技能筛选

## 7.1 城市筛选

查询：

```text
GET /api/jobs?city=深圳市
```

先：

```text
normalize_city("深圳市")
→ 深圳
```

数据库已经保存标准化城市，因此能够匹配。

---

## 7.2 公司筛选

阶段6发现：

写入：

```text
Example   Tech
```

和查询：

```text
Example Tech
```

以前可能采用不同标准化规则。

因此增加：

```python
normalize_company()
```

规则：

```text
删除首尾空白
合并连续空白
```

例如：

```text
" Example   Tech "
→
"Example Tech"
```

写入和查询复用同一个函数。

这是很重要的原则：

> 查询标准化必须与写入标准化一致。

---

## 7.3 技能筛选

数据库技能：

```json
["Python", "FastAPI", "SQL"]
```

不能简单使用：

```sql
LIKE '%SQL%'
```

因为：

```text
SQL
```

可能错误匹配：

```text
NoSQL
```

因此使用SQLite JSON1能力：

```text
json_each()
```

将数组展开成：

```text
Python
FastAPI
SQL
```

然后执行完整元素等值比较。

所以：

```text
skill=SQL
```

匹配SQL，但不匹配NoSQL。

---

# 8. 分页设计

接口：

```text
GET /api/jobs?page=2&page_size=10
```

规则：

```text
page >= 1
1 <= page_size <= 100
```

offset：

```text
(page - 1) * page_size
```

例如：

```text
page=2
page_size=10

offset=10
```

即跳过前10条。

---

## 8.1 pages计算

公式：

```text
(total + page_size - 1) // page_size
```

例如：

```text
total=21
page_size=10

pages=3
```

没有数据：

```text
total=0
→ pages=0
```

---

## 8.2 超出范围页码

例如：

```text
total=5
page=100
page_size=10
```

返回：

```json
{
  "items": [],
  "total": 5,
  "page": 100,
  "page_size": 10,
  "pages": 1
}
```

这是清晰的API契约：

> 页码合法，只是该页没有数据。

因此返回200，而不是404。

---

## 8.3 极大页码问题

曾测试：

```text
page=10**18
page_size=100
```

原实现会把巨大offset发送给SQLite，最终出现：

```text
OverflowError:
Python int too large to convert to SQLite INTEGER
```

修复：

```text
先查询total
→ 算offset
→ 如果offset >= total
→ 直接return [], total
```

数据库不再执行巨大OFFSET。

---

# 9. 岗位详情接口

接口：

```text
GET /api/jobs/{job_id}
```

Repository：

```python
session.get(
    JobModel,
    job_id,
)
```

因为`job_id`是数据库主键，所以`Session.get()`非常适合。

状态码：

```text
GET /api/jobs/1
数据库有ID 1
→ 200

GET /api/jobs/999999
ID格式合法但资源不存在
→ 404

GET /api/jobs/0
违反ge=1
→ 422

GET /api/jobs/abc
不是整数
→ 422
```

面试中需要明确：

> 404表示资源不存在，422表示请求参数本身无法通过接口约束。

---

# 10. 岗位采集接口

接口：

```text
POST /api/crawl
```

为什么不是GET？

因为它会：

```text
读取岗位
→ 清洗
→ 写数据库
```

具有副作用。

因此使用POST。

路由没有重新实现：

```text
crawler.fetch_jobs
process_jobs
save_jobs
```

而是复用：

```text
ingest_jobs()
```

依赖方向：

```text
API
→ Workflow
→ Crawler / Service / Repository
```

---

## 10.1 幂等性

第一次：

```text
POST /api/crawl
→ database_total=6
```

第二次：

```text
POST /api/crawl
→ database_total仍然=6
```

重复执行不会增加数据库记录。

这依赖：

```text
process_jobs业务去重
+
Repository保存前查询
+
identity_key数据库唯一约束
```

---

# 11. 数据库健康检查

阶段1：

```text
GET /api/health
→ {"status": "ok"}
```

只能证明FastAPI函数还能运行。

阶段6：

```text
GET /api/health
→ Depends(get_session)
→ SELECT 1
```

数据库正常：

```text
200
```

数据库异常：

```text
503 Service Unavailable
```

使用：

```python
except SQLAlchemyError
```

只捕获合理的数据库异常。

对客户端只返回：

```text
数据库不可用
```

不会泄漏：

- SQL
- 文件路径
- SQLite底层错误
- 数据库内部结构

---

# 12. FastAPI lifespan与自动建表

## 12.1 原来的问题

测试中都会：

```python
init_database(engine)
```

所以测试正常。

但是新用户克隆项目以后直接：

```powershell
python -m uvicorn app.main:app
```

数据库可能没有`jobs`表。

第一次：

```text
GET /api/jobs
```

会：

```text
500
no such table: jobs
```

---

## 12.2 最终方案

使用：

```python
@asynccontextmanager
async def lifespan(app):
    ...
```

应用启动：

```text
FastAPI
→ lifespan
→ init_database
→ create_all
→ 接受请求
```

因此全新环境可以直接启动。

需要记住：

```text
create_all
```

适合创建不存在的表，但不是正式数据库迁移工具。

修改已有表结构时仍需要Alembic。

---

# 13. FastAPI依赖覆盖与临时数据库测试

正式路由：

```python
Depends(get_session)
```

默认使用正式：

```text
internscout.db
```

测试不能碰正式数据库。

因此：

```python
app.dependency_overrides[get_session] = (
    override_get_session
)
```

将请求Session切换到临时SQLite。

同时：

```python
app.state.database_engine = test_engine
```

让lifespan创建表时也使用同一个临时Engine。

两者必须同时配置：

```text
lifespan Engine
=
请求 Session Engine
```

否则可能：

```text
临时数据库建表
但API请求查询正式数据库
```

或者反过来。

---

## 13.1 为什么finally非常重要

测试结束：

```python
finally:
    dependency_overrides.pop(...)
    engine.dispose()
```

确保：

- 删除依赖覆盖
- 恢复Engine状态
- 释放数据库连接
- 后续测试不被当前fixture污染

---

# 14. 阶段6完整自动化测试

阶段6最终不只测试单个函数。

测试层次包括：

```text
Schema测试
Repository测试
API测试
完整HTTP集成测试
```

完整闭环测试：

```text
全新数据库
→ health
→ jobs为空
→ crawl
→ jobs有6条
→ filter
→ pagination
→ detail
→ repeated crawl
```

最终：

```text
111 passed
1 warning
```

正式`internscout.db`在测试前后未发生变化。

---

# 15. Codex发现的关键问题

阶段6第一次审查发现4个必须修改。

## 15.1 新环境首次查询500

问题：

```text
jobs表未自动创建
```

解决：

```text
FastAPI lifespan
```

---

## 15.2 极大页码500

问题：

```text
SQLite OFFSET整数溢出
```

解决：

```text
offset >= total
→ 提前返回空列表
```

---

## 15.3 纯空格筛选返回全部岗位

问题：

```text
city="   "
```

能通过`min_length=1`。

标准化后又被当成没有筛选条件。

解决：

```text
API层拒绝
+
Repository层拒绝
```

---

## 15.4 公司标准化不一致

问题：

```text
写入公司名称
≠
查询公司名称标准化规则
```

解决：

```text
normalize_company
```

写入和查询共同使用。

---

## 15.5 最终Codex审查

最终：

```text
必须修改：无
```

验收结论：

```text
可以进入阶段6最终收尾
```

Codex确认：

> 当前已经形成“采集 → 清洗 → 去重 → SQLite → FastAPI查询”的第一版完整服务闭环。

---

# 16. 本阶段实际遇到的问题

## 16.1 VS Code文件突然大量标红

`mock_crawler.py`曾显示大量：

```text
return只能在函数中使用
self未定义
card未定义
bs4无法解析
pydantic无法解析
```

但：

```text
python -m pytest
```

仍然全部通过。

处理方式：

```powershell
python -m py_compile app\crawlers\mock_crawler.py
git diff -- app\crawlers\mock_crawler.py
python -c "import sys; print(sys.executable)"
```

先判断：

- 文件是否真的损坏
- 是否存在未保存编辑内容
- Pylance是否选择错误解释器

经验：

> 编辑器红线不是最终运行结果，必须结合Python编译、pytest、git diff和解释器路径判断。

---

## 16.2 CRLF/LF警告

出现：

```text
CRLF will be replaced by LF
```

项目使用：

```text
.gitattributes
```

统一：

```text
*.py → LF
```

开发完成后使用：

```powershell
git diff --check
```

检查。

---

## 16.3 Codex审查时所在分支错误

Codex一次审查实际位于：

```text
main
```

而预期是：

```text
feat/job-query-api
```

后续Codex提示词要求先执行：

```powershell
git branch --show-current
git status
```

经验：

> 工具声称正在审查哪个分支不重要，Git命令输出才是真实状态。

---

# 17. 面试可能提问

## 1. 阶段6主要完成了什么？

参考回答：

> 我把前面已经完成的爬虫、数据清洗和SQLite持久化能力通过FastAPI组成了完整服务。实现了岗位采集、列表查询、城市公司技能筛选、分页、岗位详情和数据库健康检查，同时使用lifespan解决全新环境自动建表，并通过临时SQLite和依赖覆盖完成API集成测试，最终111个测试通过。

---

## 2. 为什么API不能直接返回SQLAlchemy ORM对象？

参考回答：

> ORM包含数据库内部字段和实现细节，不应该直接作为API契约。我使用Pydantic的JobRead作为响应模型，并通过from_attributes从ORM读取数据，从而避免暴露identity_key等内部字段。

---

## 3. `from_attributes=True`有什么作用？

参考回答：

> 它允许Pydantic模型直接从对象属性读取字段，所以可以把JobModel这样的SQLAlchemy ORM对象转换成JobRead，而不需要手动先转成dict。

---

## 4. 为什么分页需要total和pages？

参考回答：

> items只表示当前页的数据，前端还需要知道全部结果数量和总页数，才能展示分页组件和判断下一页是否存在。因此查询会同时返回items和total，API再根据total和page_size计算pages。

---

## 5. 为什么巨大page会导致问题？

参考回答：

> 正常分页会将(page - 1) * page_size作为SQLite OFFSET。如果page非常大，这个Python整数可能超过SQLite INTEGER范围而导致500。我的修复是在得到total以后先判断offset是否已经超出结果范围，如果超出就直接返回空页，不再执行OFFSET查询。

---

## 6. 为什么SQL技能不能用LIKE查询？

参考回答：

> 因为SQL可能匹配NoSQL。技能字段本身是JSON数组，所以我使用SQLite json_each展开数组，再对单个数组元素做精确等值比较。

---

## 7. 为什么写入和查询必须复用同一个normalize_company？

参考回答：

> 如果写入和查询使用不同的标准化规则，数据库可能保存“Example   Tech”，查询却标准化成“Example Tech”，最终导致漏查。复用同一个标准化函数可以保证数据进入数据库和查询输入采用同一套规则。

---

## 8. 为什么超出总页数返回200而不是404？

参考回答：

> 页码参数本身是合法的，只是该页暂时没有数据，所以返回200和空items，同时保留total和pages。404更适合表示具体资源不存在，比如查询不存在的岗位ID。

---

## 9. 404和422有什么区别？

参考回答：

> `/api/jobs/999999`中的ID格式合法，只是岗位不存在，所以返回404；`/api/jobs/abc`不是合法整数，或者ID为0违反ge=1约束，所以请求参数本身不合法，由FastAPI返回422。

---

## 10. 为什么使用POST /api/crawl？

参考回答：

> 采集操作会读取数据并写入数据库，具有副作用，因此不适合GET。POST更符合“触发一次处理任务”的HTTP语义。

---

## 11. `/api/crawl`为什么不直接写爬虫和数据库逻辑？

参考回答：

> 阶段5已经建立ingest_jobs工作流。API层只负责HTTP输入输出，业务编排继续复用workflow，避免在路由中重复crawler、cleaner和repository逻辑。

---

## 12. 为什么重复crawl不会产生重复数据？

参考回答：

> 系统有三层保护：process_jobs处理同一批输入内的重复，Repository保存前查询已有岗位，数据库identity_key唯一约束作为最后一道并发保护，所以重复执行相同采集任务时数据库总量不会增长。

---

## 13. 为什么健康检查使用SELECT 1？

参考回答：

> SELECT 1非常轻量，但能够验证Session、Engine、SQLite连接和SQL执行整条数据库访问链路是否正常，不需要为了健康检查读取真实业务数据。

---

## 14. 为什么数据库异常返回503？

参考回答：

> FastAPI本身可能仍然运行，但数据库暂时不可用，此时服务无法提供完整能力。503 Service Unavailable比未处理异常导致的500更准确。

---

## 15. lifespan解决了什么问题？

参考回答：

> 原来测试会显式初始化数据库，但新环境直接启动FastAPI时可能没有jobs表，首次请求会500。现在应用启动进入lifespan时调用init_database，自动创建缺失表，因此首次启动无需额外手动初始化命令。

---

## 16. 测试怎么保证不修改正式数据库？

参考回答：

> API测试为每个fixture创建临时SQLite Engine，然后通过app.state.database_engine让lifespan使用测试Engine，再通过dependency_overrides替换get_session，让HTTP请求也使用同一个临时数据库。最终Codex还比较了正式数据库的哈希，确认测试前后完全一致。

---

## 17. 什么是依赖覆盖？

参考回答：

> FastAPI路由依赖get_session获取正式数据库Session。测试时可以用dependency_overrides把这个依赖替换为测试Session，而不需要修改生产路由代码，这样可以做到测试隔离。

---

## 18. 你如何使用Codex进行代码审查？

参考回答：

> 我让Codex只读检查实际功能分支，允许运行测试和读取Git状态，但不允许修改、commit或push。第一次审查发现自动建表、巨大页码、纯空格参数和公司标准化四个真实问题，我逐一修复并补回归测试；最终审查必须修改为无，111个测试通过。

---

# 18. 一分钟阶段介绍

> 阶段6我把项目从本地Python数据处理程序升级成了完整FastAPI服务。我实现了岗位列表、城市公司技能筛选、分页和岗位详情，同时增加POST /api/crawl，通过HTTP复用现有ingest_jobs工作流完成爬虫、清洗、去重和SQLite持久化。为了支持全新环境启动，我使用FastAPI lifespan自动创建数据库表，并把健康检查升级成真实执行SELECT 1的数据库检查。测试层使用dependency_overrides和临时SQLite隔离正式数据库，并加入从空库到采集、查询、筛选、详情和重复采集的完整HTTP闭环测试。Codex审查发现并帮助定位了巨大页码OFFSET溢出、纯空格参数以及公司标准化不一致等问题，修复后全项目111个测试通过，最终审查没有必须修改项。

---

# 19. 当前技术债

阶段6不继续扩大范围修改以下问题：

- API测试fixture存在重复代码
- Engine和Session依赖注入契约还可以进一步统一
- SQLite lower()不能保证完整Unicode大小写无关比较
- health 503尚未创建独立错误响应模型
- Repository批量写入仍然逐条commit
- 默认SQLite路径依赖工作目录
- 尚未引入Alembic
- Starlette TestClient/httpx存在弃用警告
- 暂未接入真实招聘网站
- 暂未实现认证、异步任务或复杂并发
- Agent智能匹配尚未进入正式实现阶段

这些问题属于：

```text
后续扩展
性能优化
工程增强
```

而不是阶段6阻塞项。

---

# 20. 阶段6验收清单

## Response Schema

- [x] 创建JobRead
- [x] 创建JobListResponse
- [x] 支持ORM直接转换
- [x] identity_key不暴露
- [x] 分页字段有约束

## Repository查询

- [x] 城市筛选
- [x] 公司筛选
- [x] 技能筛选
- [x] 组合筛选
- [x] total统计
- [x] 分页
- [x] 主键稳定排序
- [x] 空结果
- [x] 超页查询
- [x] 极大页码安全处理
- [x] 空白筛选拒绝

## FastAPI

- [x] GET /
- [x] GET /api/health
- [x] POST /api/crawl
- [x] GET /api/jobs
- [x] GET /api/jobs/{job_id}
- [x] 404岗位不存在
- [x] 422非法岗位ID
- [x] 422非法分页
- [x] 422纯空格筛选
- [x] Swagger自动生成接口文档

## Lifespan

- [x] 应用启动自动创建jobs表
- [x] 新环境首次请求不再500
- [x] 测试可以指定临时Engine

## Health

- [x] 执行SELECT 1
- [x] 正常返回200
- [x] 数据库异常返回503
- [x] 不泄漏底层错误信息

## Crawl

- [x] API复用ingest_jobs
- [x] 从空数据库采集6条
- [x] 保存标准化数据
- [x] 重复crawl保持数据库幂等
- [x] GET /api/crawl返回405

## Testing

- [x] 使用临时SQLite
- [x] dependency_overrides替换Session
- [x] 测试不访问正式数据库
- [x] 完整空库HTTP闭环测试
- [x] Codex最终确认正式数据库未修改
- [x] git diff --check通过
- [x] 全项目111 passed

## Code Review

- [x] Codex第一次审查发现真实问题
- [x] 修复首次启动500
- [x] 修复巨大页码500
- [x] 修复空白筛选语义
- [x] 修复公司标准化不一致
- [x] 最终Codex必须修改为无
- [x] Codex结论允许进入阶段6最终收尾

---

# 21. 自测题

请尝试不看前文回答：

1. 阶段6相比阶段5最大的变化是什么？
2. 为什么需要JobRead，而不是直接返回JobModel？
3. `from_attributes=True`有什么作用？
4. 为什么API不暴露identity_key？
5. `total`和`len(items)`有什么区别？
6. pages如何计算？
7. 为什么page超出总页数仍然返回200？
8. 极大page为什么可能导致SQLite异常？
9. 如何避免巨大OFFSET进入SQLite？
10. 为什么技能SQL不能使用普通LIKE？
11. SQLite json_each有什么作用？
12. 为什么SQL查询不能匹配NoSQL？
13. 为什么公司写入和查询要复用normalize_company？
14. 为什么纯空格可以通过FastAPI的min_length=1？
15. 阶段6如何处理纯空格查询？
16. 为什么详情接口使用session.get？
17. 404和422分别代表什么？
18. 为什么crawl使用POST而不是GET？
19. crawl接口为什么应该调用workflow？
20. 为什么重复crawl不会重复入库？
21. processed_count为什么不等于“新增数量”？
22. health为什么使用SELECT 1？
23. 为什么数据库异常返回503？
24. lifespan是什么？
25. 为什么应用启动时需要自动建表？
26. `create_all()`为什么不能替代Alembic？
27. dependency_overrides有什么作用？
28. 为什么测试需要同时覆盖Engine和get_session？
29. 如何证明API测试没有修改正式数据库？
30. Codex阶段6发现的4个必须修改问题分别是什么？
31. 为什么Codex建议并不是全部都需要当前修改？
32. 当前阶段6还有哪些技术债？

---

## 阶段6总结

阶段6是InternScout Agent项目目前非常关键的一步。

项目从：

```text
Crawler
+
Cleaning
+
Database
```

进一步升级成：

```text
Crawler
+
Cleaning
+
Deduplication
+
Persistence
+
FastAPI
+
Automated Integration Testing
```

最终形成：

```text
采集
→ 清洗
→ 去重
→ SQLite
→ HTTP查询
```

第一版完整服务闭环。

这意味着后续Agent或智能匹配功能不需要重新解决：

- 岗位从哪里来
- 岗位如何标准化
- 岗位如何去重
- 岗位保存在哪里
- 岗位如何查询

而可以直接建立在当前稳定的数据和API基础之上。

一句话总结：

> 阶段6把InternScout Agent从一个能够处理和保存岗位数据的Python项目，推进成了一个拥有采集、数据库、筛选、分页、详情、健康检查和完整自动化测试的FastAPI后端服务。
