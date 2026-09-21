"""Agent orchestrator, stages S1 and S2 (P3-004, FR-014, FR-023, DEC-010).

S1 builds the plan. S2 checks source health (T-007) and then calls the read tools the
plan asks for. Everything is carried in one AgentRunContext, which later stages extend.

The required-source gate: if a required source is unavailable, or a required tool fails,
the run must not reach the model (S4). It returns UNKNOWN with the reason instead, and
the model is never called. A missing health answer counts as unavailable: never assume
a source is healthy.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.planner import QuestionType, RetrievalPlan, Source, build_plan
from app.schemas.errors import ToolFailure
from app.schemas.insight import Insight, MemberInsight
from app.schemas.evidence import EvidenceSet
from app.schemas.tools import (
    CommitOut,
    GetAssignedWorkItemsInput,
    GetCommitsInput,
    GetPullRequestsInput,
    GetReviewsInput,
    GetSourceHealthInput,
    GetWorkItemLinksInput,
    PullRequestOut,
    ReviewOut,
    SourceHealthOut,
    WorkItemLinkOut,
    WorkItemOut,
)
from app.tools.get_assigned_work_items import get_assigned_work_items
from app.tools.get_commits import get_commits
from app.tools.get_pull_requests import get_pull_requests
from app.tools.get_reviews import get_reviews
from app.tools.get_source_health import get_source_health
from app.tools.get_work_item_links import get_work_item_links

logger = logging.getLogger("argus.agent")

# "All open items with a due date" (the risks question) reaches back further than any
# activity window, so it uses its own, very long, lookback.
OPEN_ITEMS_LOOKBACK_DAYS = 3650

# The sources each read tool depends on. A tool is only called when every one of its
# sources is usable, meaning fresh or stale but not unavailable.
TOOL_SOURCES: dict[str, tuple[Source, ...]] = {
    "T-002": ("jira",),
    "T-003": ("github",),
    "T-004": ("github",),
    "T-005": ("github",),
    "T-006": ("jira", "github"),
}


@dataclass(frozen=True)
class ReadTools:
    """The read tools stage S2 calls. Tests pass fakes here instead."""

    source_health: Callable[..., Any] = get_source_health
    assigned_work_items: Callable[..., Any] = get_assigned_work_items
    pull_requests: Callable[..., Any] = get_pull_requests
    commits: Callable[..., Any] = get_commits
    reviews: Callable[..., Any] = get_reviews
    work_item_links: Callable[..., Any] = get_work_item_links


class RetrievalResult(BaseModel):
    """Everything stage S2 retrieved for the subject."""

    work_items: list[WorkItemOut] = Field(default_factory=list)
    open_due_items: list[WorkItemOut] = Field(default_factory=list)
    pull_requests: list[PullRequestOut] = Field(default_factory=list)
    commits: list[CommitOut] = Field(default_factory=list)
    commits_truncated: bool = False
    reviews: list[ReviewOut] = Field(default_factory=list)
    links: list[WorkItemLinkOut] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)


class GateResult(BaseModel):
    """Whether the run may go on to reasoning, and if not, why."""

    proceed: bool = True
    reasons: list[str] = Field(default_factory=list)

    @property
    def reason(self) -> str | None:
        """All reasons as one line, or None when the gate is open."""
        return "; ".join(self.reasons) or None


class AgentRunContext(BaseModel):
    """Carries everything between stages: plan, retrieval, health, evidence, and failures."""

    subject_user_id: int
    team_id: int
    question_type: QuestionType
    plan: RetrievalPlan
    started_at: datetime
    window_start: datetime
    window_end: datetime
    health: list[SourceHealthOut] = Field(default_factory=list)
    retrieval: RetrievalResult = Field(default_factory=RetrievalResult)
    evidence_set: EvidenceSet | None = None
    failures: list[ToolFailure] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    gate: GateResult = Field(default_factory=GateResult)


def _call(context: AgentRunContext, tool_id: str, call: Callable[[], Any]) -> Any | None:
    """Run one tool. Record the call, and keep a typed failure instead of raising."""
    context.retrieval.tools_called.append(tool_id)
    result = call()
    if isinstance(result, ToolFailure):
        logger.warning("tool failed: tool_id=%s error_type=%s", tool_id, result.error_type)
        context.failures.append(result)
        return None
    return result


def _check_health(session: Session, context: AgentRunContext, tools: ReadTools) -> set[Source]:
    """Call T-007 and return the sources that are safe to read from.

    If T-007 itself fails, nothing is usable: fail closed, never assume healthy.
    """
    sources = [*context.plan.required_sources, *context.plan.optional_sources]
    data = GetSourceHealthInput(team_id=context.team_id, sources=sources)
    output = _call(context, "T-007", lambda: tools.source_health(session, data))
    if output is None:
        return set()
    context.health = list(output.sources)
    return {health.source for health in output.sources if health.state != "unavailable"}


def _retrieve(
    session: Session, context: AgentRunContext, tools: ReadTools, usable: set[Source]
) -> None:
    """Stage S2: call the tools the plan asks for, skipping any whose source is unusable."""
    plan, retrieval, subject = context.plan, context.retrieval, context.subject_user_id

    def allowed(tool_id: str) -> bool:
        if tool_id not in plan.tools:
            return False
        unusable = [source for source in TOOL_SOURCES[tool_id] if source not in usable]
        if unusable:
            context.notes.append(f"{tool_id} skipped: {', '.join(unusable)} data is not usable")
            return False
        return True

    if allowed("T-002"):
        data = GetAssignedWorkItemsInput(
            subject_user_id=subject,
            window_start=context.window_start,
            window_end=context.window_end,
        )
        output = _call(context, "T-002", lambda: tools.assigned_work_items(session, data))
        if output is not None:
            retrieval.work_items = list(output.items)

        if plan.include_open_due_items:
            open_data = GetAssignedWorkItemsInput(
                subject_user_id=subject,
                window_start=context.window_end - timedelta(days=OPEN_ITEMS_LOOKBACK_DAYS),
                window_end=context.window_end,
                include_done=False,
            )
            output = _call(context, "T-002", lambda: tools.assigned_work_items(session, open_data))
            if output is not None:
                retrieval.open_due_items = [
                    item for item in output.items if item.due_date is not None
                ]

    if allowed("T-003"):
        pr_data = GetPullRequestsInput(
            subject_user_id=subject,
            window_start=context.window_start,
            window_end=context.window_end,
        )
        output = _call(context, "T-003", lambda: tools.pull_requests(session, pr_data))
        if output is not None:
            retrieval.pull_requests = list(output.pull_requests)

    if allowed("T-004"):
        commit_data = GetCommitsInput(
            subject_user_id=subject,
            window_start=context.window_start,
            window_end=context.window_end,
        )
        output = _call(context, "T-004", lambda: tools.commits(session, commit_data))
        if output is not None:
            retrieval.commits = list(output.commits)
            retrieval.commits_truncated = output.truncated

    if allowed("T-005"):
        review_data = GetReviewsInput(
            subject_user_id=subject,
            window_start=context.window_start,
            window_end=context.window_end,
        )
        output = _call(context, "T-005", lambda: tools.reviews(session, review_data))
        if output is not None:
            retrieval.reviews = list(output.reviews)

    if allowed("T-006"):
        work_item_ids = sorted(
            {item.work_item_id for item in [*retrieval.work_items, *retrieval.open_due_items]}
        )
        pull_request_ids = sorted({pr.pull_request_id for pr in retrieval.pull_requests})
        # T-006 needs at least one id. With none, there is nothing to link.
        if work_item_ids or pull_request_ids:
            link_data = GetWorkItemLinksInput(
                work_item_ids=work_item_ids or None,
                pull_request_ids=pull_request_ids or None,
            )
            output = _call(context, "T-006", lambda: tools.work_item_links(session, link_data))
            if output is not None:
                retrieval.links = list(output.links)


def _unavailable_reason(source: Source, health: SourceHealthOut | None) -> str:
    """Explain in one phrase why a source is unavailable, from typed fields only."""
    if health is None:
        return f"{source} has no health record"
    if health.last_error_type:
        return f"{source} is unavailable (last error: {health.last_error_type})"
    return f"{source} is unavailable (no successful sync recorded)"


def _evaluate_gate(context: AgentRunContext, usable: set[Source]) -> None:
    """Decide whether the run may go on to reasoning (the required-source gate)."""
    plan = context.plan
    by_source = {health.source: health for health in context.health}
    reasons: list[str] = []

    health_failure = next((f for f in context.failures if f.tool_id == "T-007"), None)
    if health_failure is not None:
        reasons.append(f"source health could not be determined ({health_failure.error_type})")
    else:
        for source in plan.required_sources:
            if source not in usable:
                reasons.append(_unavailable_reason(source, by_source.get(source)))
        for source in plan.optional_sources:
            if source not in usable:
                context.notes.append(
                    f"{source} is unavailable and optional for {plan.question_type}; "
                    f"continuing without {source} data"
                )

    for failure in context.failures:
        if failure.tool_id == "T-007":
            continue
        sources = TOOL_SOURCES.get(failure.tool_id)
        # An unknown tool id is treated as required, so the gate fails closed.
        if sources is None or any(source in plan.required_sources for source in sources):
            reasons.append(f"{failure.tool_id} failed ({failure.error_type})")
        else:
            context.notes.append(
                f"{failure.tool_id} failed ({failure.error_type}); continuing without it"
            )

    context.gate = GateResult(proceed=not reasons, reasons=reasons)


def run_s1_s2(
    session: Session,
    *,
    subject_user_id: int,
    team_id: int,
    question_type: str,
    tools: ReadTools | None = None,
    now: datetime | None = None,
) -> AgentRunContext:
    """Run stages S1 (plan) and S2 (retrieve), and return the filled AgentRunContext.

    An invalid question type raises InvalidQuestionTypeError (422) before any tool runs.
    Check context.gate.proceed before going on to S3 and later stages.
    """
    plan = build_plan(question_type)
    tools = tools if tools is not None else ReadTools()
    moment = now if now is not None else datetime.now(UTC)
    context = AgentRunContext(
        subject_user_id=subject_user_id,
        team_id=team_id,
        question_type=plan.question_type,
        plan=plan,
        started_at=moment,
        window_start=moment - timedelta(days=plan.window_days),
        window_end=moment,
    )

    usable = _check_health(session, context, tools)
    _retrieve(session, context, tools, usable)
    _evaluate_gate(context, usable)

    logger.info(
        "s1_s2 done: question=%s proceed=%s tools=%s failures=%d",
        plan.question_type,
        context.gate.proceed,
        context.retrieval.tools_called,
        len(context.failures),
    )
    return context


def unknown_response(context: AgentRunContext) -> MemberInsight:
    """Build the UNKNOWN answer for a run whose gate is closed (FR-023).

    The reason goes into the slot for the question that was asked, so an unavailable
    source can never be mistaken for "no blockers found".
    """
    reason = context.gate.reason or "required data is unavailable"

    def unknown() -> Insight:
        return Insight(
            claim=f"Cannot be established: {reason}",
            classification="unknown",
            confidence="UNKNOWN",
        )

    return MemberInsight(
        user_id=context.subject_user_id,
        likely_current_work=unknown() if context.question_type == "current_work" else None,
        blockers=[unknown()] if context.question_type == "blockers" else [],
        risks=[unknown()] if context.question_type == "risks" else [],
        unknowns=[reason],
        last_synced={health.source: health.last_success_at for health in context.health},
        source_health=list(context.health),
    )