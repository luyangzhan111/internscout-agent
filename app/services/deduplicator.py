"""岗位数据唯一标识与去重。"""

from app.schemas.job import JobCreate
from app.services.cleaner import normalize_city


JobIdentity = tuple[str, str, str]


def normalize_identity_text(value: str) -> str:
    """清理用于身份比较的文本，并忽略大小写差异。"""

    return " ".join(value.split()).casefold()


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


def deduplicate_jobs(jobs: list[JobCreate]) -> list[JobCreate]:
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