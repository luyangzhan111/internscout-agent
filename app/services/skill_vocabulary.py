"""Shared canonical skill vocabulary and normalization."""


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


def normalize_skill(skill: str) -> str:
    """将单个技能名称转换为统一展示形式。"""

    normalized = " ".join(skill.split())

    if not normalized:
        return ""

    return SKILL_ALIASES.get(
        normalized.casefold(),
        normalized,
    )


def normalize_skills(
    skills: list[str],
) -> list[str]:
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
