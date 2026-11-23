# Stage21 修复前应用

在任何Stage22学历/排序修改前保存80个应用源码和原算法清单，归档SHA-256为`f2ddc0d50c473246e6b7d4dcb2f2afbbaee4386732333e351ee076195733e578`，逐文件指纹见`manifest.json`。

原26岗/260对标签与报告继续保留，Stage22将它连同此前两批80岗作为开发回归。当前应用已不应当作Stage21历史实现运行，使用隔离归档回放：

```powershell
.venv/Scripts/python.exe -X utf8 -m evals.recommendation_comparison `
  --dataset evals/cases/recommendation_quality_stage21_holdout26 --baseline stage21 --replay-archive `
  --json tmp/stage21-replay.json --markdown tmp/stage21-replay.md
```

归档不接线上服务。Stage22另存仅学历修复中间版本，四组对照区分资格修复与排序变化；不得覆盖本归档或历史金标。
