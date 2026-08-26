from datetime import date, datetime

from app.rag.document import build_job_document
from app.schemas.job_response import JobRead


def make_job(**overrides: object) -> JobRead:
    data: dict[str, object] = {
        "id": 1,
        "title": "Python Backend Intern",
        "company": "Example Tech",
        "city": "Shenzhen",
        "salary": None,
        "description": "Build and maintain backend APIs.",
        "skills": ["Python", "FastAPI"],
        "source": "mock",
        "source_url": "https://example.com/jobs/1",
        "published_at": date(2026, 8, 1),
        "created_at": datetime(2026, 8, 1, 10, 0),
    }
    data.update(overrides)
    return JobRead(**data)


def test_build_job_document_includes_all_searchable_fields() -> None:
    job = make_job()

    document = build_job_document(job)

    assert document.content == (
        "Title: Python Backend Intern\n"
        "Company: Example Tech\n"
        "City: Shenzhen\n"
        "Skills: Python, FastAPI\n"
        "Description: Build and maintain backend APIs."
    )


def test_build_job_document_sets_metadata() -> None:
    job = make_job()

    document = build_job_document(job)

    assert document.id == job.id
    assert document.metadata == {
        "job_id": job.id,
        "company": job.company,
        "city": job.city,
    }


def test_build_job_document_handles_empty_description() -> None:
    document = build_job_document(make_job(description=""))

    assert document.content.endswith("Description: ")


def test_build_job_document_handles_empty_skills() -> None:
    document = build_job_document(make_job(skills=[]))

    assert "\nSkills: \n" in document.content


def test_build_job_document_does_not_modify_job() -> None:
    job = make_job()
    original = job.model_dump()

    build_job_document(job)

    assert job.model_dump() == original
