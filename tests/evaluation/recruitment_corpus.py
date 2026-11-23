"""Pytest marker for tests that replay the recorded recruitment corpus."""

from pathlib import Path

import pytest


_ROOT = Path(__file__).resolve().parents[2]

# The trial package omits the entire recorded corpus. A partial local copy must
# still run these tests so missing snapshots or fingerprints are detected.
REQUIRES_RECORDED_CORPUS = pytest.mark.skipif(
    not (_ROOT / "data/real_jobs").exists()
    and not any((_ROOT / "evals/cases").glob("recommendation_quality*")),
    reason="Recorded recruitment corpus is omitted from the trial package.",
)
