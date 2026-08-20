"""岗位数据清洗与标准化。"""

from app.schemas.job import JobCreate
from app.services.skill_vocabulary import (
    SKILL_ALIASES,
    normalize_skill,
    normalize_skills,
)


# 只标准化当前项目明确支持的城市，未知名称原样保留。
CITY_ALIASES: dict[str, str] = {
    "北京市": "北京",
    "上海市": "上海",
    "天津市": "天津",
    "重庆市": "重庆",
    "深圳市": "深圳",
    "广州市": "广州",
    "东莞市": "东莞",
}

def normalize_company(company: str) -> str:
    """删除公司名称首尾空白，并合并连续空白。"""

    return " ".join(company.split())


def normalize_city(city: str) -> str:
    """标准化已知城市别名，未知城市名称保持不变。"""

    normalized = " ".join(city.split())

    return CITY_ALIASES.get(
        normalized,
        normalized,
    )


def clean_job(job: JobCreate) -> JobCreate:
    """返回经过重新验证的清洗后岗位，不修改原始对象。"""

    job_data = job.model_dump()
    job_data.update(
        {
            "company": normalize_company(
                job.company
            ),
            "city": normalize_city(
                job.city
            ),
            "skills": normalize_skills(
                job.skills
            ),
        }
    )

    return JobCreate.model_validate(job_data)
