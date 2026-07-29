# 阶段4复习：岗位数据清洗、标准化与去重

## 目录

- [1. 阶段目标](#1-阶段目标)
- [2. 阶段完成内容](#2-阶段完成内容)
- [3. 项目数据处理流程](#3-项目数据处理流程)
- [4. 项目目录变化](#4-项目目录变化)
- [5. 核心知识点](#5-核心知识点)
  - [5.1 为什么爬虫数据还需要清洗](#51-为什么爬虫数据还需要清洗)
  - [5.2 城市名称标准化](#52-城市名称标准化)
  - [5.3 技能名称标准化](#53-技能名称标准化)
  - [5.4 技能列表去重](#54-技能列表去重)
  - [5.5 清洗后重新进行Pydantic验证](#55-清洗后重新进行pydantic验证)
  - [5.6 岗位唯一标识](#56-岗位唯一标识)
  - [5.7 岗位去重](#57-岗位去重)
  - [5.8 为什么必须先清洗再去重](#58-为什么必须先清洗再去重)
  - [5.9 不直接修改原始岗位对象](#59-不直接修改原始岗位对象)
- [6. 核心模块说明](#6-核心模块说明)
- [7. 自动化测试](#7-自动化测试)
- [8. Codex代码审查与修复](#8-codex代码审查与修复)
- [9. 本阶段遇到的问题](#9-本阶段遇到的问题)
- [10. Git开发流程](#10-git开发流程)
- [11. 面试可能提问](#11-面试可能提问)
- [12. 一分钟阶段介绍](#12-一分钟阶段介绍)
- [13. 当前不足与后续优化](#13-当前不足与后续优化)
- [14. 阶段验收结果](#14-阶段验收结果)
- [15. 自我检查](#15-自我检查)

---

## 1. 阶段目标

阶段4的目标是对爬虫产生的岗位数据进行清洗、标准化和去重，为后续数据库存储和岗位查询功能提供稳定、统一的数据。

阶段3完成后，项目已经可以将本地模拟招聘网页解析为 `JobCreate` 对象，但不同岗位中的城市和技能可能存在不同写法，例如：

```text
深圳市
深圳

python
Python
PYTHON

beautifulsoup
beautiful soup
beautifulsoup4
```

如果不先进行标准化，这些实际含义相同的数据会被系统当成不同数据，影响后续的：

- 岗位查询；
- 技能统计；
- 岗位匹配；
- 重复岗位识别；
- 数据库存储；
- Agent工具调用。

因此，阶段4建立了完整的数据处理管道：

```text
原始岗位数据
→ 城市标准化
→ 技能标准化
→ 空白和重复技能清理
→ 岗位身份构建
→ 重复岗位过滤
→ 干净岗位列表
```

---

## 2. 阶段完成内容

本阶段完成了以下功能：

- 创建 `app/services` 业务处理模块；
- 实现城市名称标准化；
- 使用受控城市映射避免错误删除城市名称；
- 实现技能名称标准化；
- 统一 Python、FastAPI、SQL、pytest 等技能的展示形式；
- 统一 Beautiful Soup 相关别名；
- 删除空白技能；
- 删除重复技能并保持第一次出现的顺序；
- 清洗后重新使用 Pydantic 验证岗位数据；
- 根据公司、岗位名称和标准化城市构建岗位身份；
- 实现岗位列表去重；
- 重复岗位保留第一次出现的数据；
- 实现 `process_jobs()` 数据处理管道；
- 保证处理过程不直接修改原始 `JobCreate` 对象；
- 完成模拟爬虫到数据处理管道的集成测试；
- 使用 Codex 完成只读代码审查；
- 修复城市名称误截断问题；
- 修复 pytest 技能名称不规范问题；
- 修复 `model_copy(update=...)` 不重新验证数据的问题；
- 全项目达到 **36个测试通过**。

阶段4的核心成果是：

```text
统一的城市名称
+
统一的技能名称
+
稳定的岗位唯一标识
+
可解释的岗位去重规则
+
完整的数据处理管道
+
自动化回归测试
```

---

## 3. 项目数据处理流程

阶段4完成后，项目的数据链路为：

```text
app/fixtures/sample_jobs.html
            ↓
       MockJobCrawler
            ↓
       list[JobCreate]
            ↓
        process_jobs
            ↓
  ┌─────────┴─────────┐
  ↓                   ↓
clean_job       deduplicate_jobs
  ↓                   ↓
城市标准化          岗位身份比较
技能标准化          删除重复岗位
技能去重            保留第一次出现
  └─────────┬─────────┘
            ↓
   清洗且去重后的岗位列表
```

对应代码调用方式：

```python
from app.crawlers import MockJobCrawler
from app.services import process_jobs

raw_jobs = MockJobCrawler().fetch_jobs()
processed_jobs = process_jobs(raw_jobs)
```

输入：

```text
爬虫解析得到的原始岗位列表
```

输出：

```text
城市、技能已经标准化，并且重复岗位已经删除的岗位列表
```

---

## 4. 项目目录变化

阶段4新增的主要文件如下：

```text
internscout-agent/
├── app/
│   ├── services/
│   │   ├── __init__.py
│   │   ├── cleaner.py
│   │   ├── deduplicator.py
│   │   └── processor.py
│   │
│   ├── crawlers/
│   ├── fixtures/
│   ├── schemas/
│   └── main.py
│
├── tests/
│   ├── test_cleaner.py
│   ├── test_deduplicator.py
│   ├── test_processor.py
│   ├── test_health.py
│   ├── test_job_schema.py
│   └── test_mock_crawler.py
│
└── docs/
    ├── development-log.md
    └── stage-reviews/
        └── stage-04-review.md
```

各文件职责：

| 文件 | 作用 |
|---|---|
| `cleaner.py` | 城市和技能的清洗、标准化 |
| `deduplicator.py` | 构建岗位身份并过滤重复岗位 |
| `processor.py` | 串联清洗和去重流程 |
| `services/__init__.py` | 统一导出业务处理函数 |
| `test_cleaner.py` | 测试城市和技能清洗 |
| `test_deduplicator.py` | 测试岗位身份与去重 |
| `test_processor.py` | 测试完整处理管道 |

---

## 5. 核心知识点

### 5.1 为什么爬虫数据还需要清洗

爬虫只是按照网页结构提取内容，不能保证不同数据源使用相同格式。

例如，不同网站可能分别提供：

```text
深圳市
深圳
广东深圳
```

技能也可能写成：

```text
python
Python
PYTHON
```

如果直接保存，会产生以下问题：

- 相同城市无法正确筛选；
- 相同技能被重复统计；
- 相同岗位无法识别为重复；
- 用户技能与岗位技能无法正确匹配；
- Agent查询结果不稳定。

因此，爬虫与数据清洗承担不同职责：

```text
爬虫：负责从HTML中提取数据
数据模型：负责验证数据是否合法
清洗模块：负责统一数据格式
去重模块：负责识别重复记录
```

---

### 5.2 城市名称标准化

最初的实现方式是：

```python
if normalized.endswith("市"):
    normalized = normalized[:-1]
```

这种写法对于以下城市有效：

```text
深圳市 → 深圳
广州市 → 广州
```

但是会错误处理本身名称就以“市”结尾的地点：

```text
四日市 → 四日
```

这可能进一步导致不同城市形成相同岗位身份，从而错误删除岗位。

因此，最终改为受控映射：

```python
CITY_ALIASES: dict[str, str] = {
    "北京市": "北京",
    "上海市": "上海",
    "天津市": "天津",
    "重庆市": "重庆",
    "深圳市": "深圳",
    "广州市": "广州",
    "东莞市": "东莞",
}
```

标准化函数：

```python
def normalize_city(city: str) -> str:
    """标准化已知城市别名，未知城市名称保持不变。"""

    normalized = " ".join(city.split())

    return CITY_ALIASES.get(normalized, normalized)
```

效果：

```text
深圳市 → 深圳
广州市 → 广州
四日市 → 四日市
新加坡 → 新加坡
```

这里采用的原则是：

> 只转换项目明确支持和确认过的城市，未知数据保持原样。

这种方案比直接删除所有“市”字更加安全。

---

### 5.3 技能名称标准化

不同岗位可能使用不同的大小写或名称表示同一种技能：

```text
python
PYTHON
Python

fastapi
FASTAPI
FastAPI

beautifulsoup
beautiful soup
beautifulsoup4
bs4
```

项目使用 `SKILL_ALIASES` 定义规范展示名称：

```python
SKILL_ALIASES: dict[str, str] = {
    "python": "Python",
    "fastapi": "FastAPI",
    "sql": "SQL",
    "git": "Git",
    "pytest": "pytest",
    "http": "HTTP",
    "html": "HTML",
    "requests": "Requests",
    "beautifulsoup": "Beautiful Soup",
    "beautiful soup": "Beautiful Soup",
    "beautifulsoup4": "Beautiful Soup",
    "bs4": "Beautiful Soup",
    "docker": "Docker",
    "linux": "Linux",
    "shell": "Shell",
    "postman": "Postman",
    "llm": "LLM",
    "rag": "RAG",
}
```

标准化过程：

```python
def normalize_skill(skill: str) -> str:
    """将单个技能名称转换为统一展示形式。"""

    normalized = " ".join(skill.split())

    if not normalized:
        return ""

    return SKILL_ALIASES.get(
        normalized.casefold(),
        normalized,
    )
```

这里使用：

```python
" ".join(skill.split())
```

它可以：

- 删除首尾空格；
- 将多个连续空格合并成一个空格；
- 处理制表符和换行符。

例如：

```text
"  python  " → "python"
"beautiful   soup" → "beautiful soup"
```

随后使用：

```python
casefold()
```

进行不区分大小写的别名查找。

最终效果：

```text
python → Python
FASTAPI → FastAPI
PYTEST → pytest
beautifulsoup4 → Beautiful Soup
beautiful   soup → Beautiful Soup
```

需要注意：

> `pytest` 的官方名称保持小写，不能写成 `Pytest`。

---

### 5.4 技能列表去重

岗位技能列表可能包含空值或重复项：

```python
[
    "python",
    " Python ",
    "",
    "SQL",
    "sql",
    "FastAPI",
]
```

标准化后应该得到：

```python
[
    "Python",
    "SQL",
    "FastAPI",
]
```

项目使用：

```python
normalized_skills: list[str] = []
seen: set[str] = set()
```

其中：

- `set` 用于快速判断技能是否已经出现；
- `list` 用于保存结果并维持原始顺序。

核心逻辑：

```python
for skill in skills:
    normalized = normalize_skill(skill)

    if not normalized:
        continue

    identity = normalized.casefold()

    if identity in seen:
        continue

    seen.add(identity)
    normalized_skills.append(normalized)
```

这段代码能够：

- 删除空字符串；
- 忽略技能大小写；
- 删除重复技能；
- 保留技能第一次出现的顺序。

时间复杂度接近：

```text
O(n)
```

因为 `set` 的成员查询平均为常数时间。

---

### 5.5 清洗后重新进行Pydantic验证

原来的清洗方式使用：

```python
job.model_copy(
    update={
        "city": normalized_city,
        "skills": normalized_skills,
    }
)
```

Codex审查发现：

> Pydantic v2的 `model_copy(update=...)` 默认不会重新验证更新后的字段。

这意味着即使清洗函数意外产生：

```python
city=""
```

也可能生成一个不符合 `JobCreate` 约束的对象。

因此，最终改为：

```python
def clean_job(job: JobCreate) -> JobCreate:
    """返回经过重新验证的清洗后岗位，不修改原始对象。"""

    job_data = job.model_dump()
    job_data.update(
        {
            "city": normalize_city(job.city),
            "skills": normalize_skills(job.skills),
        }
    )

    return JobCreate.model_validate(job_data)
```

处理步骤：

```text
原始JobCreate
→ model_dump转换为字典
→ 更新清洗字段
→ model_validate重新构造模型
→ 再次执行Pydantic验证
```

优点：

- 清洗结果仍然符合模型约束；
- 新增字段验证器后仍然安全；
- 不会静默生成非法模型；
- 原始岗位对象保持不变。

---

### 5.6 岗位唯一标识

为了判断两条岗位是否重复，需要为岗位建立可比较的身份。

当前项目使用：

```text
公司名称 + 岗位名称 + 标准化城市
```

类型定义：

```python
JobIdentity = tuple[str, str, str]
```

身份构建函数：

```python
def build_job_identity(job: JobCreate) -> JobIdentity:
    """
    构建跨来源去重身份。

    公司、岗位名称和城市相同的记录被视为重复，
    当前策略保留第一次出现的岗位。
    """

    return (
        normalize_identity_text(job.company),
        normalize_identity_text(job.title),
        normalize_identity_text(normalize_city(job.city)),
    )
```

身份文本处理：

```python
def normalize_identity_text(value: str) -> str:
    """清理用于身份比较的文本，并忽略大小写差异。"""

    return " ".join(value.split()).casefold()
```

它会：

- 删除多余空格；
- 合并连续空格；
- 处理制表符和换行；
- 忽略英文大小写差异。

例如：

```text
Example Tech
example tech
 Example   Tech
```

会形成相同身份。

---

### 5.7 岗位去重

去重函数：

```python
def deduplicate_jobs(
    jobs: list[JobCreate],
) -> list[JobCreate]:
    """按岗位唯一标识去重，并保留第一次出现的顺序。"""

    unique_jobs: list[JobCreate] = []
    seen: set[JobIdentity] = set()

    for job in jobs:
        identity = build_job_identity(job)

        if identity in seen:
            continue

        seen.add(identity)
        unique_jobs.append(job)

    return unique_jobs
```

工作过程：

```text
读取第一条岗位
→ 构建身份
→ 身份未出现
→ 保存岗位和身份

读取下一条岗位
→ 构建身份
→ 身份已经出现
→ 跳过该岗位
```

当前策略为：

> 对于重复岗位，保留第一次出现的数据。

例如：

```text
去重前：2条
去重后：1条
保留链接：https://example.com/1
```

这种实现同时具备：

- 可解释；
- 时间复杂度较低；
- 保持输入顺序；
- 不改变原岗位对象。

---

### 5.8 为什么必须先清洗再去重

假设存在两条岗位：

```text
公司：星河科技
岗位：Python实习生
城市：深圳市
```

以及：

```text
公司：星河科技
岗位：Python实习生
城市：深圳
```

如果先去重：

```text
深圳市 != 深圳
```

系统会错误地保留两条岗位。

如果先清洗：

```text
深圳市 → 深圳
深圳 → 深圳
```

再进行去重，两条岗位会形成相同身份。

因此正确顺序是：

```text
清洗
→ 再去重
```

对应代码：

```python
def process_jobs(
    jobs: list[JobCreate],
) -> list[JobCreate]:
    """依次清洗岗位数据，并过滤重复岗位。"""

    cleaned_jobs = [
        clean_job(job)
        for job in jobs
    ]

    return deduplicate_jobs(cleaned_jobs)
```

---

### 5.9 不直接修改原始岗位对象

`clean_job()` 返回一个新的 `JobCreate` 对象，而不是修改输入对象。

例如：

```python
original_job.city == "深圳市"
cleaned_job.city == "深圳"
```

处理完成后：

```python
original_job.city
```

仍然是：

```text
深圳市
```

这样做的好处：

- 原始爬虫数据仍然可以追踪；
- 减少函数副作用；
- 测试结果更加稳定；
- 发生清洗错误时可以比较原始数据；
- 后续可以选择保存原始数据和清洗数据。

---

## 6. 核心模块说明

### `cleaner.py`

主要职责：

```text
城市标准化
技能标准化
技能列表清理
重新验证清洗后的JobCreate
```

主要函数：

```python
normalize_city(city)
normalize_skill(skill)
normalize_skills(skills)
clean_job(job)
```

---

### `deduplicator.py`

主要职责：

```text
清理身份比较文本
生成岗位唯一标识
根据身份过滤重复岗位
```

主要函数：

```python
normalize_identity_text(value)
build_job_identity(job)
deduplicate_jobs(jobs)
```

---

### `processor.py`

主要职责：

```text
将清洗和去重连接为一个完整处理管道
```

核心函数：

```python
process_jobs(jobs)
```

---

### `services/__init__.py`

统一导出业务函数，使其他模块可以使用：

```python
from app.services import (
    clean_job,
    deduplicate_jobs,
    process_jobs,
)
```

而不需要分别从多个文件导入。

---

## 7. 自动化测试

阶段4新增了三类测试。

### 7.1 清洗测试

文件：

```text
tests/test_cleaner.py
```

覆盖：

- `深圳市 → 深圳`；
- `广州市 → 广州`；
- 普通城市名称保持不变；
- `四日市`不会被误改为`四日`；
- Python、FastAPI、SQL等技能名称规范化；
- pytest保持官方小写形式；
- Beautiful Soup相关别名统一；
- 空白技能被删除；
- 重复技能被删除；
- 技能顺序保持稳定；
- 清洗返回新对象；
- 原岗位对象不被修改；
- 清洗结果重新经过Pydantic验证。

---

### 7.2 去重测试

文件：

```text
tests/test_deduplicator.py
```

覆盖：

- 城市和大小写差异不影响岗位身份；
- 完全重复岗位只保留一条；
- `深圳市`和`深圳`被视为同一城市；
- 不同公司岗位不会被误删；
- 不同岗位名称不会被误删；
- 去重保持第一次出现顺序；
- `四日市`和`四日`不会发生身份碰撞；
- 相同公司和岗位但城市不同的记录应保留。

---

### 7.3 处理管道测试

文件：

```text
tests/test_processor.py
```

覆盖：

- 先清洗再去重；
- 不同岗位全部保留；
- 原始岗位对象不被修改；
- 空岗位列表返回空列表；
- `MockJobCrawler`输出可以直接进入`process_jobs`；
- 模拟网页中的城市被正确标准化；
- 模拟网页中的技能被正确标准化。

完整集成链路：

```text
sample_jobs.html
→ MockJobCrawler
→ JobCreate
→ process_jobs
→ 标准化岗位列表
```

最终测试结果：

```text
36 passed
```

阶段1、阶段2和阶段3原有测试仍然通过，说明阶段4没有破坏已有功能。

测试中的 FastAPI/Starlette 弃用警告与本阶段业务代码无关，暂时记录为技术债。

---

## 8. Codex代码审查与修复

本阶段使用 Codex进行了只读代码审查。

审查重点包括：

- 城市清洗规则是否安全；
- 技能规范名称是否正确；
- `model_copy()`是否重新验证；
- 岗位身份规则是否合理；
- 去重是否保持原顺序；
- 处理管道顺序是否正确；
- 测试是否覆盖关键边界情况。

### Codex发现的必须修改问题

#### 问题一：城市名称误截断

原规则会删除所有名称末尾的“市”：

```text
深圳市 → 深圳
四日市 → 四日
```

风险：

- 修改真实城市名称；
- 构建错误岗位身份；
- 不同城市产生身份碰撞；
- 后出现的岗位被静默删除。

解决：

```text
使用受控CITY_ALIASES映射
未知名称保持不变
```

---

#### 问题二：pytest规范名称错误

原技能表将：

```text
pytest
```

转换为：

```text
Pytest
```

但官方项目名称应保持小写：

```text
pytest
```

解决：

```python
"pytest": "pytest"
```

并同步修改相关自动化测试。

---

### Codex发现的建议修改问题

#### `model_copy(update=...)`不重新验证

风险：

```text
清洗函数可能生成非法字段
但JobCreate不会主动拒绝
```

解决：

```python
JobCreate.model_validate(job_data)
```

重新验证所有清洗结果。

---

#### Beautiful Soup名称需要统一

原项目中可能混合：

```text
BeautifulSoup
Beautiful Soup
beautifulsoup4
bs4
```

当前项目确定：

```text
面向用户展示：Beautiful Soup
包名称：beautifulsoup4
Python导入：bs4
```

别名表统一转换为：

```text
Beautiful Soup
```

---

#### 岗位三元组去重可能存在误判

当前规则：

```text
公司 + 岗位名称 + 城市
```

可能将以下岗位误认为重复：

- 同一公司；
- 同一城市；
- 同名岗位；
- 但属于不同部门或不同招聘批次。

当前阶段保留简单、可解释的规则，同时将该问题记录为局限，不引入复杂文本相似度。

---

## 9. 本阶段遇到的问题

### 9.1 城市名称被错误截断

现象：

```text
四日市 → 四日
```

原因：

```python
endswith("市")
```

规则范围过大。

解决：

```text
使用受控城市别名映射
```

学到：

> 数据清洗规则不能只根据字符串表面特征进行过度泛化。

---

### 9.2 pytest名称不规范

现象：

```text
pytest → Pytest
```

原因：

没有在建立技能别名表前明确统一的展示标准。

解决：

```text
保持官方名称pytest
```

学到：

> 数据标准化前应先定义规范表，而不是凭感觉修改大小写。

---

### 9.3 `model_copy()`没有重新验证

现象：

使用：

```python
model_copy(update=...)
```

可以生成不符合模型约束的数据。

原因：

误以为Pydantic复制并更新模型时会自动重新执行验证。

解决：

```python
JobCreate.model_validate(job_data)
```

学到：

> 使用框架方法前，需要理解它是否执行数据验证，而不能只根据方法名称推断行为。

---

### 9.4 测试代码被放入错误文件

现象：

`tests/test_cleaner.py` 中出现：

```python
def build_job_identity(
    job: JobCreate,
) -> JobIdentity:
```

报错：

```text
NameError: JobIdentity is not defined
```

原因：

修改多个文件时，将属于 `deduplicator.py` 的代码误放入 `test_cleaner.py`。

解决：

- 根据报错文件和行号定位；
- 删除错误位置的函数；
- 确认函数位于正确模块；
- 单独运行对应测试文件。

学到：

> Pytest在收集阶段报错时，测试尚未真正运行，应优先检查导入和模块顶层代码。

---

### 9.5 `create_job()`辅助函数被误删

现象：

```text
NameError: create_job is not defined
```

原因：

清理误粘贴代码时，将测试辅助函数一并删除。

解决：

重新在 `test_cleaner.py` 顶层定义：

```python
def create_job(
    **overrides: object,
) -> JobCreate:
    ...
```

学到：

> 测试辅助函数必须定义在模块顶层，才能被多个测试函数复用。

---

## 10. Git开发流程

阶段4使用独立功能分支：

```text
feat/job-cleaning-dedup
```

开发流程：

```text
main保持稳定
→ 创建功能分支
→ 开发清洗模块
→ 编写清洗测试
→ 开发去重模块
→ 编写去重测试
→ 建立处理管道
→ 编写集成测试
→ Codex只读审查
→ 修复问题
→ 36个测试通过
→ 分开提交功能、测试和文档
→ 推送分支
→ 创建Pull Request
→ 合并到main
```

建议提交记录：

```text
feat: add job cleaning and deduplication pipeline
test: cover job cleaning and deduplication
docs: record stage 4 development progress
docs: add stage 4 review notes
```

功能、测试和文档分别提交，便于：

- 查看开发历史；
- 代码审查；
- 回滚某一类修改；
- 面试时展示真实工程过程。

---

## 11. 面试可能提问

### 1. 为什么爬虫数据还需要清洗？

参考回答：

> 不同网站的数据格式可能不一致，例如“深圳市”和“深圳”表示同一个城市，Python技能也可能使用不同大小写。如果不统一，会影响查询、统计、匹配和去重。因此我在爬虫和数据库之间增加了数据清洗层。

---

### 2. 为什么不能直接删除城市名称末尾的“市”？

参考回答：

> 这种规则会过度泛化。例如“四日市”是完整名称，直接删除会变成“四日”，甚至可能导致不同城市的岗位生成相同身份并被错误去重。因此项目改为受控城市映射，只转换已经确认的城市别名。

---

### 3. 为什么使用技能别名表？

参考回答：

> 技能名称的可能写法较多，例如python、PYTHON和Python。别名表可以将它们统一为规范展示名称，便于后续技能统计、岗位匹配和Agent查询。

---

### 4. 如何删除重复技能并保持顺序？

参考回答：

> 我同时使用set和list。set负责快速判断标准化后的技能是否已经出现，list负责保存结果和维持第一次出现的顺序。

---

### 5. `casefold()`与`lower()`有什么区别？

参考回答：

> 两者都可以处理大小写，但casefold更适合进行不区分大小写的文本比较，对部分Unicode字符的处理更完整。本项目用它生成技能和岗位身份的比较值。

---

### 6. 为什么不直接修改原始岗位对象？

参考回答：

> 返回新对象可以减少函数副作用，同时保留原始爬虫数据。发生清洗问题时，可以比较原数据和处理结果，也有利于自动化测试。

---

### 7. `model_copy()`和`model_validate()`有什么区别？

参考回答：

> Pydantic v2的model_copy(update=...)默认不会重新验证更新数据，而model_validate会重新执行模型约束。为了保证清洗后的城市和技能仍然合法，我使用model_dump取得数据，再通过model_validate重新构造模型。

---

### 8. 当前岗位去重规则是什么？

参考回答：

> 当前使用标准化后的公司名称、岗位名称和城市组成三元组作为岗位身份。如果身份相同，就认为是重复岗位，并保留第一次出现的数据。

---

### 9. 为什么去重之前必须先清洗？

参考回答：

> 如果先去重，“深圳市”和“深圳”会被视为不同城市。先标准化后，两条岗位才能生成相同身份并被正确识别为重复。

---

### 10. 当前去重规则有什么不足？

参考回答：

> 同一公司在同一城市可能发布多个同名但不同部门或不同批次的岗位，当前规则可能将它们误判为重复。后续可以结合岗位编号、部门、发布时间或来源链接优化，但当前阶段保留简单且可解释的规则。

---

### 11. 为什么不用岗位链接作为唯一标识？

参考回答：

> 同一个岗位可能被多个网站转载，从而拥有不同链接。如果只使用链接，同一岗位无法跨来源去重。因此当前使用公司、岗位名称和城市进行跨来源识别。

---

### 12. 如何保证去重后仍然保持岗位顺序？

参考回答：

> 使用set记录已经出现的身份，同时用list保存第一次出现的岗位。遍历顺序没有改变，因此结果保持原始顺序。

---

### 13. 单元测试和集成测试在本阶段分别测试什么？

参考回答：

> 单元测试分别验证城市标准化、技能标准化和岗位去重等单个函数；集成测试则从MockJobCrawler读取模拟HTML，再交给process_jobs，确认整个真实处理链路可以正确工作。

---

### 14. Codex在本阶段起到了什么作用？

参考回答：

> 我让Codex进行只读代码审查，而不是直接生成并提交代码。它发现了城市名称误截断、pytest命名不规范和model_copy不重新验证等问题。我判断建议后亲自修改代码、补回归测试并运行全部测试。

---

## 12. 一分钟阶段介绍

可以按照下面的方式介绍阶段4：

> 阶段4主要负责岗位数据的清洗、标准化和去重。我建立了独立的services层，使用受控映射统一城市名称，避免直接删除“市”字导致四日市等名称被错误修改；同时使用技能别名表统一Python、FastAPI、pytest和Beautiful Soup等技能名称，并通过set和list删除空白、重复技能且保持原顺序。
>
> 在去重方面，我使用标准化后的公司名称、岗位名称和城市组成岗位身份，重复岗位保留第一次出现的数据。整个处理过程封装在process_jobs中，按照先清洗、再去重的顺序执行。
>
> Codex审查发现Pydantic的model_copy不会重新验证更新数据，因此我改为使用model_validate重新构造岗位模型，并补充了城市边界、重新验证和爬虫到处理管道的集成测试。目前全项目共有36个自动化测试通过。

---

## 13. 当前不足与后续优化

### 13.1 城市映射范围有限

当前只包含项目模拟数据中使用的常见城市。

后续可以：

- 根据真实岗位数据补充映射；
- 引入标准行政区划数据；
- 区分城市、区县和国家；
- 对不支持的地域进行明确标记。

---

### 13.2 技能别名表仍不完整

未收录技能保持原始格式，因此：

```text
Django
django
```

输入顺序不同可能产生不同展示形式。

后续可以：

- 根据真实岗位数据扩展别名；
- 将展示名称和内部标识分开；
- 增加技能分类；
- 建立可配置的技能词典。

当前不使用模糊匹配，避免错误合并不同技能。

---

### 13.3 去重规则可能误判

当前身份：

```text
公司 + 岗位名称 + 城市
```

可能误删：

- 不同部门的同名岗位；
- 不同招聘批次；
- 同一城市的多个办公地点；
- 职责不同但名称相同的岗位。

后续可以考虑增加：

- 岗位编号；
- 部门；
- 发布时间；
- 标准化后的来源链接；
- 描述文本指纹；
- 文本相似度。

---

### 13.4 重复岗位只保留第一条

当前不会合并重复岗位中的不同信息。

例如：

```text
第一条有薪资，但没有完整技能
第二条没有薪资，但技能更完整
```

当前只保留第一条。

后续可以设计字段合并策略，优先保留信息更完整的记录。

---

### 13.5 尚未进行数据库持久化

当前处理结果仍然保存在内存列表中。

下一阶段将实现：

```text
process_jobs输出
→ SQLite数据库
→ 岗位新增和查询
→ 数据持久化
```

---

## 14. 阶段验收结果

### 功能验收

- [x] 创建岗位业务处理模块
- [x] 实现城市标准化
- [x] 使用受控城市映射
- [x] 未知城市名称保持原样
- [x] 实现技能标准化
- [x] pytest保持官方小写形式
- [x] Beautiful Soup相关别名统一
- [x] 删除空白技能
- [x] 删除重复技能
- [x] 保持技能第一次出现顺序
- [x] 清洗结果重新经过Pydantic验证
- [x] 不直接修改原始岗位对象
- [x] 构建岗位唯一标识
- [x] 实现岗位列表去重
- [x] 保留第一次出现的岗位
- [x] 去重后保持原始顺序
- [x] 实现先清洗再去重的处理管道
- [x] 模拟爬虫可以直接接入处理管道

### 测试验收

- [x] 城市标准化正常测试
- [x] 城市名称边界测试
- [x] 四日市不会被错误截断
- [x] 技能规范名称测试
- [x] 空白与重复技能测试
- [x] 原始岗位对象不被修改
- [x] 清洗结果重新验证测试
- [x] 完全重复岗位测试
- [x] 城市变体去重测试
- [x] 不同公司岗位保留
- [x] 不同岗位名称保留
- [x] 不同城市岗位保留
- [x] 去重顺序测试
- [x] 空列表测试
- [x] 爬虫到处理管道集成测试
- [x] 全项目36个测试通过

### 工程流程验收

- [x] 使用独立功能分支
- [x] 开发前确认main分支基线正常
- [x] 使用Codex完成只读代码审查
- [x] 根据审查结果修复真实问题
- [x] 为修复内容增加回归测试
- [x] `git diff --check`无格式错误
- [ ] 提交业务代码
- [ ] 提交自动化测试
- [ ] 更新开发日志
- [ ] 提交阶段4复习文档
- [ ] 推送功能分支
- [ ] 创建Pull Request
- [ ] 合并到main
- [ ] 删除完成后的功能分支

后续完成Git和PR流程后，将未完成项更新为：

```markdown
- [x]
```

---

## 15. 自我检查

阶段4完成后，应当能够独立回答：

1. 为什么需要在爬虫之后增加数据清洗层？
2. 为什么不能删除所有城市名称末尾的“市”？
3. `CITY_ALIASES`解决了什么问题？
4. `SKILL_ALIASES`解决了什么问题？
5. 为什么pytest应保持小写？
6. 为什么统一使用Beautiful Soup作为展示名称？
7. `casefold()`在本项目中的作用是什么？
8. 如何删除重复技能并保持顺序？
9. 为什么需要同时使用set和list？
10. 为什么不能直接使用`model_copy(update=...)`？
11. `model_validate()`在清洗流程中的作用是什么？
12. 为什么清洗函数不直接修改原对象？
13. 当前岗位身份由哪些字段组成？
14. 为什么不直接使用岗位链接去重？
15. 为什么必须先清洗再去重？
16. 当前去重规则可能产生哪些误判？
17. `process_jobs()`负责什么？
18. 单元测试和集成测试有什么区别？
19. Codex本阶段发现了哪些问题？
20. 如果未来接入真实岗位数据，清洗和去重规则应如何扩展？

如果这些问题能够用自己的语言回答，说明已经基本理解阶段4的核心内容。

---

## 阶段4总结

阶段4将项目从：

```text
能够解析岗位
```

推进到了：

```text
能够生成格式统一、经过验证并去除重复项的岗位数据
```

目前完整流程已经达到：

```text
模拟招聘HTML
→ BeautifulSoup解析
→ JobCreate验证
→ 城市标准化
→ 技能标准化
→ 技能去重
→ 岗位身份构建
→ 岗位去重
→ 干净岗位列表
```

这为下一阶段的 SQLite数据库存储和岗位查询接口奠定了基础。