"""Synthetic service checks, not a measure of recruitment prediction quality."""

from datetime import datetime, timezone

import pytest

from app.agent.tools.job_query import JobQueryPort
from app.eligibility.contracts import EligibilityProfile
from app.matching.contracts import CandidateProfile
from app.matching.matcher import CandidateMatcher
from app.matching.skill_extractor import JobSkillExtractor
from app.recommendations.contracts import RecommendationCandidate
from app.recommendations.contracts import RecommendationBatch
from app.recommendations.service import RecommendationService, build_recommendation_summary
from app.schemas.job_response import JobRead


UNRESTRICTED = "毕业届次不限；学历不限；工作经验不限；实习时长不限。"


def make_job(job_id, **changes):
    values = dict(id=job_id, title=f"岗位{job_id}", company="测试公司", city="深圳",
                  salary=None, description=UNRESTRICTED, skills=["Python"],
                  source="manual", source_url=f"https://jobs.fixture.test/jobs/{job_id}",
                  published_at=None, created_at=datetime(2026, 11, 12), status="active")
    values.update(changes)
    return JobRead(**values)


def candidate(**conditions):
    values = {"acceptable_cities": []}
    values.update(conditions)
    return RecommendationCandidate(skills=["Python"], conditions=EligibilityProfile(**values))


class Query(JobQueryPort):
    def __init__(self, jobs=None, *, pages=None, total=None, on_search=None):
        self.jobs = list(jobs or [])
        self.pages = pages
        self.total = total
        self.on_search = on_search
        self.calls = []

    def search_jobs(self, *, city=None, company=None, skill=None, page=1, page_size=10):
        self.calls.append(dict(city=city, company=company, skill=skill, page=page, page_size=page_size))
        if self.on_search:
            self.on_search()
        if self.pages is not None:
            rows = self.pages.get(page, [])
        else:
            rows = self.jobs[(page - 1) * page_size:page * page_size]
        return list(rows), len(self.jobs) if self.total is None else self.total

    def get_job_by_id(self, job_id):
        return next((job for job in self.jobs if job.id == job_id), None)


def test_lower_skill_met_precedes_high_skill_unknown_without_changing_scores():
    jobs = [make_job(1, description="负责产品开发。"), make_job(2, skills=["SQL"])]
    batch = RecommendationService(Query(jobs)).recommend(candidate())
    assert [item.job.id for item in batch.recommendations] == [2, 1]
    assert [item.match_score for item in batch.recommendations] == [0, 100]
    assert [item.eligibility.overall for item in batch.recommendations] == ["met", "unknown"]
    assert batch.counts.model_dump() == dict(evaluated=2, met=1, unknown=1, not_met=0, closed=0, direction_mismatch=0, returned=2)
    assert batch.assessed_at.tzinfo is timezone.utc


def test_sixth_low_skill_eligible_job_survives_five_high_skill_ineligible_jobs():
    jobs = [make_job(index, description="仅限2026届毕业生。") for index in range(1, 6)]
    jobs.append(make_job(6, skills=["SQL"]))
    batch = RecommendationService(Query(jobs)).recommend(candidate(graduation_year=2027), limit=1)
    assert [item.job.id for item in batch.recommendations] == [6]
    assert batch.recommendations[0].match_score == 0
    assert batch.counts.not_met == 5
    assert batch.counts.evaluated == 6


def test_evaluation_reads_all_pages_before_applying_the_display_limit():
    jobs = [make_job(index, description="仅限2026届毕业生。") for index in range(1, 101)]
    jobs.append(make_job(101, skills=["SQL"]))
    query = Query(jobs)
    batch = RecommendationService(query).recommend(candidate(graduation_year=2027), limit=1)
    assert [item.job.id for item in batch.recommendations] == [101]
    assert batch.counts.evaluated == 101 and batch.counts.not_met == 100
    assert [call["page"] for call in query.calls] == [1, 2]
    assert all(call["page_size"] == 100 for call in query.calls)
    assert [item.job.id for item in batch.excluded] == list(range(1, 11))


def test_duplicate_ids_across_pages_are_evaluated_once_using_first_snapshot():
    first = make_job(1)
    changed_duplicate = make_job(1, status="closed")
    query = Query(pages={1: [first], 2: [changed_duplicate, make_job(2)]}, total=101)
    batch = RecommendationService(query).recommend(candidate())
    assert batch.counts.evaluated == 2
    assert batch.counts.closed == 0
    assert [item.job.id for item in batch.recommendations] == [1, 2]


