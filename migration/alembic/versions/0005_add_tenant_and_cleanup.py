"""Add tenant and user_tenant tables; remove nickname, role from user; rename password to hashed_password; drop refresh_token table.

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop refresh_token table (moved to Redis)
    op.drop_index("ix_refresh_token_user_id", table_name="refresh_token")
    op.drop_index("ix_refresh_token_token", table_name="refresh_token")
    op.drop_table("refresh_token")

    # 2. Alter user table: drop nickname, role; rename password -> hashed_password
    op.drop_column("user", "nickname")
    op.drop_column("user", "role")
    op.alter_column("user", "password", new_column_name="hashed_password")

    # 3. Create tenant table
    op.create_table(
        "tenant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("ix_tenant_name", "tenant", ["name"], unique=True)

    # 4. Create user_tenant table
    op.create_table(
        "user_tenant",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_role", sa.String(), nullable=False, server_default=sa.text("'member'")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_user_tenant"),
    )
    op.create_index("ix_user_tenant_user_id", "user_tenant", ["user_id"])
    op.create_index("ix_user_tenant_tenant_id", "user_tenant", ["tenant_id"])


def downgrade() -> None:
    # Drop user_tenant
    op.drop_index("ix_user_tenant_tenant_id", table_name="user_tenant")
    op.drop_index("ix_user_tenant_user_id", table_name="user_tenant")
    op.drop_table("user_tenant")

    # Drop tenant
    op.drop_index("ix_tenant_name", table_name="tenant")
    op.drop_table("tenant")

    # Restore user table columns
    op.alter_column("user", "hashed_password", new_column_name="password")
    op.add_column("user", sa.Column("role", sa.String(), nullable=False, server_default=sa.text("'user'")))
    op.add_column("user", sa.Column("nickname", sa.String(), nullable=True))

    # Restore refresh_token table
    op.create_table(
        "refresh_token",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refresh_token_token", "refresh_token", ["token"], unique=True)
    op.create_index("ix_refresh_token_user_id", "refresh_token", ["user_id"], unique=False)
