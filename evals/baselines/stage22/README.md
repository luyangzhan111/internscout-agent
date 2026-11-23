# Stage22应用归档

Stage23开发前保存的80个应用源码文件及原始算法清单。ZIP SHA-256：`da6133ce28b6f6f1c13f75c0b61af7ecbeedf68f0cd720bce1811e7694636f48`。

原始清单来自`recommendation_quality_stage22/algorithm_freeze.json`，SHA-256为`5d39106d170abb2b2b2bc0a6721f8a2f5ddd92b6d1d6a268e1c292b58fe5b758`。资格版本`stage22-rules-v1`，排序版本`direction-support-v4`。隔离回放时先验证归档、清单及每个成员的字节；运行进程禁用网络。

历史回放：`python -m evals.recommendation_comparison --dataset evals/cases/recommendation_quality_stage22 --baseline stage22 --replay-archive --json tmp/stage22-replay.json --markdown tmp/stage22-replay.md`。