def test_multiple_city_job_is_not_removed_by_legacy_city_string_filter():
    query = Query([make_job(1, city="北京/深圳")])
    batch = RecommendationService(query).recommend(candidate(acceptable_cities=["深圳"]))
    assert [item.job.id for item in batch.recommendations] == [1]
    assert batch.recommendations[0].eligibility.overall == "met"
    assert all(call["city"] is None and call["skill"] is None for call in query.calls)


def test_group_ranking_uses_score_then_matched_count_then_job_id():
    jobs = [make_job(9, skills=["Python", "SQL", "Git", "Docker"]),
            make_job(8, skills=["Python", "SQL"]),
            make_job(4, skills=["Python", "SQL"]),
            make_job(10, skills=["Python", "Git", "SQL", "Docker"])]
    profile = RecommendationCandidate(skills=["Python", "Git"], conditions=EligibilityProfile(acceptable_cities=[]))
    batch = RecommendationService(Query(jobs)).recommend(profile)
    assert [item.job.id for item in batch.recommendations] == [9, 10, 4, 8]
    assert all(item.match_score == 50 for item in batch.recommendations)
    assert [len(item.matched_skills) for item in batch.recommendations] == [2, 2, 1, 1]


def test_unknowns_remain_and_missing_degree_is_never_changed_to_pass():
    job = make_job(1, description="本科及以上学历；毕业届次不限；工作经验不限；实习时长不限。")
    batch = RecommendationService(Query([job])).recommend(candidate())
    assert batch.counts.unknown == 1 and len(batch.recommendations) == 1
    degree = next(item for item in batch.recommendations[0].eligibility.checks if item.dimension == "degree")
    assert degree.status == "unknown"


def test_closed_and_ineligible_counts_are_disjoint_and_excluded_examples_are_id_sorted():
    jobs = [make_job(20, status="closed", description="仅限2026届。"),
            make_job(3, description="仅限2026届。"), make_job(8)]
    batch = RecommendationService(Query(jobs)).recommend(candidate(graduation_year=2027))
    assert [item.job.id for item in batch.recommendations] == [8]
    assert batch.counts.closed == 1 and batch.counts.not_met == 1
    assert batch.counts.evaluated == sum((batch.counts.met, batch.counts.unknown,
                                        batch.counts.not_met, batch.counts.closed))
    assert [item.job.id for item in batch.excluded] == [3, 20]
    assert all(item.overall == "not_met" and item.blocking_reasons for item in batch.excluded)


def test_repeated_requests_read_current_jobs_and_recompute_evidence():
    query = Query([make_job(1, description="🎓仅限2027届。")])
    service = RecommendationService(query)
    profile = candidate(graduation_year=2027)
    initial = service.recommend(profile)
    initial_fingerprint = initial.recommendations[0].eligibility.source_fingerprint
    query.jobs[0].description = "🎓仅限2026届。"
    query.jobs[0].updated_at = datetime(2026, 11, 12, 1)
    updated = service.recommend(profile)
    assert updated.recommendations == [] and updated.counts.not_met == 1
    assert updated.excluded[0].source_fingerprint != initial_fingerprint
    assert initial.recommendations[0].job.description == "🎓仅限2027届。"
    assert updated.excluded[0].checks[0].evidence[0].text == "🎓仅限2026届"
    query.jobs[0].status = "closed"
    assert service.recommend(profile).counts.closed == 1


def test_skill_and_eligibility_share_identical_detached_snapshot_and_exact_quotes():
    source_job = make_job(1, description="🎓2027届；本科在读；工作经验不限；至少实习6个月。", skills=["Python", "SQL"])
    profile = candidate(graduation_year=2027, degree="bachelor", degree_status="enrolled", internship_months=6)
    item = RecommendationService(Query([source_job])).recommend(profile).recommendations[0]
    direct = CandidateMatcher().match(candidate=CandidateProfile(skills=profile.skills), job=source_job,
                                      evidence=JobSkillExtractor().extract(source_job))
    assert item.model_dump(include=set(type(direct).model_fields)) == direct.model_dump()
    assert item.job == item.eligibility.job
    for condition in item.eligibility.checks:
        for span in condition.evidence:
            assert getattr(item.job, span.field)[span.start:span.end] == span.text
    source_job.skills.append("Docker")
    assert "Docker" not in item.job.skills


