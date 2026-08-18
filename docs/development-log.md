# InternScout Agent 开发日志

## 2026-07-23：阶段1项目初始化

### 今天完成

- 创建正式项目目录
- 创建Python 3.12虚拟环境
- 初始化Git仓库
- 安装FastAPI、Uvicorn、Pytest和HTTPX
- 完成根路径和健康检查接口
- 编写并运行两个接口自动化测试

### 学到的知识

- 虚拟环境可以隔离不同项目的Python依赖
- FastAPI通过路由装饰器定义接口
- Uvicorn负责启动FastAPI应用
- Pytest使用assert检查程序实际结果
- Uvicorn启动后一直等待请求，不是程序卡住

### 遇到的问题

- PowerShell最初禁止运行虚拟环境的激活脚本
- 浏览器请求favicon.ico时返回404
- Pytest出现一个第三方库的弃用警告

### 解决方法

- 将CurrentUser执行策略设置为RemoteSigned
- favicon.ico不是业务接口，可以暂时忽略
- Pytest警告不影响当前两个测试通过，后续统一检查依赖兼容性

### 已解决的疑问

- FastAPI负责定义接口和处理请求，Uvicorn负责监听端口并运行FastAPI应用
- git add将修改加入暂存区，git commit将暂存内容保存为正式版本

### 仍然不理解

- FastAPI为什么可以自动将Python字典转换成JSON
- Pytest的fixture具体有什么作用

## 阶段2：岗位数据模型与模拟招聘数据

## 2026-07-25

### 今天完成

- 创建阶段2功能分支
- 使用Pydantic定义岗位数据模型
- 添加岗位字段类型和长度限制
- 编写岗位数据模型测试
- 创建包含6条岗位的模拟招聘页面
- 为后续爬虫准备缺失薪资等边界数据

### 学到的知识

- Pydantic模型用于验证和规范输入数据
- 必填字段和可选字段对应不同的业务情况
- default_factory用于安全地创建默认列表
- 模拟HTML可以让爬虫测试稳定且可重复
- 开发新功能前应先运行旧测试建立基线

### Codex代码审查

本次使用Codex对以下文件进行了只读审查：

- app/schemas/job.py
- app/schemas/__init__.py
- tests/test_job_schema.py
- app/fixtures/sample_jobs.html

#### 审查结论

- 当前岗位模型与模拟HTML整体结构一致
- 6条模拟岗位的ID和链接具有唯一性
- 至少存在一条缺少薪资字段的边界样例
- 没有发现阻塞下一阶段的模型或HTML错误
- 可以进入模拟爬虫解析阶段

#### 后续需要处理

- 爬虫创建JobCreate时注入source="mock"
- HTML没有salary标签时解析为None
- 后续补充HTML到JobCreate的集成测试
- 数据清洗阶段处理技能去重和标准化
- 后续评估是否将source_url改为URL验证类型

#### Codex使用体会

- 先限定只读权限，可以避免工具直接修改代码
- Codex的建议需要结合当前项目阶段判断，并非全部立即实施
- 最终仍需通过git status、git diff和pytest确认结果

### 遇到的问题

根据实际情况填写。

### 解决方法

根据实际情况填写。

### 仍然不理解

根据实际情况填写。

## 阶段3：模拟岗位爬虫与HTML解析

### 本阶段完成

- 安装BeautifulSoup并更新项目依赖
- 定义BaseJobCrawler抽象接口
- 实现MockJobCrawler
- 将模拟招聘HTML解析为JobCreate对象
- 解析岗位名称、公司、城市、薪资、描述、技能、链接和日期
- 支持缺少薪资或空白薪资时返回None
- 支持datetime属性为空白时回退到标签正文
- 为Pydantic校验异常补充岗位序号和文件路径
- 增加文件不存在、页面无岗位、必填字段缺失等异常处理
- 编写12个模拟爬虫测试
- 项目全部18个测试通过
- 使用Codex进行只读代码审查并修复边界问题

### 学到的知识

- BeautifulSoup用于解析HTML文档
- CSS选择器用于定位网页中的岗位字段
- 爬虫负责提取数据，Pydantic负责验证和转换数据
- pathlib可以构造不依赖本机绝对路径的文件路径
- 抽象基类可以统一不同爬虫的调用接口
- Pytest的tmp_path可以创建临时测试文件
- monkeypatch可以临时修改测试运行环境
- 异常链可以保留原始错误，同时增加业务上下文
- 新功能开发完成后需要运行全部回归测试

### 遇到的问题

1. PowerShell使用重定向生成requirements.txt时，将文件保存为UTF-16，Git将其识别为二进制文件。
2. 终端显示(.venv)，但实际使用了旧测试目录中的虚拟环境，导致找不到pytest。
3. datetime属性为纯空白字符串时，没有回退到time标签正文，导致日期校验失败。

### 解决方法

1. 使用Python的Path.write_text并指定UTF-8重新生成requirements.txt。
2. 使用sys.executable检查实际Python路径，并重新选择正式项目的.venv解释器。
3. 对datetime属性先执行strip，再决定使用属性值、标签正文或None。
4. 捕获Pydantic ValidationError，添加岗位序号和文件路径，并保留原始异常链。

### 后续优化

- 明确source_url是否允许相对地址
- 正式接入真实数据源时统一补全和验证URL
- 项目打包时确保fixtures文件被包含
- 后续统一处理FastAPI TestClient的弃用警告

## 阶段4：岗位数据清洗、标准化与去重

### 本阶段完成

- 创建岗位业务处理模块
- 实现城市名称标准化
- 实现技能名称规范化
- 删除空白和重复技能并保持原始顺序
- 根据公司、岗位名称和标准化城市构建岗位身份
- 实现岗位列表去重并保留第一次出现的数据
- 实现先清洗、再去重的 process_jobs 处理管道
- 使用 JobCreate.model_validate 重新验证清洗结果
- 完成模拟爬虫到数据处理管道的集成测试
- 全项目36个测试通过
- 使用Codex完成只读代码审查

### 核心设计

#### 城市标准化

使用受控的 CITY_ALIASES 映射，只转换项目明确支持的城市：

- 深圳市 → 深圳
- 广州市 → 广州
- 上海市 → 上海

未知名称保持原样，避免将“四日市”错误转换为“四日”。

#### 技能标准化

使用 SKILL_ALIASES 统一常见技能展示名称：

- python → Python
- fastapi → FastAPI
- pytest → pytest
- beautifulsoup4 → Beautiful Soup

#### 岗位去重

当前使用以下三元组作为岗位身份：

公司名称 + 岗位名称 + 标准化城市

相同身份的岗位只保留第一次出现的数据。

#### 数据处理顺序

原始岗位列表
→ 逐条清洗
→ 根据清洗后的结果去重
→ 返回干净岗位列表

### 遇到的问题

1. 原来的城市清洗规则会删除所有名称末尾的“市”，导致“四日市”被错误转换为“四日”。
2. 技能规范表将pytest错误写成Pytest。
3. Pydantic的model_copy(update=...)不会重新验证更新后的字段。
4. 修改测试文件时误将其他模块代码放入test_cleaner.py，造成JobIdentity未定义。
5. 清理错误代码时遗漏create_job辅助函数，造成NameError。

### 解决方法

1. 使用受控的CITY_ALIASES城市映射，不再直接截断所有“市”字。
2. 将pytest规范名称统一为官方小写形式。
3. 使用model_dump和JobCreate.model_validate重新构造并验证清洗结果。
4. 根据pytest报错中的文件和行号定位错误代码位置。
5. 恢复独立的create_job测试辅助函数。
6. 为以上问题补充回归测试。

### 当前局限

- 城市映射只覆盖当前项目中的常见城市
- 未收录技能的大小写仍保留输入形式
- 公司、岗位名称和城市相同但部门或批次不同的岗位，可能被视为重复
- 当前未使用描述相似度或岗位编号进行高级去重

### 后续计划

- 将处理后的岗位数据保存到数据库
- 提供岗位查询和筛选接口
- 根据真实数据逐步扩充城市和技能别名

## 阶段5：SQLite数据库与岗位持久化

### 本阶段完成

