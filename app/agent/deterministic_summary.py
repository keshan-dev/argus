"""Deterministic member summary generator (P4-008, Issue #32).

Produces a structured, factual member summary with zero model calls.
Serves as the primary factual rollup for member profiles, the baseline
input passed to Ollama in S4, and the deterministic fallback whenever
an LLM call fails, times out, or is rejected by the narrative validator
(DEC-018, FR-012, FR-022, FR-026).
"""

from typing import Sequence

from pydantic import BaseModel, Field

from app.schemas.tools import CommitOut, PullRequestOut, ReviewOut, WorkItemOut

# Mandatory context note required by FR-026
PRODUCTIVITY_CONTEXT_NOTE = "Activity counts are context, not a productivity measure."

FALLBACK_HEADER = (
    "Deterministic summary generated from recorded activity (LLM narrative unavailable)."
)


class DeterministicSummaryResult(BaseModel):
    """Structured container for deterministic summary output."""

    text: str = Field(description="Formatted human-readable factual summary")
    is_fallback: bool = Field(default=False, description="True if generated as an LLM fallback")
    assigned_count: int = Field(description="Number of assigned work items")
    open_pr_count: int = Field(description="Number of open pull requests")
    commit_count: int = Field(description="Number of recent commits analyzed")
    review_count: int = Field(description="Number of code reviews analyzed")
    disclaimer: str = Field(
        default=PRODUCTIVITY_CONTEXT_NOTE,
        description="Mandatory context disclaimer enforcing FR-026",
    )


def generate_deterministic_summary(
    work_items: Sequence[WorkItemOut],
    pull_requests: Sequence[PullRequestOut],
    commits: Sequence[CommitOut],
    reviews: Sequence[ReviewOut],
    is_fallback: bool = False,
) -> DeterministicSummaryResult:
    """Produce a factual member summary from tool outputs with zero model calls.

    Summarizes assigned Jira tickets by status and priority, open GitHub pull requests
    with review and check states, and recent commits/reviews with the mandatory
    productivity disclaimer (FR-026).
    """
    sections: list[str] = []

    if is_fallback:
        sections.append(FALLBACK_HEADER)

    # 1. Assigned Work Items
    assigned_active = [w for w in work_items if w.status != "done"]
    assigned_done = [w for w in work_items if w.status == "done"]

    if not work_items:
        sections.append("No work items currently assigned in this window.")
    else:
        wi_lines = [f"Assigned work items ({len(work_items)} total):"]
        if assigned_active:
            for item in assigned_active:
                prio_str = f", {item.priority}" if item.priority else ""
                flag_str = " [FLAGGED]" if item.is_flagged else ""
                blocked_str = (
                    f" (blocked by: {', '.join(item.blocked_by)})"
                    if item.blocked_by
                    else ""
                )
                wi_lines.append(
                    f"  - {item.external_id}: {item.title} "
                    f"[{item.raw_status}{prio_str}]{flag_str}{blocked_str}"
                )
        if assigned_done:
            done_keys = ", ".join(w.external_id for w in assigned_done)
            wi_lines.append(f"  - Completed: {done_keys}")
        sections.append("\n".join(wi_lines))

    # 2. Pull Requests
    open_prs = [pr for pr in pull_requests if pr.state == "open"]
    merged_prs = [pr for pr in pull_requests if pr.state == "merged"]

    if not pull_requests:
        sections.append("No authored pull requests in this window.")
    else:
        pr_lines = [f"Pull requests ({len(open_prs)} open, {len(merged_prs)} merged):"]
        for pr in open_prs:
            draft_label = " [DRAFT]" if pr.is_draft else ""
            checks_label = (
                f", checks: {pr.checks_state}"
                if pr.checks_state != "unknown"
                else ""
            )
            review_label = (
                f", review: {pr.review_state}"
                if pr.review_state != "none"
                else ""
            )
            pr_lines.append(
                f"  - #{pr.number} ({pr.repo_full_name}): {pr.title}"
                f"{draft_label} [{pr.state}{review_label}{checks_label}]"
            )
        sections.append("\n".join(pr_lines))

    # 3. Activity Counts and Context Disclaimer (FR-026)
    activity_line = (
        f"Recorded activity: {len(commits)} commit(s) and {len(reviews)} review(s). "
        f"{PRODUCTIVITY_CONTEXT_NOTE}"
    )
    sections.append(activity_line)

    summary_text = "\n\n".join(sections)

    return DeterministicSummaryResult(
        text=summary_text,
        is_fallback=is_fallback,
        assigned_count=len(work_items),
        open_pr_count=len(open_prs),
        commit_count=len(commits),
        review_count=len(reviews),
        disclaimer=PRODUCTIVITY_CONTEXT_NOTE,
    )
