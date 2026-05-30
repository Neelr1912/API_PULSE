"""add api_logs and upload_history

Revision ID: 002_upload
Revises: 001_initial
Create Date: 2026-05-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_upload"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # upload_id: backfill existing rows then enforce NOT NULL
    op.add_column("api_logs", sa.Column("upload_id", sa.String(length=36), nullable=True))
    op.execute(sa.text("UPDATE api_logs SET upload_id = 'legacy-import' WHERE upload_id IS NULL"))
    op.alter_column("api_logs", "upload_id", nullable=False)
    op.create_index(op.f("ix_api_logs_upload_id"), "api_logs", ["upload_id"], unique=False)

    op.add_column(
        "api_logs",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.alter_column(
        "api_logs",
        "response_time_ms",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using="response_time_ms::double precision",
    )
    op.alter_column(
        "api_logs",
        "payload_size_bytes",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using="payload_size_bytes::double precision",
    )

    op.create_table(
        "upload_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("upload_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("inserted_rows", sa.Integer(), nullable=False),
        sa.Column("failed_rows", sa.Integer(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_upload_history_id"), "upload_history", ["id"], unique=False)
    op.create_index(op.f("ix_upload_history_upload_id"), "upload_history", ["upload_id"], unique=False)
    op.create_index(op.f("ix_upload_history_user_id"), "upload_history", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_upload_history_user_id"), table_name="upload_history")
    op.drop_index(op.f("ix_upload_history_upload_id"), table_name="upload_history")
    op.drop_index(op.f("ix_upload_history_id"), table_name="upload_history")
    op.drop_table("upload_history")

    op.alter_column(
        "api_logs",
        "payload_size_bytes",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="payload_size_bytes::integer",
    )
    op.alter_column(
        "api_logs",
        "response_time_ms",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="response_time_ms::integer",
    )
    op.drop_column("api_logs", "created_at")
    op.drop_index(op.f("ix_api_logs_upload_id"), table_name="api_logs")
    op.drop_column("api_logs", "upload_id")
