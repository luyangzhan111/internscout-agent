# 真实岗位推荐评测

本评测自Stage19开始比较简单技能匹配与生产推荐，并用归档实现保留后续修复前后的公平对照。任务和验收见 [Stage 19](tasks/stage-19-real-data-evaluation.md)及[Stage21](tasks/stage-21-direction-evidence.md)。这是新来源、小样本的离线留出对照，标签由 AI 辅助阅读原文并在项目内复核，不是独立真人标注、用户试验或录用效果统计。

已执行的30岗位／6档案对照见 [结果报告](evaluations/stage19-results.md)，问题归因与下一阶段建议见 [结果分析](evaluations/stage19-analysis.md)。本地新增岗位和旧记录保护见 [导入验收](evaluations/stage19-import-acceptance.json)。

Stage20将旧30岗转为开发回归，并另收24岗／8档案作新留出；原Stage19数据、标签、报告和[封存实现](../evals/baselines/stage19/README.md)保持不变。当前三组比较见[旧集回归](evaluations/stage20-regression.md)、[新集验证](evaluations/stage20-holdout.md)和[收益/退步分析](evaluations/stage20-analysis.md)。旧版和新版使用隔离进程及相同数据，技能基线须完全一致；新集出结果后未调规则或标签。

Stage21将上述两批54岗均转为开发回归，保留原始文件，新增26岗/17公司/10档案/260对标签的新留出。[Stage20归档](../evals/baselines/stage20/README.md)作为修复前，当前v3作为修复后，技能基线不变。[旧30岗](evaluations/stage21-regression19.md)、[旧24岗](evaluations/stage21-regression20.md)、[新26岗](evaluations/stage21-holdout.md)与[收益和退步](evaluations/stage21-analysis.md)分别报告，不混成一次泛化结果。

最终新集为`recommendation_quality_stage21_holdout26`；`recommendation_quality_stage21`保留首次排名前的25岗准备稿，不是另一批效果验证。原24种子、明确多模态补充岗、第三个纯负例的追加声明和原始字节均保留。追加均发生在排名前，不替换既有案例；AI产品/产品工程混合职责的金标分歧也保留，不能把它凑成纯负例。

Stage22把三批80岗均转为开发回归，另收28岗/15主体/280标签新留出。比较简单技能、[Stage21归档](../evals/baselines/stage21/README.md)、[仅学历中间归档](../evals/baselines/stage22_degree_only/README.md)、学历＋排序四组；[结果](evaluations/stage22-holdout.md)与[分析/限制](evaluations/stage22-analysis.md)区分资格恢复和排序收益。仅学历与完整版的逐岗资格、方向、完整候选集合必须完全相同，技能基线所有版本一致；验证失败时拒绝生成消融结论。

## 输入与独立性

Stage23将原四批108岗/912对标签全部作为开发回归，原文件及报告不变。新批33岗/16主体/330对标签独立标注、全量来源复核后冻结，比较简单技能、[Stage22归档](../evals/baselines/stage22/README.md)、[仅学历版](../evals/baselines/stage23_degree_only/README.md)、学历＋地点。相对于仅学历版只允许城市check变化，另外四维完整check精确相同；共同进入方向评估的岗位，方向和排序支持相同，共同保留的技能分数/命中项相同。资格分区与保留集合可以因城市修复变化。旧Stage22的严格排序消融约束继续保留，不能混用两种协议。

本轮首次输入及归档指纹见[首次运行协议](evaluations/stage23-first-run-protocol.json)，结果/逐档退步与采样缺口见[分析](evaluations/stage23-analysis.md)。初始28个查询桶含偏题结果，全部保留并事前追加5条后端职责，最终33条；实际职责覆盖可交叠，查询桶不等于方向真值。使用两种官网模板，但4条主混合工作岗位全部同院，跨主体工作形式目标未达到。新标签为AI辅助、项目内交叉复核，未独立真人验证。

当前Stage23复跑命令：

```powershell
python -m evals.recommendation_comparison `
  --dataset evals/cases/recommendation_quality_stage23 --baseline stage22 --location-phase-baseline `
  --json tmp/stage23-holdout-replay.json --markdown tmp/stage23-holdout-replay.md
```

