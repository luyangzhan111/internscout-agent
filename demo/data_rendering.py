"""Presentation rules for source freshness and import outcomes."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from demo.data_client import ImportRun


SOURCE_LABELS = {
    "manual": "手动导入",
    "oppo": "OPPO 官网",
    "mock": "样例数据（非真实招聘）",
}
STATUS_LABELS = {
    "active": "已确认在招",
    "closed": "已关闭",
    "unknown": "待确认（不代表仍在招聘）",
}
RUN_STATUS_LABELS = {
    "running": "进行中",
    "succeeded": "已完成",
    "partial": "部分完成",
    "failed": "失败",
}


@dataclass(frozen=True)
class ImportRunView:
    level: Literal["info", "success", "warning", "error"]
    title: str
    counts: str
    note: str | None
    errors: tuple[str, ...]


def format_timestamp(value: datetime | None) -> str:
    if value is None:
        return "尚无记录"
    # The backend stores naive timestamps in UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(
        timezone(timedelta(hours=8))
    ).strftime("%Y-%m-%d %H:%M（北京时间）")


def build_import_run_view(run: ImportRun) -> ImportRunView:
    """Never show a failed or truncated run as an unqualified success."""

    if run.status == "running":
        level, title = "info", "本次操作仍在进行"
    elif run.status == "failed":
        level, title = "error", "本次操作失败"
    elif run.status == "partial" or not run.complete:
        level, title = "warning", "本次操作部分完成"
    else:
        level, title = "success", "本次操作已完成"
    note = None
    if run.status == "running":
        note = "请稍后刷新记录查看结果，避免重复提交。"
    elif not run.complete:
        note = (
            "本次未完整检查来源，可能受数量上限或采集失败影响。"
            "请查看详情后再决定是否重试。"
        )
    errors = tuple(
        f"{item.item_id}：{item.message}" if item.item_id else item.message
        for item in run.errors
    )
    return ImportRunView(
        level=level,
        title=title,
        counts=(
            f"新增 {run.created_count} · 更新 {run.updated_count} · "
            f"未变化 {run.unchanged_count} · 失败 {run.failed_count}"
        ),
        note=note,
        errors=errors,
    )
