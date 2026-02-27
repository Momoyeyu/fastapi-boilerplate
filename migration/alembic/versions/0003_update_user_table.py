from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("user", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    op.alter_column("user", "email", existing_type=sa.String(), nullable=False)

    op.create_index("ix_user_username", "user", ["username"])
    op.create_index("ix_user_email", "user", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_user_email", table_name="user")
    op.drop_index("ix_user_username", table_name="user")

    op.alter_column("user", "email", existing_type=sa.String(), nullable=True)

    op.drop_column("user", "deleted_at")
    op.drop_column("user", "is_deleted")
