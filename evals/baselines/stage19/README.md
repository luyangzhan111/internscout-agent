# Stage19 原始应用基线

`application.zip` 在任何 Stage20 规则修改前保存了 Stage19 的80个 `app/**/*.py` 文件和原 `algorithm_freeze.json`。归档及每文件的 SHA-256 见 `manifest.json`；外层归档指纹为 `87f67b89fc9bcc6bb0968470b3900b4a3c657d91ed2368c519baab853131e278`。

这是项目已有应用的历史实现，保留用于旧结果回放和同批新岗位上的修复前后比较。它不接入在线服务，也不替代当前 `app/`。旧30岗和原报告仍保留在原位置，之后作为开发回归数据。

`evals.recommendation_comparison` 检查归档、路径和每个源码指纹后，在项目临时目录解包，使用禁止网络的新进程优先导入该 `app`。CLI再次核对实际导入位置，运行前再校验实现指纹；数据与金标不得改变，技能基线必须与新版完全相同。

原始结果回放（无需模型、网络或个人数据库）：

```powershell
.venv/Scripts/python.exe -X utf8 -m evals.recommendation_comparison `
  --dataset evals/cases/recommendation_quality --replay-archive `
  --json tmp/stage19-replay.json --markdown tmp/stage19-replay.md
```

两版本对照与限制见 [评测说明](../../../docs/recommendation-evaluation.md)。归档和清单保持原始字节；不要将新的规则写入此目录或替换旧归档。