- 安装并引入SQLAlchemy 2.x
- 使用SQLite作为项目第一版持久化数据库
- 创建JobModel岗位ORM模型
- 定义jobs数据库表及字段约束
- 使用JSON字段保存岗位技能列表
- 为岗位身份identity_key增加唯一约束
- 实现数据库Engine和Session工厂
- 实现数据库表初始化函数
- 实现岗位模型转换、保存和查询Repository
- 重复保存岗位时返回已有数据库记录
- 捕获唯一约束竞争产生的IntegrityError
- 实现批量岗位保存并保持首次出现顺序
- 实现爬虫、清洗、去重和入库的完整工作流
- 使用临时SQLite文件完成自动化测试
- 完成正式数据库手动验证
- 完成Codex只读代码审查
- 全项目59个测试通过

### 完整数据链路

模拟招聘HTML
→ MockJobCrawler
→ JobCreate
→ process_jobs
→ 城市和技能标准化
→ 岗位去重
→ ingest_jobs
→ save_jobs
→ SQLite jobs表

### 数据库设计

jobs表包含：

- id
- identity_key
- title
- company
- city
- salary
- description
- skills
- source
- source_url
- published_at
- created_at

identity_key由标准化后的公司名称、岗位名称和城市组成，并通过数据库唯一约束防止重复写入。

### 重复岗位保护

项目目前具有三层重复保护：

1. process_jobs负责当前输入列表内的业务去重
2. save_job保存前查询数据库是否已有相同身份
3. jobs.identity_key数据库唯一约束处理竞争窗口

发生预期唯一约束冲突时：

提交失败
→ rollback
→ 查询已有岗位
→ 返回已有记录

如果回滚后找不到对应身份记录，则重新抛出IntegrityError，避免掩盖其他数据库约束错误。

### 事务契约

当前save_job会直接提交调用方传入的Session。

save_jobs采用逐条提交策略：

- 已成功保存的岗位不会因后续岗位失败而回滚
- 适合当前小批量模拟岗位
- 调用方应使用专门用于岗位持久化的Session
- 不应在同一Session中混入无关的未提交数据

后续数据量扩大后，可以将事务边界移动到工作流层，并评估批量原子事务。

### Codex审查结果

必须修改：无。

建议内容包括：

- 明确Repository的事务边界
- 明确Repository只接收已清洗岗位
- 后续评估identity_key字段长度或固定哈希
- 增加IntegrityError无法匹配岗位时重新抛出的测试
- 后续将数据库路径改为配置注入
- 失败测试中应确保Engine可靠释放

本阶段补充了Repository输入契约、事务契约和IntegrityError重新抛出回归测试。

### 当前技术债

- 默认SQLite路径依赖进程工作目录
- 默认Engine在模块导入时创建
- 批量岗位采用逐条提交，非原子事务
- identity_key使用JSON字符串而非固定长度哈希
- 尚未引入Alembic数据库迁移
- 尚未提供岗位数据库API
- 尚未实现数据库分页和条件筛选
- FastAPI TestClient仍存在Starlette弃用警告

### 后续计划

- 为岗位数据库提供查询API
- 支持城市、公司和技能筛选
- 增加分页参数
- 将数据库Session接入FastAPI依赖注入
- 后续根据数据库结构变化引入Alembic

## 阶段6：FastAPI岗位服务闭环、查询筛选与分页

### 本阶段完成

- 创建独立的FastAPI API路由模块
- 实现岗位列表响应模型JobRead和JobListResponse
- JobRead支持直接从SQLAlchemy JobModel生成API响应
- API响应不暴露数据库内部identity_key
- Repository新增岗位筛选和分页查询能力
- 支持按城市精确筛选岗位
- 支持按公司精确筛选岗位
- 支持按技能精确筛选岗位
- 支持城市、公司和技能组合查询
- 使用SQLite json_each精确匹配JSON技能数组成员
- 保证查询SQL技能时不会错误匹配NoSQL
- 实现page和page_size分页
- 返回items、total、page、page_size和pages
- 超出结果范围的页码返回200和空items
- 极大合法页码不会再触发SQLite OFFSET整数溢出
- 纯空格city、company和skill参数返回422
- 新增normalize_company，保证公司名称写入和查询时使用相同空格规范
- 实现GET /api/jobs岗位列表接口
- 实现GET /api/jobs/{job_id}岗位详情接口
- 不存在岗位返回404
- 非法岗位ID返回422
- 实现POST /api/crawl岗位采集接口
- POST /api/crawl复用既有ingest_jobs工作流
- 重复执行采集不会重复写入数据库
- 实现GET /api/health数据库健康检查
- 健康检查执行真实SELECT 1
- 数据库正常返回200
- 数据库不可用返回503
- 使用FastAPI lifespan在应用启动时自动创建数据库表
- 全新环境不再需要手动初始化jobs表
- 测试使用app.state.database_engine和dependency_overrides切换到临时SQLite
- 正式internscout.db不会被API自动化测试污染
- 增加从空数据库到采集、查询、筛选、详情和重复采集的完整HTTP闭环测试
- 完成Codex阶段6最终只读代码审查
- Codex最终结论：必须修改为无
- 全项目111个测试通过

### 阶段6完整HTTP接口

当前FastAPI应用提供：

```text
GET  /
GET  /api/health
POST /api/crawl
GET  /api/jobs
GET  /api/jobs/{job_id}
```

接口职责：

```text
GET /
→ 返回服务基本信息

GET /api/health
→ 检查FastAPI和数据库是否可用

POST /api/crawl
→ 触发模拟岗位采集、清洗、去重和入库

GET /api/jobs
→ 查询岗位列表、筛选和分页

GET /api/jobs/{job_id}
→ 根据数据库主键查询单个岗位详情
```

### 完整服务闭环

阶段6完成后，项目形成了第一版完整服务闭环：

```text
HTTP请求
→ FastAPI
→ MockJobCrawler
→ JobCreate
→ process_jobs
→ 城市、公司、技能标准化
→ 岗位去重
→ ingest_jobs
→ Repository
→ SQLAlchemy
→ SQLite
→ query_jobs / get_job_by_id
→ JobRead / JobListResponse
→ JSON响应
```

完整HTTP操作流程：

```text
全新SQLite数据库
→ FastAPI lifespan自动创建jobs表
→ GET /api/health确认数据库可用
→ GET /api/jobs确认初始岗位为空
→ POST /api/crawl采集6条模拟岗位
→ GET /api/jobs查询岗位
→ 使用城市、公司和技能条件筛选
→ 使用page和page_size分页
→ GET /api/jobs/{job_id}查看岗位详情
→ 再次POST /api/crawl
→ 数据库岗位总数保持不变
```

### API响应模型

阶段6新增：

- JobRead
- JobListResponse
- CrawlResponse
- HealthResponse

JobRead用于对外展示岗位数据。

数据库中的：

```text
identity_key
```

属于内部去重字段，不在JobRead中声明，因此不会出现在API响应或OpenAPI岗位响应Schema中。

JobListResponse返回：

```text
items
total
page
page_size
pages
```

其中：

- items：当前页岗位
- total：所有符合条件的岗位数量
- page：当前页
- page_size：每页最大岗位数量
- pages：符合条件结果的总页数

### 岗位筛选设计

#### 城市筛选

查询参数先使用与写入阶段相同的normalize_city。

例如：

```text
深圳市
→ 深圳
```

因此可以正确匹配数据库中的标准化城市。

#### 公司筛选

阶段6新增normalize_company：

```text
" Example   Tech "
→ "Example Tech"
```

写入和查询均复用相同规则，避免数据库保存一种格式、查询使用另一种格式造成漏查。

#### 技能筛选

技能存储为SQLite JSON数组：

```json
["Python", "FastAPI", "SQL"]
```

查询时通过json_each展开数组并按完整元素等值匹配。

因此：

```text
skill=SQL
```

可以匹配：

```text
["Python", "SQL"]
```

但不会错误匹配：

```text
["NoSQL"]
```

### 分页设计

Repository支持：

```text
page >= 1
1 <= page_size <= 100
```

offset计算：

```text
(page - 1) * page_size
```

查询结果按JobModel.id排序，保证当前阶段分页顺序稳定。

如果请求页码已经超出结果范围：

```text
offset >= total
```

Repository直接返回：

```text
items = []
total = 实际符合条件的数量
```

而不会再把巨大OFFSET交给SQLite执行。

这修复了极大页码可能触发：

```text
OverflowError:
Python int too large to convert to SQLite INTEGER
```

