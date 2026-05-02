"""保有銘柄（holdings）と残高スナップショット（balance_snapshots）の作成。

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-30

`docs/plans/00-initial-design.md §4.2` の holdings / balance_snapshots を作成する。

設計判断:
- holdings.quantity / unit_cost は NUMERIC(18,6)、market_value / balance は
  NUMERIC(18,4)。前者は投資信託の口数等で 6 桁精度が必要、後者は通貨単位の
  4 桁で十分（ADR-005）。
- balance_snapshots は (account_id, as_of) の複合 PK。スナップショット粒度を
  日次以下に固定し、同日重複を防ぐ（§4.2 DDL の指定どおり）。
- holdings.raw_payload は §4.2 DDL に DEFAULT 指定なし。NOT NULL のみ強制し、
  挿入側で必ず値を渡す方針（transactions と異なり、holdings は外部入力の
  生データを必須とする）。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "holdings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("symbol_kind", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("market_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("unit_cost", sa.Numeric(18, 6), nullable=True),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_holdings"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_holdings_account",
        ),
        sa.UniqueConstraint(
            "account_id",
            "symbol",
            "as_of",
            name="uq_holdings_account_symbol_as_of",
        ),
    )

    op.create_table(
        "balance_snapshots",
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("balance", sa.Numeric(18, 4), nullable=False),
        sa.PrimaryKeyConstraint(
            "account_id",
            "as_of",
            name="pk_balance_snapshots",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_balance_snapshots_account",
        ),
    )


def downgrade() -> None:
    op.drop_table("balance_snapshots")
    op.drop_table("holdings")
