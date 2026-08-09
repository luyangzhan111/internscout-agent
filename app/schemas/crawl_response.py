"""岗位采集API响应模型。"""

from pydantic import BaseModel, Field


class CrawlResponse(BaseModel):
    """岗位采集任务响应。"""

    processed_count: int = Field(
        ge=0,
        description="本次采集、清洗和去重后处理的岗位数量",
    )

    database_total: int = Field(
        ge=0,
        description="采集完成后的数据库岗位总数",
    )