的问题。

### 空白查询参数

FastAPI的min_length只检查原始字符串长度，因此：

```text
"   "
```

虽然没有有效内容，也能通过min_length=1。

阶段6最终在API层和Repository层均增加保护：

```text
city="   "
company="   "
skill="   "
```

不会被静默视为“没有筛选条件”。

API返回422，避免错误地返回全部岗位。

### 岗位详情接口

详情接口：

```text
GET /api/jobs/{job_id}
```

Repository通过：

```python
session.get(JobModel, job_id)
```

根据数据库主键读取岗位。

接口语义：

```text
存在岗位
→ 200

ID格式正确但数据库不存在
→ 404

job_id=0
→ 422

job_id为负数
→ 422

job_id不是整数
→ 422
```

### 采集接口

采集接口：

```text
POST /api/crawl
```

没有在路由中重新实现爬虫、清洗和数据库逻辑，而是复用：

```text
ingest_jobs
```

因此依赖方向保持：

```text
API
→ Workflow
→ Crawler + Services + Repository
```

当前响应：

```json
{
  "processed_count": 6,
  "database_total": 6
}
```

processed_count表示本次工作流处理后的唯一岗位数量，并不表示数据库新增数量。

因此重复执行：

```text
第一次crawl
→ processed_count=6
→ database_total=6

第二次crawl
→ processed_count=6
→ database_total=6
```

符合当前工作流语义。

### 健康检查

阶段1的健康检查只证明FastAPI函数能够执行。

阶段6升级为：

```text
GET /api/health
→ Depends(get_session)
→ SELECT 1
```

数据库正常：

```json
{
  "status": "ok",
  "database": "ok"
}
```

HTTP状态码：

```text
200
```

数据库出现SQLAlchemy错误：

```json
{
  "detail": "数据库不可用"
}
```

HTTP状态码：

```text
503
```

对外不会泄漏数据库文件路径、SQL或底层驱动错误。

### 应用生命周期与首次启动

Codex第一次阶段6审查发现：

```text
全新环境中jobs表不存在
→ 首次GET /api/jobs
→ 500
```

原因是之前只有测试和手动命令调用init_database，正式应用启动没有自动创建表。

最终使用FastAPI lifespan：

```text
FastAPI启动
→ lifespan
→ init_database(engine)
→ Base.metadata.create_all()
→ 开始处理HTTP请求
```

测试时使用：

```text
app.state.database_engine = test_engine
```

让lifespan初始化临时数据库。

请求Session则通过：

```text
app.dependency_overrides[get_session]
```

切换到同一个临时SQLite Engine。

这样可以同时做到：

```text
正式运行
→ 使用正式Engine

自动化测试
→ lifespan使用临时Engine
→ API Session也使用临时Engine
→ 不连接正式internscout.db
```

### 自动化测试

阶段6测试覆盖：

- JobRead从ORM读取数据
- JobListResponse分页字段验证
- identity_key不会被API暴露
- Repository城市筛选
- Repository公司筛选
- Repository技能筛选
- SQL不会误匹配NoSQL
- 多条件组合查询
- 正常分页
- 空结果
- 超页查询
- 极大页码
- page和page_size非法值
- city/company/skill纯空白
- GET /api/jobs默认查询
- API城市筛选
- API公司筛选
- API技能筛选
- API组合筛选
- API分页
- API空结果
- GET /api/jobs/{job_id}详情查询
- 详情404
- 详情ID 422
- POST /api/crawl首次入库
- 重复crawl幂等
- crawl保存标准化数据
- GET /api/crawl返回405
- health数据库正常返回200
- health数据库异常返回503
- lifespan全新数据库自动建表
- 从空数据库开始的完整HTTP闭环
- 采集后筛选和分页
- HTTP层重复采集幂等

最终结果：

```text
111 passed
1 warning
```

唯一警告仍然是Starlette TestClient/httpx相关弃用警告，与当前业务功能无关。

### Codex审查发现并修复的问题

阶段6第一次Codex审查发现4个必须修改问题。

#### 1. 全新环境首次请求返回500

原因：

```text
正式应用启动没有调用init_database
```

解决：

```text
使用FastAPI lifespan自动创建表
```

#### 2. 极大合法页码导致SQLite OFFSET溢出

原因：

```text
(page - 1) * page_size
```

可能超过SQLite INTEGER范围。

解决：

```text
取得total后
→ 如果offset >= total
→ 直接返回空items
→ 不执行OFFSET查询
```

#### 3. 纯空格筛选被视为无筛选条件

原因：

FastAPI的min_length检查原始长度，纯空格可以通过。

解决：

```text
API层strip后拒绝空值
Repository层再次拒绝空白筛选
```

#### 4. 公司名称写入和查询标准化不一致

原因：

查询会合并连续空格，但写入阶段以前没有统一处理公司名称。

解决：

```text
新增normalize_company
→ clean_job写入前使用
→ query_jobs查询时复用
```

### 开发过程中遇到的其他问题

#### VS Code中mock_crawler.py突然出现大量红色错误

Pytest仍然59 passed，但Pylance显示：

```text
return只能在函数中使用
card未定义
self未定义
bs4无法解析
pydantic无法解析
```

处理时先区分：

```text
磁盘文件
VS Code编辑器内容
Pylance解释器状态
```

通过：

```powershell
python -m py_compile app\crawlers\mock_crawler.py
git diff -- app\crawlers\mock_crawler.py
python -c "import sys; print(sys.executable)"
```

确认真实代码和解释器状态，避免看到红色提示就盲目修改已经正常的业务代码。

#### CRLF与LF警告

阶段6修改Python文件时再次遇到：

```text
CRLF will be replaced by LF
```

项目已经通过：

```text
.gitattributes
```

规定Python和项目文本文件统一使用LF。

修改完成后使用Python重新规范换行，并通过：

```powershell
git diff --check
```

确认无问题。

#### Codex审查时分支状态需要确认

一次Codex审查发现实际所在分支为main，而不是预期的feat/job-query-api。

因此后续审查提示词增加：

```text
先执行git branch --show-current
git status
```

在审查开始前确认真实Git状态。

### 阶段6最终Codex审查

最终只读审查结论：

```text
必须修改：无
```

Codex确认：

- lifespan自动建表可以保留
- 测试Engine与API Session指向相同临时数据库
- get_session可以可靠关闭Session
- health真实执行SELECT 1
- crawl正确复用ingest_jobs
- query_jobs的count和items使用相同筛选条件
- 极大页码在进入SQLite前安全返回
- normalize_company不会破坏岗位身份一致性
- json_each技能筛选不会将SQL错误匹配为NoSQL
- session.get适合岗位详情主键查询
- JobRead不会暴露identity_key
- API路由不存在冲突
- 重复crawl幂等
- 未发现循环导入
- 未发现正式数据库被测试访问
- 阶段6已经形成第一版完整FastAPI服务闭环

Codex沙箱外最终测试：

```text
111 passed
```

正式internscout.db在测试前后SHA-256、文件大小和修改时间均未变化。

### 当前技术债

- 多个API测试文件重复创建临时数据库fixture
- fixture结束时目前主要恢复项目默认Engine，而不是统一保存并恢复进入fixture前的状态
- app.state.database_engine只负责lifespan建表，请求Session仍依赖get_session覆盖，Engine注入契约可以进一步统一
- SQLite lower()主要可靠支持ASCII大小写，不保证完整Unicode case-insensitive比较
- health的503目前只有OpenAPI描述，没有独立错误响应模型
- save_jobs仍然逐条查询、提交和refresh，小数据量可接受，大数据量需要优化
- 默认SQLite路径仍依赖进程当前工作目录
- 尚未引入Alembic数据库迁移
- Starlette TestClient/httpx仍存在弃用警告
- 尚未引入真正的外部招聘数据源
- 尚未进入Agent智能匹配能力

### 阶段6结论

阶段6已经完成第一版：

```text
采集
→ 清洗
→ 去重
→ SQLite
→ FastAPI查询
```

服务闭环。

项目已经不再只是由多个独立Python模块组成，而是能够通过HTTP接口实际操作整个岗位数据系统。

当前可以通过：

```text
POST /api/crawl
```

触发岗位采集，再通过：

```text
GET /api/jobs
GET /api/jobs/{job_id}
```

查询结果，并通过：

