import pytest
from pydantic import ValidationError

from app.rag.contracts import JobDocument


def test_job_document_can_be_created() -> None:
    document = JobDocument(
        id=1,
        content="Title: Python Intern",
        metadata={
            "job_id": 1,
            "company": "Example Tech",
            "city": "Shenzhen",
        },
    )

    assert document.id == 1
    assert document.content == "Title: Python Intern"
    assert document.metadata == {
        "job_id": 1,
        "company": "Example Tech",
        "city": "Shenzhen",
    }


@pytest.mark.parametrize("missing_field", ["id", "content", "metadata"])
def test_job_document_requires_all_fields(missing_field: str) -> None:
    data: dict[str, object] = {
        "id": 1,
        "content": "Title: Python Intern",
        "metadata": {"job_id": 1},
    }
    del data[missing_field]

    with pytest.raises(ValidationError):
        JobDocument(**data)


def test_job_document_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        JobDocument(
            id=1,
            content="Title: Python Intern",
            metadata={"job_id": 1},
            embedding=[0.1, 0.2],
        )
