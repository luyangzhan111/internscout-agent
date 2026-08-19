"""Network-free integration test for OPPO job ingestion."""

from collections.abc import Generator, Sequence
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.crawlers.oppo_crawler import OppoJobCrawler
from app.crawlers.oppo_source_client import (
    OppoPositionDetail,
    OppoPositionPage,
    OppoPositionSummary,
)
from app.database import (
    create_database_engine,
    create_session_factory,
    init_database,
    list_jobs,
)
from app.workflows import ingest_jobs


POSITION_ID = "2061649545671430146"
SOURCE_URL = (
    "https://career.oppo.com/official/oppo/recruitment/post/"
    f"{POSITION_ID}?recruitType=OFFEN-RECRUITMENT"
)
DESCRIPTION = (
    "岗位职责：\n"
    "负责 AI 产品调研、需求分析与方案设计。\n\n"
    "任职要求：\n"
    "了解大模型、Prompt、RAG 或 Agent 等相关概念。"
)


class FakeOppoJobSourceClient:
    """Return one real-source-shaped position without using HTTP."""

    def search_positions(
        self,
        *,
        page_num: int,
        page_size: int,
        recruit_types: Sequence[str] = (),
        keyword: str = "",
        city_codes: Sequence[str] = (),
        job_types: Sequence[str] = (),
        share_id: str = "",
    ) -> OppoPositionPage:
        """Return the single deterministic discovery page."""

        return OppoPositionPage(
            page_num=page_num,
            page_size=page_size,
            pages=1,
            total=1,
            positions=(
                OppoPositionSummary(position_id=POSITION_ID),
            ),
        )

    def get_position_detail(
        self,
        position_id: str,
    ) -> OppoPositionDetail:
        """Return typed detail data for the discovered position."""

        assert position_id == POSITION_ID
        return OppoPositionDetail(
            position_id=position_id,
            publish_name="AI产品实习生",
            publish_date=date(2026, 6, 1),
            recruit_type="OFFEN-RECRUITMENT",
            work_city_name="东莞市",
            job_duty="负责 AI 产品调研、需求分析与方案设计。",
            work_require=(
                "了解大模型、Prompt、RAG 或 Agent 等相关概念。"
            ),
        )


@pytest.fixture
def database_session(
    tmp_path: Path,
) -> Generator[Session, None, None]:
    """Create an isolated temporary SQLite session."""

    database_path = tmp_path / "oppo-ingestion-test.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    engine = create_database_engine(database_url)
    init_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        yield session

    engine.dispose()


def test_oppo_crawler_flows_through_existing_ingestion_pipeline(
    database_session: Session,
) -> None:
    """OPPO data is cleaned, persisted, and idempotent in the old pipeline."""

    source_client = FakeOppoJobSourceClient()
    crawler = OppoJobCrawler(source_client)  # type: ignore[arg-type]

    first_result = ingest_jobs(crawler, database_session)
    second_result = ingest_jobs(crawler, database_session)
    stored_jobs = list_jobs(database_session)

    assert len(first_result) == 1
    assert len(second_result) == 1
    assert second_result[0].id == first_result[0].id
    assert len(stored_jobs) == 1

    stored_job = stored_jobs[0]
    assert stored_job.title == "AI产品实习生"
    assert stored_job.company == "OPPO"
    assert stored_job.city == "东莞"
    assert stored_job.salary is None
    assert stored_job.description == DESCRIPTION
    assert stored_job.skills == []
    assert stored_job.source == "oppo"
    assert stored_job.source_url == SOURCE_URL
    assert stored_job.published_at == date(2026, 6, 1)
