# InternScout Agent 阶段1复习文档

> 阶段名称：项目初始化与第一个 FastAPI 接口  
> 项目：InternScout Agent  
> 目标：完成正式项目环境、FastAPI 服务、自动化测试和第一次 Git 提交

---

## 目录

- [1. 阶段1完成内容](#1-阶段1完成内容)
- [2. Python虚拟环境](#2-python虚拟环境)
- [3. 项目目录结构](#3-项目目录结构)
- [4. FastAPI基础](#4-fastapi基础)
- [5. Uvicorn基础](#5-uvicorn基础)
- [6. HTTP接口基础](#6-http接口基础)
- [7. 自动化测试与Pytest](#7-自动化测试与pytest)
- [8. Git基础](#8-git基础)
- [9. gitignore与requirements](#9-gitignore与requirements)
- [10. 本阶段遇到的问题](#10-本阶段遇到的问题)
- [11. 面试常见问题](#11-面试常见问题)
- [12. 一分钟阶段介绍](#12-一分钟阶段介绍)
- [13. 自测题](#13-自测题)
- [14. 阶段1验收清单](#14-阶段1验收清单)

---

## 1. 阶段1完成内容

本阶段完成了以下内容：

- 创建正式项目目录 `internscout-agent`
- 使用 Python 3.12.4 创建独立虚拟环境
- 在 VS Code 中选择项目自己的 `.venv` 解释器
- 初始化 Git 仓库，并将默认分支设置为 `main`
- 安装 FastAPI、Uvicorn、Pytest 和 HTTPX
- 创建基础项目目录结构
- 编写根路径 `/`
- 编写健康检查接口 `/api/health`
- 使用 Uvicorn 启动 FastAPI 应用
- 使用 Swagger 文档查看接口
- 编写两个接口自动化测试
- 运行 Pytest，得到 `2 passed`
- 配置 `.gitignore`
- 生成 `requirements.txt`
- 编写 README 和开发日志
- 完成第一次 Git 提交

第一次提交示例：

```text
ae67b0d chore: initialize project and add health API
```

---

## 2. Python虚拟环境

### 2.1 什么是虚拟环境

虚拟环境是一个项目专属的 Python 运行环境。

本项目使用：

```text
D:\AI-Project\internscout-agent\.venv
```

虚拟环境中包含：

- 独立的 Python 解释器
- 独立的 pip
- 独立安装的第三方库

### 2.2 为什么每个项目要使用独立虚拟环境

不同项目可能依赖不同版本的第三方库。

例如：

```text
项目A需要 FastAPI 0.x
项目B需要 FastAPI 1.x
```

如果所有项目共用全局 Python，一个项目升级依赖后，可能导致另一个项目无法运行。

虚拟环境可以：

- 隔离不同项目的依赖
- 避免全局环境被污染
- 让项目更容易复现
- 降低版本冲突风险

### 2.3 创建与激活

创建：

```powershell
& "D:\python3.12.4\python.exe" -m venv .venv
```

激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

激活成功后，终端前面会出现：

```text
(.venv)
```

检查解释器：

```powershell
python -c "import sys; print(sys.executable)"
```

正确结果应指向：

```text
D:\AI-Project\internscout-agent\.venv\Scripts\python.exe
```

### 2.4 退出虚拟环境

```powershell
deactivate
```

---

## 3. 项目目录结构

当前项目结构：

```text
internscout-agent/
├── app/
│   ├── __init__.py
│   └── main.py
├── docs/
│   └── development-log.md
├── tests/
│   └── test_health.py
├── .gitignore
├── README.md
└── requirements.txt
```

### 3.1 各文件作用

#### `app/`

保存正式业务代码。

#### `app/__init__.py`

让 Python 将 `app` 识别为一个包。

#### `app/main.py`

FastAPI 应用入口，目前保存：

- FastAPI 应用对象
- 根路径接口
- 健康检查接口

#### `tests/`

保存自动化测试代码。

#### `tests/test_health.py`

测试根路径和健康检查接口。

#### `docs/`

保存项目文档和开发记录。

#### `.gitignore`

告诉 Git 哪些文件不应该进入版本库。

#### `README.md`

项目首页说明，包括：

- 项目介绍
- 技术栈
- 启动方式
- 测试方式

#### `requirements.txt`

记录项目所需的 Python 第三方依赖。

---

## 4. FastAPI基础

### 4.1 FastAPI是什么

FastAPI 是一个 Python Web 后端框架，用于开发 HTTP API。

在本项目中，FastAPI 负责：

- 定义接口路径
- 接收请求
- 调用对应函数
- 处理参数
- 返回 JSON
- 自动生成 Swagger 接口文档

### 4.2 创建应用对象

```python
from fastapi import FastAPI

app = FastAPI(
    title="InternScout Agent",
    description="实习岗位采集与智能匹配助手",
    version="0.1.0",
)
```

这里的 `app` 是整个 FastAPI 应用对象。

后续所有接口都会注册到这个对象上。

### 4.3 定义接口

```python
@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
```

`@app.get("/api/health")` 是路由装饰器。

它表示：

> 当客户端使用 GET 请求访问 `/api/health` 时，执行下面的 `health_check` 函数。

### 4.4 为什么字典会变成JSON

Python 函数返回：

```python
{"status": "ok"}
```

FastAPI会将这个 Python 字典序列化为 JSON 响应：

```json
{
  "status": "ok"
}
```

这个过程由 FastAPI 和底层响应组件自动完成。

### 4.5 自动生成接口文档

启动服务后访问：

```text
http://127.0.0.1:8000/docs
```

FastAPI会自动生成 Swagger UI。

Swagger可以用于：

- 查看所有接口
- 查看参数
- 查看返回结果
- 直接发送测试请求
- 演示项目功能

---

## 5. Uvicorn基础

### 5.1 Uvicorn是什么

Uvicorn 是一个 ASGI Web 服务器。

FastAPI负责定义应用和接口，但它本身不会主动监听网络端口。

Uvicorn负责：

- 监听地址和端口
- 接收HTTP请求
- 将请求交给FastAPI
- 将FastAPI返回结果发送给浏览器
- 保持服务持续运行

### 5.2 FastAPI和Uvicorn的关系

可以简单理解为：

```text
浏览器
  ↓ HTTP请求
Uvicorn
  ↓
FastAPI接口
  ↓
Python函数返回结果
  ↓
Uvicorn
  ↓ HTTP响应
浏览器
```

一句话：

> FastAPI负责“应用逻辑”，Uvicorn负责“运行应用并接收网络请求”。

### 5.3 启动命令

```powershell
python -m uvicorn app.main:app --reload
```

`app.main:app` 的含义：

```text
app.main:app
│   │    │
│   │    └── main.py中的FastAPI对象变量名
│   └────── main.py模块
└────────── app目录 / Python包
```

即：

> 进入 `app` 包，找到 `main.py`，再找到其中名为 `app` 的对象。

### 5.4 `--reload` 的作用

开发时修改代码后，Uvicorn会自动重启服务。

适合本地开发，但生产环境通常不会这样使用。

### 5.5 为什么终端停在 Application startup complete

出现：

```text
Application startup complete.
```

说明服务器已经启动成功，正在等待请求。

这不是卡死。

此时：

- 浏览器可以访问接口
- 当前终端被服务器进程占用
- 按 `Ctrl + C` 可以停止服务器
- 也可以新建另一个终端执行其他命令

---

## 6. HTTP接口基础

### 6.1 什么是接口

接口可以理解为：

> 前端、浏览器或其他程序与后端通信的入口。

例如：

```text
GET /api/health
```

### 6.2 GET请求

GET通常用于获取数据。

本项目的接口：

```text
GET /
GET /api/health
```

### 6.3 HTTP状态码200

测试中：

```python
assert response.status_code == 200
```

`200 OK` 表示请求成功。

### 6.4 404是什么意思

`404 Not Found` 表示访问的路径不存在。

浏览器自动请求：

```text
/favicon.ico
```

而项目中没有配置网站图标，因此它返回404。

这不影响业务接口。

### 6.5 健康检查接口的用途

访问：

```text
GET /api/health
```

返回：

```json
{"status": "ok"}
```

它可以用于：

- 人工检查服务是否运行
- 自动化测试
- Docker健康检查
- 部署平台监控
- 后续检查数据库连接状态

目前只检查应用是否正常响应，后续可以扩展为：

```json
{
  "status": "ok",
  "database": "connected",
  "version": "0.1.0"
}
```

---

## 7. 自动化测试与Pytest

### 7.1 Pytest是什么

Pytest是Python自动化测试框架。

本项目运行命令：

```powershell
python -m pytest -v
```

当前结果：

```text
2 passed, 1 warning
```

表示：

- 收集到2个测试
- 两个测试都通过
- 有一个第三方依赖警告
- 没有测试失败

### 7.2 TestClient是什么

```python
from fastapi.testclient import TestClient

client = TestClient(app)
```

`TestClient` 可以在测试中模拟客户端请求FastAPI接口。

它不需要真正启动Uvicorn，也可以发送：

```python
client.get("/")
client.get("/api/health")
```

### 7.3 测试状态码

```python
assert response.status_code == 200
```

用于验证接口是否成功返回。

### 7.4 测试响应内容

```python
assert response.json() == {"status": "ok"}
```

用于验证接口返回内容是否符合预期。

### 7.5 手动测试与自动化测试的区别

#### 手动测试

通过浏览器访问接口。

优点：

- 直观
- 适合查看页面和Swagger
- 方便临时调试

缺点：

- 需要重复点击
- 容易漏测
- 无法快速检查大量功能
- 难以自动执行

#### 自动化测试

通过Pytest自动发送请求并检查结果。

优点：

- 可重复运行
- 速度快
- 结果明确
- 适合回归测试
- 可以接入GitHub Actions

两者应该配合使用。

### 7.6 什么是回归测试

修改或增加功能后，重新运行已有测试，确认旧功能没有被破坏。

例如以后增加数据库功能后，仍然运行：

```powershell
python -m pytest -v
```

确认根接口和健康检查仍然通过。

### 7.7 当前警告如何处理

当前出现的是第三方库内部弃用警告。

它不影响：

```text
2 passed
```

现阶段记录即可，不需要为了消除警告随意修改依赖版本。

---

## 8. Git基础

### 8.1 Git是什么

Git是版本控制工具。

它用于：

- 保存代码历史
- 查看修改
- 回退版本
- 管理分支
- 与GitHub协作

### 8.2 Git与GitHub的区别

Git：

- 本地版本控制工具
- 可以不联网使用

GitHub：

- 远程代码托管平台
- 用于备份、展示和协作

### 8.3 初始化仓库

```powershell
git init
```

会在项目中创建隐藏的：

```text
.git
```

它保存Git仓库的版本信息。

### 8.4 Git三个区域

```text
工作区
正在编辑的文件
   ↓ git add
暂存区
准备进入本次提交的文件
   ↓ git commit
版本历史
正式保存的版本
```

### 8.5 `git status`

```powershell
git status
```

用于查看：

- 当前分支
- 未跟踪文件
- 已修改文件
- 已暂存文件
- 工作区是否干净

### 8.6 `git add`

```powershell
git add .
```

含义：

> 将当前目录下未被 `.gitignore` 排除的修改加入暂存区。

`git add` 还没有形成正式版本。

### 8.7 `git commit`

```powershell
git commit -m "chore: initialize project and add health API"
```

含义：

> 将暂存区内容保存为一个正式版本。

### 8.8 `git log --oneline`

```powershell
git log --oneline
```

用于查看简化的提交记录。

当前提交：

```text
ae67b0d chore: initialize project and add health API
```

### 8.9 常见提交前流程

```powershell
git status
git add .
git status
git commit -m "提交说明"
git log --oneline
git status
```

---

## 9. gitignore与requirements

### 9.1 `.gitignore`的作用

`.gitignore`用于告诉Git忽略哪些文件。

本项目忽略：

- `.venv`
- `__pycache__`
- `.pytest_cache`
- `.env`
- 数据库文件
- 编辑器缓存
- 系统文件

### 9.2 为什么不能上传`.venv`

`.venv`：

- 文件很多
- 占用空间大
- 与当前操作系统有关
- 可能包含本机路径
- 可以根据依赖文件重新创建

所以只上传：

```text
requirements.txt
```

### 9.3 `requirements.txt`是什么

它记录项目依赖及版本。

生成：

```powershell
python -m pip freeze > requirements.txt
```

安装：

```powershell
python -m pip install -r requirements.txt
```

可以理解为：

```text
requirements.txt = 配料清单
.venv = 根据配料清单创建的环境
```

---

## 10. 本阶段遇到的问题

### 10.1 Python默认版本是3.10

原因：

- Windows PATH优先找到旧Python
- 电脑中同时安装多个Python版本

解决：

- 不急于删除Python 3.10
- 使用Python 3.12.4完整路径创建虚拟环境
- 项目运行时使用`.venv`

### 10.2 PowerShell禁止激活脚本

错误原因：

- PowerShell执行策略限制了`Activate.ps1`

解决：

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

最终策略：

```text
CurrentUser RemoteSigned
```

### 10.3 VS Code找不到Python解释器命令

原因：

- 项目处于受限模式
- Python扩展未在当前工作区完全启用

解决：

- 信任项目文件夹
- 确认Microsoft Python扩展已启用
- 手动选择项目`.venv`解释器

### 10.4 `/favicon.ico`返回404

原因：

- 浏览器自动请求标签页图标
- 项目尚未配置图标

结论：

- 不影响业务接口
- 可以暂时忽略

### 10.5 Uvicorn看起来一直不动

原因：

- 服务器已经启动
- 正在等待HTTP请求

解决：

- 浏览器访问接口
- 或按`Ctrl + C`停止服务器

### 10.6 Pytest出现警告

原因：

- FastAPI/Starlette第三方依赖内部存在弃用提醒

结论：

- 测试仍然是`2 passed`
- 现阶段记录，不随意降级依赖

---

## 11. 面试常见问题

### 11.1 为什么使用虚拟环境

参考回答：

> 不同Python项目可能依赖不同版本的第三方库。虚拟环境可以为每个项目提供独立的解释器和依赖目录，避免版本冲突和全局环境污染，也方便其他人根据requirements文件复现环境。

### 11.2 FastAPI和Uvicorn有什么区别

参考回答：

> FastAPI是Web框架，负责定义接口、参数校验、业务逻辑和响应；Uvicorn是ASGI服务器，负责监听网络端口、接收HTTP请求，并将请求交给FastAPI处理。

### 11.3 `app.main:app`是什么意思

参考回答：

> 第一个app是Python包目录，main是main.py模块，最后一个app是main.py中创建的FastAPI应用对象。Uvicorn通过这个路径找到并运行应用。

### 11.4 为什么需要健康检查接口

参考回答：

> 健康检查接口用于确认后端服务是否能够正常响应。它可以供开发人员、自动化测试、Docker、部署平台和监控系统使用。后续还可以扩展为数据库连接等依赖检查。

### 11.5 为什么要写自动化测试

参考回答：

> 手工测试适合临时检查，但难以重复和批量执行。自动化测试可以稳定验证状态码和响应内容，修改代码后可以快速进行回归测试，也能接入持续集成。

### 11.6 TestClient是否真的启动了服务器

参考回答：

> FastAPI的TestClient可以直接调用ASGI应用，不需要真正启动Uvicorn监听端口，因此测试运行速度更快，也更容易隔离环境。

### 11.7 为什么不能上传`.venv`

参考回答：

> `.venv`体积大、包含本机和操作系统相关文件，而且可以通过requirements重新生成。上传它会增加仓库体积，也不利于跨平台复现。

### 11.8 `git add`和`git commit`区别

参考回答：

> `git add`将工作区中的修改加入暂存区，用于选择本次要提交的内容；`git commit`把暂存区内容保存为一个正式版本记录。

### 11.9 Git和GitHub有什么区别

参考回答：

> Git是本地版本控制工具，GitHub是远程代码托管和协作平台。即使不连接GitHub，也可以在本地使用Git管理代码版本。

### 11.10 为什么用`python -m pip`

参考回答：

> 当电脑中存在多个Python版本时，直接执行pip可能调用错误的pip。`python -m pip`可以确保使用当前Python解释器对应的pip。

### 11.11 200和404状态码分别是什么

参考回答：

> 200表示请求成功；404表示请求路径或资源不存在。本项目中的favicon.ico返回404是因为没有配置图标，不影响业务接口。

### 11.12 为什么README重要

参考回答：

> README帮助别人快速理解项目目标、技术栈、安装方式、运行方式和测试方法。对于个人项目，它也是招聘人员审查项目的重要入口。

### 11.13 为什么需要`.gitignore`

参考回答：

> `.gitignore`避免虚拟环境、缓存、密钥、数据库等不应进入仓库的文件被误提交，从而减少仓库体积并降低敏感信息泄露风险。

### 11.14 `--reload`适合生产环境吗

参考回答：

> 不适合。`--reload`主要用于本地开发，它会监控文件变化并重启进程，会增加额外开销。生产环境通常采用更稳定的进程和部署配置。

### 11.15 项目当前有什么不足

参考回答：

> 当前只完成了应用骨架、健康接口和基础测试，还没有岗位数据模型、数据库、爬虫和Agent功能。健康检查也只验证应用响应，没有检查数据库等外部依赖。后续阶段会逐步补齐。

---

## 12. 一分钟阶段介绍

> 在项目第一阶段，我使用Python 3.12创建了独立虚拟环境，并搭建了InternScout Agent的FastAPI项目骨架。我实现了根路径和健康检查接口，使用Uvicorn启动服务，并通过FastAPI自动生成的Swagger文档进行手工验证。同时，我使用Pytest和TestClient编写了两个接口测试，验证状态码和JSON响应，测试结果为2个用例全部通过。此外，我配置了requirements.txt、.gitignore、README和开发日志，并完成了第一次Git提交。通过这一阶段，我掌握了虚拟环境、FastAPI与Uvicorn的分工、基础HTTP接口、自动化测试和Git版本控制流程。

---

## 13. 自测题

请先不看答案，尝试自己回答。

1. 虚拟环境解决了什么问题？
2. 为什么不直接使用全局Python安装所有依赖？
3. `app.main:app`三部分分别指什么？
4. FastAPI和Uvicorn各自负责什么？
5. 为什么Uvicorn启动后终端不会返回提示符？
6. `/api/health`有什么用途？
7. 为什么Python字典可以作为接口返回值？
8. TestClient如何测试接口？
9. 手工测试和自动化测试有什么区别？
10. 什么是回归测试？
11. `git add`和`git commit`有什么区别？
12. 为什么`.venv`不能上传？
13. `requirements.txt`有什么作用？
14. 为什么推荐使用`python -m pip`？
15. 当前项目还有哪些不足？

---

## 14. 阶段1验收清单

- [x] 创建正式项目目录
- [x] 创建Python 3.12虚拟环境
- [x] VS Code选择正确`.venv`
- [x] 初始化Git仓库
- [x] 安装FastAPI、Uvicorn、Pytest和HTTPX
- [x] 创建项目基础目录
- [x] 完成根路径接口
- [x] 完成健康检查接口
- [x] Uvicorn服务正常启动
- [x] Swagger文档可以访问
- [x] 两个Pytest测试通过
- [x] 配置`.gitignore`
- [x] 生成`requirements.txt`
- [x] 编写README
- [x] 编写开发日志
- [x] 完成第一次Git提交

---

## 阶段1结论

阶段1已经建立了项目最基本的工程基础：

```text
独立环境
+ 清晰目录
+ 可运行API
+ 自动化测试
+ Git版本记录
+ 项目文档
```

下一阶段将开始实现：

- 岗位数据模型
- 模拟招聘页面
- 第一个岗位爬虫解析器
- 爬虫解析测试
