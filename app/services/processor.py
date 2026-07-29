"""岗位数据清洗和去重处理管道。"""

from app.schemas.job import JobCreate
from app.services.cleaner import clean_job
from app.services.deduplicator import deduplicate_jobs


def process_jobs(jobs: list[JobCreate]) -> list[JobCreate]:
    """依次清洗岗位数据，并过滤重复岗位。"""

    cleaned_jobs = [
        clean_job(job)
        for job in jobs
    ]

    return deduplicate_jobs(cleaned_jobs)
