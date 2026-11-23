"""Current-snapshot recommendations with eligibility before skill ranking."""

from datetime import datetime, timezone

from app.agent.tools.job_query import JobQueryPort
from app.eligibility.evaluator import evaluate_eligibility
from app.matching.contracts import CandidateProfile
from app.matching.matcher import CandidateMatcher
from app.matching.skill_extractor import JobSkillExtractor
from app.recommendations.contracts import (
    EligibleRecommendation, RecommendationBatch, RecommendationCandidate,
    RecommendationCounts, RecommendationDataScope, DuplicateGroup, SourceRecord,
)
from app.recommendations.identity import group_jobs, is_sample_record
from app.recommendations.quality import classify_skill_requirements, evaluate_direction, evaluate_ranking_support, quality_rank_key
from app.schemas.job_response import JobRead


PAGE_SIZE = 100
EXCLUDED_EXAMPLE_LIMIT = 10


class RecommendationService:
    """Read all supplied jobs, assess one bound candidate, then limit results.

    The query adapter must include closed jobs when closed counts are wanted.
    This service never applies the legacy preferred-city string filter.
    """

    def __init__(self, job_query: JobQueryPort) -> None:
        self._job_query = job_query
        self._skill_extractor = JobSkillExtractor()
        self._matcher = CandidateMatcher()

    def recommend(
        self, candidate: RecommendationCandidate, limit: int = 10, *, include_samples: bool = False,
    ) -> RecommendationBatch:
        if type(limit) is not int:
            raise TypeError("展示数量必须是整数，不能使用布尔值或小数。")
        if not 1 <= limit <= 50:
            raise ValueError("展示数量必须在 1 至 50 之间。")
        if type(include_samples) is not bool:
            raise TypeError("是否包含样例必须是布尔值。")

        # Capture user-owned mutable lists before any query or model-facing work.
        bound_candidate = candidate.model_copy(deep=True)
        skill_profile = CandidateProfile(skills=list(bound_candidate.skills))
        source_records = self._collect_unique_jobs()
        selected_records = [job for job in source_records if include_samples or not is_sample_record(job)]
        groups = group_jobs(selected_records)
        jobs = [group.primary for group in groups]
        recommendations: list[EligibleRecommendation] = []
        direction_excluded: list[EligibleRecommendation] = []
        excluded = []
        counts = {"met": 0, "unknown": 0, "not_met": 0, "closed": 0, "direction_mismatch": 0}
        for job in jobs:
            eligibility = evaluate_eligibility(job, bound_candidate.conditions)
            if job.status == "closed" or eligibility.overall == "not_met":
                counts["closed" if job.status == "closed" else "not_met"] += 1
                excluded.append(eligibility)
                continue
            skill_result = self._matcher.match(
                candidate=skill_profile, job=job,
                evidence=self._skill_extractor.extract(job),
            )
            fit = evaluate_direction(job, bound_candidate.target_directions)
            card = EligibleRecommendation(
                **skill_result.model_dump(), eligibility=eligibility, direction_fit=fit,
                ranking_support=evaluate_ranking_support(
                    job, bound_candidate.target_directions, fit, skill_result.matched_skills,
                ),
                skill_requirements=classify_skill_requirements(
                    job, skill_result.detected_job_skills, bound_candidate.skills,
                ),
            )
            if fit.status == "unrelated":
                counts["direction_mismatch"] += 1
                direction_excluded.append(card)
            else:
                counts[eligibility.overall] += 1
                recommendations.append(card)

        recommendations.sort(key=quality_rank_key)
        excluded.sort(key=lambda result: result.job.id)
        returned = recommendations[:limit]
        excluded = excluded[:EXCLUDED_EXAMPLE_LIMIT]
        direction_excluded.sort(key=lambda item: item.job.id)
        direction_excluded = direction_excluded[:EXCLUDED_EXAMPLE_LIMIT]
        displayed_ids = {item.job.id for item in (*returned, *excluded, *direction_excluded)}
        return RecommendationBatch(
            recommendations=returned,
            excluded=excluded,
            direction_excluded=direction_excluded, target_directions=bound_candidate.target_directions,
            ranking_version="direction-support-v4",
            counts=RecommendationCounts(
                evaluated=len(jobs), returned=len(returned), **counts,
            ),
            limit=limit, assessed_at=datetime.now(timezone.utc),
            data_scope=RecommendationDataScope(
                total_records=len(source_records),
                sample_records_excluded=len(source_records) - len(selected_records),
                duplicate_records_collapsed=len(selected_records) - len(jobs),
                include_samples=include_samples,
            ),
            duplicate_groups=[DuplicateGroup(
                primary_job_id=group.primary.id,
                sources=[SourceRecord(
                    job_id=job.id, source=job.source, source_url=job.source_url,
                    status=job.status, last_checked_at=job.last_checked_at,
                    updated_at=job.updated_at, title=job.title, company=job.company,
                ) for job in group.records],
                has_conflict=group.has_conflict, selection_reason=group.selection_reason,
            ) for group in groups if len(group.records) > 1 and group.primary.id in displayed_ids],
        )

    def _collect_unique_jobs(self) -> list[JobRead]:
        first_page, total = self._job_query.search_jobs(page=1, page_size=PAGE_SIZE)
        if type(total) is not int or total < 0:
            raise ValueError("岗位查询返回的总数无效，无法完成全量判断。")
        unique: dict[int, JobRead] = {}

        def collect(items: list[JobRead]) -> None:
            for job in items:
                if job.id not in unique:
                    # The skill result and eligibility evidence use this same
                    # detached value, even if the query owner later changes it.
                    unique[job.id] = job.model_copy(deep=True)

        collect(first_page)
        page_count = (total + PAGE_SIZE - 1) // PAGE_SIZE
        for page in range(2, page_count + 1):
            jobs, _ = self._job_query.search_jobs(page=page, page_size=PAGE_SIZE)
            collect(jobs)
        return list(unique.values())


