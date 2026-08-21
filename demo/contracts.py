"""Public response models consumed by the Streamlit demo."""

from pydantic import BaseModel, ConfigDict, Field


class DemoJob(BaseModel):
    """Job fields needed to render one recommendation card."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    city: str = Field(min_length=1)
    salary: str | None = None
    source_url: str | None = None


class DemoRecommendation(BaseModel):
    """Structured recommendation data exposed by the Backend API."""

    model_config = ConfigDict(extra="ignore")

    job: DemoJob
    match_score: int = Field(ge=0, le=100)
    matched_skills: list[str]
    missing_skills: list[str]
    reason: str = Field(min_length=1)


class DemoAgentResponse(BaseModel):
    """Stable response contract used by the Demo HTTP boundary."""

    model_config = ConfigDict(extra="ignore")

    answer: str = Field(min_length=1)
    steps: int = Field(ge=0)
    tool_execution_count: int = Field(ge=0)
    recommendations: list[DemoRecommendation] | None = None