def test_candidate_is_deep_copied_before_queries_can_mutate_external_input():
    profile = candidate(graduation_year=2027)
    def mutate_external_input():
        profile.skills[:] = ["SQL"]
        profile.conditions.graduation_year = 2026
        profile.conditions.acceptable_cities.append("北京")
    query = Query([make_job(1, description="2027届；学历不限；工作经验不限；实习时长不限。")], on_search=mutate_external_input)
    batch = RecommendationService(query).recommend(profile)
    assert batch.counts.met == 1
    assert batch.recommendations[0].match_score == 100
    assert profile.conditions.graduation_year == 2026  # The query did mutate the original.


@pytest.mark.parametrize("months,expected", [(None, "unknown"), (0, "met")])
def test_zero_work_experience_remains_different_from_missing(months, expected):
    job = make_job(1, description="毕业届次不限；学历不限；至少0个月工作经验；实习时长不限。")
    batch = RecommendationService(Query([job])).recommend(candidate(work_experience_months=months))
    assert batch.recommendations[0].eligibility.overall == expected


@pytest.mark.parametrize("cities,expected", [(None, "unknown"), ([], "met")])
def test_unknown_city_intention_remains_different_from_explicit_no_restriction(cities, expected):
    batch = RecommendationService(Query([make_job(1)])).recommend(candidate(acceptable_cities=cities))
    assert batch.recommendations[0].eligibility.overall == expected


@pytest.mark.parametrize("limit,exception", [(True, TypeError), (False, TypeError), (1.0, TypeError),
                                           ("10", TypeError), (None, TypeError), (0, ValueError), (51, ValueError)])
def test_invalid_display_limits_fail_before_query(limit, exception):
    query = Query([make_job(1)])
    with pytest.raises(exception):
        RecommendationService(query).recommend(candidate(), limit=limit)
    assert query.calls == []


def test_empty_database_and_all_ineligible_have_different_summaries():
    empty = RecommendationService(Query()).recommend(candidate())
    rejected = RecommendationService(Query([make_job(1, description="2026届")])).recommend(candidate(graduation_year=2027))
    assert "岗位库目前为空" in build_recommendation_summary(empty)
    assert "明确不满足" in build_recommendation_summary(rejected)
    assert "排除依据" in build_recommendation_summary(rejected)
    assert empty.counts.evaluated == empty.counts.returned == 0


def test_all_unknown_summary_retains_results_and_says_confirmation_is_needed():
    batch = RecommendationService(Query([make_job(1, description="工作内容介绍")])).recommend(candidate())
    summary = build_recommendation_summary(batch)
    assert len(batch.recommendations) == 1
    assert "当前推荐均为待确认" in summary
    assert "待确认不等于符合" in summary


def test_summary_explains_both_kinds_of_results_hidden_by_limit():
    jobs = [make_job(index) for index in range(1, 4)]
    jobs += [make_job(index, description="工作内容介绍") for index in range(4, 6)]
    batch = RecommendationService(Query(jobs)).recommend(candidate(), limit=2)
    summary = build_recommendation_summary(batch)
    assert batch.counts.met == 3 and batch.counts.unknown == 2 and batch.counts.returned == 2
    assert "还有 1 个符合、2 个待确认岗位未展示" in summary


def test_summary_does_not_lose_unknown_jobs_behind_a_page_of_met_results():
    jobs = [make_job(1), make_job(2, description="工作内容介绍")]
    batch = RecommendationService(Query(jobs)).recommend(candidate(), limit=1)
    assert "还有 0 个符合、1 个待确认岗位未展示" in build_recommendation_summary(batch)


def test_closed_only_summary_and_bounded_excluded_samples():
    jobs = [make_job(index, status="closed") for index in reversed(range(1, 13))]
    batch = RecommendationService(Query(jobs)).recommend(candidate())
    summary = build_recommendation_summary(batch)
    assert batch.counts.closed == 12 and batch.counts.not_met == 0
    assert batch.recommendations == []
    assert [item.job.id for item in batch.excluded] == list(range(1, 11))
    assert "均已标记关闭" in summary and "附 10 条排除依据" in summary and "共排除 12" in summary


