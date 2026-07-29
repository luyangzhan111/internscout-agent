"""岗位数据清洗与标准化。"""

from app.schemas.job import JobCreate


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

# 这里保存面向用户展示的技能规范名称。
SKILL_ALIASES: dict[str, str] = {
    "python": "Python",
    "fastapi": "FastAPI",
    "sql": "SQL",
    "git": "Git",
    "pytest": "pytest",
    "http": "HTTP",
    "html": "HTML",
    "requests": "Requests",
    "beautifulsoup": "Beautiful Soup",
    "beautiful soup": "Beautiful Soup",
    "beautifulsoup4": "Beautiful Soup",
    "bs4": "Beautiful Soup",
    "docker": "Docker",
    "linux": "Linux",
    "shell": "Shell",
    "postman": "Postman",
    "llm": "LLM",
    "rag": "RAG",
}


def normalize_city(city: str) -> str:
    """标准化已知城市别名，未知城市名称保持不变。"""

    normalized = " ".join(city.split())

    return CITY_ALIASES.get(normalized, normalized)


def normalize_skill(skill: str) -> str:
    """将单个技能名称转换为统一展示形式。"""

    normalized = " ".join(skill.split())

    if not normalized:
        return ""

    return SKILL_ALIASES.get(
        normalized.casefold(),
        normalized,
    )


def normalize_skills(skills: list[str]) -> list[str]:
    """标准化技能列表，并在保持顺序的情况下去重。"""

    normalized_skills: list[str] = []
    seen: set[str] = set()

    for skill in skills:
        normalized = normalize_skill(skill)

        if not normalized:
            continue

        identity = normalized.casefold()

        if identity in seen:
            continue

        seen.add(identity)
        normalized_skills.append(normalized)

    return normalized_skills


def clean_job(job: JobCreate) -> JobCreate:
    """返回经过重新验证的清洗后岗位，不修改原始对象。"""

    job_data = job.model_dump()
    job_data.update(
        {
            "city": normalize_city(job.city),
            "skills": normalize_skills(job.skills),
        }
    )

    return JobCreate.model_validate(job_data)
