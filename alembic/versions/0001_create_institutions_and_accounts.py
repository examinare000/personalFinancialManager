"""機関・口座マスタテーブルの作成。

Revision ID: 0001
Revises:
Create Date: 2026-04-30

`docs/plans/00-initial-design.md §4.2` の最上流マスタである institutions と
accounts を作成する。後続の transactions / holdings / balance_snapshots は
accounts.id を参照するため、本マイグレーションが Phase 1.1 の起点となる。

設計判断:
- 制約は名前付き（`ck_*` / `fk_*` / `uq_*`）にして migration 識別性を高める
  （planner レポート §5.4「型・カラム定義の標準」）。
- accounts.id は BIGSERIAL（`sa.BigInteger` + `autoincrement=True` + PK）。
- accounts.currency は固定長 3 文字で 'JPY' をデフォルト。テストでは
  character_maximum_length=3 / data_type='character' を期待する。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_INSTITUTION_KINDS: tuple[str, ...] = ("bank", "securities", "fund", "ec", "wallet")


def upgrade() -> None:
    op.create_table(
        "institutions",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("code", name="pk_institutions"),
        sa.CheckConstraint(
            "kind IN ('" + "', '".join(_INSTITUTION_KINDS) + "')",
            name="ck_institutions_kind",
        ),
    )

    op.create_table(
        "accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("institution", sa.Text(), nullable=False),
        sa.Column("account_no", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column(
            "currency",
            sa.CHAR(length=3),
            nullable=False,
            server_default=sa.text("'JPY'"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_accounts"),
        sa.ForeignKeyConstraint(
            ["institution"],
            ["institutions.code"],
            name="fk_accounts_institution",
        ),
        sa.UniqueConstraint(
            "institution",
            "account_no",
            name="uq_accounts_institution_account_no",
        ),
    )


def downgrade() -> None:
    op.drop_table("accounts")
    op.drop_table("institutions")
