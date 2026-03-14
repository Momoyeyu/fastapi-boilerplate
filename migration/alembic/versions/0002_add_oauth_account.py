"""Add oauth_account table and make user.hashed_password nullable.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make hashed_password nullable for SSO-only users
    op.alter_column("user", "hashed_password", existing_type=sa.String(), nullable=True)

    # Create oauth_account table
    op.create_table(
        "oauth_account",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("provider_email", sa.String(255), nullable=True),
        sa.Column("provider_username", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
    )
    op.create_index("ix_oauth_account_user_id", "oauth_account", ["user_id"])
    op.create_index("ix_oauth_account_provider_email", "oauth_account", ["provider", "provider_email"])


def downgrade() -> None:
    op.drop_index("ix_oauth_account_provider_email", table_name="oauth_account")
    op.drop_index("ix_oauth_account_user_id", table_name="oauth_account")
    op.drop_table("oauth_account")
    op.alter_column("user", "hashed_password", existing_type=sa.String(), nullable=False)
