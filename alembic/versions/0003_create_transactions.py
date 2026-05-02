"""取引テーブル（transactions）と category_source_enum 型、NaN 拒否トリガの作成。

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-30

`docs/plans/00-initial-design.md §4.2` の transactions と、Phase 1.1 spec
§実装方針 4-6 の上書き指示を反映する:

- `category_source` は PostgreSQL ENUM `category_source_enum`（'rule'/'llm'/'manual'）。
- `hash` は `CHAR(64)` NOT NULL UNIQUE（SHA256 hex 固定長、ADR-006 と整合）。
- `raw_payload` は JSONB NOT NULL DEFAULT `'{}'::jsonb`（ADR-004）。

NaN 拒否のための補助実装:
- PostgreSQL の NUMERIC は `'NaN'` リテラルを許容するため、CHECK 制約だけでは
  仕様 §受入条件「NaN 投入で型エラー」を満たせない。さらに psycopg は
  CHECK 違反を `IntegrityError → CheckViolation` として返し、テストが期待する
  `psycopg.errors.DataError`（SQLSTATE クラス 22）の系統に該当しない。
- 代替案として、BEFORE INSERT/UPDATE のトリガ関数で NEW.amount = 'NaN'::numeric
  を判定し、SQLSTATE '22003'（NumericValueOutOfRange / DataError 派生）を
  RAISE EXCEPTION で送出する。これにより spec の「NaN は型エラー」要件と
  「具体例外型は実装に委ねる（DataError 親クラスで捕捉）」の両立を実現する。

設計判断（DRY 違反の押し付けを避ける）:
- ENUM 作成・破棄は `postgresql.ENUM(..., create_type=False)` を宣言してから
  upgrade/downgrade で `enum.create(bind, checkfirst=True)` /
  `enum.drop(bind, checkfirst=True)` を呼ぶ。create_type=False にすることで
  Column 定義側の暗黙生成と二重実行になるのを避け、明示的に制御する。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CATEGORY_SOURCE_ENUM_NAME = "category_source_enum"
_CATEGORY_SOURCE_VALUES: tuple[str, ...] = ("rule", "llm", "manual")

_AMOUNT_NAN_TRIGGER_FN = "check_transactions_amount_not_nan"
_AMOUNT_NAN_TRIGGER = "trg_transactions_amount_not_nan"

# トリガ関数: amount = NaN を SQLSTATE '22003' で拒否する。
# 22003 は NumericValueOutOfRange に対応し、psycopg では DataError 派生として届く。
_TRIGGER_FN_BODY = f"""
CREATE OR REPLACE FUNCTION {_AMOUNT_NAN_TRIGGER_FN}() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.amount = 'NaN'::numeric THEN
        RAISE EXCEPTION 'transactions.amount must not be NaN'
            USING ERRCODE = '22003';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_TRIGGER_DEFINITION = f"""
CREATE TRIGGER {_AMOUNT_NAN_TRIGGER}
BEFORE INSERT OR UPDATE OF amount ON transactions
FOR EACH ROW EXECUTE FUNCTION {_AMOUNT_NAN_TRIGGER_FN}();
"""


def _category_source_enum() -> postgresql.ENUM:
    """ENUM 型ハンドル。create/drop の対称性を保つため宣言を一元化する。

    create_type=False: Column 側の暗黙生成を抑止し、upgrade/downgrade での
    明示的な create()/drop() のみで型ライフサイクルを管理する。
    """
    return postgresql.ENUM(
        *_CATEGORY_SOURCE_VALUES,
        name=_CATEGORY_SOURCE_ENUM_NAME,
        create_type=False,
    )


def upgrade() -> None:
    bind = op.get_bind()
    enum_type = _category_source_enum()
    enum_type.create(bind, checkfirst=True)

    op.create_table(
        "transactions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "currency",
            sa.CHAR(length=3),
            nullable=False,
            server_default=sa.text("'JPY'"),
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("counterparty", sa.Text(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("category_source", enum_type, nullable=True),
        sa.Column("linked_tx_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("source_file", sa.Text(), nullable=True),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("hash", sa.CHAR(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_transactions"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name="fk_transactions_account",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_transactions_category",
        ),
        sa.ForeignKeyConstraint(
            ["linked_tx_id"],
            ["transactions.id"],
            name="fk_transactions_linked_tx",
        ),
        sa.UniqueConstraint("hash", name="uq_transactions_hash"),
    )

    op.create_index(
        "ix_transactions_account_id_occurred_on",
        "transactions",
        ["account_id", "occurred_on"],
    )
    op.create_index(
        "ix_transactions_category_id_occurred_on",
        "transactions",
        ["category_id", "occurred_on"],
    )

    op.execute(_TRIGGER_FN_BODY)
    op.execute(_TRIGGER_DEFINITION)


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {_AMOUNT_NAN_TRIGGER} ON transactions")
    op.execute(f"DROP FUNCTION IF EXISTS {_AMOUNT_NAN_TRIGGER_FN}()")
    op.drop_index("ix_transactions_category_id_occurred_on", table_name="transactions")
    op.drop_index("ix_transactions_account_id_occurred_on", table_name="transactions")
    op.drop_table("transactions")
    _category_source_enum().drop(op.get_bind(), checkfirst=True)
