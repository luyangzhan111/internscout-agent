"""岗位数据采集模块。"""

from app.crawlers.base import BaseJobCrawler
from app.crawlers.mock_crawler import MockJobCrawler

__all__ = [
    "BaseJobCrawler",
    "MockJobCrawler",
]