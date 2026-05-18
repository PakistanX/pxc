"""Drop FieldLogSeq; use FieldLogEntry.id as the entry id.

Existing log data is dropped — there is no backward-compat requirement.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-18 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the per-log next_id counter table.
    with op.batch_alter_table("fieldlogseq", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_fieldlogseq_user_id"))
        batch_op.drop_index(batch_op.f("ix_fieldlogseq_key"))
        batch_op.drop_index(batch_op.f("ix_fieldlogseq_course_id"))
        batch_op.drop_index(batch_op.f("ix_fieldlogseq_activity_name"))
        batch_op.drop_index(batch_op.f("ix_fieldlogseq_activity_id"))
    op.drop_table("fieldlogseq")

    # Rebuild fieldlogentry without the entry_id column or the 6-tuple unique
    # constraint. Existing rows are discarded.
    with op.batch_alter_table("fieldlogentry", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_fieldlogentry_user_id"))
        batch_op.drop_index(batch_op.f("ix_fieldlogentry_key"))
        batch_op.drop_index(batch_op.f("ix_fieldlogentry_course_id"))
        batch_op.drop_index(batch_op.f("ix_fieldlogentry_activity_name"))
        batch_op.drop_index(batch_op.f("ix_fieldlogentry_activity_id"))
    op.drop_table("fieldlogentry")

    op.create_table(
        "fieldlogentry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("activity_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("activity_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("value", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("fieldlogentry", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_fieldlogentry_activity_id"), ["activity_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_fieldlogentry_activity_name"),
            ["activity_name"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_fieldlogentry_course_id"), ["course_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_fieldlogentry_key"), ["key"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_fieldlogentry_user_id"), ["user_id"], unique=False
        )


def downgrade() -> None:
    # Recreate the pre-0005 schema. Existing rows in the new fieldlogentry
    # are dropped (the entry_id column was discarded on upgrade).
    with op.batch_alter_table("fieldlogentry", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_fieldlogentry_user_id"))
        batch_op.drop_index(batch_op.f("ix_fieldlogentry_key"))
        batch_op.drop_index(batch_op.f("ix_fieldlogentry_course_id"))
        batch_op.drop_index(batch_op.f("ix_fieldlogentry_activity_name"))
        batch_op.drop_index(batch_op.f("ix_fieldlogentry_activity_id"))
    op.drop_table("fieldlogentry")

    op.create_table(
        "fieldlogentry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("activity_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("activity_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("value", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_id", "activity_name", "activity_id", "user_id", "key", "entry_id"
        ),
    )
    with op.batch_alter_table("fieldlogentry", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_fieldlogentry_activity_id"), ["activity_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_fieldlogentry_activity_name"),
            ["activity_name"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_fieldlogentry_course_id"), ["course_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_fieldlogentry_key"), ["key"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_fieldlogentry_user_id"), ["user_id"], unique=False
        )

    op.create_table(
        "fieldlogseq",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("activity_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("activity_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("next_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_id", "activity_name", "activity_id", "user_id", "key"
        ),
    )
    with op.batch_alter_table("fieldlogseq", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_fieldlogseq_activity_id"), ["activity_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_fieldlogseq_activity_name"), ["activity_name"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_fieldlogseq_course_id"), ["course_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_fieldlogseq_key"), ["key"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_fieldlogseq_user_id"), ["user_id"], unique=False
        )
