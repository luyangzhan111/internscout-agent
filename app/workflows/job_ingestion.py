"""岗位采集、处理与持久化工作流。"""

from typing import Protocol

from sqlalchemy.orm import Session

from app.database.models import JobModel
from app.database.repository import save_jobs
from app.schemas.job import JobCreate
from app.services.processor import process_jobs


class JobCrawlerProtocol(Protocol):
    """岗位爬虫需要满足的最小接口。"""

    def fetch_jobs(self) -> list[JobCreate]:
        """获取经过模型验证的原始岗位列表."""


def ingest_jobs(
    crawler: JobCrawlerProtocol,
    session: Session,
) -> list[JobModel]:
    """
    抓取、清洗、去重并保存岗位。

    返回本次输入所对应的数据库岗位记录。
    已存在的重复岗位会返回原数据库记录，而不会重复插入。
    """

    raw_jobs = crawler.fetch_jobs()
    processed_jobs = process_jobs(raw_jobs)

    return save_jobs(
        session,
        processed_jobs,
    )
