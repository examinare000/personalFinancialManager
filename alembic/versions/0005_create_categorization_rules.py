"""自動分類ルールテーブル（categorization_rules）の作成。

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-30

`docs/plans/00-initial-design.md §4.2` の categorization_rules を作成する。
priority / match_field / match_type / pattern / category_id / is_active の
カラム構成で、Phase 4.1 LLM 分類サービスとの併用を想定したルールエンジンの
土台となる。

設計判断:
- priority のデフォルトは 100（§4.2 DDL の DEFAULT 100）。低い優先度から
  評価していき、複数ルールが当たる場合は priority 値の小さい方を優先する想定。
- match_type は CHECK 制約で 'regex' / 'contains' / 'exact' のみ許可。
  カテゴリと異なり ENUM 化しないのは、将来的に 'amount_sign' 等の追加が
  発生し得るためテキスト + CHECK の方が柔軟（design/01-data-model.md §3）。
- match_field は CHECK 制約を持たせない。description / counterparty 以外への
  拡張余地を残すため、文字列の自由形式とする（§4.2 DDL のコメントどおり）。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_MATCH_TYPES: tuple[str, ...] = ("regex", "contains", "exact")


def upgrade() -> None:
    op.create_table(
        "categorization_rules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("100"),
        ),
        sa.Column("match_field", sa.Text(), nullable=False),
        sa.Column("match_type", sa.Text(), nullable=False),
        sa.Column("pattern", sa.Text(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_categorization_rules"),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_categorization_rules_category",
        ),
        sa.CheckConstraint(
            "match_type IN ('" + "', '".join(_MATCH_TYPES) + "')",
            name="ck_categorization_rules_match_type",
        ),
    )


def downgrade() -> None:
    op.drop_table("categorization_rules")
