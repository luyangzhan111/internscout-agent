"""服务健康检查API响应模型。"""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """服务和数据库均正常时的健康检查响应。"""

    status: Literal["ok"]
    database: Literal["ok"]
