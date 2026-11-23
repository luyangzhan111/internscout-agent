# Agent 推荐：技能、投递条件与原文依据

Stage 16–18 为当前工作区实现，尚未发布新版本。[推荐任务与验收](tasks/stage-16-agent-eligibility-recommendations.md) · [可信推荐基础版](tasks/stage-17-trustworthy-recommendations.md) · [目标方向与核心技能](tasks/stage-18-recommendation-quality.md)。

## 使用

1. 打开项目页面，选择顶部 **Agent 推荐**。
2. 至少填写一项技能，选择目标岗位方向（可多选，留空表示不限），再填写自己确定的毕业届次、学历与在读／已取得状态、正式工作经验、可接受城市和可实习时长。未确定的条件留空，模型不会代填。
3. 选择最多展示数量（1–50），点击 **获取推荐**。**AI 补充说明**默认关闭，首次使用可直接获得规则结果。配置模型并勾选后，会在规则卡片之外显示 AI 说明。
4. 先看数据范围和推荐顺序，再按岗位阅读方向判断、核心／加分／未分类技能，以及**推荐理由、待确认条件、原文依据**。卡片保留总技能覆盖率及分母，完整判断和依据可展开。方向不符与资格不符分别展示有界排除记录。
5. 修改输入后旧结果会隐藏。导入或更新岗位后重新点击获取推荐；“刷新 / 清除旧结果”只清除旧显示，不自动发起模型调用。

输入只保留在浏览器会话，不存入个人档案。推荐默认隔离 `mock` 及 example.com／example.org／example.net（含子域）示例链接记录；需要体验时可主动开启“包含演示数据（仅用于体验）”。非示例链接的手动记录仍需核验，不因通过隔离就视为真实在招。

## 可信推荐的数据范围

先读取当前岗位记录，隔离演示数据，再合并同一规范化 URL、公司和岗位名称的记录，之后才判断、排序并截取展示数量。路径、查询参数与非空网址片段保留，不凭同名跨站猜测合并；参数顺序或锚点不同也可能继续分别保留。分组只影响推荐展示，岗位库与导入历史保留全部原记录。

重复组优先采用已接入的官网来源；其他来源按时间和稳定规则选定一份主快照。技能、条件和引用都来自这份快照，不把不同来源的要求拼成一个岗位。可展开查看各来源、核验时间与差异提示；来源存在内容或状态差异时需要核对。手动来源的检查时间仅表示本地处理时间，不代表原站在线核验。

摘要分别展示读取记录数、隔离样例数、合并重复数和实际判断的独立岗位数：读取数 = 隔离数 + 合并数 + 判断数。分类数量统计的是独立岗位；组内来源不会各占一个推荐名额。模型也只看到本次范围内的岗位。

## 排序与三态

后台先读取岗位全集、逐项计算技能及投递条件，再排序，最后截取展示数量：

1. **符合**排在**待确认**之前。
2. 同资格组先看方向一致／方向待确认，再按核心技能覆盖率、加分技能覆盖率、总技能覆盖率、匹配技能数量和岗位编号稳定排序。核心／加分覆盖率各自按匹配项数除以识别项数比较；空分类表示缺少证据，排在有该类证据的岗位之后，不当作满分。
3. **不符合**和**已关闭**不进入推荐列表。选择目标方向后，明确**方向不符**的岗位也单列；它们的五项资格可能仍符合或待确认，不能称为资格不符合。没有目标方向时不做方向排除。

待确认继续参与排名，不会被当作不符合过滤。符合岗位较多时，上限可能截掉待确认岗位；摘要显示未展示的数量，可增加展示上限。全是待确认时仍会推荐，全部存在阻断与岗位库为空会分别说明。

## 目标方向与技能重要性

可选择 AI 应用开发、后端开发、计算机视觉、数据开发／分析、前端开发、测试开发、运维／DevOps、安全研发。岗位标题中的明确职能优先，泛称或证据不足的方向保留待确认；公关、营销、产品／项目管理不会因为正文出现 Python、AI 或 Agent 就自动转成开发岗位。方向证据来自原文，方向不符只影响本次目标推荐范围，岗位库仍可浏览。

每个已识别技能划分为核心、加分或未分类。核心需要明确掌握／熟悉等要求或任职要求段落依据；优先／加分列为加分；职责提及、结构化技能标签、否定或任选组等不能单独证明逐项必需，保留未分类。各项显示匹配情况和引用；缺核心技能影响排序，不直接更改五项资格总评。这个分类不证明用户熟练掌握了技能。

