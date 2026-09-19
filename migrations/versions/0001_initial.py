"""Initial schema with 17 canonical tables (P1-001, DATA_AND_EVIDENCE.md 6.3).

Revision ID: 0001_initial
Revises: None
Create Date: 2026-09-19 20:30:00.000000+00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    # 1. organization
    op.create_table(
        "organization",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. team
    op.create_table(
        "team",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_team_organization_id", "team", ["organization_id"])

    # 3. app_user (named app_user because 'user' is reserved in PostgreSQL)
    op.create_table(
        "app_user",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("role_label", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_app_user_organization_id", "app_user", ["organization_id"])
    op.create_index("ix_app_user_team_id", "app_user", ["team_id"])

    # 4. repository
    op.create_table(
        "repository",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("default_branch", sa.String(length=255), server_default="main", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("full_name"),
    )
    op.create_index("ix_repository_organization_id", "repository", ["organization_id"])

    # 5. project
    op.create_table(
        "project",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_project_organization_id", "project", ["organization_id"])

    # 6. identity_link
    op.create_table(
        "identity_link",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("app_user_id", sa.Integer(), nullable=False),
        sa.Column("integration", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("external_handle", sa.String(length=255), nullable=False),
        sa.Column("match_method", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["app_user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration", "external_id", name="uq_identity_link_integration_external"
        ),
    )
    op.create_index("ix_identity_link_app_user_id", "identity_link", ["app_user_id"])

    # 7. unmatched_entity
    op.create_table(
        "unmatched_entity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("integration", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("external_handle", sa.String(length=255), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("resolved_app_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["resolved_app_user_id"], ["app_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration", "external_id", name="uq_unmatched_entity_integration_external"
        ),
    )
    op.create_index(
        "ix_unmatched_entity_resolved_app_user_id",
        "unmatched_entity",
        ["resolved_app_user_id"],
    )

    # 8. work_item
    op.create_table(
        "work_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("raw_status", sa.String(length=64), nullable=False),
        sa.Column("assignee_app_user_id", sa.Integer(), nullable=True),
        sa.Column("priority", sa.String(length=32), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_flagged", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignee_app_user_id"], ["app_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_item_assignee_app_user_id", "work_item", ["assignee_app_user_id"])
    op.create_index("ix_work_item_external_id", "work_item", ["external_id"])
    op.create_index("ix_work_item_project_external", "work_item", ["project_id", "external_id"])
    op.create_index("ix_work_item_project_id", "work_item", ["project_id"])

    # 9. work_item_dependency
    op.create_table(
        "work_item_dependency",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("work_item_id", sa.Integer(), nullable=False),
        sa.Column("blocked_by_work_item_id", sa.Integer(), nullable=False),
        sa.Column("link_type", sa.String(length=64), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["blocked_by_work_item_id"], ["work_item.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_item_id"], ["work_item.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_work_item_dependency_blocked_by",
        "work_item_dependency",
        ["blocked_by_work_item_id"],
    )
    op.create_index(
        "ix_work_item_dependency_work_item_id",
        "work_item_dependency",
        ["work_item_id"],
    )

    # 10. pull_request
    op.create_table(
        "pull_request",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("body_excerpt", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("is_draft", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("branch_name", sa.String(length=255), nullable=False),
        sa.Column("author_app_user_id", sa.Integer(), nullable=True),
        sa.Column("review_state", sa.String(length=64), nullable=True),
        sa.Column("last_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checks_state", sa.String(length=64), nullable=True),
        sa.Column("created_at_source", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_commit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_app_user_id"], ["app_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["repository_id"], ["repository.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pull_request_author_app_user_id", "pull_request", ["author_app_user_id"])
    op.create_index("ix_pull_request_branch_name", "pull_request", ["branch_name"])
    op.create_index("ix_pull_request_repo_number", "pull_request", ["repository_id", "number"])
    op.create_index("ix_pull_request_repository_id", "pull_request", ["repository_id"])

    # 11. commit
    op.create_table(
        "commit",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("sha", sa.String(length=64), nullable=False),
        sa.Column("message_excerpt", sa.Text(), nullable=True),
        sa.Column("branch_name", sa.String(length=255), nullable=True),
        sa.Column("author_app_user_id", sa.Integer(), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_app_user_id"], ["app_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["repository_id"], ["repository.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "sha", name="uq_commit_repo_sha"),
    )
    op.create_index("ix_commit_author_app_user_id", "commit", ["author_app_user_id"])
    op.create_index("ix_commit_branch_name", "commit", ["branch_name"])
    op.create_index("ix_commit_repo_committed", "commit", ["repository_id", "committed_at"])
    op.create_index("ix_commit_repository_id", "commit", ["repository_id"])

    # 12. review
    op.create_table(
        "review",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pull_request_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("reviewer_app_user_id", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("body_excerpt", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pull_request_id"], ["pull_request.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_app_user_id"], ["app_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pull_request_id", "external_id", name="uq_review_pr_external_id"),
    )
    op.create_index("ix_review_pull_request_id", "review", ["pull_request_id"])
    op.create_index("ix_review_reviewer_app_user_id", "review", ["reviewer_app_user_id"])

    # 13. work_item_link
    op.create_table(
        "work_item_link",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("work_item_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=False),
        sa.Column("link_method", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["work_item_id"], ["work_item.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "work_item_id", "target_type", "target_id", name="uq_work_item_link_target"
        ),
    )
    op.create_index("ix_work_item_link_work_item_id", "work_item_link", ["work_item_id"])

    # 14. insight
    op.create_table(
        "insight",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subject_app_user_id", sa.Integer(), nullable=False),
        sa.Column("question_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["subject_app_user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_insight_evidence_hash", "insight", ["evidence_hash"])
    op.create_index("ix_insight_subject_app_user_id", "insight", ["subject_app_user_id"])
    op.create_index(
        "ix_insight_subject_question",
        "insight",
        ["subject_app_user_id", "question_type"],
    )

    # 15. agent_run
    op.create_table(
        "agent_run",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_app_user_id", sa.Integer(), nullable=True),
        sa.Column("subject_app_user_id", sa.Integer(), nullable=False),
        sa.Column("question_type", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_set", sa.JSON(), nullable=False),
        sa.Column("source_health", sa.JSON(), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("raw_model_output", sa.JSON(), nullable=True),
        sa.Column("validated_output", sa.JSON(), nullable=True),
        sa.Column("dropped_claims", sa.JSON(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_type", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_app_user_id"], ["app_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subject_app_user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_run_actor_app_user_id", "agent_run", ["actor_app_user_id"])
    op.create_index("ix_agent_run_subject_app_user_id", "agent_run", ["subject_app_user_id"])
    op.create_index(
        "ix_agent_run_subject_created",
        "agent_run",
        ["subject_app_user_id", "created_at"],
    )

    # 16. sync_run
    op.create_table(
        "sync_run",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_fetched", sa.Integer(), server_default="0", nullable=False),
        sa.Column("items_written", sa.Integer(), server_default="0", nullable=False),
        sa.Column("items_skipped", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_type", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_run_source_started", "sync_run", ["source", "started_at"])

    # 17. sync_cursor
    op.create_table(
        "sync_cursor",
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=255), nullable=False),
        sa.Column("cursor_value", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("source", "scope"),
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("sync_cursor")
    op.drop_table("sync_run")
    op.drop_table("agent_run")
    op.drop_table("insight")
    op.drop_table("work_item_link")
    op.drop_table("review")
    op.drop_table("commit")
    op.drop_table("pull_request")
    op.drop_table("work_item_dependency")
    op.drop_table("work_item")
    op.drop_table("unmatched_entity")
    op.drop_table("identity_link")
    op.drop_table("project")
    op.drop_table("repository")
    op.drop_table("app_user")
    op.drop_table("team")
    op.drop_table("organization")
