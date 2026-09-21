"""Deterministic read tool T-004: get_commits (P3-002, Issue #22).

Returns commits authored by a person within a window, with branch and message
excerpt from PostgreSQL. Flags truncated=True if more rows exist than limit.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.canonical import AppUser, Repository
from app.models.work import Commit
from app.schemas.errors import ToolFailure
from app.schemas.tools import (
    CommitOut,
    GetCommitsInput,
    GetCommitsOutput,
)
from app.tools.base import execute_tool_query


def get_commits(
    session: Session,
    input_data: GetCommitsInput,
) -> GetCommitsOutput | ToolFailure:
    """Retrieve commits authored by a subject with truncation detection."""

    def _query() -> GetCommitsOutput | ToolFailure:
        user = session.get(AppUser, input_data.subject_user_id)
        if not user:
            return ToolFailure(
                tool_id="T-004",
                error_type="NOT_FOUND",
                detail=f"User with ID {input_data.subject_user_id} does not exist",
            )

        # Query limit + 1 rows to determine if results were truncated
        stmt = (
            select(Commit, Repository)
            .join(Repository, Commit.repository_id == Repository.id)
            .where(
                Commit.author_app_user_id == input_data.subject_user_id,
                Commit.committed_at.between(input_data.window_start, input_data.window_end),
            )
            .order_by(Commit.committed_at.desc())
            .limit(input_data.limit + 1)
        )
        results = session.execute(stmt).all()

        truncated = len(results) > input_data.limit
        if truncated:
            results = results[: input_data.limit]

        commits: list[CommitOut] = []
        for commit, repo in results:
            commits.append(
                CommitOut(
                    commit_id=commit.id,
                    sha=commit.sha,
                    repo_full_name=repo.full_name,
                    message_excerpt=commit.message_excerpt or "",
                    branch_name=commit.branch_name,
                    author_user_id=commit.author_app_user_id,
                    committed_at=commit.committed_at,
                    source_url=commit.source_url,
                    retrieved_at=commit.retrieved_at,
                )
            )

        return GetCommitsOutput(commits=commits, truncated=truncated)

    return execute_tool_query("T-004", _query)
