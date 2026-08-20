from datetime import date, datetime

import pytest

from app.matching.contracts import JobSkillEvidence
from app.matching.skill_extractor import (
    TEXT_SKILL_ALIASES,
    JobSkillExtractor,
)
from app.schemas.job_response import JobRead
from app.services.skill_vocabulary import SKILL_ALIASES


def make_job(**overrides: object) -> JobRead:
    data: dict[str, object] = {
        "id": 1,
        "title": "产品实习生",
        "company": "示例科技",
        "city": "深圳",
        "salary": None,
        "description": "负责产品调研与需求分析。",
        "skills": [],
        "source": "mock",
        "source_url": "https://example.com/jobs/1",
        "published_at": date(2026, 8, 1),
        "created_at": datetime(2026, 8, 1, 10, 0),
    }
    data.update(overrides)
    return JobRead(**data)


def extract_skills(**overrides: object) -> list[str]:
    return JobSkillExtractor().extract(
        make_job(**overrides)
    ).skills


def test_text_aliases_are_backed_by_shared_vocabulary() -> None:
    assert "requests" not in TEXT_SKILL_ALIASES
    assert len(TEXT_SKILL_ALIASES) == len(set(TEXT_SKILL_ALIASES))
    assert set(TEXT_SKILL_ALIASES) == set(SKILL_ALIASES) - {
        "requests"
    }


def test_structured_skills_normalize_preserve_and_deduplicate() -> None:
    evidence = JobSkillExtractor().extract(
        make_job(
            skills=[
                "python",
                "Kubernetes",
                "PYTHON",
                "   ",
                "requests",
            ]
        )
    )

    assert evidence == JobSkillEvidence(
        skills=["Python", "Kubernetes", "Requests"]
    )


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Python开发实习生", ["Python"]),
        ("熟悉fAsTaPi的实习生", ["FastAPI"]),
        ("Python（FastAPI）开发", ["Python", "FastAPI"]),
        ("SQL/NoSQL开发", ["SQL"]),
        ("Python-FastAPI开发", ["Python", "FastAPI"]),
        ("RAG系统与LLM应用", ["RAG", "LLM"]),
        ("pytest-cov实践", ["pytest"]),
    ],
)
def test_title_extraction(
    title: str,
    expected: list[str],
) -> None:
    assert extract_skills(title=title) == expected


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("参与Docker部署。", ["Docker"]),
        (
            "先使用Docker，再用python和SQL；最后维护DOCKER。",
            ["Docker", "Python", "SQL"],
        ),
        (
            "具备HTTP接口、pytest经验和HTML解析能力。",
            ["HTTP", "pytest", "HTML"],
        ),
    ],
)
def test_description_extraction(
    description: str,
    expected: list[str],
) -> None:
    assert extract_skills(description=description) == expected


@pytest.mark.parametrize(
    "description",
    [
        "beautiful soup经验",
        "Beautiful Soup经验",
        "beautiful   soup经验",
        "BeautifulSoup经验",
        "beautifulsoup4经验",
        "bs4经验",
    ],
)
def test_beautiful_soup_aliases_use_flexible_whitespace(
    description: str,
) -> None:
    assert extract_skills(
        description=description
    ) == ["Beautiful Soup"]


def test_arbitrary_punctuation_does_not_replace_alias_space() -> None:
    assert extract_skills(
        description="beautiful-soup经验"
    ) == []


def test_requests_is_not_detected_in_ordinary_prose() -> None:
    assert extract_skills(
        description="The role handles ordinary requests from users."
    ) == []


def test_combined_sources_follow_frozen_precedence() -> None:
    assert extract_skills(
        skills=["Unknown", "sql"],
        title="Python/FastAPI开发实习生",
        description="SQL、Python、Docker和RAG经验",
    ) == [
        "Unknown",
        "SQL",
        "Python",
        "FastAPI",
        "Docker",
        "RAG",
    ]


def test_zero_evidence_is_a_normal_result() -> None:
    assert JobSkillExtractor().extract(
        make_job()
    ) == JobSkillEvidence(skills=[])


def test_oppo_shaped_description_detects_only_supported_evidence() -> None:
    description = (
        "岗位职责：\n"
        "负责 AI 产品调研、需求分析与方案设计。\n\n"
        "任职要求：\n"
        "了解大模型、Prompt、RAG 或 Agent 等相关概念。"
    )

    assert extract_skills(
        title="AI产品实习生",
        description=description,
        skills=[],
    ) == ["RAG"]


@pytest.mark.parametrize(
    "text",
    [
        "NoSQL",
        "SQLAlchemy",
        "github",
        "digital",
        "HTTPServer",
        "HTML5",
        "python3",
        "ragged",
        "storage",
        "shellscript",
        "my_python_module",
    ],
)
def test_ascii_identifier_boundaries_prevent_false_positives(
    text: str,
) -> None:
    assert extract_skills(description=text) == []


def test_non_evidence_job_fields_are_ignored() -> None:
    assert extract_skills(
        company="Python FastAPI",
        city="SQL",
        salary="Docker",
        source="linux",
        source_url="https://example.com/http",
        published_at=date(2026, 8, 20),
        created_at=datetime(2026, 8, 20, 12, 0),
    ) == []


def test_extraction_is_repeatable_and_uses_textual_order() -> None:
    extractor = JobSkillExtractor()
    job = make_job(
        title="Docker、Python与SQL实习生",
        description="RAG系统使用FastAPI和Docker。",
    )

    first = extractor.extract(job)
    second = extractor.extract(job)

    assert first == second
    assert first.skills == [
        "Docker",
        "Python",
        "SQL",
        "RAG",
        "FastAPI",
    ]
