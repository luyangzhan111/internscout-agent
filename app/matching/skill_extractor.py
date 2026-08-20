"""Deterministic canonical skill extraction from stored jobs."""

import re

from app.matching.contracts import JobSkillEvidence
from app.schemas.job_response import JobRead
from app.services.skill_vocabulary import (
    SKILL_ALIASES,
    normalize_skills,
)


# Free-text detection is deliberately narrower than explicit normalization.
# Canonical display values continue to come exclusively from SKILL_ALIASES.
TEXT_SKILL_ALIASES: tuple[str, ...] = (
    "python",
    "fastapi",
    "sql",
    "git",
    "pytest",
    "http",
    "html",
    "beautifulsoup",
    "beautiful soup",
    "beautifulsoup4",
    "bs4",
    "docker",
    "linux",
    "shell",
    "postman",
    "llm",
    "rag",
)


def _compile_alias_pattern(alias: str) -> re.Pattern[str]:
    """Compile one escaped alias with strict ASCII identifier boundaries."""

    escaped_alias = r"\s+".join(
        re.escape(token) for token in alias.split()
    )
    return re.compile(
        rf"(?<![A-Za-z0-9_])(?i:{escaped_alias})"
        rf"(?![A-Za-z0-9_])"
    )


_TEXT_SKILL_PATTERNS: tuple[
    tuple[str, re.Pattern[str]], ...
] = tuple(
    (alias, _compile_alias_pattern(alias))
    for alias in TEXT_SKILL_ALIASES
)


def _detect_text_skills(text: str) -> list[str]:
    """Return canonical detections ordered by their first text occurrence."""

    matches: list[tuple[int, int, int, str]] = []

    for declaration_order, (alias, pattern) in enumerate(
        _TEXT_SKILL_PATTERNS
    ):
        canonical_skill = SKILL_ALIASES[alias]

        for match in pattern.finditer(text):
            matches.append(
                (
                    match.start(),
                    -(match.end() - match.start()),
                    declaration_order,
                    canonical_skill,
                )
            )

    matches.sort(key=lambda match: match[:3])

    return normalize_skills(
        [match[3] for match in matches]
    )


class JobSkillExtractor:
    """Combine structured and lexical job-skill evidence deterministically."""

    def extract(
        self,
        job: JobRead,
    ) -> JobSkillEvidence:
        """Extract canonical skills from structured data, title, and description."""

        skills = normalize_skills(job.skills)
        skills.extend(_detect_text_skills(job.title))
        skills.extend(_detect_text_skills(job.description))

        return JobSkillEvidence(
            skills=normalize_skills(skills)
        )