```text
GET /api/health
```

检查服务和数据库状态。

这是项目从“后端功能模块集合”进入“可运行Web服务”的关键阶段。

### 后续计划

- 在后续阶段继续复用当前FastAPI、数据库和岗位查询能力
- 根据项目任务书进入智能匹配和Agent相关功能
- 后续真实接入招聘数据源时复用现有Crawler接口和处理管道
- 根据实际需求进一步统一数据库配置和测试fixture
- 在合适阶段处理数据库迁移和TestClient依赖升级


## 阶段7：Tool-Calling Agent Layer 与 Agent Runtime

### 本阶段完成

- 在Stage 6现有FastAPI、SQLite和岗位查询能力之上建立独立Agent Layer
- 创建Agent内部统一Contract
- 实现ToolDefinition
- 实现ToolCall
- 实现ToolResult
- 实现ToolExecution
- 实现ModelRequest
- 实现ToolCallResponse
- 实现FinalAnswerResponse
- 实现AgentResult
- 创建AgentState保存单次Agent Run运行状态
- 创建AgentError异常基类
- 创建AgentMaxStepsExceeded最大步骤异常
- 实现BaseTool统一Tool执行协议
- Tool参数使用Pydantic模型验证
- Tool参数错误转换为失败ToolResult
- Tool内部异常转换为统一失败ToolResult
- Tool内部异常不会向Agent泄漏底层错误信息
- 实现ToolRegistry
- 支持Tool注册、查找和ToolDefinition列表生成
- 重复Tool名称注册会被拒绝
- 实现SearchJobsTool
- 实现GetJobDetailTool
- 实现ModelClient抽象接口
- 实现FakeModelClient用于确定性Agent单元测试
- 实现AgentOrchestrator
- 支持Model直接返回FinalAnswer
- 支持Model发起ToolCall
- 支持Tool执行结果作为Observation进入下一轮模型决策
- 支持多个Tool按顺序连续调用
- Tool参数失败不会直接终止Agent
- Tool内部失败不会直接终止Agent
- Unknown Tool不会直接导致Agent崩溃
- Unknown Tool会转换为失败Observation
- FinalAnswer会正常终止Agent Run
- 使用max_steps限制单次Agent Run中的Model调用次数
- max_steps在下一次Model.generate之前检查
- 增加Agent Run之间的状态隔离
- 每次run创建独立AgentState，不使用self.state保存单次运行状态
- Repo Reality Check发现Job Tool仍然直接依赖Repository和SQLAlchemy Session
- 新增JobQueryPort作为Agent侧岗位查询抽象
- 新增RepositoryJobQueryAdapter连接JobQueryPort和现有Repository
- SearchJobsTool和GetJobDetailTool改为只依赖JobQueryPort
- Agent Job Tool不再直接依赖SQLAlchemy Session
- Agent Job Tool不再直接调用Repository
- Adapter负责将Repository返回的数据转换为JobRead
- 完成Codex Stage 7最终只读代码审查
- Codex最终结论：必须修改为无
- Codex提出3项非阻塞Hardening建议
- Tool参数模型增加extra="forbid"，禁止未知参数被静默忽略
- FinalAnswerResponse增加纯空白答案保护
- 增加同一AgentOrchestrator连续两次run的状态隔离测试
- Codex提出的3项建议全部完成
- Stage 7最终Agent Layer测试70 passed
- 全项目最终184 passed，1 warning

### Stage 7 Agent架构

阶段7最终形成：

```text
User Goal
↓
AgentOrchestrator
↓
ModelClient
↓
Model Decision
├─ ToolCallResponse
│      ↓
│   ToolRegistry
│      ↓
│     Tool
│      ↓
│  ToolResult
│      ↓
│ Observation
│      ↓
│ Next Model Decision
│
└─ FinalAnswerResponse
       ↓
    AgentResult

```

### Stage 7 结论

Stage 7 建立了 InternScout Agent 第一版独立、可测试的 Tool-Calling Agent Runtime。

核心结果：

```text
User Goal
→ AgentOrchestrator
→ ModelClient
→ ToolCall
→ Tool
→ Observation
→ ModelClient
→ FinalAnswer
```

并通过 `JobQueryPort + RepositoryJobQueryAdapter` 保持 Agent Tool 与 Repository / SQLAlchemy 解耦。

Stage 7 最终状态：

```text
Agent Layer:
70 passed

Full Regression:
184 passed
1 warning
```

后续 Stage 将在不重新设计当前 Agent Runtime 的前提下接入真实 LLM Provider。

---

## 阶段8：Real LLM Provider Integration

### 本阶段目标

Stage 8 的核心目标不是简单完成一次大模型 API 调用，而是验证：

```text
Stage 7 已建立的 provider-neutral Agent Runtime
是否可以在不重新设计核心架构的情况下
接入真实 LLM Provider。
```

需要保持：

```text
AgentOrchestrator
↓
ModelClient
↓
Provider Adapter
```

其中 `AgentOrchestrator` 不直接知道：

```text
DeepSeek
Responses API
OpenAI Python SDK
API Key
Provider-specific Response
```

---

### 本阶段完成

- 创建 `docs/codex-workflow.md`
- 创建 `docs/tasks/stage-08-task.md`
- 从 Stage 8 开始正式采用 Architecture-First + Codex-Driven Implementation + Human Verification 工作流
- 明确 Codex 常规实现使用 Luna
- 高推理模型仅用于复杂架构、疑难 Debug 和 Stage Final Review
- 建立真实 LLM Provider Adapter
- 保持 Stage 7 `ModelClient` Contract 不变
- 保持 `AgentOrchestrator` 不变
- 保持 `AgentState` 不变
- 保持现有 Tool System 不变
- 实现 Provider Request Mapping
- 实现 Provider ToolDefinition Mapping
- 实现 Provider FinalAnswer Mapping
- 实现 Provider Function Call Mapping
- 实现 ToolExecution History Mapping
- 实现成功 Tool Observation Mapping
- 实现失败 Tool Observation Mapping
- 支持多个 Sequential ToolExecution 的历史重建
- 保留原始 `call_id`
- 增加 JSON Serialization Fail-Fast
- 保留 Unicode Observation
- 明确拒绝一次 Provider Response 中的多个 Function Calls
- 完成 Provider Offline Tests
- 完成 Provider + AgentOrchestrator Offline Integration Test
- 完成 Tool Failure → Observation → Next Model Decision 测试
- Stage 8 中途将真实 Provider 从 OpenAI 调整为 DeepSeek
- 将 `OpenAIModelClient` 替换为 `DeepSeekModelClient`
- 将 `openai_client.py` 迁移为 `deepseek_client.py`
- 将 Provider tests 同步迁移到 DeepSeek identity
- DeepSeek 继续复用 OpenAI Python SDK 作为兼容客户端
- 配置 DeepSeek API base URL
- 使用 `DEEPSEEK_API_KEY`
- 缺少 API Key 且没有注入 Client 时 fail-fast
- 注入 Fake Client 时不需要真实 API Key
- 每次 DeepSeek request 显式设置 `reasoning={"effort": "none"}`
- 不依赖 `parallel_tool_calls=False` 作为 Sequential guarantee
- Adapter 自己负责检测并拒绝多个 Function Calls
- 完成真实 DeepSeek FinalAnswer Smoke Test
- 完成真实 DeepSeek ToolCall → Tool → Observation → FinalAnswer Smoke Test
- 完成 Codex Stage 8 Final Read-Only Review
- Final Review `MUST FIX = 0`
- 修复 `docs/codex-workflow.md` Markdown fence 格式问题
- Stage 8 最终本地 Full Regression：204 passed，0 warnings

---

### Stage 8 最终 Provider 架构

```text
User Goal
↓
AgentOrchestrator
↓
ModelClient
↓
DeepSeekModelClient
↓
DeepSeek Responses API
↓
Provider Response
├─ ToolCallResponse
│      ↓
│   ToolRegistry
│      ↓
│     Tool
│      ↓
│  ToolResult
│      ↓
│ Observation
│      ↓
│ DeepSeekModelClient
│      ↓
│ DeepSeek Responses API
│      ↓
│ FinalAnswerResponse
│
└─ FinalAnswerResponse
       ↓
    AgentResult
```

---

### Provider Adapter Boundary

Stage 8 最重要的架构边界：

