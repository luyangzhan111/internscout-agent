# 阶段5复习：SQLite数据库与岗位持久化

## 目录

- [1. 阶段目标](#1-阶段目标)
- [2. 完成内容](#2-完成内容)
- [3. 完整数据链路](#3-完整数据链路)
- [4. 核心模块](#4-核心模块)
- [5. 核心知识点](#5-核心知识点)
- [6. 岗位重复保护](#6-岗位重复保护)
- [7. 数据库事务](#7-数据库事务)
- [8. 自动化测试](#8-自动化测试)
- [9. Codex审查](#9-codex审查)
- [10. 遇到的问题](#10-遇到的问题)
- [11. 面试可能提问](#11-面试可能提问)
- [12. 当前不足](#12-当前不足)
- [13. 阶段验收](#13-阶段验收)

---

## 1. 阶段目标

阶段5的目标是将经过爬虫采集、数据清洗和去重后的岗位保存到SQLite数据库，使岗位数据在程序关闭后仍然存在。

阶段4结束时，岗位数据只保存在Python列表中：

```text
程序运行
→ 岗位列表存在

程序关闭
→ 岗位列表消失
```

阶段5完成后：

```text
程序运行
→ 岗位写入SQLite

程序关闭
→ 数据库文件仍然存在

程序再次启动
→ 可以继续查询原有岗位
```

---

## 2. 完成内容

本阶段完成：

- 引入SQLAlchemy 2.x
- 使用SQLite数据库
- 创建JobModel ORM模型
- 创建jobs岗位表
- 定义字段类型和数据库约束
- 使用JSON保存技能列表
- 使用identity_key唯一约束防止重复写入
- 创建Engine
- 创建Session工厂
- 创建数据库初始化函数
- 实现Repository仓库层
- 实现单条岗位保存
- 实现批量岗位保存
- 实现岗位查询
- 实现重复岗位返回已有记录
- 实现IntegrityError回滚和恢复
- 创建岗位采集入库工作流
- 完成完整链路集成测试
- 完成Codex只读代码审查
- 全项目59个测试通过

---

## 3. 完整数据链路

```text
sample_jobs.html
        ↓
MockJobCrawler
        ↓
list[JobCreate]
        ↓
process_jobs
        ↓
城市标准化
技能标准化
技能去重
岗位去重
        ↓
ingest_jobs
        ↓
save_jobs
        ↓
JobModel
        ↓
SQLite jobs表
```

统一调用入口：

```python
from app.crawlers import MockJobCrawler
from app.database import SessionLocal
from app.workflows import ingest_jobs

with SessionLocal() as session:
    saved_jobs = ingest_jobs(
        MockJobCrawler(),
        session,
    )
```

---

## 4. 核心模块

### 4.1 `models.py`

职责：

```text
描述数据库表结构
```

主要模型：

```python
class JobModel(Base):
    __tablename__ = "jobs"
```

主要字段：

| 字段 | 作用 |
|---|---|
| id | 数据库自增主键 |
| identity_key | 岗位业务身份 |
| title | 岗位名称 |
| company | 公司名称 |
| city | 标准化城市 |
| salary | 薪资，可为空 |
| description | 岗位描述 |
| skills | JSON技能列表 |
| source | 数据来源 |
| source_url | 来源链接 |
| published_at | 发布日期 |
| created_at | 数据库创建时间 |

### 4.2 `session.py`

职责：

- 创建Engine
- 创建Session工厂
- 初始化数据库表
- 提供数据库Session

### 4.3 `repository.py`

职责：

- 将JobCreate转换为JobModel
- 生成identity_key
- 保存单条岗位
- 保存多条岗位
- 查询全部岗位
- 处理重复写入

### 4.4 `job_ingestion.py`

职责：

```text
编排爬虫、数据处理和数据库持久化
```

工作流函数：

```python
ingest_jobs(crawler, session)
```

---

## 5. 核心知识点

### 5.1 SQLite是什么

SQLite是嵌入式关系型数据库。

特点：

- 不需要额外启动数据库服务器
- 数据保存在单个文件中
- Python原生支持
- 适合本地开发、小型项目和自动化测试

本项目数据库文件：

```text
internscout.db
```

该文件属于本地运行数据，通过`.gitignore`忽略，不提交到GitHub。

### 5.2 SQLAlchemy是什么

SQLAlchemy是Python数据库工具库。

本项目主要使用它的ORM能力：

```text
Python对象
↔
数据库表记录
```

例如：

```python
JobModel(
    title="Python后端实习生",
    company="星河科技",
)
```

可以转换为jobs表中的一行数据。

### 5.3 `JobCreate`和`JobModel`的区别

`JobCreate`是Pydantic模型：

- 验证外部输入
- 用于爬虫和业务层
- 保证岗位字段合法

`JobModel`是SQLAlchemy模型：

- 描述数据库表
- 用于保存和查询
- 维护数据库约束

处理关系：

```text
JobCreate
→ job_model_from_schema
→ JobModel
→ SQLite
```

### 5.4 Engine是什么

Engine是Python程序访问数据库的入口。

它负责：

- 管理数据库连接
- 识别数据库类型
- 将SQLAlchemy操作发送给SQLite
- 管理连接池

### 5.5 Session是什么

Session表示一次数据库工作会话。

它负责：

- 添加ORM对象
- 查询数据库
- 提交事务
- 回滚事务
- 跟踪ORM对象状态

### 5.6 Session工厂是什么

`SessionLocal`不是一个具体Session，而是创建Session的工厂：

```python
with SessionLocal() as session:
    ...
```

每次调用都会创建一个新的数据库会话。

### 5.7 `create_all()`的作用

```python
Base.metadata.create_all(bind=engine)
```

它读取所有继承自Base的ORM模型，并创建尚不存在的数据库表。

它可以重复调用，但不能自动完成数据库字段迁移。

后续修改已有表结构时，需要使用Alembic。

### 5.8 为什么skills使用JSON

Python中的技能是：

```python
["Python", "FastAPI", "SQL"]
```

使用JSON可以保留列表结构。

如果保存为普通字符串：

```text
Python,FastAPI,SQL
```

后续还需要自行拆分，并且技能名称中出现分隔符时可能造成歧义。

### 5.9 为什么需要identity_key

数据库自增主键`id`只能表示某一条数据库记录，不能判断两个岗位是否是同一个业务岗位。

因此项目增加：

```text
identity_key
```

它由以下信息构成：

```text
标准化公司名称
+
标准化岗位名称
+
标准化城市
```

例如：

```json
["星河科技","python后端实习生","深圳"]
```

### 5.10 为什么使用JSON字符串保存身份

岗位身份最初是元组：

```python
(
    "星河科技",
    "python后端实习生",
    "深圳",
)
```

数据库字段需要字符串，因此使用稳定的JSON序列化：

```python
json.dumps(
    identity,
    ensure_ascii=False,
    separators=(",", ":"),
)
```

相比使用`|`拼接，JSON不会因为公司或岗位名称本身含有分隔符而产生歧义。

---

## 6. 岗位重复保护

当前项目具有三层重复保护。

### 第一层：业务处理去重

```python
process_jobs()
```

删除同一次爬虫结果中的重复岗位。

### 第二层：保存前查询

```python
get_job_by_identity_key()
```

保存岗位前先检查数据库是否已经存在。

存在时直接返回原记录。

### 第三层：数据库唯一约束

```python
identity_key unique=True
```

处理并发情况下的竞争窗口：

```text
请求A查询：不存在
请求B查询：不存在
请求A插入成功
请求B插入冲突
```

数据库唯一约束会拒绝第二次写入。

---

## 7. 数据库事务

### 7.1 commit

```python
session.commit()
```

作用：

```text
将当前事务正式保存到数据库
```

### 7.2 rollback

```python
session.rollback()
```

作用：

```text
撤销当前失败事务
恢复Session可用状态
```

发生数据库提交错误后必须回滚，否则Session会处于失败状态。

### 7.3 refresh

```python
session.refresh(database_job)
```

作用：

```text
从数据库重新加载记录
```

提交后可以获得：

- 自动生成的id
- 数据库生成的created_at
- 其他服务端默认值

### 7.4 当前事务契约

当前`save_job()`会直接：

```python
session.commit()
```

因此调用方应使用专用Session，不应混入无关的未提交数据。

`save_jobs()`逐条调用`save_job()`，因此是逐条提交：

```text
第一条成功
→ 已提交

第二条失败
→ 第二条回滚
→ 第一条仍然存在
```

这表示当前批量操作允许部分成功，不是原子事务。

对于当前6条模拟岗位，该方案简单且可以接受。

---

## 8. 自动化测试

阶段5新增测试包括：

### ORM模型测试

- jobs表注册成功
- 表名正确
- 字段完整
- nullable约束正确
- identity_key唯一
- skills使用JSON

### 数据库连接测试

- 默认数据库URL正确
- Engine使用指定URL
- 初始化创建jobs表
- 初始化函数可重复执行
- Session工厂配置正确

### Repository测试

- identity_key标准化
- 保存全部岗位字段
- 可选字段可以保存NULL
- 重复岗位返回已有记录
- 批量保存保持首次顺序
- 查询结果按主键排序
- 数据库唯一约束有效
- 无匹配记录的IntegrityError重新抛出
- 回滚后Session仍可继续使用

### 工作流测试

- MockJobCrawler岗位清洗后保存
- 重复执行采集不会增加数据库数量
- 空爬虫结果安全处理
- 重复岗位保留第一条数据

最终结果：

```text
59 passed
```

---

## 9. Codex审查

Codex审查结论：

```text
必须修改：无
```

主要建议：

- 明确Repository事务边界
- 明确Repository只接收已清洗数据
- 后续重新评估identity_key长度
- 固定IntegrityError重新抛出契约
- 后续通过配置注入数据库路径
- 测试失败时也应可靠释放Engine

本阶段已经完成：

- 补充事务契约文档
- 补充清洗输入契约
- 增加IntegrityError重新抛出测试
- 验证rollback后Session仍然可用

暂未进行大型事务架构重构。

---

## 10. 遇到的问题

### 10.1 虚拟环境显示激活但Python路径错误

现象：

```text
ModuleNotFoundError: No module named 'pydantic'
```

终端显示`(.venv)`，但实际Python路径指向全局解释器。

解决：

```powershell
python -c "import sys; print(sys.executable)"
```

必须确认输出：

```text
项目目录\.venv\Scripts\python.exe
```

学到：

> 终端提示符不是最终依据，sys.executable才是实际解释器路径。

### 10.2 Git提示LF将转换为CRLF

现象：

```text
warning: LF will be replaced by CRLF
```

解决：

- 创建`.gitattributes`
- 仓库文本文件统一使用LF
- 设置仓库级`core.autocrlf=false`
- 使用UTF-8和LF重新写入requirements.txt

### 10.3 ORM模型无法导入

现象：

```text
cannot import name 'Base'
```

原因：

`models.py`没有正确保存或缺少类定义。

解决：

- 检查实际文件内容
- 单独测试模块导入
- 再运行pytest

### 10.4 Codex沙箱无法使用tmp_path

Codex沙箱中的部分数据库测试在临时目录初始化阶段失败。

这不是业务断言失败，而是沙箱对Windows临时目录的权限限制。

在沙箱外运行：

```text
58 passed
```

修复后本机最终达到：

```text
59 passed
```

---

## 11. 面试可能提问

### 1. 为什么项目选择SQLite？

参考回答：

> SQLite不需要额外部署数据库服务器，数据保存在单个文件中，适合项目第一版、本地开发和自动化测试。后续部署规模扩大时可以切换到PostgreSQL。

### 2. ORM解决什么问题？

参考回答：

> ORM将Python类和数据库表建立映射，使业务代码可以通过对象保存和查询数据，同时集中管理字段类型和约束。

### 3. Pydantic模型和ORM模型有什么区别？

参考回答：

> Pydantic模型主要负责输入验证和业务数据传递，ORM模型负责描述数据库表和执行持久化。项目通过转换函数将JobCreate变成JobModel。

### 4. 为什么数据库中还需要唯一约束？

参考回答：

> 应用层保存前查询不能完全解决并发竞争。两个请求可能同时查询到不存在，然后都尝试插入。数据库唯一约束是最后一道一致性保护。

### 5. 为什么IntegrityError后必须rollback？

参考回答：

> SQLAlchemy事务提交失败后，Session会处于失败状态。只有rollback后才能恢复并继续查询或执行新的数据库操作。

### 6. 为什么重复保存返回已有岗位？

参考回答：

> 这样可以让保存操作具备幂等性。调用方重复执行相同任务时，不会创建重复记录，同时仍能得到对应的数据库对象。

### 7. 当前save_jobs是原子事务吗？

参考回答：

> 不是。当前采用逐条提交，因此中途失败时之前成功的岗位仍然保留。这适合目前的小批量数据，但后续可以由工作流统一控制事务，实现批量原子提交。

### 8. 为什么identity_key不用URL？

参考回答：

> 同一个岗位可能在不同招聘网站拥有不同URL。如果使用URL，无法跨来源识别重复岗位，因此使用公司、岗位名称和标准化城市构建身份。

### 9. 为什么使用Repository层？

参考回答：

> Repository集中封装数据库保存和查询，避免爬虫、API和业务代码直接操作Session，使数据库逻辑更容易测试、维护和替换。

### 10. ingest_jobs有什么作用？

参考回答：

> ingest_jobs是业务编排层，负责调用爬虫获取岗位、执行清洗和去重，然后保存到数据库。调用方只需要使用一个统一入口。

### 11. 如何验证重复采集不会重复入库？

参考回答：

> 自动化测试连续两次执行同一个MockJobCrawler入库工作流，确认两次返回相同数据库ID，并且数据库总记录数仍然为6。

### 12. 你如何使用Codex？

参考回答：

> 我让Codex进行只读代码审查，重点检查事务边界、重复写入、资源释放和测试覆盖。Codex不直接修改代码，我根据审查结果判断哪些问题当前修复，哪些记录为技术债，并补充回归测试。

---

## 12. 当前不足

- SQLite路径依赖当前工作目录
- 默认Engine在模块导入时创建
- 批量保存采用逐条提交
- identity_key使用可变长度JSON字符串
- 尚未引入Alembic
- 尚未实现分页查询
- 尚未实现城市、公司和技能筛选
- 尚未通过FastAPI暴露数据库岗位接口
- 尚未支持异步数据库
- 尚未支持生产环境数据库配置

---

## 13. 阶段验收

### 功能验收

- [x] 安装SQLAlchemy
- [x] 配置SQLite
- [x] 创建JobModel
- [x] 创建jobs表
- [x] 创建Engine和Session
- [x] 初始化数据库表
- [x] 保存单条岗位
- [x] 保存多条岗位
- [x] 查询岗位
- [x] 防止重复写入
- [x] 处理IntegrityError
- [x] 实现完整入库工作流
- [x] 正式数据库手动验证
- [x] 数据库文件被Git忽略

### 测试验收

- [x] ORM字段测试
- [x] 数据库约束测试
- [x] Engine测试
- [x] Session测试
- [x] 初始化测试
- [x] 保存测试
- [x] 可选字段测试
- [x] 重复写入测试
- [x] 唯一约束测试
- [x] IntegrityError重新抛出测试
- [x] 批量保存测试
- [x] 工作流幂等测试
- [x] 空输入测试
- [x] 完整集成测试
- [x] 全项目59个测试通过

### 工程验收

- [x] 使用独立功能分支
- [x] Codex只读审查
- [x] 必须修改项为无
- [x] 补充关键回归测试
- [x] `.gitattributes`统一LF
- [x] `git diff --check`无错误
- [ ] 完成Git提交
- [ ] 推送功能分支
- [ ] 创建Pull Request
- [ ] 合并到main
- [ ] 删除功能分支