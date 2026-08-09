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
- 端到端测试
- 后续 Agent 能力

项目同时承担以下学习目标：

- Python 工程实践
- FastAPI
- Pydantic
- Web Crawling
- BeautifulSoup
- SQLAlchemy
- SQLite
- Repository Pattern
- pytest
- Integration Testing
- Git / GitHub / Pull Request Workflow
- Codex Code Review
- Agent Development
- 软件工程面试准备
- 实习简历项目积累

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

# 3. Current Stage

## 已完成阶段

Stage 0 ～ Stage 6

## 当前状态

Stage 6：

**已完成并合并至 main。**

Stage 6 最终完成：

- 岗位列表 API
- 岗位详情 API
- 多条件筛选
- 分页
- 查询 Repository
- Response Schema
- API 参数校验
- 极端分页边界处理
- FastAPI 生命周期数据库初始化
- API 集成测试
- Stage 6 端到端流程测试
- 重复抓取幂等性验证

## 下一阶段

Stage 7

Stage 7 将开始在现有数据采集、处理、数据库和 API 基础设施之上进一步构建 Agent 能力。

---

# 4. Implemented Capabilities

## 4.1 FastAPI Application

已经建立 FastAPI 应用。

目前主要 HTTP API 包括：

```text
GET /api/health
GET /api/jobs
GET /api/jobs/{job_id}