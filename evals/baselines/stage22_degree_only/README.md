# Stage22 仅学历修复对照

本归档在学历修复完成、任何排序与应用接入修改前保存80个应用文件。与Stage21相比只有`app/eligibility/extractor.py`和`evaluator.py`改变；资格版本为`stage22-rules-v1`，排序仍为Stage21的v3。

归档SHA-256为`f629219664249f5a737f7a08b0c48ab49b79200541fe085be84f372650b60746`。原始清单与逐文件指纹见`algorithm_freeze.json`和`manifest.json`。这是离线消融对照，不是线上第三套产品。

Stage22比较使用`--baseline stage21 --degree-only-baseline`，输入目录必须冻结`degree_only_algorithm_freeze.json`。评测自动核对仅学历版与完整版的资格、方向、完整候选保留集合完全相同；排序只改变顺序和排序解释。