```text
Agent Runtime
        │
        ▼
    ModelClient
        │
        ▼
DeepSeekModelClient
        │
        ▼
DeepSeek API
```

`DeepSeekModelClient` 负责：

```text
Internal Contract
↕
Provider Contract
```

包括：

```text
ModelRequest
→ DeepSeek Request

ToolDefinition
→ Function Tool

DeepSeek Function Call
→ ToolCallResponse

DeepSeek Final Text
→ FinalAnswerResponse
```

它不负责：

```text
Agent Loop
Tool Execution
Repository
Database
FastAPI
Retry
Memory
RAG
```

---

### DeepSeek Provider 配置

最终 Provider：

```text
DeepSeek
```

API：

```text
DeepSeek Responses API
```

Base URL：

```text
https://api.deepseek.com
```

底层 SDK：

```text
OpenAI Python SDK
```

这里：

```text
Provider = DeepSeek
SDK = OpenAI-compatible client
```

两者不是同一个概念。

---

### Model 名称配置

模型名称不写死在：

```text
AgentOrchestrator
ModelClient Contract
Agent Contract
```

而是通过：

```python
DeepSeekModelClient(
    model="..."
)
```

传入。

真实 Smoke Test 使用：

```text
deepseek-v4-flash
```

---

### API Key 处理

真实 API Key 使用：

```text
DEEPSEEK_API_KEY
```

环境变量提供。

原则：

```text
不得硬编码
不得提交 Git
不得写入测试
不得写入 PROJECT_STATE
不得写入 Stage Review
不得输出真实 Secret
```

真实 Client：

```text
DEEPSEEK_API_KEY
↓
OpenAI Python SDK
↓
base_url=https://api.deepseek.com
↓
DeepSeek API
```

如果没有注入 Fake Client，同时：

```text
DEEPSEEK_API_KEY
```

不存在：

```text
Fail Fast
```

---

### Dependency Injection

`DeepSeekModelClient` 支持：

```python
DeepSeekModelClient(
    model="...",
    client=fake_client,
)
```

测试中：

```text
Fake Client
→ 不读取真实 API Key
→ 不访问真实网络
```

生产 / Smoke Test：

```text
没有 injected client
→ 读取 DEEPSEEK_API_KEY
→ 创建真实 SDK Client
```

这使自动化测试保持：

```text
Offline
Deterministic
Repeatable
```

---

### Stateless Provider Mapping

Stage 8 保持：

```text
Stateless Provider Adapter
```

没有引入：

```text
self.history
self.last_response
previous_response_id
Provider Conversation State
Persistent Conversation
```

每次：

```python
generate(ModelRequest)
```

都根据当前 Request 重建 Provider Input。

---

### 第一次 Model Request

如果：

```text
tool_executions == []
```

直接发送：

```text
user_message
```

保持第一次请求最小化。

---

### ToolExecution History Mapping

如果 Tool 已经执行：

```text
ModelRequest.tool_executions
```

Adapter 按顺序重建：

```text
User Message
↓
function_call
↓
function_call_output
```

如果发生多个 Sequential Tool Calls：

```text
User
↓
function_call 1
↓
function_call_output 1
↓
function_call 2
↓
function_call_output 2
```

不会：

```text
只保留最后一个
覆盖历史 Observation
重新生成 call_id
```

---

### Function Call Mapping

Provider Function Call 映射为：

```text
ToolCallResponse
↓
ToolCall
```

保留：

```text
call_id
tool_name
arguments
```

arguments 必须：

```text
JSON parse success
+
最终是 dict / object
```

以下情况明确失败：

```text
invalid JSON
array
string
number
```

---

### Success Observation

Tool 成功：

```text
ToolResult(
    success=True
)
```

Provider Observation 包含：

```json
{
    "success": true,
    "tool_name": "...",
    "data": ...
}
```

必须保留实际：

```text
data
```

不能只告诉模型：

```text
Tool succeeded
```

---

### Failed Observation

Tool 失败：

```text
ToolResult(
    success=False
)
```

Provider Observation 包含：

```json
{
    "success": false,
    "tool_name": "...",
    "error": "..."
}
```

继续保持 Stage 7 原则：

```text
Tool Failure != Agent Failure
```

模型可以根据失败 Observation：

```text
修改参数
↓
再次决策
```

---

### call_id 一致性

完整关联：

```text
Provider Function Call
↓
ToolCall.call_id
↓
ToolResult.call_id
↓
function_call_output.call_id
```

Stage 8 不重新生成 Provider `call_id`。

---

### JSON Serialization

Observation 使用 JSON string 传给 Provider。

使用：

```text
ensure_ascii=False
```

保留中文内容。

如果数据不能 JSON Serialize：

```text
明确失败
```

不会使用：

```text
str(object)
repr(object)
```

强行转换。

---

### Sequential Tool Calling Boundary

Stage 8 继续保持：

```text
Sequential Tool Calling Only
```

支持：

```text
Model
→ Tool A
→ Model
→ Tool B
→ Model
```

但不支持：

```text
一次 Model Response
→ Tool A + Tool B
```

如果 Provider 单次返回多个 Function Calls：

```text
明确失败
```

不会：

```text
只取第一个
忽略其他调用
```

---

### DeepSeek Parallel Tool Call 差异

Provider 切换到 DeepSeek 后确认：

```text
不能依赖 parallel_tool_calls=False
保证 Provider 一定只返回一个 Tool Call。
```

所以删除了对 Provider-side sequential guarantee 的依赖。

真正的保护位于：

```text
DeepSeekModelClient Response Mapping
```

逻辑：

```text
function_call count > 1
↓
明确失败
```

---

### DeepSeek Thinking Mode Boundary

Stage 8 第一版只验证：

```text
non-reasoning Provider Integration
```

每次 DeepSeek Request 显式发送：

```python
reasoning={
    "effort": "none"
}
```

Stage 8 不实现：

```text
reasoning item persistence
reasoning continuity
provider-specific reasoning state
```

未来如果支持 reasoning model：

```text
需要新的 Architecture Decision
```

---

### Provider Response Protection

Stage 8 Provider Adapter 明确处理：

```text
Final text only
→ FinalAnswerResponse

Single function call
→ ToolCallResponse
```

并拒绝：

```text
Invalid JSON Arguments
Non-object Arguments
Multiple Function Calls
Function Call + Final Text
Empty Provider Response
Unsupported Response
```

Provider SDK Exception：

```text
继续传播
```

不会生成虚假的成功回答。

---

### Stage 8 Offline Tests

Provider targeted tests 最终：

```text
20 passed
```

Agent subsystem：

```text
90 passed
```

主要覆盖：

- blank model
- DeepSeek SDK config
- DEEPSEEK_API_KEY
- missing API key
- injected Fake Client
- reasoning effort none
- 不依赖 parallel_tool_calls
- ToolDefinition mapping
- FinalAnswer mapping
- Single ToolCall mapping
- invalid JSON arguments
- non-object JSON arguments
- successful ToolExecution history
- failed ToolExecution history
- multiple sequential ToolExecution history
- JSON serialization failure
- Provider exception
- multiple Function Calls
- mixed Function Call + Final Text
- empty Provider output
- successful offline Agent loop
- failed Tool observation loop

---

### Offline Agent Loop

成功 Observation 流程：

```text
Fake Provider
↓
ToolCallResponse
↓
AgentOrchestrator
↓
Tool
↓
ToolResult(success=True)
↓
function_call_output
↓
Fake Provider
↓
FinalAnswerResponse
↓
AgentResult
```

失败 Observation 流程：

```text
Fake Provider
↓
Invalid Tool Arguments
↓
BaseTool
↓
ToolResult(success=False)
↓
function_call_output
↓
Fake Provider
↓
FinalAnswer
```

两种流程均通过测试。

---

### Real DeepSeek Smoke Test A

第一次真实 Provider 验证：

```text
ModelRequest
↓
DeepSeekModelClient
↓
Real DeepSeek Responses API
↓
FinalAnswerResponse
```

测试要求：

```text
只回复 smoke-ok
```

实际结果：

```text
response_type:
FinalAnswerResponse

answer:
smoke-ok
```

结果：

```text
PASS
```

---

### Real DeepSeek Smoke Test B

Stage 8 最关键的真实验证：

