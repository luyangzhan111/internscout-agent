# 阶段3复习：模拟岗位爬虫与HTML解析

## 1. 阶段目标

将本地模拟招聘HTML解析为统一的JobCreate岗位对象。

## 2. 核心流程

sample_jobs.html  
→ BeautifulSoup  
→ CSS选择器  
→ 字段提取  
→ JobCreate验证  
→ list[JobCreate]

## 3. 完成内容

- BaseJobCrawler抽象基类
- MockJobCrawler模拟爬虫
- 岗位字段解析
- 可选薪资处理
- 日期解析和回退
- 明确的异常信息
- 12个爬虫测试
- 全项目18个测试通过
- Codex只读代码审查

## 4. 关键知识点

### BeautifulSoup

将HTML文本解析为可以通过标签和CSS选择器查询的对象结构。

### CSS选择器

- `article.job-card`：所有岗位卡片
- `.job-title`：岗位名称
- `.skills li`：技能列表
- `.source-url`：岗位链接

### pathlib

通过当前代码文件的位置寻找fixture，不依赖执行命令时所在的目录。

### 抽象基类

BaseJobCrawler规定所有岗位爬虫都必须实现：

```python
fetch_jobs() -> list[JobCreate]