def build_recommendation_summary(batch: RecommendationBatch) -> str:
    """Explain totals, uncertainty and bounded examples without model claims."""

    counts = batch.counts
    scope = batch.data_scope
    if counts.evaluated == 0:
        if scope is not None and scope.total_records:
            return (
                f"本次读取 {scope.total_records} 条记录，已隔离 {scope.sample_records_excluded} 条样例；"
                "当前没有可判断的非样例岗位。可导入真实来源岗位，或显式开启包含样例的演示模式。"
            )
        return "岗位库目前为空，请先导入或刷新真实岗位，再获取推荐。"

    pieces = []
    if scope is not None:
        pieces.append(
            f"本次读取 {scope.total_records} 条来源记录，隔离 {scope.sample_records_excluded} 条样例，"
            f"合并 {scope.duplicate_records_collapsed} 条重复记录，实际判断 {counts.evaluated} 个独立岗位。"
        )
        if scope.include_samples:
            pieces.append("本次已开启包含样例的演示模式；样例记录不代表真实招聘机会。")
    pieces.append(
        f"本次检查 {counts.evaluated} 个岗位：{counts.met} 个符合已识别条件，"
        f"{counts.unknown} 个待确认，{counts.not_met} 个明确不符合，{counts.closed} 个已关闭。"
    )
    if batch.target_directions:
        pieces.append(
            f"另有 {counts.direction_mismatch} 个岗位与目标方向明确不符，"
            f"列出其中 {len(batch.direction_excluded)} 条方向依据。"
        )
    if not batch.recommendations:
        if counts.closed == counts.evaluated:
            pieces.append("岗位均已标记关闭，暂无可推荐岗位。")
        elif counts.not_met == counts.evaluated:
            pieces.append("岗位均有明确不满足的投递条件，暂无可推荐岗位。")
        elif counts.direction_mismatch == counts.evaluated:
            pieces.append("所有岗位的明确方向都与本次选择不同，可调整目标方向或补充岗位。")
        elif counts.direction_mismatch:
            pieces.append("本次岗位均因投递条件、关闭状态或目标方向被排除。")
        else:
            pieces.append("岗位均明确不符合或已关闭，暂无可推荐岗位。")
    else:
        sort_by = ("同组依次按方向、待确认排序线索、核心技能、加分技能及总技能覆盖排序"
                   if batch.ranking_version == "direction-support-v4" else
                   "同组依次按方向、核心技能、加分技能及总技能覆盖排序" if batch.ranking_version else "同组按技能覆盖率排序")
        pieces.append(f"已展示 {counts.returned} 个推荐岗位，符合的岗位优先，{sort_by}。")
        if counts.met == 0:
            pieces.append("当前推荐均为待确认，请先核对原文中的未明条件；待确认不等于符合。")
        shown_met = sum(item.eligibility.overall == "met" for item in batch.recommendations)
        shown_unknown = sum(item.eligibility.overall == "unknown" for item in batch.recommendations)
        remaining_met = counts.met - shown_met
        remaining_unknown = counts.unknown - shown_unknown
        if remaining_met or remaining_unknown:
            pieces.append(
                f"受展示上限 {batch.limit} 限制，还有 {remaining_met} 个符合、"
                f"{remaining_unknown} 个待确认岗位未展示。"
            )
        pieces.append("“符合”仅覆盖已识别的五项条件，其他招聘要求仍需核对。")
    excluded_total = counts.not_met + counts.closed
    if excluded_total:
        pieces.append(
            f"附 {len(batch.excluded)} 条排除依据（共排除 {excluded_total} 个岗位），"
            f"最多展示 {EXCLUDED_EXAMPLE_LIMIT} 条。"
        )
    return "\n".join(pieces)