def test_samples_are_removed_before_grouping_and_assessment_unless_explicitly_included():
    url = "https://careers.acme.test/jobs/shared"
    jobs = [make_job(1, source="mock", title="同一岗位", source_url=url),
            make_job(2, source="manual", title="同一岗位", source_url=url),
            make_job(3, source="manual", source_url="https://jobs.EXAMPLE.org./jobs/3")]
    service = RecommendationService(Query(jobs))
    default = service.recommend(candidate())
    assert [item.job.id for item in default.recommendations] == [2]
    assert default.data_scope.model_dump() == dict(total_records=3, sample_records_excluded=2,
        duplicate_records_collapsed=0, include_samples=False)
    assert default.duplicate_groups == []
    demo = service.recommend(candidate(), include_samples=True)
    assert demo.counts.evaluated == 2
    assert demo.data_scope.model_dump() == dict(total_records=3, sample_records_excluded=0,
        duplicate_records_collapsed=1, include_samples=True)
    assert "演示模式" in build_recommendation_summary(demo)


def test_all_sample_records_have_a_different_message_from_an_empty_database():
    service = RecommendationService(Query([make_job(1, source_url="https://example.com/1")]))
    batch = service.recommend(candidate())
    assert batch.counts.evaluated == 0
    assert batch.data_scope.total_records == batch.data_scope.sample_records_excluded == 1
    summary = build_recommendation_summary(batch)
    assert "隔离 1 条样例" in summary and "岗位库目前为空" not in summary


def test_cross_page_duplicate_group_does_not_consume_a_second_recommendation_slot():
    shared = "https://career.oppo.com/jobs/shared?recruitType=intern"
    first = make_job(7, source="oppo", title="CV岗位", company="OPPO", source_url=shared)
    copy = make_job(17, title="CV岗位", company="OPPO", source_url=shared, updated_at=datetime(2026, 11, 14))
    other = make_job(18, skills=["SQL"])
    query = Query(pages={1: [copy], 2: [first, other]}, total=101)
    batch = RecommendationService(query).recommend(candidate(), limit=2)
    assert [item.job.id for item in batch.recommendations] == [7, 18]
    assert batch.counts.evaluated == 2
    assert batch.data_scope.total_records == 3 and batch.data_scope.duplicate_records_collapsed == 1
    group = batch.duplicate_groups[0]
    assert group.primary_job_id == 7
    assert [source.job_id for source in group.sources] == [7, 17]
    assert not group.has_conflict  # Time and source name alone are not content conflicts.


def test_same_title_different_query_ids_and_companies_remain_separate_positions():
    jobs = [make_job(1, title="相同岗位", source_url="https://careers.acme.test/job?id=1"),
            make_job(2, title="相同岗位", source_url="https://careers.acme.test/job?id=2"),
            make_job(3, title="相同岗位", company="另一公司", source_url="https://careers.acme.test/job?id=1")]
    batch = RecommendationService(Query(jobs)).recommend(candidate())
    assert batch.counts.evaluated == 3 and len(batch.recommendations) == 3
    assert batch.data_scope.duplicate_records_collapsed == 0 and not batch.duplicate_groups


def test_official_closed_source_cannot_be_revived_by_active_manual_copy():
    url = "https://career.oppo.com/jobs/123"
    jobs = [make_job(7, source="oppo", status="closed", title="同一岗位", source_url=url),
            make_job(17, status="active", title="同一岗位", source_url=url, updated_at=datetime(2026, 11, 14))]
    batch = RecommendationService(Query(jobs)).recommend(candidate())
    assert batch.recommendations == []
    assert batch.counts.closed == 1 and batch.counts.not_met == 0
    assert [item.job.id for item in batch.excluded] == [7]
    assert batch.duplicate_groups[0].has_conflict
    assert batch.duplicate_groups[0].sources[1].status == "active"


def test_primary_snapshot_alone_determines_skills_eligibility_and_exact_evidence():
    url = "https://career.oppo.com/jobs/123"
    official = make_job(7, source="oppo", title="同一岗位", source_url=url, skills=["Python"],
                        description="2027届；学历不限；工作经验不限；实习时长不限。")
    manual = make_job(17, title="同一岗位", source_url=url, skills=["SQL", "Docker"],
                     description="2026届；硕士及以上；至少24个月工作经验。")
    batch = RecommendationService(Query([manual, official])).recommend(candidate(graduation_year=2027))
    card = batch.recommendations[0]
    assert card.job.id == 7 and card.match_score == 100
    assert card.detected_job_skills == ["Python"]
    assert card.eligibility.overall == "met" and batch.duplicate_groups[0].has_conflict
    for condition in card.eligibility.checks:
        for span in condition.evidence:
            assert getattr(official, span.field)[span.start:span.end] == span.text