```text
User
↓
Real DeepSeek
↓
ToolCall
↓
AgentOrchestrator
↓
get_smoke_code
↓
ToolResult
↓
Observation
↓
Real DeepSeek
↓
FinalAnswer
↓
AgentResult
```

真实结果：

```text
result_type:
AgentResult

steps:
2

tool_execution_count:
1

tool_name:
get_smoke_code

arguments:
{"request": "stage8d2"}

success:
True

data:
{
    "code": "DEEPSEEK_TOOL_SMOKE_OK",
    "request": "stage8d2"
}

error:
None
```

最终 Answer 包含：

```text
DEEPSEEK_TOOL_SMOKE_OK
```

结果：

```text
PASS
```

这证明真实：

```text
LLM
→ ToolCall
→ Tool
→ Observation
→ LLM
→ FinalAnswer
```

链路完整工作。

---

### Stage 8 测试基线变化

Stage 7 merge 后：

```text
184 passed
1 warning
```

Stage 8 Provider Core：

```text
197 passed
```

Observation Mapping：

```text
202 passed
0 warnings
```

DeepSeek Provider Alignment 后：

```text
204 passed
0 warnings
```

Stage 8 当前最终 Full Regression：

```text
204 passed
0 warnings
```

---

### Warning 变化

Stage 7 唯一 warning：

```text
StarletteDeprecationWarning
```

与：

```text
FastAPI TestClient
Starlette
httpx
```

兼容层有关。

Stage 8 安装 OpenAI Python SDK 时引入：

```text
httpx2
```

之后原 warning 消失。

Stage 8 最终：

```text
0 warnings
```

没有通过修改业务代码隐藏 warning。

---

### Provider 从 OpenAI 切换为 DeepSeek

Stage 8 最初 Provider：

```text
OpenAI
```

完成了：

```text
OpenAI Model Client Core
OpenAI Tool Observation Mapping
```

随后项目需求调整：

```text
OpenAI
↓
DeepSeek
```

由于 Provider Adapter 已经与 Agent Runtime 解耦：

```text
AgentOrchestrator
ModelClient Contract
AgentState
Tool System
Database
FastAPI
```

全部不需要重构。

主要变化集中：

```text
Provider Adapter
Provider Tests
Stage Task Documentation
```

这实际证明：

```text
Provider-Neutral Architecture
```

产生了真实工程价值。

---

### Stage 8 Git Checkpoints

Stage 8 关键提交：

```text
6d5550b docs: add codex workflow and stage 8 plan

54a21b3 feat: add OpenAI model client core

f8ec4b1 feat: add OpenAI tool observation mapping

937630f refactor: switch model provider to DeepSeek

c0c37b9 docs: fix codex workflow markdown fence
```

历史 OpenAI Commit 被保留。

原因：

```text
它们属于真实开发历史
```

不通过 reset / rebase 重写。

---

### Codex 开发流程变化

Stage 8 开始正式明确：

```text
Architecture-First
+
Codex-Driven Implementation
+
Human Verification
```

职责：

```text
ChatGPT / Human
→ Architecture
→ Scope
→ Acceptance Criteria
→ Human Verification

Codex Luna
→ Routine Implementation
→ Tests
→ Repository Analysis

Codex Sol High
→ Complex Architecture
→ Difficult Debug
→ Final Read-Only Review
```

Codex 默认不得自动：

```text
git add
git commit
git push
PR
merge
branch deletion
```

---

### Codex Sandbox 测试权限问题

Stage 8 多次出现：

```text
PermissionError
WinError 5
pytest tmp_path
.pytest_cache
```

表现为：

```text
部分测试 passed
大量 tests error
```

但错误全部来自：

```text
Codex Sandbox Temporary Directory Permissions
```

没有因此修改项目代码。

最终始终使用开发者正常 VS Code PowerShell：

```text
python -m pytest -q
```

重新验证 Repository Reality。

这进一步确认：

```text
Tool Environment Error
!=
Project Regression
```

---

### Stage 8 Final Read-Only Review

最终使用高推理 Codex Model 执行：

```text
READ ONLY
```

代码审查。

最终：

```text
MUST FIX:
无
```

Architecture Verdict：

```text
PASS
```

Final Verdict：

```text
READY FOR STAGE 8 CLOSEOUT
```

唯一 SHOULD FIX：

```text
docs/codex-workflow.md
Markdown code fence 未关闭
```

随后已单独修复并提交。

---

### Stage 8 未实现的能力

Stage 8 明确没有加入：

```text
Agent HTTP API
Retry
Memory
RAG
Vector Database
Streaming
Parallel Tool Execution
Multi-Agent
Persistent Conversation
Agent Trace Persistence
Token Accounting
Cost Accounting
Prompt Management Framework
LangChain
LlamaIndex
AutoGen
CrewAI
```

这些属于未来 Stage。

---

### 本阶段遇到的主要问题

#### 1. Stage 8 最初 Provider 发生变化

最开始计划：

```text
OpenAI
```

中途需求调整为：

```text
DeepSeek
```

处理方式：

```text
不重写 Agent Runtime
只替换 Provider Adapter
```

这反而验证了 Stage 7 Provider abstraction 的价值。

---

#### 2. Responses Tool Observation History

Stage 8B 初版只能处理：

```text
首次 Model Call
```

如果：

```text
Model
→ ToolCall
→ ToolResult
```

第二次 `generate()` 不能忽略 Tool history。

最终 Stage 8C 实现：

```text
ToolExecution
↓
function_call
+
function_call_output
```

完整重建。

---

#### 3. Parallel Tool Calling Boundary

DeepSeek 无法依赖：

```text
parallel_tool_calls=False
```

确保 Sequential。

最终改成：

```text
Provider 可能返回多个 Call
↓
Adapter defensive validation
↓
>1 calls
→ explicit failure
```

---

#### 4. Thinking Mode Compatibility

DeepSeek Responses 默认可能使用 Thinking。

当前 Contract 没有：

```text
Reasoning Continuity
```

所以 Stage 8 明确限制：

```text
reasoning effort = none
```

没有为了支持 reasoning 偷偷增加 Provider-specific State。

---

#### 5. Codex pytest Environment Error

Codex 环境多次出现：

```text
tmp_path PermissionError
```

没有将环境错误误判为项目错误。

最终通过：

```text
Human Local Regression
```

确定：

```text
204 passed
0 warnings
```

---

#### 6. Markdown Fence

Final Review 发现：

```text
docs/codex-workflow.md
```

存在未关闭 fenced code block。

该问题：

```text
不影响 Runtime
不影响 Tests
```

但作为 Stage Closeout 文档质量问题进行了修复。

---

### 本阶段学到的知识

- LLM Provider 不应该直接耦合 Agent Runtime
- `ModelClient` 是 Dependency Inversion 的边界
- Provider Adapter 可以隔离外部 API 变化
- SDK 与 Provider 是两个不同概念
- Dependency Injection 可以让真实 Provider 代码离线测试
- Function Calling 不等于 Tool Execution
- ToolResult 必须作为 Observation 返回模型
- `call_id` 用于关联 Function Call 与 Function Output
- Provider History 可以通过 Stateless Reconstruction 重建
- Tool Failure 不一定意味着 Agent Failure
- Sequential Calls 与 Parallel Calls 是两个不同概念
- 不支持的 Provider Response 应 Explicit Failure，而不是 Silent Truncation
- API Key 应通过环境变量管理
- 自动化测试和真实 API Smoke Test 应严格分离
- Provider Error 不应该伪装成 FinalAnswer
- Repository Reality 必须优先于 Codex Sandbox 报告
- Provider-neutral Architecture 可以降低切换外部模型服务的成本

---

### Stage 8 当前结论

Stage 8 已经证明：

```text
InternScout Agent
```

现有的：

```text
Provider-Neutral Agent Runtime
```

可以：

```text
在不重新设计 AgentOrchestrator、
ModelClient Contract、
AgentState 和 Tool System 的情况下
接入真实 DeepSeek Provider。
```

并真实完成：

```text
User
→ DeepSeek
→ ToolCall
→ Tool
→ Observation
→ DeepSeek
→ FinalAnswer
```

Stage 8 当前功能验收：

```text
Implementation:
PASS

Provider Isolation:
PASS

ModelClient Contract:
PASS

Offline Tests:
PASS

Full Regression:
204 passed
0 warnings

Real FinalAnswer Smoke:
PASS

Real ToolCall Smoke:
PASS

Codex Final Review:
MUST FIX = 0
```

