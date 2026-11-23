"""Conservative source identity and selection never alter stored records."""

from datetime import datetime, timezone

import pytest

from app.recommendations.identity import canonical_identity, group_jobs, is_sample_source
from app.schemas.job_response import JobRead


def job(job_id, **changes):
    values = dict(id=job_id, title="CV Engineer", company="OPPO", city="北京", salary=None,
                  description="Python and PyTorch work", skills=["Python", "PyTorch"],
                  source="manual", source_url="https://career.oppo.com/official/post/123?type=intern",
                  status="active", published_at=None, created_at=datetime(2026, 1, 1))
    values.update(changes)
    return JobRead(**values)


@pytest.mark.parametrize("source,url,expected", [
    ("mock", "https://careers.acme.test/jobs/1", True),
    (" MOCK ", "not-a-url", True),
    ("manual", "https://EXAMPLE.COM./jobs/1", True),
    ("oppo", "https://jobs.example.org/job/1", True),
    ("manual", "https://nested.jobs.example.net./job/1", True),
    ("manual", "https://evil-example.com/job/1", False),
    ("manual", "https://example.com.attacker.test/job/1", False),
    ("manual", "https://real.test/example.com?id=example.org", False),
    ("manual", "https://example.com@real.test/job/1", False),
])
def test_only_mock_and_exact_example_hosts_or_subdomains_are_samples(source, url, expected):
    assert is_sample_source(source, url) is expected


def test_canonical_identity_normalizes_origin_and_names_but_keeps_job_identifiers():
    first = canonical_identity("HTTPS://Career.OPPO.com.:443/post/A?type=intern&id=7", " OPPO  Labs ", " CV  Engineer ")
    same = canonical_identity("https://career.oppo.com/post/A?type=intern&id=7", "oppo labs", "cv engineer")
    assert first == same
    for url in (
        "https://career.oppo.com/post/a?type=intern&id=7",
        "https://career.oppo.com/post/A?type=intern&id=8",
        "https://career.oppo.com/post/A?id=7&type=intern",
        "http://career.oppo.com/post/A?type=intern&id=7",
    ):
        assert canonical_identity(url, "OPPO Labs", "CV Engineer") != first


@pytest.mark.parametrize("url", [
    "https://user:password@career.oppo.com/job/1", "ftp://career.oppo.com/job/1",
    "https://career.oppo.com:bad/job/1", "not-a-url",
])
def test_invalid_and_credential_bearing_urls_never_merge_even_when_identical(url):
    assert canonical_identity(url, "OPPO", "CV Engineer") is None
    assert len(group_jobs([job(1, source_url=url), job(2, source_url=url)])) == 2


def test_spa_routes_and_unknown_fragments_cannot_collapse_different_positions():
    jobs = [job(1, source_url="https://careers.acme.test/#/jobs/123"),
            job(2, source_url="https://careers.acme.test/#/jobs/456"),
            job(3, source_url="https://careers.acme.test/#job=789")]
    assert len(group_jobs(jobs)) == 3
    assert canonical_identity("https://careers.acme.test/#top", "A", "B") != canonical_identity("https://careers.acme.test/", "A", "B")


def test_official_closed_record_beats_newer_active_manual_copy_and_preserves_all_records():
    official = job(7, source="oppo", status="closed", updated_at=datetime(2026, 1, 1))
    manual = job(17, updated_at=datetime(2026, 11, 14), description="Newer manual text")
    before = [record.model_dump() for record in (manual, official)]
    result = group_jobs([manual, official])[0]
    assert result.primary.id == 7 and result.primary.status == "closed"
    assert [record.id for record in result.records] == [7, 17]
    assert result.has_conflict
    assert [record.model_dump() for record in (manual, official)] == before


def test_oppo_label_alone_does_not_make_an_unknown_host_authoritative():
    records = [job(1, source="oppo", source_url="https://careers.other.test/job/1", updated_at=datetime(2026, 1, 1)),
               job(2, source_url="https://careers.other.test/job/1", updated_at=datetime(2026, 2, 1))]
    assert group_jobs(records)[0].primary.id == 2


def test_same_authority_uses_latest_available_time_then_closed_then_smallest_id():
    records = [job(1, updated_at=datetime(2026, 1, 1)),
               job(2, updated_at=datetime(2026, 1, 2)),
               job(3, last_checked_at=datetime(2026, 1, 3), status="active"),
               job(5, updated_at=datetime(2026, 1, 3, tzinfo=timezone.utc), status="closed"),
               job(4, last_checked_at=datetime(2026, 1, 3), status="closed")]
    assert group_jobs(records)[0].primary.id == 4
    assert group_jobs(list(reversed(records)))[0].primary.id == 4


def test_source_time_and_skill_order_differences_alone_do_not_report_content_conflict():
    records = [job(1, source="oppo", last_checked_at=datetime(2026, 1, 1)),
               job(2, source="manual", updated_at=datetime(2026, 2, 1), skills=["pytorch", "PYTHON"])]
    assert group_jobs(records)[0].has_conflict is False


@pytest.mark.parametrize("changes", [
    {"description": "Different actual requirements"}, {"city": "深圳"},
    {"skills": ["Python", "SQL"]}, {"status": "unknown"}, {"salary": "200元/天"},
])
def test_actual_content_or_status_differences_are_disclosed(changes):
    assert group_jobs([job(1), job(2, **changes)])[0].has_conflict is True


def test_description_paragraph_boundaries_are_not_erased_by_conflict_detection():
    first = job(1, description="本科及以上\n硕士优先")
    second = job(2, description="本科及以上 硕士优先")
    assert group_jobs([first, second])[0].has_conflict is True
