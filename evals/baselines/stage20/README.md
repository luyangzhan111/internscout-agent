# Stage20 原始应用基线

在Stage21方向规则修改前保存80个应用源文件及Stage20原始算法清单。归档与逐文件指纹见`manifest.json`；`application.zip` SHA-256为`99b8703f49fafc643823d8d94d5153de4c72f28a7161fdb39d4c8199f2e3b559`。

原24岗/192对标签及报告保留原始字节，之后作为开发回归。隔离执行器验证归档及实际导入位置、禁止网络；Stage21三组比较选用`--baseline stage20`，技能基线必须完全相同。

```powershell
.venv/Scripts/python.exe -X utf8 -m evals.recommendation_comparison `
  --dataset evals/cases/recommendation_quality_stage20 --baseline stage20 --replay-archive `
  --json tmp/stage20-replay.json --markdown tmp/stage20-replay.md
```

这份历史实现仅供评测，不接入在线服务。不要替换归档或原冻结数据。
