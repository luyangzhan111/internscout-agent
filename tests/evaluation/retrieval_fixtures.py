"""Offline semantic fixtures for direct retrieval evaluation.

These fixtures deliberately live under ``tests/evaluation``.  They are a
small, repository-specific semantic proxy for evaluation and are not a
production embedding implementation.
"""

from datetime import date, datetime
import re

from app.rag.embedding import EmbeddingProvider
from app.rag.retriever import JobKnowledgeRetriever
from app.rag.vector_store import InMemoryVectorStore
from app.schemas.job_response import JobRead


class ControlledEmbeddingProvider(EmbeddingProvider):
    """Map text evidence to a deterministic six-axis concept vector.

    The provider only receives text.  Each dimension is the deterministic sum
    of weights for role-specific aliases found in that text.  Generic terms
    such as ``Python`` and ``测试`` are intentionally excluded because they
    occur across several sample jobs.
    """

    CONCEPT_AXES = (
        "backend_api",
        "automated_testing",
        "data_crawling",
        "devops",
        "ai_rag_agent",
        "functional_testing",
    )

    CONCEPT_ALIASES: dict[str, tuple[tuple[str, float], ...]] = {
        "backend_api": (
            ("fastapi", 1.0),
            ("api", 1.0),
            ("后端", 1.0),
            ("数据库", 1.0),
            ("接口开发", 1.0),
        ),
        "automated_testing": (
            ("pytest", 1.0),
            ("接口自动化测试", 1.0),
            ("自动化测试", 1.0),
        ),
        "data_crawling": (
            ("网页", 1.0),
            ("采集", 1.0),
            ("数据采集", 1.0),
            ("html", 1.0),
            ("html解析", 1.0),
            ("解析", 1.0),
            ("数据清洗", 1.0),
        ),
        "devops": (
            ("linux", 1.0),
            ("docker", 1.0),
            ("ci", 1.0),
            ("部署", 1.0),
            ("devops", 1.0),
        ),
        "ai_rag_agent": (
            ("大模型", 1.0),
            ("工具调用", 1.0),
            ("rag", 1.0),
            ("llm", 1.0),
            ("agent", 1.0),
        ),
        "functional_testing": (
            ("功能测试", 1.0),
            ("接口验证", 1.0),
            ("回归测试", 1.0),
            ("软件测试", 1.0),
            ("缺陷记录", 1.0),
        ),
    }

    @property
    def dimensions(self) -> int:
        """Return the fixed vector size required by the embedding contract."""

        return len(self.CONCEPT_AXES)

    def embed(self, text: str) -> list[float]:
        """Return a vector derived solely from normalized text evidence."""

        self._validate_text(text)
        normalized_text = text.casefold()
        return [
            float(
                sum(
                    weight
                    for alias, weight in self.CONCEPT_ALIASES[concept]
                    if self._alias_matches(alias, normalized_text)
                )
            )
            for concept in self.CONCEPT_AXES
        ]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed each input text in its original order."""

        if not isinstance(texts, list):
            raise TypeError("texts must be a list of strings.")
        return [self.embed(text) for text in texts]

    @staticmethod
    def _validate_text(text: str) -> None:
        if not isinstance(text, str):
            raise TypeError("text must be a string.")
        if not text.strip():
            raise ValueError("text cannot be blank.")

    @staticmethod
    def _alias_matches(alias: str, normalized_text: str) -> bool:
        """Match ASCII aliases as tokens while keeping Chinese substring matching."""

        if alias.isascii() and alias.isalnum():
            pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
            return re.search(pattern, normalized_text) is not None
        return alias in normalized_text


def build_evaluation_jobs() -> list[JobRead]:
    """Return six explicit, stable-ID jobs matching the local sample page."""

    fixture_date = date(2026, 7, 20)
    created_at = datetime(2026, 7, 20, 0, 0, 0)
    return [
        JobRead(
            id=1,
            title="Python后端实习生",
            company="星河科技",
            city="深圳市",
            salary="150-200元/天",
            description="负责FastAPI后端接口开发，参与数据库设计和接口测试。",
            skills=["Python", "FastAPI", "SQL", "Git"],
            source="mock",
            source_url="https://example.invalid/jobs/001",
            published_at=fixture_date,
            created_at=created_at,
        ),
        JobRead(
            id=2,
            title="自动化测试实习生",
            company="云帆软件",
            city="广州市",
            salary="120-180元/天",
            description="使用Pytest完成接口自动化测试，并维护测试数据。",
            skills=["Python", "Pytest", "HTTP", "SQL"],
            source="mock",
            source_url="https://example.invalid/jobs/002",
            published_at=date(2026, 7, 19),
            created_at=created_at,
        ),
        JobRead(
            id=3,
            title="数据采集实习生",
            company="启明数据",
            city="上海市",
            salary="180-220元/天",
            description="负责公开网页数据采集、HTML解析、数据清洗和去重。",
            skills=["Python", "Requests", "BeautifulSoup", "SQL"],
            source="mock",
            source_url="https://example.invalid/jobs/003",
            published_at=date(2026, 7, 18),
            created_at=created_at,
        ),
        JobRead(
            id=4,
            title="DevOps实习生",
            company="智云网络",
            city="深圳",
            salary="160-200元/天",
            description="参与Linux服务器维护、Docker部署和CI流程建设。",
            skills=["Linux", "Docker", "Git", "Shell"],
            source="mock",
            source_url="https://example.invalid/jobs/004",
            published_at=date(2026, 7, 17),
            created_at=created_at,
        ),
        JobRead(
            id=5,
            title="AI应用开发实习生",
            company="拓界智能",
            city="北京市",
            salary="200-300元/天",
            description="参与大模型应用、工具调用和RAG检索功能开发。",
            skills=["Python", "FastAPI", "LLM", "RAG"],
            source="mock",
            source_url="https://example.invalid/jobs/005",
            published_at=date(2026, 7, 16),
            created_at=created_at,
        ),
        JobRead(
            id=6,
            title="软件测试实习生",
            company="海纳信息",
            city="东莞市",
            salary=None,
            description="负责功能测试、接口验证、缺陷记录和回归测试。",
            skills=["软件测试", "Postman", "SQL"],
            source="mock",
            source_url="https://example.invalid/jobs/006",
            published_at=date(2026, 7, 15),
            created_at=created_at,
        ),
    ]


def build_controlled_retriever(
    jobs: list[JobRead] | None = None,
) -> JobKnowledgeRetriever:
    """Build the production retriever over the explicit offline fixtures."""

    retriever = JobKnowledgeRetriever(
        embedding_provider=ControlledEmbeddingProvider(),
        vector_store=InMemoryVectorStore(),
    )
    retriever.index_jobs(build_evaluation_jobs() if jobs is None else jobs)
    return retriever
