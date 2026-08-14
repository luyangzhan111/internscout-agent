# InternScout Agent — Project State

> 本文件是 InternScout Agent 当前状态的唯一项目快照（Project Snapshot）。
>
> 它不是开发日志，也不记录完整 Debug 过程。
>
> 本文件只维护当前仍然有效的：
>
> - 项目能力
> - 系统架构
> - 技术决策
> - 测试状态
> - 已知问题
> - 下一阶段目标
> - 长期开发规范
>
> 每完成一个主要 Stage 后更新一次。

---

# 1. Project Overview

## 项目名称

InternScout Agent

## 项目定位

InternScout Agent 是一个面向软件工程、AI 与 Agent 实习岗位的信息采集、处理、存储、查询，并逐步扩展智能分析能力的练习型软件工程项目。

项目采用阶段式开发方式，从基础 FastAPI 服务开始，逐步实现：

- 岗位数据模型
- 招聘信息爬取
- 数据清洗
- 数据标准化
- 岗位去重
- 数据库存储
- 查询 Repository
- REST API
- 筛选与分页
- HTTP 服务闭环
- 自动化测试
- Agent Contract
- Tool System
- Model Client Abstraction
- Tool-Calling Agent Runtime
- Agent Orchestrator
- Tool / Repository 架构解耦

项目同时承担以下学习目标：

- Python 工程实践
- FastAPI
- Pydantic
- Web Crawling
- BeautifulSoup
- SQLAlchemy
- SQLite
- Repository Pattern
- Port / Adapter Pattern
- pytest
- Unit Testing
- Integration Testing
- Git / GitHub / Pull Request Workflow
- Codex Code Review
- Agent Development
- Tool Calling
- 软件工程面试准备
- AI / Agent 岗位项目积累

---

# 2. Core Technology Stack

当前主要技术栈：

- Python 3.12
- FastAPI
- Pydantic
- BeautifulSoup
- SQLAlchemy 2.x
- SQLite
- pytest
- Git
- GitHub
- Codex
- VS Code

开发环境：

- Windows
- PowerShell
- Python Virtual Environment (`.venv`)

---

# 3. Current Version Identity

## 当前主分支

```text
main