把dataset改为`recommendation_quality_stage23_regression19/20/21/22`中某个完整目录名，可复跑对应旧批。历史Stage22归档回放使用`--dataset evals/cases/recommendation_quality_stage22 --baseline stage22 --replay-archive`，不与消融参数合用。所有运行离线且不调用真实模型。

- `data/real_jobs/stage19/` 保存官网采集器、原始响应、岗位快照和采样记录。采集过程不调用推荐规则，也不按推荐输出选择样本。
- `evals/cases/recommendation_quality/jobs.jsonl` 是经过同一导入清洗流程的固定岗位，含稳定评测编号、原文、来源和内容指纹。评测编号与个人数据库编号分开。
- `profiles.json` 的六组合成条件覆盖 AI 应用、后端、计算机视觉，各有在校与有正式经验两种档案；不是用户真实简历。
- `gold.jsonl` 对每一档案与独立岗位组合记录方向、五维资格、0–3 级相关性及逐字原文依据。相关性 2–3 表示值得进一步核对，资格待确认不自动算不可投。
- `annotation-guide.md` 与 `annotation-review.md` 记录标注规范、歧义和复核。标注完成前不运行两组真实排名，标注完成后不依据输出改规则或标签。
- `annotation-facts.json` 保留逐岗的独立事实判断；`annotation-peer-review.md` 记录另一名项目 Agent 在查看排名前对事实和硬阻断的复核。`source-review.md` 与 `source-ownership.json` 核对原始响应、转换和招聘门户归属；这些复核均不是独立真人研究。
- `algorithm_freeze.json` 校验生产规则指纹，`dataset_freeze.json` 校验数据与标签的原始文件字节。后续改进应创建新的版本及修订记录，不覆盖留出结果。
- 原始记录和冻结目录通过 Git 属性保留精确字节；算法源码仅允许 LF/CRLF 换行转换等价，不允许内容变化，保证 Windows 与 Linux 检出都能复核。生产规则改变后，旧版工具会拒绝把新算法当成旧结果；应保留对应代码状态和旧报告，另建新实验版本。

官网正文可读只证明收集到了一份招聘描述。`unknown` 状态、采集时间和系统导入时间不代表岗位仍接受投递。真实应聘前仍需核对原站。

## 公平比较

两组使用同一个固定岗位池，先隔离样例、按相同逻辑跨来源分组，并排除明确关闭的岗位。

| 方案 | 过滤与排序 |
| --- | --- |
| 简单技能 | 复用生产技能提取与覆盖率；按覆盖率、匹配数、稳定编号排序；不使用目标方向、五维投递条件和技能重要性。 |
| 当前推荐 | 调用生产 `RecommendationService`：资格、方向、核心技能、加分技能、总技能覆盖和稳定编号。 |

比较衡量整套过滤与排序的差异，不能把差异单独归因于核心技能、方向规则或模型。本流程不调用大模型、embedding 或招聘网站，不写入数据库。

当前推荐接口有展示和排除样例上限。评测对分组后的同一主快照逐岗重放，恢复完整保留/排除集合，再核对其前五名与全批接口一致；不把展示上限之外的相关岗位误算成被过滤。

## 运行

在项目根目录使用 Python 虚拟环境：

```powershell
.venv/Scripts/python.exe -X utf8 -m evals.recommendation_comparison `
  --dataset evals/cases/recommendation_quality_stage22 --baseline stage21 --degree-only-baseline `
  --json tmp/stage22-holdout-replay.json `
  --markdown tmp/stage22-holdout-replay.md
```

JSON 保存完整排名、全部判断、混淆矩阵、失败案例和输入指纹；Markdown 用于阅读对照。报告写在冻结输入目录之外。

将dataset改为`evals/cases/recommendation_quality_stage22_regression19`、`recommendation_quality_stage22_regression20`或`recommendation_quality_stage22_regression21`，保持`--baseline stage21 --degree-only-baseline`，可复跑三批旧数据的四组回归。默认基线仍为Stage19以兼容旧调用；各历史阶段须选各自修复前实现，不能混称。当前应用直接加载旧原始算法清单会拒绝；回放原始Stage19使用：

```powershell
.venv/Scripts/python.exe -X utf8 -m evals.recommendation_comparison `
  --dataset evals/cases/recommendation_quality --replay-archive `
  --json tmp/stage19-replay.json --markdown tmp/stage19-replay.md
