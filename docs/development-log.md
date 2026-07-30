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