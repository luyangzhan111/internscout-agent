"""Transform job response models into searchable documents."""

from app.rag.contracts import JobDocument
from app.schemas.job_response import JobRead


def build_job_document(job: JobRead) -> JobDocument:
    """Build a deterministic document without mutating the source job."""

    skills = ", ".join(job.skills)
    description = job.description or ""
    content = "\n".join(
        [
            f"Title: {job.title}",
            f"Company: {job.company}",
            f"City: {job.city}",
            f"Skills: {skills}",
            f"Description: {description}",
        ]
    )

    return JobDocument(
        id=job.id,
        content=content,
        metadata={
            "job_id": job.id,
            "company": job.company,
            "city": job.city,
        },
    )