```

回放原始Stage20：dataset使用`recommendation_quality_stage20`，带`--baseline stage20 --replay-archive`。回放原始Stage21：dataset使用`recommendation_quality_stage21_holdout26`，带`--baseline stage21 --replay-archive`。历史回放不带`--degree-only-baseline`。默认、修复前与仅学历三个算法清单分别冻结，实际导入位置及80源码指纹各自校验。

数据准备及首次冻结（标签完成后才执行冻结）：

下例保留Stage21通用准备流程作为历史示例。Stage22已打包独立盲标输入和与快照逐字段相同的手动导入文件，不用新的采集时间/重新准备结果覆盖冻结快照；复现使用上面的冻结输入命令。新采集或修订另建版本目录。来源采样、路由更正、原始响应及审核JSON也纳入本轮指纹链。

```powershell
.venv/Scripts/python.exe -m evals.real_job_snapshot prepare `
  --source data/real_jobs/stage21/holdout26/jobs.json `
  --dataset evals/cases/recommendation_quality_stage21_holdout26

.venv/Scripts/python.exe -m evals.real_job_snapshot freeze `
  --dataset evals/cases/recommendation_quality_stage21_holdout26
```

再次准备/冻结只允许完全相同的文件；输入改变需要新版本目录。

## 阅读指标

- **P@5**：前五个位置中相关性至少 2 的数量除以 5；少返回的空位计零，不能靠少返回提高指标。
- **nDCG@5**：相关性按 `2^relevance-1` 计增益，并考虑排名位置；无任何非零金标增益的档案为 N/A，单列分母。
- **明确错误**：前五名中金标方向明确不符或五维资格明确不符合的岗位；同时报告返回条数与固定位置数。
- **值得核对岗位误排除**：金标相关性至少 2、没有已知资格阻断、方向非明确无关，却未进入系统完整保留集合的岗位。待确认与五项全符合分别保留统计；这不代表所有招聘条件已满足。
- **三态一致性**：当前系统与金标在五维和整体资格上的比较，包含所有待确认及混淆矩阵；简单技能组不提供资格判断，记 N/A。
- **方向已判断覆盖**：生产流程会在明确资格阻断后短路，未执行方向判断的岗位不能冒称方向判对。
- **方向错误硬排**：分别统计金标aligned和uncertain被硬排；分母只含已实际评估方向的相应金标，资格短路另列。不能把“少排除”直接解释为全部判断准确。
- **待确认代价**：记录完整候选池保留待确认的总数、其中相关性低于2的比例及金标明确无关的数量；同时记录金标明确无关的硬排召回，防止全判待确认掩盖噪声。

每份档案都应查看原始排名与错误，而不只看总体均值。这批目的性采样与六组合成条件不足以估计全部求职人群表现；后续仍需跨公司/时间扩充与真人复核。

## 导入个人岗位库

使用显式数据库路径，默认只在隔离副本预览，检查重复导入的 ID 和正文稳定性：

```powershell
.venv/Scripts/python.exe -m evals.real_job_snapshot import `
  --dataset evals/cases/recommendation_quality_stage22 `
  --database D:/AI-Project/internscout-agent/internscout.db
```

加 `--apply` 才写入该本地数据库，写入前先做 SQLite 一致备份。该工具只负责新增这批冻结岗位与相同内容的重复导入；已存在同 URL 的不同正文应通过原手动更新入口处理。导入的系统观察时间与冻结数据的官网采集时间分开保留。

导入期间应保持单一写入者。工具会核对预览与写入前的数据指纹，但现有逐条提交工作流不保证整个批次的并发原子性；异常时保留备份供检查，不自动覆盖恢复个人数据库。