技能覆盖率仍按原有确定性匹配规则计算，不混入资格权重，不代表录用概率。卡片同时显示“匹配 N / 已识别 M 项”；这里的分母只是系统识别出的岗位技能，不代表招聘要求全部覆盖。未识别到技能时明确显示证据不足，不显示全匹配。“符合”仅覆盖已识别的五类条件。待确认会说明原因分类和下一步建议，详见 [投递条件说明](application-eligibility.md)。

## AI 说明与岗位变化

推荐卡片、排序和主摘要始终由后台规则生成。专用 `recommend_jobs` 工具只读取本次绑定的结果，参数为空；模型不能修改候选条件、技能或展示数量。模型首轮就能看到真实工具结果，即使直接回答也不会跳过条件判断。

AI 为每个推荐岗位提供 1–3 条简短中文理由，服务端核对岗位身份后按规则顺序展示。待确认条件和引用直接来自已验证的规则结果，不让模型代写原文。界面不展示模型输出中的原始字段、状态码或 Markdown 标记，Python、C++ 等技能名称照常保留。

已有会话中的旧文字说明只在能明确识别岗位编号时关联；同名岗位不会凭标题或段落位置猜测。无法关联、格式不完整或模型失败时，保留规则卡片并明确提示，不自动重新调用模型。界面的“规则说明”与“AI 补充说明”分开标注。

AI 补充说明需要配置 `DEEPSEEK_API_KEY` 和 `DEEPSEEK_MODEL`。此入口最多 3 轮模型决策，使用 8 秒 HTTP 阶段超时且不自动重试；阶段超时不等于整个请求的严格时间上限。客户端等待默认 60 秒，如整体等待超时，可关闭 AI 后重新获取规则结果。模型缺配置、调用失败或超过轮次时，后台会保留规则卡片并明确说明状态；不会生成假模型答复。