def test_duplicate_scope_counts_hidden_groups_but_metadata_only_covers_shown_jobs():
    jobs = []
    for job_id in range(1, 5):
        jobs.extend([make_job(job_id, title=f"岗位{job_id}", source_url=f"https://careers.acme.test/{job_id}"),
                     make_job(job_id + 10, title=f"岗位{job_id}", source_url=f"https://careers.acme.test/{job_id}")])
    batch = RecommendationService(Query(jobs)).recommend(candidate(), limit=1)
    assert batch.data_scope.total_records == 8 and batch.data_scope.duplicate_records_collapsed == 4
    assert batch.counts.evaluated == 4
    assert [group.primary_job_id for group in batch.duplicate_groups] == [1]


@pytest.mark.parametrize("value", [None, 0, 1, "false"])
def test_include_samples_requires_a_real_boolean(value):
    query = Query([make_job(1)])
    with pytest.raises(TypeError):
        RecommendationService(query).recommend(candidate(), include_samples=value)
    assert not query.calls


@pytest.mark.parametrize("defect", [
    "scope_total", "demo_and_excluded", "missing_primary", "duplicated_member", "wrong_metadata",
    "extra_visible_member", "group_total", "hidden_primary", "different_identity", "sample_member",
])
def test_new_scope_and_group_metadata_must_be_consistent(defect):
    url = "https://career.oppo.com/jobs/1"
    jobs = [make_job(1, source="oppo", title="同一岗位", source_url=url),
            make_job(2, title="同一岗位", source_url=url), make_job(3)]
    payload = RecommendationService(Query(jobs)).recommend(candidate()).model_dump()
    group = payload["duplicate_groups"][0]
    if defect == "scope_total":
        payload["data_scope"]["total_records"] += 1
    elif defect == "demo_and_excluded":
        payload["data_scope"].update(include_samples=True, sample_records_excluded=1, total_records=4)
    elif defect == "missing_primary":
        group["primary_job_id"] = 99
    elif defect == "duplicated_member":
        group["sources"][1]["job_id"] = 1
    elif defect == "wrong_metadata":
        group["sources"][0]["updated_at"] = datetime(2020, 1, 1)
    elif defect == "extra_visible_member":
        group["sources"][1]["job_id"] = 3
    elif defect == "group_total":
        payload["duplicate_groups"] = []
    elif defect == "hidden_primary":
        group["primary_job_id"] = 2
    elif defect == "different_identity":
        group["sources"][1]["source_url"] = "https://careers.acme.test/another"
    else:
        group["sources"][1]["source"] = "mock"
    with pytest.raises(ValueError):
        RecommendationBatch.model_validate(payload)


def test_old_batch_without_scope_has_safe_unknown_scope_default():
    payload = RecommendationService(Query([make_job(1)])).recommend(candidate()).model_dump()
    payload.pop("data_scope")
    payload.pop("duplicate_groups")
    old = RecommendationBatch.model_validate(payload)
    assert old.data_scope is None and old.duplicate_groups == []


def targeted(*directions):
    return RecommendationCandidate(skills=["Python"], conditions=EligibilityProfile(
        acceptable_cities=[], graduation_year=2027,
    ), target_directions=list(directions))


@pytest.mark.parametrize("value", ["backend", ("backend",), None, [1], ["made_up"]])
def test_targets_require_a_list_of_supported_directions(value):
    with pytest.raises(ValueError):
        RecommendationCandidate(skills=["Python"], target_directions=value)


