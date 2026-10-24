"""Feature 002: roles, NSE allow-list, security settings, standalone tool.

Adds `role` to operator_accounts, `selected_scripts` to discovery_profiles,
and five new tables (nse_script_allowlist_entries, security_settings,
tool_tasks, tool_check_runs, tool_check_results). New AuditEventType enum
members are a Python-side StrEnum (SQLAlchemy stores it as a plain string
column) so no DB-side enum migration is required for them.

Revises: (none — first real Alembic migration for this project; the
baseline feature-001 schema is provisioned via `db.init.main()` /
`Base.metadata.create_all`, consistent with how this repo has always
bootstrapped a fresh install. This migration applies the feature-002
delta on top of that baseline.)

Revision ID: 0002_feature_002
Revises:
Create Date: 2026-10-21

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_feature_002"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "operator_accounts" in existing_tables:
        existing_columns = {c["name"] for c in inspector.get_columns("operator_accounts")}
        if "role" not in existing_columns:
            with op.batch_alter_table("operator_accounts") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "role", sa.String(length=32), nullable=False, server_default="operator"
                    )
                )
            # Data migration companion to FR-030's "first account is
            # Administrator" bootstrap rule: an UPGRADE (as opposed to a
            # fresh install) may already have accounts created under
            # feature 001's single-role model, which the ADD COLUMN above
            # defaults to 'operator'. Promote the earliest-created existing
            # account to Administrator so an upgraded install is never left
            # with zero administrators (mirrors the last-admin invariant
            # this feature otherwise enforces going forward).
            accounts_table = sa.table(
                "operator_accounts",
                sa.column("id", sa.String),
                sa.column("role", sa.String),
                sa.column("created_at", sa.DateTime),
            )
            first_account_id = bind.execute(
                sa.select(accounts_table.c.id).order_by(accounts_table.c.created_at.asc()).limit(1)
            ).scalar()
            if first_account_id is not None:
                op.execute(
                    accounts_table.update()
                    .where(accounts_table.c.id == first_account_id)
                    .values(role="administrator")
                )

    if "discovery_profiles" in existing_tables:
        existing_columns = {c["name"] for c in inspector.get_columns("discovery_profiles")}
        if "selected_scripts" not in existing_columns:
            with op.batch_alter_table("discovery_profiles") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "selected_scripts", sa.JSON(), nullable=False, server_default="[]"
                    )
                )

    if "nse_script_allowlist_entries" not in existing_tables:
        op.create_table(
            "nse_script_allowlist_entries",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("script_id", sa.String(length=128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("safety", sa.String(length=16), nullable=False, server_default="safe"),
            sa.Column("expected_ports", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by", sa.String(length=36), sa.ForeignKey("operator_accounts.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_nse_script_allowlist_entries_script_id",
            "nse_script_allowlist_entries",
            ["script_id"],
            unique=True,
        )

    if "security_settings" not in existing_tables:
        op.create_table(
            "security_settings",
            sa.Column("key", sa.String(length=64), primary_key=True),
            sa.Column("value", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    if "tool_tasks" not in existing_tables:
        op.create_table(
            "tool_tasks",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tool", sa.String(length=32), nullable=False, server_default="default_credentials"),
            sa.Column("target_scope", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("port", sa.Integer(), nullable=False),
            sa.Column("service", sa.String(length=16), nullable=False),
            sa.Column("recurrence", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("next_run_at", sa.DateTime(), nullable=False),
            sa.Column("overlap_policy", sa.String(length=16), nullable=False, server_default="skip"),
            sa.Column("catch_up_policy", sa.String(length=16), nullable=False, server_default="run_once"),
            sa.Column("last_triggered_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.String(length=36), sa.ForeignKey("operator_accounts.id"), nullable=True),
        )

    if "tool_check_runs" not in existing_tables:
        op.create_table(
            "tool_check_runs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tool_task_id", sa.String(length=36), sa.ForeignKey("tool_tasks.id"), nullable=True),
            sa.Column("trigger", sa.String(length=16), nullable=False, server_default="manual"),
            sa.Column("triggered_by_id", sa.String(length=36), sa.ForeignKey("operator_accounts.id"), nullable=True),
            sa.Column("target_scope", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("port", sa.Integer(), nullable=False),
            sa.Column("service", sa.String(length=16), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("summary", sa.JSON(), nullable=False, server_default="{}"),
        )
        op.create_index("ix_tool_check_runs_tool_task_id", "tool_check_runs", ["tool_task_id"])
        op.create_index("ix_tool_check_runs_status", "tool_check_runs", ["status"])
        op.create_index("ix_tool_check_runs_started_at", "tool_check_runs", ["started_at"])

    if "tool_check_results" not in existing_tables:
        op.create_table(
            "tool_check_results",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("run_id", sa.String(length=36), sa.ForeignKey("tool_check_runs.id"), nullable=False),
            sa.Column("address", sa.String(length=128), nullable=False),
            sa.Column("result", sa.String(length=16), nullable=False),
            sa.Column("attempts_made", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        )
        op.create_index("ix_tool_check_results_run_id", "tool_check_results", ["run_id"])


def downgrade() -> None:
    op.drop_table("tool_check_results")
    op.drop_table("tool_check_runs")
    op.drop_table("tool_tasks")
    op.drop_table("security_settings")
    op.drop_table("nse_script_allowlist_entries")

    with op.batch_alter_table("discovery_profiles") as batch_op:
        batch_op.drop_column("selected_scripts")

    with op.batch_alter_table("operator_accounts") as batch_op:
        batch_op.drop_column("role")