本地真实体验可使用 `DEEPSEEK_MODEL=deepseek-flash`（2026-11-14 已验证官方模型列表及实际说明生成；[Responses API 文档](https://api-docs.deepseek.com/guides/responses_api/)）。这两个变量必须进入**后端启动进程**；直接运行 Python 不会自动加载 `.env`。已经配置好本机密钥时，在启动后端的 PowerShell 中设置 `$env:DEEPSEEK_MODEL = 'deepseek-flash'` 即可沿用密钥。修改环境变量后需要重启后端。密钥不应写入代码、日志或界面。

每次请求按当前数据库内容重新计算，不直接刷新招聘网站。若模型等待期间数据库版本改变，后台重新检查岗位并舍弃旧说明；连续变化导致无法取得稳定结果时返回重试提示。页面没有外部更新推送，已显示的结果应结合判断时间理解。

模型仅提供补充文字，仍可能出现自然语言错误。资格结论和原文以规则卡片为准；原文是证据数据，不能通过其中的指令改变规则或个人档案。

## API

新增 `POST /api/agent/recommend`。以下为虚构测试档案：

```json
{
  "candidate": {
    "skills": ["Python", "PyTorch"],
    "target_directions": ["ai_application", "backend"],
    "conditions": {
      "graduation_year": 2027,
      "degree": "bachelor",
      "degree_status": "enrolled",
      "work_experience_months": 0,
      "acceptable_cities": ["深圳"],
      "internship_months": 6
    }
  },
  "limit": 10,
  "explain_with_model": false,
  "include_samples": false
}
```

`conditions` 可省略，表示五项都未填写；城市 `null` 为未知、`[]` 为不限。`include_samples` 默认 `false`，只能用布尔值。所有结构化输入在模型调用前校验，未知字段拒绝。

`target_directions` 默认空列表；支持 `ai_application / backend / computer_vision / data / frontend / test_development / devops / security`。重复值按首次出现去重，未知值拒绝。模型不能增删目标方向。

响应含 `recommendations`、`excluded`、`counts`、UTC `assessed_at`、规则 `summary` 及兼容保留的 `model_explanation`。新增 `job_explanations`，每项为 `{job_id, reasons}`，只含简短理由，岗位身份、数量与顺序必须对应本次推荐；格式无效时为空列表。每条推荐同时包含原技能匹配字段和 `eligibility`（五项判断、精确原文位置、来源内容指纹、规则版本）。两者必须来自同一岗位快照。

`counts` 按 `met / unknown / not_met / closed / direction_mismatch` 对 `evaluated` 分区，优先统计关闭、资格不符，再统计资格未阻断但方向不符；剩余岗位归入符合／待确认。`returned` 为本次推荐数量。`explanation_status` 区分 `generated / disabled / unavailable / failed / stale / not_needed`；失败未取得运行轨迹时 `steps` 与 `tool_execution_count` 为 `null`，不能解释为未发生模型请求。

Stage 18 响应增加 `target_directions`、`ranking_version=direction-core-v1`、`direction_excluded`。每个推荐和方向排除项包含 `direction_fit`（`aligned / uncertain / unrelated / not_requested`、识别方向、理由和证据），以及 `skill_requirements`（`skill / importance / matched / evidence`）。其技能顺序和全集对应原 `detected_job_skills`，分类只影响新排序，原总技能分数保持独立。方向排除最多 10 条，完整数量见计数；合并来源元数据也覆盖显示的方向排除。旧响应缺少版本可展示旧规则，有目标方向的请求必须取得相同目标和新排序版本后才展示。

Stage20的`direction-core-v2`补充标题与本岗直接职责的复合方向，但曾因识别出AI而把CV误判无关；其原始数据与[报告](evaluations/stage20-analysis.md)保留。

Stage21版本为`direction-evidence-v3`，前端继续接受v1/v2历史响应。`direction_fit.target_checks`依请求顺序给每个目标的`target / status / reason / evidence`：明确本岗职责支持为`aligned`，明确否定目标或纯保护非技术职能为`unrelated`，缺依据/正负冲突为`uncertain`。任一目标aligned则总aligned，全部unrelated才总unrelated，其余总uncertain。不限方向时仍not_requested且checks为空。旧版本不得混入新checks，未知版本拒绝。

AI等已有方向线索可与CV待确认并存；仅“多模态”也可能是音频，不能推断视觉。明确图像生成/图文理解Agent交付可支持CV，团队/同事/历史经历/资格/偏好/使用AI工具不能冒充本岗职责。UI按目标显示中文判断与逐字引文，缺证据明确提示核对；整体方向匹配不意味着每个目标均匹配，也不意味着五项投递条件已满足。只有总unrelated进入方向排除，待确认继续保留；资格、技能分类和排序公式未改。结果、保留噪声和适用边界见[Stage21分析](evaluations/stage21-analysis.md)。

Stage22当前版本为`direction-support-v4`，每个推荐/方向排除卡片增加`ranking_support`：`level / targets / matched_target_skills / reason / evidence`。仅总方向uncertain按`target_specific / insufficient / other_direction`细分，其他状态使用`not_applicable`。先资格、方向，再比较该分层及原技能覆盖，稳定编号收尾。支持目标是本次请求的有序子集，相关技能必须属于既有匹配集合，每条引文来自同一岗位快照；服务端重新核对支持结果。v4缺字段拒绝，旧v1/v2/v3禁止混入支持字段并保持旧排序语义。

“排序参考”只帮助决定先核对哪一岗，不把待确认变成符合/明确无关。通用语言/框架、裸基座研究、整理研发材料、AI工具使用、同事或偏好不能冒充本岗研发支持；真正开发/训练后整理记录可保留线索。所有待确认仍在完整候选池，原总分与分母未改。模型工具返回同一已验证支持，不能重排；原文与排序理由由界面直接显示，内部字段不进入AI补充文字。[四组验证与剩余问题](evaluations/stage22-analysis.md)分别记录学历恢复和排序收益。

Stage23资格版本更新为`stage23-rules-v1`，排序继续使用`direction-support-v4`。学历能力分支不再错误缩窄共同招募范围，明确学生身份仍核对；混合工作地点的异地权限不明时保留待确认，明确到岗/远程地域限制仍严格。卡片的条件详情、待确认下一步和原文依据直接显示分支备注与本岗工作形式。没有增加候选人输入项，也未改变方向判断、技能分类或排序公式。城市修复可能让更多岗位进入方向检查，这不代表新增岗位已符合全部条件。[规则说明](application-eligibility.md#stage23-学历分支与工作地点)。

Stage 17 返回 `data_scope`（`total_records / sample_records_excluded / duplicate_records_collapsed / include_samples`）以及已返回推荐／排除岗位的 `duplicate_groups`。重复组包含 `primary_job_id`、`sources`、`has_conflict` 和 `selection_reason`；来源信息保留岗位编号、来源、链接、状态与时间。旧响应缺少范围字段时不推断其已完成隔离。

旧 `/api/agent/query` 和原 `match_jobs` 保留自由问答及技能匹配协议。需要同时获得投递条件的调用方使用新结构化入口。此推荐路径不构建向量索引，也不依赖 embedding 服务。