def test_direction_mismatch_is_separate_from_eligibility_and_does_not_consume_limit():
    repeated = make_job(1, title="公关经理")
    jobs = [repeated, repeated.model_copy(update={"id": 9, "source": "other_feed"}),
            make_job(2, title="公关经理", status="closed"),
            make_job(3, title="公关经理", description="仅限2026届。"),
            make_job(4, title="算法工程师"), make_job(5, title="后端开发工程师", skills=["SQL"])]
    profile = targeted("backend", "computer_vision", "backend")
    batch = RecommendationService(Query(jobs)).recommend(profile, limit=1)
    assert batch.target_directions == profile.target_directions == ["backend", "computer_vision"]
    assert batch.ranking_version == "direction-support-v4"
    assert batch.counts.model_dump() == dict(evaluated=5, met=2, unknown=0, direction_mismatch=1,
                                             not_met=1, closed=1, returned=1)
    assert [item.job.id for item in batch.recommendations] == [5]
    assert batch.recommendations[0].direction_fit.status == "aligned"
    assert [item.job.id for item in batch.excluded] == [2, 3]
    assert [item.job.id for item in batch.direction_excluded] == [1]
    assert batch.direction_excluded[0].eligibility.overall == "met"
    assert batch.direction_excluded[0].direction_fit.status == "unrelated"
    assert batch.duplicate_groups[0].primary_job_id == 1
    assert batch.data_scope.total_records == 6 and batch.data_scope.duplicate_records_collapsed == 1
    summary = build_recommendation_summary(batch)
    assert "1 个岗位与目标方向明确不符" in summary and "还有 1 个符合" in summary


def test_direction_filter_reads_second_page_before_limiting_and_bounds_examples_independently():
    jobs = [make_job(i, title="公关经理") for i in range(1, 101)]
    jobs.append(make_job(101, title="后端开发工程师", skills=[]))
    query = Query(jobs)
    batch = RecommendationService(query).recommend(targeted("backend"), limit=1)
    assert [item.job.id for item in batch.recommendations] == [101]
    assert batch.counts.direction_mismatch == 100 and batch.counts.not_met == 0 and not batch.excluded
    assert [item.job.id for item in batch.direction_excluded] == list(range(1, 11))
    assert [call["page"] for call in query.calls] == [1, 2]


def test_eligibility_then_direction_then_core_skills_precede_an_inflated_total_score():
    jobs = [
        make_job(1, title="后端开发工程师", description=UNRESTRICTED + "必须掌握SQL；Python优先。", skills=[]),
        make_job(2, title="后端开发工程师", description=UNRESTRICTED + "必须掌握Python；SQL、Git、Docker优先。", skills=[]),
        make_job(3, title="算法工程师", skills=["Python"]),
        make_job(4, title="后端开发工程师", description="必须掌握Python。", skills=[]),
    ]
    batch = RecommendationService(Query(jobs)).recommend(targeted("backend"))
    assert [item.job.id for item in batch.recommendations] == [2, 1, 3, 4]
    strong, weak, uncertain, unknown = batch.recommendations
    assert (strong.match_score, weak.match_score, uncertain.match_score) == (25, 50, 100)
    assert [(r.skill, r.matched) for r in strong.skill_requirements if r.importance == "core"] == [("Python", True)]
    assert weak.eligibility.overall == "met" and unknown.eligibility.overall == "unknown"
    assert uncertain.direction_fit.status == "uncertain"
    unrestricted = RecommendationService(Query(jobs[:2])).recommend(targeted())
    assert [item.job.id for item in unrestricted.recommendations] == [2, 1]
    assert all(item.direction_fit.status == "not_requested" for item in unrestricted.recommendations)


@pytest.mark.parametrize("defect", ["quote", "wrong_skill_name", "reversed_skills", "wrong_matched",
                                    "version_removed", "targets_removed", "missing_fit", "mismatch_as_card"])
def test_quality_contract_rejects_fabricated_or_partial_metadata(defect):
    rows = [make_job(1, title="后端开发工程师", description=UNRESTRICTED + "必须掌握Python和SQL。"),
            make_job(2, title="公关经理")]
    original = RecommendationService(Query(rows)).recommend(targeted("backend"))
    data = original.model_dump()
    card = data["recommendations"][0]
    if defect == "quote":
        span = card["direction_fit"]["evidence"][0]
        span["text"] = "伪" * len(span["text"])
    elif defect == "wrong_skill_name":
        card["skill_requirements"][0]["skill"] = "python"
    elif defect == "reversed_skills":
        card["skill_requirements"].reverse()
    elif defect == "wrong_matched":
        card["skill_requirements"][0]["matched"] = False
    elif defect == "version_removed":
        data.pop("ranking_version")
    elif defect == "targets_removed":
        data["target_directions"] = []
    elif defect == "missing_fit":
        card["direction_fit"], card["skill_requirements"] = None, []
    else:
        data["recommendations"][0], data["direction_excluded"][0] = data["direction_excluded"][0], card
    with pytest.raises(ValueError):
        RecommendationBatch.model_validate(data)
