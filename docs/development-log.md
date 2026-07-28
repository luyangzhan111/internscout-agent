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