# InternScout Agent 阶段二复习总结

> 文件名称：`stage-02-review.md`  
> 对应阶段：岗位数据模型、模拟招聘数据、自动化测试、Git 分支与 Pull Request、Codex 代码审查  
> 复习目的：回顾阶段二的技术知识、工程流程、常见问题和面试表达

---

## 目录

- [1. 阶段二完成了什么](#1-阶段二完成了什么)
- [2. 本阶段项目结构变化](#2-本阶段项目结构变化)
- [3. 核心知识点一：Pydantic 数据模型](#3-核心知识点一pydantic-数据模型)
- [4. 核心知识点二：岗位字段设计](#4-核心知识点二岗位字段设计)
- [5. 核心知识点三：模拟招聘 HTML](#5-核心知识点三模拟招聘-html)
- [6. 核心知识点四：自动化测试](#6-核心知识点四自动化测试)
- [7. 核心知识点五：Git 功能分支与 Pull Request](#7-核心知识点五git-功能分支与-pull-request)
- [8. 核心知识点六：Codex 辅助代码审查](#8-核心知识点六codex-辅助代码审查)
- [9. 本阶段遇到的实际问题](#9-本阶段遇到的实际问题)
- [10. 阶段二完整数据流](#10-阶段二完整数据流)
- [11. 面试中可能被问的问题](#11-面试中可能被问的问题)
- [12. 推荐面试回答](#12-推荐面试回答)
- [13. 容易答错的地方](#13-容易答错的地方)
- [14. 阶段二自测清单](#14-阶段二自测清单)
- [15. 阶段二成果如何写入简历](#15-阶段二成果如何写入简历)
- [16. 进入阶段三前需要记住什么](#16-进入阶段三前需要记住什么)

---

# 1. 阶段二完成了什么

阶段二的主要目标不是直接爬取真实招聘网站，而是先解决两个基础问题：

1. 系统中的一条“岗位数据”应该长什么样；
2. 后续爬虫应该从什么样的网页结构中提取数据。

本阶段完成了：

- 创建 `JobCreate` 岗位数据模型；
- 使用 Pydantic 对岗位字段进行类型和规则验证；
- 创建岗位模型测试；
- 创建包含 6 条岗位的模拟招聘 HTML；
- 在模拟 HTML 中加入“缺少薪资字段”的边界样例；
- 使用 Git 功能分支开发阶段二；
- 将功能分支推送到 GitHub；
- 创建并合并 Pull Request；
- 使用 Codex 对阶段二代码进行只读审查；
- 处理 Codex 旧中转站配置和连接问题；
- 将阶段二代码合并回 `main`。

阶段二解决的核心问题可以概括为：

> 在真正编写爬虫前，先统一数据格式，并准备稳定、可重复测试的网页样本。

---

# 2. 本阶段项目结构变化

阶段二主要增加了以下目录和文件：

```text
internscout-agent/
├── app/
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── job.py
│   └── fixtures/
│       └── sample_jobs.html
├── tests/
│   └── test_job_schema.py
├── stage-reviews/
│   ├── stage-01-review.md
│   └── stage-02-review.md
└── docs/
    └── development-log.md
```

各文件职责：

| 文件 | 作用 |
|---|---|
| `app/schemas/job.py` | 定义岗位数据的数据结构和验证规则 |
| `app/schemas/__init__.py` | 统一导出数据模型 |
| `app/fixtures/sample_jobs.html` | 提供稳定的模拟招聘网页 |
| `tests/test_job_schema.py` | 验证岗位模型的正常、边界和异常情况 |
| `docs/development-log.md` | 记录开发过程、问题和解决方法 |
| `stage-reviews/stage-02-review.md` | 阶段二复习文档 |

---

# 3. 核心知识点一：Pydantic 数据模型

## 3.1 什么是数据模型

数据模型用于定义：

- 一条数据有哪些字段；
- 每个字段是什么类型；
- 哪些字段必须提供；
- 哪些字段可以为空；
- 输入不合法时如何处理。

例如一条岗位数据可能包含：

```python
{
    "title": "Python 后端实习生",
    "company": "星河科技",
    "city": "深圳市",
    "salary": "150-200元/天",
    "description": "负责 FastAPI 接口开发",
    "skills": ["Python", "FastAPI", "SQL"],
    "source": "mock",
    "source_url": "https://example.com/jobs/001",
    "published_at": "2026-07-20"
}
```

如果没有统一模型，不同爬虫可能返回完全不同的数据：

```python
{"job_name": "Python实习"}
```

```python
{"title": "Python实习", "location": "深圳"}
```

```python
{"position": "Python实习", "city_name": "深圳"}
```

这样后续数据库、API 和 Agent 很难统一处理。

因此，`JobCreate` 的作用是：

> 把不同来源的岗位数据统一转换成系统内部认可的标准格式。

---

## 3.2 `BaseModel`

```python
class JobCreate(BaseModel):
```

表示 `JobCreate` 继承自 Pydantic 的 `BaseModel`。

它可以：

- 验证字段；
- 检查类型；
- 转换部分输入；
- 输出字典；
- 输出 JSON；
- 生成 FastAPI 接口文档需要的 Schema。

普通 Python 类主要用于封装对象和行为，而 Pydantic 模型更强调：

> 外部输入数据的校验和标准化。

---

## 3.3 `Field`

例如：

```python
title: str = Field(
    min_length=1,
    max_length=100,
    description="岗位名称",
)
```

含义：

- `title` 必须是字符串；
- 长度至少为 1；
- 长度不能超过 100；
- `description` 可以用于接口文档说明。

如果输入：

```python
title=""
```

或者：

```python
title="   "
```

在启用字符串首尾空格清理后，都会变成空字符串，因此验证失败。

---

## 3.4 必填字段与可选字段

必填字段：

```python
title: str
company: str
city: str
description: str
source: str
source_url: str
```

创建 `JobCreate` 时必须提供。

可选字段：

```python
salary: str | None = None
published_at: date | None = None
```

表示：

- 可以是指定类型；
- 也可以是 `None`；
- 未提供时默认是 `None`。

之所以把薪资设置为可选字段，是因为真实招聘页面中，有些岗位不会公开薪资。

---

## 3.5 `str | None`

```python
salary: str | None = None
```

表示：

```text
salary 可以是字符串，也可以是 None。
```

例如：

```python
salary="150-200元/天"
```

合法。

```python
salary=None
```

也合法。

但是需要注意：

```python
salary=""
```

当前模型可能仍会接受，因为没有设置 `min_length=1`。

这意味着：

- `None` 可以表示“页面没有薪资字段”；
- `""` 可能表示“页面存在字段，但内容为空”。

后续数据清洗阶段应考虑把空字符串统一转换为 `None`。

---

## 3.6 `default_factory=list`

```python
skills: list[str] = Field(default_factory=list)
```

表示如果没有提供技能列表，则自动生成：

```python
[]
```

使用 `default_factory=list` 的原因是：

> 每个模型对象都需要拥有独立的列表，避免多个对象共享同一个可变默认值。

这比直接写：

```python
skills: list[str] = []
```

更加安全、规范。

---

## 3.7 日期自动转换

```python
published_at: date | None = None
```

输入：

```python
published_at="2026-07-20"
```

Pydantic 可以将字符串转换成：

```python
date(2026, 7, 20)
```

如果日期格式非法，例如：

```python
published_at="2026-99-99"
```

模型会抛出 `ValidationError`。

---

## 3.8 自动清理首尾空格

```python
model_config = ConfigDict(str_strip_whitespace=True)
```

输入：

```python
title="  Python 后端实习生  "
```

模型中最终保存为：

```python
"Python 后端实习生"
```

但这个配置只能处理首尾空格，不能完成：

```text
深圳市 → 深圳
python → Python
```

这些属于后续数据清洗模块的工作。

---

# 4. 核心知识点二：岗位字段设计

阶段二定义的主要字段包括：

| 字段 | 类型 | 必填 | 含义 |
|---|---|---:|---|
| `title` | `str` | 是 | 岗位名称 |
| `company` | `str` | 是 | 公司名称 |
| `city` | `str` | 是 | 工作城市 |
| `salary` | `str \| None` | 否 | 薪资描述 |
| `description` | `str` | 是 | 岗位职责和要求 |
| `skills` | `list[str]` | 否 | 技能列表 |
| `source` | `str` | 是 | 数据来源 |
| `source_url` | `str` | 是 | 原始岗位链接 |
| `published_at` | `date \| None` | 否 | 发布时间 |

## 4.1 为什么 `source` 不写在 HTML 中

模拟 HTML 中没有：

```html
<span class="source">mock</span>
```

这是合理的。

因为 `source` 表示：

> 这条数据是由哪个采集器获取的。

它属于采集器上下文，而不是网页中必须展示的字段。

下一阶段爬虫解析时，可以主动加入：

```python
source="mock"
```

---

## 4.2 为什么保留 `source_url`

`source_url` 用于：

- 回到原始岗位页面；
- 数据溯源；
- 检查数据是否过期；
- 后续判断重复岗位；
- API 返回原始链接。

Codex 审查中指出，当前 `source_url` 只是普通字符串，没有验证是否是真实 URL。

这是一个可优化点，但不是阶段二的阻塞问题。

后续可以考虑：

```python
from pydantic import HttpUrl
```

然后改为：

```python
source_url: HttpUrl
```

但要注意，`HttpUrl` 的输出类型和序列化方式可能影响测试和数据库设计，因此应在真正需要时再修改。

---

## 4.3 为什么没有把 `data-job-id` 放入模型

HTML 中包含：

```html
<article class="job-card" data-job-id="job-001">
```

这个字段主要用于：

- HTML 节点定位；
- 调试；
- 标识模拟页面中的岗位；
- 检查是否重复。

当前业务模型没有 `job_id` 字段，是因为后续数据库会生成自己的主键。

如果后续需要保留原网页 ID，可以增加：

```python
external_id: str | None = None
```

但阶段二暂时不需要。

---

# 5. 核心知识点三：模拟招聘 HTML

## 5.1 为什么不直接爬真实网站

真实网站存在很多不稳定因素：

- 网页结构随时变化；
- 可能需要登录；
- 可能有验证码；
- 可能有访问限制；
- 网络请求可能失败；
- 自动化测试无法稳定复现；
- 不适合频繁请求。

因此先创建本地 HTML，可以保证：

- 页面结构固定；
- 测试结果稳定；
- 不依赖网络；
- 可以主动设计边界情况；
- 可以重复运行；
- 不涉及绕过网站限制。

---

## 5.2 岗位卡片结构

每条岗位使用：

```html
<article class="job-card">
```

内部包含：

```html
<h2 class="job-title">
<p class="company">
<span class="city">
<span class="salary">
<time class="published-at">
<p class="description">
<ul class="skills">
<a class="source-url">
```

下一阶段 BeautifulSoup 会根据这些 class 查找内容。

例如：

```python
card.select_one(".job-title")
```

用于寻找岗位标题。

---

## 5.3 为什么故意缺少薪资字段

某条岗位故意不包含：

```html
<span class="salary">...</span>
```

这是为了测试真实情况：

> 爬虫不能假设网页的每一个字段永远存在。

如果解析器直接写：

```python
salary = card.select_one(".salary").get_text()
```

当 `.salary` 不存在时，会出现：

```text
AttributeError
```

正确思路应是：

```python
salary_element = card.select_one(".salary")
salary = salary_element.get_text(strip=True) if salary_element else None
```

这就是边界数据设计的价值。

---

## 5.4 Fixture 是什么

`fixture` 可以理解为：

> 为开发和测试提前准备的固定输入数据。

本项目中的：

```text
app/fixtures/sample_jobs.html
```

就是爬虫测试使用的固定网页样本。

注意，`fixture` 在 Pytest 中还有另一个含义：

> 用于准备测试环境、测试数据和清理工作的函数。

两者名称相同，但具体语境不同。

---

# 6. 核心知识点四：自动化测试

阶段二增加了 `test_job_schema.py`，主要验证数据模型。

## 6.1 合法岗位可以创建

测试内容包括：

- 标题正确；
- 公司正确；
- 技能列表正确；
- 日期字符串能够转换为 `date`。

目标是确认：

> 正常输入不会被模型错误拒绝。

---

## 6.2 自动清理空格

测试输入：

```python
title="  Python后端实习生  "
```

期望：

```python
job.title == "Python后端实习生"
```

目标是确认配置：

```python
str_strip_whitespace=True
```

真正生效。

---

## 6.3 允许缺少薪资

测试：

```python
salary=None
```

期望：

```python
job.salary is None
```

需要理解：这个测试验证的是模型允许 `None`，还没有真正验证：

> HTML 中缺少 salary 标签时，解析器能否自动得到 None。

后者会在阶段三的爬虫集成测试中完成。

---

## 6.4 拒绝空标题

使用：

```python
with pytest.raises(ValidationError):
```

表示预期下面的代码应该抛出验证异常。

这是在测试：

> 非法输入是否被正确拒绝。

自动化测试不仅要测试成功路径，还要测试失败路径。

---

## 6.5 测试分层

目前主要是模型单元测试。

后续会逐步增加：

### 单元测试

测试单个模块：

- 模型；
- 解析函数；
- 清洗函数；
- 匹配算法。

### 集成测试

测试多个模块配合：

```text
HTML → 爬虫解析 → JobCreate
```

### API 测试

测试：

```text
HTTP 请求 → FastAPI 路由 → 返回结果
```

---

# 7. 核心知识点五：Git 功能分支与 Pull Request

## 7.1 为什么不直接在 `main` 开发

`main` 用于保存稳定版本。

新功能在：

```text
feat/job-schema-fixtures
```

分支开发。

优点：

- 新代码不会直接影响稳定版本；
- 出问题时容易回退；
- 可以单独审查；
- 更接近真实团队流程；
- GitHub 能清楚展示开发过程。

---

## 7.2 创建功能分支

```powershell
git switch -c feat/job-schema-fixtures
```

含义：

- 创建新分支；
- 同时切换到新分支。

---

## 7.3 `git add`、`commit`、`push` 的区别

### `git add`

```powershell
git add app/schemas/job.py
```

把修改放入暂存区。

### `git commit`

```powershell
git commit -m "feat: add job data schema"
```

在本地创建一个版本记录。

### `git push`

```powershell
git push -u origin feat/job-schema-fixtures
```

把本地提交上传到 GitHub。

三者不是同一件事：

```text
工作区 → git add → 暂存区 → git commit → 本地仓库 → git push → GitHub
```

---

## 7.4 Pull Request 是什么

Pull Request 表示：

> 请求把功能分支中的代码合并到主分支。

本阶段的方向是：

```text
base: main
compare: feat/job-schema-fixtures
```

意思是：

```text
将 feat/job-schema-fixtures 的修改合并到 main。
```

---

## 7.5 为什么后来无法再次创建 PR

Git 历史中已经出现：

```text
Merge pull request #1 from luyangzhan111/feat/job-schema-fixtures
```

说明 PR 已经成功合并。

之后：

- 功能分支已经被合并；
- 远程功能分支被删除；
- `main` 已包含阶段二修改。

所以 GitHub 显示：

```text
There isn't anything to compare.
```

这是正常情况，不是失败。

---

## 7.6 为什么查询已删除分支会报错

执行：

```powershell
git log --oneline origin/main..origin/feat/job-schema-fixtures
```

但远程分支已经删除，所以会出现：

```text
unknown revision
```

这只是因为目标分支不存在，并不表示代码丢失。

---

# 8. 核心知识点六：Codex 辅助代码审查

## 8.1 Codex 在本阶段的作用

Codex 用于：

- 读取仓库；
- 理解已有代码；
- 检查模型与 HTML 是否一致；
- 发现潜在边界问题；
- 给出下一阶段建议。

本次没有让 Codex 直接修改代码，而是采用：

```text
只读审查
```

这是初次使用代码 Agent 时比较安全的方式。

---

## 8.2 为什么要限制 Codex 范围

提示词中明确限制：

- 只读取指定文件；
- 不修改文件；
- 不安装依赖；
- 不访问网络；
- 不执行 Git 提交；
- 不自动修复。

这样可以防止：

- 改动范围失控；
- 修改自己不理解的代码；
- 自动提交错误代码；
- 引入额外依赖；
- 破坏稳定分支。

---

## 8.3 Codex 提出的主要问题

Codex 发现：

- `source` 是必填字段，但 HTML 不提供；
- 缺少薪资测试只是传入 `salary=None`；
- `source_url` 没有 URL 类型验证；
- `salary` 可能允许空字符串；
- `skills` 可能包含重复值或空白项；
- 测试未覆盖所有必填字段；
- 测试未覆盖非法日期；
- 尚未完成 HTML 到 `JobCreate` 的完整解析测试；
- `data-job-id` 没有进入模型。

这些建议不是全部需要立刻修改。

正确做法是按阶段判断：

| 问题 | 当前处理 |
|---|---|
| HTML 没有 source | 下一阶段解析器注入 `source="mock"` |
| HTML 缺少 salary | 下一阶段解析为 `None` |
| URL 类型验证 | 后续评估 |
| 空薪资字符串 | 数据清洗阶段处理 |
| 技能重复和空白 | 数据清洗阶段处理 |
| HTML 到模型解析测试 | 阶段三完成 |
| data-job-id | 暂不进入模型 |

---

## 8.4 Codex 旧中转站配置问题

Codex 初次运行时出现旧地址：

```text
muyuan.do
```

原因是：

> 退出登录只会清除认证状态，不会清除 `config.toml` 中的自定义请求地址。

处理过程包括：

- 检查用户级 `~/.codex/config.toml`；
- 删除旧中转站地址；
- 检查环境变量；
- 检查项目级配置；
- 重启 VS Code；
- 重新登录 Codex；
- 使用最小提示词测试连接。

最终旧地址不再出现。

这个问题说明：

> 认证配置和请求地址配置是两套不同的东西。

---

## 8.5 Codex 超时问题

清理旧地址后出现：

```text
Falling back from WebSockets to HTTPS transport. request timed out
```

重试后恢复正常。

说明可能是：

- 临时网络波动；
- WebSocket 连接失败；
- HTTPS 回退请求超时；
- 代理、防火墙或网络链路不稳定。

处理时应先重试，再根据频率判断是否需要进一步检查网络。

---

# 9. 本阶段遇到的实际问题

## 9.1 `app/__init__.py` 有未提交修改

`git status` 显示：

```text
modified: app/__init__.py
```

处理原则：

1. 先执行 `git diff`；
2. 判断是否为有效修改；
3. 有效则提交；
4. 无效则 `git restore`。

不能看到未提交文件就盲目 `git add .`。

---

## 9.2 PR 页面没有操作空间

GitHub 显示：

```text
There isn't anything to compare.
```

排查后发现 PR 已经合并。

关键证据：

```text
Merge pull request #1
```

结论：

> 不是 PR 创建失败，而是之前已经完成合并。

---

## 9.3 删除远程分支后查询报错

`git fetch origin --prune` 显示远程功能分支已删除。

因此继续查询：

```text
origin/feat/job-schema-fixtures
```

会报错。

这是正常的分支清理结果。

---

## 9.4 Codex 使用旧中转站

根因：

```text
config.toml 中仍保留旧 base URL。
```

经验：

- `logout` 不等于清空配置；
- 不能只检查登录状态；
- 自定义 URL 需要单独清理；
- 不应把 API Key 或认证文件发给他人。

---

# 10. 阶段二完整数据流

当前阶段的数据关系：

```text
模拟招聘页面
sample_jobs.html
        ↓
定义网页字段结构
title/company/city/salary/description/skills/url/date
        ↓
JobCreate 数据模型
        ↓
Pydantic 类型和规则验证
        ↓
自动化测试验证模型行为
```

阶段三会把流程补完整：

```text
sample_jobs.html
        ↓
BeautifulSoup 读取和解析
        ↓
提取岗位字段
        ↓
注入 source="mock"
        ↓
创建 JobCreate
        ↓
返回 list[JobCreate]
```

---

# 11. 面试中可能被问的问题

## 数据模型

1. 为什么要使用 Pydantic？
2. Pydantic 模型和普通 Python 类有什么区别？
3. `BaseModel` 有什么作用？
4. `Field` 有什么作用？
5. 必填字段和可选字段有什么区别？
6. `str | None = None` 表示什么？
7. 为什么 `skills` 使用 `default_factory=list`？
8. 为什么要限制字符串长度？
9. Pydantic 验证失败会发生什么？
10. 为什么使用 `date` 而不是普通字符串？

## HTML 和爬虫准备

11. 为什么先使用模拟 HTML？
12. 为什么不直接爬 BOSS 直聘等网站？
13. 为什么故意设计缺少薪资字段的岗位？
14. HTML 中的 class 有什么作用？
15. `article.job-card` 的意义是什么？
16. 模拟页面和真实网页各自有什么用途？
17. `source` 为什么不直接写进 HTML？
18. `data-job-id` 为什么暂时不放进模型？

## 测试

19. 当前测试覆盖了哪些场景？
20. 为什么既测试合法输入，也测试非法输入？
21. `pytest.raises` 有什么作用？
22. 为什么 `salary=None` 还不能完全代表 HTML 缺少 salary 标签？
23. 单元测试和集成测试有什么区别？
24. 下一阶段需要补什么测试？

## Git

25. 为什么要创建功能分支？
26. `git add`、`commit`、`push` 有什么区别？
27. Pull Request 是什么？
28. `base` 和 `compare` 分别是什么？
29. 为什么 PR 合并后可以删除功能分支？
30. 为什么 GitHub 显示没有内容可比较？
31. 如何确认一条 PR 已经合并？
32. `git status` 为什么很重要？
33. `git diff` 用于做什么？

## Codex

34. 你为什么使用 Codex？
35. Codex 在项目中做了什么？
36. 为什么只让 Codex 进行只读审查？
37. 如何防止 Codex 修改不相关文件？
38. Codex 给出的建议是否全部采用？
39. 如何验证 Codex 没有修改文件？
40. Codex 与 ChatGPT 的分工是什么？
41. 为什么不让 Codex 自动提交 Git？
42. 你遇到的中转站配置问题是怎么解决的？

---

# 12. 推荐面试回答

## 12.1 为什么使用 Pydantic？

可以回答：

> 项目需要从不同招聘页面获取岗位数据，不同来源的字段名称和完整程度可能不同。我使用 Pydantic 定义统一的 `JobCreate` 模型，对字段类型、必填项、长度和日期进行验证。这样后续爬虫、数据库和 API 都只需要处理统一格式的数据，能够减少脏数据在系统内部传播。

---

## 12.2 为什么先做模拟 HTML？

可以回答：

> 真实招聘网站的页面结构和访问状态不稳定，自动化测试如果依赖实时网页，很容易因为网络、登录或者页面变化而失败。因此我先制作固定的模拟 HTML，主动覆盖字段完整和缺少薪资等场景，使爬虫测试可以离线、稳定和重复运行。之后再接入真实公开数据源。

---

## 12.3 为什么薪资允许为空？

可以回答：

> 一些岗位不会公开薪资，因此薪资不能设计成绝对必填。我使用 `str | None = None` 表示薪资可以是字符串，也可以缺失。后续解析器遇到没有薪资标签的岗位时，会统一输出 `None`，而不是让整个采集任务失败。

---

## 12.4 为什么使用功能分支？

可以回答：

> 我把 `main` 作为稳定分支，阶段二在 `feat/job-schema-fixtures` 上开发。完成模型、测试和模拟页面后，再通过 Pull Request 审查并合并。这样可以隔离新功能、保留清晰提交记录，也更接近团队开发流程。

---

## 12.5 Codex 在项目中做了什么？

可以回答：

> 我没有让 Codex 直接包办功能，而是限制它只读检查岗位模型、测试和模拟 HTML。它帮助我发现了 source 需要由解析器注入、缺少薪资的测试还没有覆盖 HTML 解析路径、技能去重应该放到后续清洗阶段等问题。最终是否修改由我根据当前阶段决定，并通过 `git status`、`git diff` 和 Pytest 验证。

---

## 12.6 Codex 的建议为什么没有全部立即采用？

可以回答：

> 代码审查建议需要结合项目阶段和职责边界判断。例如 URL 类型验证和技能去重是合理建议，但不属于当前阶段的阻塞问题。当前阶段重点是建立统一模型和稳定测试样本，技能标准化会在数据清洗阶段完成，HTML 到模型的解析会在下一阶段完成。这样能够控制范围，避免过度设计。

---

# 13. 容易答错的地方

## 错误一：Pydantic 可以自动完成所有数据清洗

不正确。

Pydantic 当前主要负责：

- 类型验证；
- 必填检查；
- 长度限制；
- 日期转换；
- 首尾空格清理。

它不会自动完成：

```text
深圳市 → 深圳
python → Python
技能去重
岗位去重
```

---

## 错误二：`salary=None` 已经测试了 HTML 缺少薪资

不完全正确。

当前测试只说明：

```text
JobCreate 接受 salary=None。
```

尚未证明：

```text
HTML 缺少 salary 标签
→ 解析器不会报错
→ 自动生成 salary=None
```

这个测试属于下一阶段。

---

## 错误三：Codex 审查后必须按照所有建议修改

不正确。

Codex 是辅助工具，建议需要结合：

- 当前阶段；
- 项目范围；
- 代码职责；
- 实际需求；
- 测试结果。

最终决策由开发者负责。

---

## 错误四：PR 页面没有内容说明代码丢了

不正确。

可能是：

- PR 已经合并；
- 两个分支内容相同；
- 功能分支已经删除。

应通过 Git 历史确认。

---

## 错误五：删除功能分支会删除已经合并的代码

不正确。

功能分支合并进 `main` 后，代码已经存在于 `main` 历史中。

删除功能分支只是删除一条旧分支引用，不会删除已经合并的代码。

---

# 14. 阶段二自测清单

## 功能和代码

- [ ] 我能说明 `JobCreate` 的作用。
- [ ] 我能解释每个岗位字段。
- [ ] 我能区分必填字段和可选字段。
- [ ] 我能解释 `str | None = None`。
- [ ] 我能解释 `default_factory=list`。
- [ ] 我能解释 `str_strip_whitespace=True`。
- [ ] 我知道 Pydantic 验证失败会抛出 `ValidationError`。
- [ ] 我知道模拟 HTML 为什么包含缺少薪资的岗位。

## 测试

- [ ] 我能说明阶段二的每个测试验证了什么。
- [ ] 我知道 `pytest.raises` 的作用。
- [ ] 我能区分模型测试和爬虫解析测试。
- [ ] 我知道下一阶段要补 HTML 到 `JobCreate` 的集成测试。

## Git

- [ ] 我能解释为什么使用功能分支。
- [ ] 我能区分 `git add`、`commit` 和 `push`。
- [ ] 我能说明 Pull Request 的作用。
- [ ] 我能正确选择 `base: main`。
- [ ] 我知道为什么 PR 合并后可以删除功能分支。
- [ ] 我能使用 `git status` 和 `git diff` 检查修改。

## Codex

- [ ] 我知道如何在项目根目录启动 Codex。
- [ ] 我知道为什么首次使用只读审查。
- [ ] 我知道如何限制 Codex 的文件范围。
- [ ] 我知道不能让 Codex自动提交或推送。
- [ ] 我能通过 Git 确认 Codex 是否修改文件。
- [ ] 我能说明旧中转站配置问题的原因和解决过程。

---

# 15. 阶段二成果如何写入简历

阶段二本身还不是完整项目，暂时不建议单独写成最终简历描述。

但它为后续简历内容提供了基础。

未来可以形成类似表述：

> 使用 Pydantic 设计统一岗位数据模型，对岗位名称、公司、城市、薪资、技能和发布日期等字段进行类型与规则验证，并构建包含缺失字段等边界情况的固定 HTML 测试样本，为多来源爬虫解析和自动化测试提供稳定数据基础。

需要等后续阶段完成后，再与爬虫、数据库、API 和 Agent 合并成完整项目描述。

---

# 16. 进入阶段三前需要记住什么

阶段三的目标：

> 使用 BeautifulSoup 读取 `sample_jobs.html`，将 6 个岗位卡片解析成 `list[JobCreate]`。

阶段三需要重点处理：

1. HTML 文件读取；
2. 查找所有 `.job-card`；
3. 提取必填字段；
4. 安全处理可选薪资；
5. 提取技能列表；
6. 提取链接和日期；
7. 主动添加：

```python
source="mock"
```

8. 创建 `JobCreate`；
9. 增加解析测试；
10. 验证最终得到 6 条岗位。

下一阶段预期数据流：

```text
sample_jobs.html
        ↓
BeautifulSoup
        ↓
HTML 元素提取
        ↓
字段缺失处理
        ↓
JobCreate 验证
        ↓
list[JobCreate]
```

---

## 阶段二总结

阶段二最重要的不是写了多少代码，而是建立了三个基础：

1. **统一的数据结构**：不同来源的岗位最终都转换为 `JobCreate`；
2. **稳定的测试输入**：模拟 HTML 不依赖网络，能够重复运行；
3. **规范的开发流程**：功能分支、测试、Pull Request、Codex只读审查和最终合并。

一句话总结：

> 阶段二完成了岗位数据的标准化设计和稳定测试样本准备，为下一阶段编写爬虫解析器打下基础。