Stage 8 下一步：

```text
Stage Review
+
Development Log
↓
Final Regression
↓
Push Feature Branch
↓
Pull Request
↓
Merge to main
↓
Main Regression
↓
PROJECT_STATE Update
↓
Branch Cleanup
```

## 阶段9：Agent HTTP API 与应用集成

### 本阶段目标

Stage 9 的核心目标是将 Stage 7 已完成的 provider-neutral Agent Runtime、Stage 8 已完成的 DeepSeek Provider Adapter，以及现有 FastAPI、Job Tools、Repository 与 SQLite 数据层正式组合为一个可以通过 HTTP 调用的 Agent Application。

目标链路：

```text
HTTP Client
↓
POST /api/agent/query
↓
FastAPI
↓
AgentOrchestrator
↓
ModelClient
↓
DeepSeekModelClient
↓
DeepSeek Responses API
↓
ToolCall
↓
Job Tool
↓
RepositoryJobQueryAdapter
↓
Repository Functions
↓
SQLite
↓
Observation
↓
DeepSeek
↓
FinalAnswer
↓
HTTP Response
```

Stage 9 不重新设计 Stage 7 / Stage 8 的 Agent Runtime，而是补齐 Application Integration 与 HTTP Boundary。

---

### 本阶段完成

- 创建 `docs/tasks/stage-09-task.md`
- 完成 Stage 9 Architecture Gate
- 新增 FastAPI Agent Application Composition Root
- 新增 `get_model_client`
- 新增 `get_agent_orchestrator`
- 使用 `DEEPSEEK_API_KEY` 与 `DEEPSEEK_MODEL` 作为 server-side Provider 配置
- DeepSeek Provider 采用 lazy application-level reuse
- 保持 SQLAlchemy Session、RepositoryJobQueryAdapter、Job Tools、ToolRegistry 与 AgentOrchestrator request-scoped
- 固定生产 Tool 注册顺序：
  1. `SearchJobsTool`
  2. `GetJobDetailTool`
- 新增 `AgentQueryRequest`
- 新增 `AgentQueryResponse`
- 新增 `POST /api/agent/query`
- HTTP API 保持单次 Request 对应单次独立 Agent Run
- HTTP Response 只暴露 `answer`、`steps` 与 `tool_execution_count`
- 不向客户端暴露 ToolExecution、Observation 或 Provider Raw Response
- 实现 HTTP 422 / 500 / 503 第一版错误边界
- 新增 11 个 Agent HTTP Offline Integration Tests
- 使用 FakeModelClient 隔离真实 Provider
- 保留真实 AgentOrchestrator、ToolRegistry、Job Tools、RepositoryJobQueryAdapter、Repository 与 SQLite 测试路径
- 完成真实 DeepSeek Agent Tool Loop Smoke
- 完成真实 DeepSeek HTTP Agent Smoke
- 在真实 Provider Smoke 中发现并修复 DeepSeek commentary + function_call 兼容问题
- 完成 Stage 9 Codex Final Read-Only Review
- Final Review `MUST FIX = 0`
- Final Verdict：`READY FOR STAGE 9 CLOSEOUT`

---

### Stage 9 主要 Commit

```text
10b602e
docs: add stage 9 task spec

d2eaa9e
feat: add agent application dependencies

b8fcdc5
feat: add agent query API

465d524
test: add agent API integration coverage

b9b7181
fix: support DeepSeek commentary tool calls
```

以上 commit identity 以真实 Git Repository Reality 为准。

Stage 9 最终 merge identity 当前仍为：

```text
UNKNOWN
```

必须等 PR 实际 merge 后再记录。

---

### Agent HTTP Contract

新增接口：

```text
POST /api/agent/query
```

Request：

```json
{
  "user_message": "请查询深圳的实习岗位"
}
```

第一版只允许客户端提供：

```text
user_message
```

不允许客户端控制：

```text
provider
model
api_key
max_steps
reasoning
tools
tool_choice
conversation_id
```

这些继续作为 server-side policy。

Response：

```json
{
  "answer": "...",
  "steps": 2,
  "tool_execution_count": 1
}
```

Stage 9 明确保持：

```text
Internal Agent Trace
!=
Public HTTP Contract
```

因此没有直接暴露：

```text
ToolCall
ToolResult
ToolExecution
Observation
Provider Raw Response
```

---

### Application Composition Root

新增：

```text
app/api/dependencies.py
```

作为 FastAPI Application Composition Root。

生产对象图：

```text
SQLAlchemy Session
↓
RepositoryJobQueryAdapter
↓
SearchJobsTool
GetJobDetailTool
↓
ToolRegistry
↓
AgentOrchestrator
```

`get_agent_orchestrator` 负责在每个 HTTP Request 中构建上述 request-scoped object graph。

两个 Job Tools 共享同一个：

```text
RepositoryJobQueryAdapter
```

因此也共享当前 Request 的 SQLAlchemy Session。

没有任何持有 Session 的 Adapter、Tool、Registry 或 Orchestrator 被全局缓存。

---

### DeepSeek ModelClient Dependency

新增：

```text
get_model_client()
```

Provider 配置：

```text
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
```

两者均来自 server environment。

没有将：

```text
API Key
Model Name
```

暴露为 HTTP Request 参数。

`DeepSeekModelClient` 采用 lazy application-level reuse。

因此：

```text
import app.main
```

不会立即创建真实 Provider Client，也不会要求 DeepSeek API Key。

只有真正调用：

```text
/api/agent/query
```

时才需要 Agent Provider configuration。

这样已有：

```text
/api/health
/api/jobs
/api/crawl
```

和自动化测试不会因为 DeepSeek 配置不存在而失效。

---

### Dependency Lifecycle

Stage 9 明确区分：

```text
Application Scope
```

与：

```text
Request Scope
```

当前：

```text
DeepSeekModelClient
→ lazy application-level reuse
```

因为 Provider Adapter 当前是 stateless。

而：

```text
SQLAlchemy Session
RepositoryJobQueryAdapter
SearchJobsTool
GetJobDetailTool
ToolRegistry
AgentOrchestrator
```

均保持：

```text
request-scoped
```

原因是 RepositoryJobQueryAdapter 持有 SQLAlchemy Session。

如果将整个 Orchestrator 或 ToolRegistry 全局缓存：

```text
Request 结束
↓
Session 关闭
↓
下一 Request 仍复用旧 Adapter
```

可能产生 closed-session lifecycle bug。

---

### HTTP Error Boundary

Stage 9 第一版：

```text
Invalid Request
→ HTTP 422
```

包括：

```text
missing user_message
empty user_message
whitespace-only user_message
unexpected request field
```

Provider server configuration 不可用：

```text
DEEPSEEK_API_KEY missing
DEEPSEEK_MODEL missing
```

返回：

```text
HTTP 503
```

Sanitized response：

```text
Agent model service is unavailable.
```

Unexpected Agent / Model runtime exception：

```text
HTTP 500
```

Sanitized response：

```text
Agent service encountered an unexpected error.
```

当前没有在 FastAPI 层引入 DeepSeek / OpenAI SDK exception 类型。

Provider-specific exception taxonomy 留待后续独立 Architecture Decision。

---

### Tool Failure 与 HTTP Failure

继续保持 Stage 7 语义：

```text
Tool Failure
!=
Agent Failure
!=
HTTP Failure
```

例如 Tool 参数错误：

```text
Tool validation failure
↓
ToolResult(success=False)
↓
Observation
↓
Model receives failure
↓
Model continues
↓
FinalAnswer
↓
HTTP 200
```

Stage 9 Offline Integration Test 已验证该路径。

---

### Offline HTTP Integration Testing

新增：

```text
tests/test_agent_api.py
```

自动化测试只替换：

```text
get_session
get_model_client
```

不会替换：

```text
get_agent_orchestrator
AgentOrchestrator
ToolRegistry
SearchJobsTool
GetJobDetailTool
RepositoryJobQueryAdapter
Repository Functions
```

因此真实测试链路：

```text
HTTP
↓
FastAPI
↓
real AgentOrchestrator
↓
FakeModelClient
↓
real ToolRegistry
↓
real Job Tools
↓
real RepositoryJobQueryAdapter
↓
real Repository
↓
temporary SQLite
↓
Observation
↓
FakeModelClient
↓
FinalAnswer
↓
HTTP
```

