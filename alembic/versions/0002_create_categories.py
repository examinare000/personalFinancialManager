"""カテゴリ階層テーブルの作成。

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-30

`docs/plans/00-initial-design.md §4.2` の categories テーブル。
自己参照 FK で階層構造を表現する（root カテゴリは parent_id IS NULL）。

設計判断:
- id は SERIAL（`sa.Integer` + `autoincrement=True` + PK）。BIGSERIAL ではなく
  SERIAL を採用するのは §4.2 DDL の指定どおりで、カテゴリ件数が爆発しない
  ディメンションテーブルだから（運用的に約 100〜1,000 件想定）。
- kind の許容値は CHECK 制約。ENUM 型は category_source に限定し、
  ディメンション側はテキストで運用しやすさを優先する。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CATEGORY_KINDS: tuple[str, ...] = ("expense", "income", "transfer", "investment")


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["categories.id"],
            name="fk_categories_parent",
        ),
        sa.CheckConstraint(
            "kind IN ('" + "', '".join(_CATEGORY_KINDS) + "')",
            name="ck_categories_kind",
        ),
    )


def downgrade() -> None:
    op.drop_table("categories")
