# InternScout Agent — Codex Development Workflow

> 本文件定义 InternScout Agent 从 Stage 8 开始使用 Codex 参与项目开发的长期工作规范。
>
> 目标：
>
> - 提高 Codex 在实际代码实现中的参与程度
> - 降低重复手工编码成本
> - 保持项目架构由开发者掌控
> - 保证 Codex 修改可测试、可审查、可回滚
> - 避免 AI Coding Agent 擅自扩大 Stage 范围
> - 保证开发者能够解释最终进入项目的关键代码
>
> 本文件是长期开发规范，不记录某一个 Stage 的具体任务。
>
> 每个 Stage 的实际 Codex 任务写入：
>
> ```text
> docs/tasks/stage-XX-task.md
> ```

---

# 1. Development Model

从 Stage 8 开始，InternScout Agent 采用：

```text
Architecture-First
+
Codex-Driven Implementation
+
Human Verification