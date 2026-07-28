"""所有岗位爬虫共同遵循的接口。"""

from abc import ABC, abstractmethod

from app.schemas.job import JobCreate


class BaseJobCrawler(ABC):
    """岗位爬虫的抽象基类。"""

    @abstractmethod
    def fetch_jobs(self) -> list[JobCreate]:
        """采集岗位并返回统一的岗位数据模型。"""
        raise NotImplementedError