---

### Stage 9D 测试问题：422 被 503 覆盖

第一版 Invalid Request Tests 出现：

```text
Expected:
422

Actual:
503
```

原因并不是 HTTP Schema 失效。

测试同时存在：

```text
invalid request
+
missing DeepSeek configuration
```

而测试没有 override：

```text
get_model_client
```

因此 Provider Dependency 先返回 503。

最终对 Validation Test 单独注入 FakeModelClient，并确认：

```text
fake_model.requests == []
```

证明非法 HTTP Request 在模型调用之前已经被拒绝。

专门的 Missing Provider Config Test 则继续使用真实：

```text
get_model_client
```

验证：

```text
valid request
+
missing provider config
→ HTTP 503
```

两个错误场景因此被正确隔离。

---

### max_steps Test Hardening

Agent 默认：

```text
max_steps = 5
```

测试最初只检查：

```text
HTTP 500
```

但 Route 会将不同 runtime exception 都映射为同一个 sanitized 500。

因此存在理论上的 false-positive：

```text
FakeModelClient responses exhausted
→ exception
→ HTTP 500
```

也可能让测试错误通过。

最终增加：

```text
assert len(fake_model.requests) == 5
```

证明：

```text
AgentOrchestrator
```

在第 6 次 Model call 之前由真实 max_steps boundary 停止。

---

### Stage 9E Real DeepSeek Compatibility Issue

Offline Tests 全部通过后，首次真实 DeepSeek HTTP Agent Smoke 返回：

```text
HTTP 500
```

先直接执行最小 Provider Smoke：

```text
DeepSeekModelClient
→ DeepSeek
→ FinalAnswerResponse
```

结果：

```text
PASS
```

因此排除：

```text
API Key
Model Name
基础 Responses API
FinalAnswer Mapping
```

问题继续缩小到真实 Tool Calling。

直接运行真实 Agent Tool Loop 后获得：

```text
ValueError:
DeepSeek response cannot contain both a function call and a final answer.
```

---

### Raw Provider Diagnosis

通过 Raw Provider Response Diagnostic 发现真实 DeepSeek 返回：

```text
ResponseOutputMessage
phase="commentary"
text="我来为您查询数据库中深圳的实习岗位。"
```

以及：

```text
ResponseFunctionToolCall
name="search_jobs"
```

也就是：

```text
commentary message
+
function_call
```

旧版 `DeepSeekModelClient` 直接使用：

```text
response.output_text
```

判断是否存在 FinalAnswer。

因此 commentary text 被错误判断为 FinalAnswer，合法 ToolCall 被拒绝。

---

### DeepSeek Provider Compatibility Fix

修复限定在：

```text
app/agent/providers/deepseek_client.py
tests/agent/providers/test_deepseek_client.py
```

没有修改：

```text
AgentOrchestrator
ModelClient Contract
Tool System
FastAPI
Database
```

新的 Provider mapping：

```text
function_call only
→ ToolCallResponse
```

```text
phase="commentary"
+
function_call
→ ToolCallResponse
```

```text
phase="final_answer"
+
function_call
→ ValueError
```

```text
unsupported / blank / missing phase
+
function_call
→ ValueError
```

同时继续拒绝：

```text
multiple function calls
invalid JSON arguments
non-object arguments
empty provider output
```

这次真实问题最终只需要修改 Provider Adapter，证明 Stage 7 / Stage 8 的 Provider Boundary 设计有效。

---

### Real DeepSeek Agent Tool Loop

修复后再次运行真实 Agent：

```text
SUCCESS
```

结果：

```text
steps:
2

tool_execution_count:
1

tool_name:
search_jobs

tool_success:
True

tool_error:
None
```

最终回答来自当前 SQLite 中真实岗位数据。

真实闭环：

```text
DeepSeek
↓
commentary
↓
ToolCall
↓
SearchJobsTool
↓
SQLite
↓
Observation
↓
DeepSeek
↓
FinalAnswer
```

验证通过。

---

### Real HTTP Agent Smoke

随后启动 FastAPI，并执行：

```text
POST /api/agent/query
```

最终返回：

```text
answer:
non-empty

steps:
2

tool_execution_count:
1
```

回答包含当前数据库中的深圳岗位，例如：

```text
Python后端实习生
DevOps实习生
```

因此完整生产链路已经验证：

```text
HTTP Client
↓
FastAPI
↓
AgentOrchestrator
↓
Real DeepSeek
↓
ToolCall
↓
SQLite Query
↓
Observation
↓
Real DeepSeek
↓
FinalAnswer
↓
HTTP Response
```

---

### 自动化测试

Stage 9 开始前：

```text
204 passed
0 warnings
```

Stage 9 Final Review：

```text
Provider targeted:
24 passed

Agent subsystem:
94 passed

Full project:
219 passed

Warnings:
0
```

因此 Stage 9 新增后：

```text
204
↓
219
```

新增：

```text
15 automated tests
```

同时完成：

```text
Real DeepSeek Agent Tool Loop
PASS

Real HTTP Agent Smoke
PASS
```

真实 Provider verification 与 pytest 保持分离。

---

### Codex Sandbox Environment

Stage 9 中 Codex Sandbox 再次出现 pytest：

```text
PermissionError
```

错误发生在：

```text
temporary directory
pytest cache
```

而不是业务 assertion。

Human local `.venv`：

```text
219 passed
0 warnings
```

作为 authoritative result。

---

### Stage 9 Final Codex Review

Final Review 使用 High Reasoning Model。

Repository Reality：

```text
Branch:
feat/stage-09-agent-http-api

Working tree:
clean
```

Final Review：

```text
MUST FIX = 0
```

Architecture Compliance：

```text
HTTP contract:
PASS

Composition root:
PASS

Dependency lifecycle:
PASS

Provider-neutral Agent Runtime:
PASS

Tool / database boundary:
PASS

AgentState per-run:
PASS

Sequential Tool Calling:
PASS

Provider isolation:
PASS

Provider commentary compatibility:
PASS

Offline test isolation:
PASS

Secret safety:
PASS

Stage 9 scope control:
PASS
```

Final Verdict：

```text
READY FOR STAGE 9 CLOSEOUT
```

---

### Final Review SHOULD FIX

Final Review 发现一个非阻塞建议：

```text
补充 legacy mixed response branch 的独立 regression test
```

当前 Production behavior 已经正确保留：

```text
non-message output_text
+
function_call
→ reject
```

但该 branch 当前缺少独立测试覆盖。

Review 将其分类为：

```text
SHOULD FIX
```

不是：

```text
MUST FIX
```

Stage 9 当前不为这个非阻塞测试建议扩大 closeout scope。

---

### 本阶段学到的知识

- FastAPI `Depends` 可以作为 Application Composition 的基础
- Composition Root 应集中负责 concrete implementation wiring
- request-scoped object 不能因为方便而随意全局缓存
- stateless Provider Client 可以与 request-scoped Agent Runtime 使用不同生命周期
- FastAPI `dependency_overrides` 可以只替换 Provider Boundary，同时保留真实应用集成路径
- HTTP Validation 与 Dependency Resolution 可能同时影响最终状态码
- 测试必须隔离当前真正想验证的行为
- 仅检查 HTTP status 可能产生 false-positive
- Offline Fake Tests 无法完全代替 Real Provider Smoke
- Provider Adapter 不只是 SDK wrapper，而是 External Contract 与 Internal Contract 的转换层
- Provider response mapping 应采用 defensive parsing
- Provider 特殊行为应该被限制在 Adapter，而不是泄漏到 Agent Runtime

---

### 当前 Stage 9 状态

```text
Implementation:
COMPLETE

Automated Tests:
219 passed

Warnings:
0

Real DeepSeek Tool Loop:
PASS

Real HTTP Agent Smoke:
PASS

Final Review:
MUST FIX = 0

Final Verdict:
READY FOR STAGE 9 CLOSEOUT
```

尚需完成：

```text
Stage 9 Review / Development Log commit
push feature branch
create PR
merge
post-merge main regression
PROJECT_STATE update
branch cleanup
```

Stage 9 最终 Merge Identity：

```text
UNKNOWN
```

必须等真实 PR merge 后确定。