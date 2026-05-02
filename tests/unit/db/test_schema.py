"""Phase 1.1 で作成される 7 テーブルのスキーマ存在検証。

検証戦略:
- ``information_schema.tables`` でテーブル存在を確認
- ``information_schema.columns`` でカラム単位の data_type / is_nullable /
  numeric_precision / numeric_scale / character_maximum_length / udt_name を
  ``expected_schema.json`` と照合
- ``pg_constraint`` / ``pg_indexes`` で UNIQUE / PRIMARY KEY / FK / index を確認
- ``pg_enum`` で ``category_source_enum`` の許容値を確認

設計準拠:
- spec §受入条件「7 テーブルすべての存在」「主要カラムの型と NULL 制約」
- spec §テスト計画1「information_schema を SQL で読み出し、JSON フィクスチャと突合」
- planner レポート §4.2 「データ駆動でテストロジックを単純化」
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    import psycopg


_EXPECTED_SCHEMA_PATH = Path(__file__).resolve().parent / "expected_schema.json"


def _load_expected_schema() -> dict[str, Any]:
    """expected_schema.json を辞書としてロードする。

    Returns:
        ``tables`` / ``category_source_enum_values`` キーを持つ辞書。
    """
    with _EXPECTED_SCHEMA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


_EXPECTED = _load_expected_schema()
_EXPECTED_TABLES: dict[str, Any] = _EXPECTED["tables"]


# --- テーブル存在検証 -------------------------------------------------------


@pytest.mark.parametrize("table_name", sorted(_EXPECTED_TABLES.keys()))
def test_テーブルがpublicスキーマに存在する(
    psycopg_connection: psycopg.Connection,
    table_name: str,
) -> None:
    """``information_schema.tables`` に各テーブルが BASE TABLE として登録されていること。

    7 テーブル（institutions / accounts / categories / transactions /
    holdings / balance_snapshots / categorization_rules）の存在を、
    マイグレーション適用済み DB に対して検証する。
    """
    with psycopg_connection.cursor() as cur:
        cur.execute(
            """
            SELECT table_type
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table_name,),
        )
        row = cur.fetchone()

    assert row is not None, f"テーブル {table_name} が public スキーマに存在しません"
    assert row[0] == "BASE TABLE", f"{table_name} が BASE TABLE として作成されていません: {row[0]}"


# --- カラム単位の型・NULL 制約検証 -----------------------------------------


def _column_assertions() -> list[tuple[str, str, dict[str, Any]]]:
    """expected_schema.json をフラット化し、parametrize に渡せる形に整形する。

    Returns:
        ``[(table_name, column_name, expected_attrs), ...]`` の一覧。
    """
    rows: list[tuple[str, str, dict[str, Any]]] = []
    for table_name, table_def in _EXPECTED_TABLES.items():
        columns: dict[str, dict[str, Any]] = table_def["columns"]
        for column_name, attrs in columns.items():
            rows.append((table_name, column_name, attrs))
    return rows


@pytest.mark.parametrize(
    ("table_name", "column_name", "expected_attrs"),
    _column_assertions(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_カラムの型とNULL制約が期待値と一致する(
    psycopg_connection: psycopg.Connection,
    table_name: str,
    column_name: str,
    expected_attrs: dict[str, Any],
) -> None:
    """``information_schema.columns`` の data_type / is_nullable / numeric_precision /
    numeric_scale / character_maximum_length / udt_name が JSON 期待値と一致すること。

    ``data_type`` は PostgreSQL 標準名（例: ``text``, ``bigint``, ``numeric``,
    ``character``, ``timestamp with time zone``, ``USER-DEFINED``）。
    ENUM の場合は ``USER-DEFINED`` + ``udt_name`` で実体を判別する。
    """
    with psycopg_connection.cursor() as cur:
        cur.execute(
            """
            SELECT
                data_type,
                is_nullable,
                numeric_precision,
                numeric_scale,
                character_maximum_length,
                udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
            """,
            (table_name, column_name),
        )
        row = cur.fetchone()

    assert row is not None, (
        f"カラム {table_name}.{column_name} が information_schema.columns に存在しません"
    )
    data_type, is_nullable, num_precision, num_scale, char_max_len, udt_name = row

    assert data_type == expected_attrs["data_type"], (
        f"{table_name}.{column_name} の data_type が一致しません: "
        f"expected={expected_attrs['data_type']!r}, actual={data_type!r}"
    )

    expected_nullable = bool(expected_attrs["nullable"])
    actual_nullable = is_nullable == "YES"
    assert actual_nullable == expected_nullable, (
        f"{table_name}.{column_name} の NULL 許可が一致しません: "
        f"expected nullable={expected_nullable}, actual is_nullable={is_nullable!r}"
    )

    if "numeric_precision" in expected_attrs:
        assert num_precision == expected_attrs["numeric_precision"], (
            f"{table_name}.{column_name} の numeric_precision が一致しません: "
            f"expected={expected_attrs['numeric_precision']}, actual={num_precision}"
        )
    if "numeric_scale" in expected_attrs:
        assert num_scale == expected_attrs["numeric_scale"], (
            f"{table_name}.{column_name} の numeric_scale が一致しません: "
            f"expected={expected_attrs['numeric_scale']}, actual={num_scale}"
        )
    if "char_max_length" in expected_attrs:
        assert char_max_len == expected_attrs["char_max_length"], (
            f"{table_name}.{column_name} の character_maximum_length が一致しません: "
            f"expected={expected_attrs['char_max_length']}, actual={char_max_len}"
        )
    if "udt_name" in expected_attrs:
        assert udt_name == expected_attrs["udt_name"], (
            f"{table_name}.{column_name} の udt_name が一致しません: "
            f"expected={expected_attrs['udt_name']!r}, actual={udt_name!r}"
        )


# --- ENUM 型の検証 ----------------------------------------------------------


def test_category_source_enum_型が作成済(
    psycopg_connection: psycopg.Connection,
) -> None:
    """``category_source_enum`` 型が ``pg_type`` に登録されていること。

    spec §実装方針5 と planner §4.1 に従い、PostgreSQL ENUM として
    実体化する。``00-initial-design.md §4.2`` の TEXT+CHECK 案ではなく、
    spec の指示を優先する。
    """
    with psycopg_connection.cursor() as cur:
        cur.execute(
            """
            SELECT typtype
            FROM pg_type
            WHERE typname = 'category_source_enum'
            """,
        )
        row = cur.fetchone()

    assert row is not None, "category_source_enum 型が作成されていません"
    assert row[0] == "e", f"category_source_enum が ENUM 型ではありません: typtype={row[0]!r}"


def test_category_source_enum_の許容値が3つだけ(
    psycopg_connection: psycopg.Connection,
) -> None:
    """``pg_enum`` 上の ``category_source_enum`` の許容値が ``rule`` / ``llm`` /
    ``manual`` の 3 つのみであること。

    spec §受入条件「ENUM 許容値が ('rule','llm','manual') のみ」を直接検証する。
    余分な値（例: ``unknown``）が混入していないことを ``len`` で担保する。
    """
    with psycopg_connection.cursor() as cur:
        cur.execute(
            """
            SELECT enumlabel
            FROM pg_enum
            JOIN pg_type ON pg_type.oid = pg_enum.enumtypid
            WHERE pg_type.typname = 'category_source_enum'
            ORDER BY enumsortorder
            """,
        )
        labels = [row[0] for row in cur.fetchall()]

    assert labels == _EXPECTED["category_source_enum_values"], (
        f"category_source_enum の許容値が期待と一致しません: "
        f"expected={_EXPECTED['category_source_enum_values']}, actual={labels}"
    )


# --- 主要制約・インデックスの検証 -------------------------------------------


def test_transactions_hash_にUNIQUE制約が存在する(
    psycopg_connection: psycopg.Connection,
) -> None:
    """``transactions.hash`` 単独の UNIQUE 制約 / インデックスが存在すること。

    spec §受入条件「transactions.hash の UNIQUE インデックス存在」と
    ADR-006 の冪等性要件を満たすことを直接検証する。
    """
    with psycopg_connection.cursor() as cur:
        cur.execute(
            """
            SELECT i.oid::regclass::text, idx.indisunique
            FROM pg_index idx
            JOIN pg_class c ON c.oid = idx.indrelid
            JOIN pg_class i ON i.oid = idx.indexrelid
            WHERE c.relname = 'transactions'
              AND idx.indisunique
              AND (
                  SELECT array_agg(att.attname ORDER BY att.attnum)
                  FROM unnest(idx.indkey) AS k(attnum)
                  JOIN pg_attribute att
                    ON att.attrelid = c.oid AND att.attnum = k.attnum
              ) = ARRAY['hash']::name[]
            """,
        )
        rows = cur.fetchall()

    assert rows, "transactions.hash 単独の UNIQUE インデックスが見つかりません"


def test_transactions_raw_payloadのデフォルトがJSONB空オブジェクト(
    psycopg_connection: psycopg.Connection,
) -> None:
    """``transactions.raw_payload`` の DEFAULT が ``'{}'::jsonb`` であること。

    spec §実装方針6 と ADR-004 で要求される、空オブジェクト初期化を検証する。
    DDL の DEFAULT は ``information_schema.columns.column_default`` に
    PostgreSQL 標準形式（例: ``'{}'::jsonb``）で格納される。
    """
    with psycopg_connection.cursor() as cur:
        cur.execute(
            """
            SELECT column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'transactions'
              AND column_name = 'raw_payload'
            """,
        )
        row = cur.fetchone()

    assert row is not None, "transactions.raw_payload カラムが存在しません"
    default_expr = row[0]
    assert default_expr is not None, "transactions.raw_payload に DEFAULT が設定されていません"
    # PostgreSQL の正規化形式は "'{}'::jsonb" だが、空白の有無に揺れる可能性が
    # あるため、JSONB キャストと空オブジェクトリテラルを両方含むかを確認する。
    assert "jsonb" in default_expr.lower(), (
        f"raw_payload DEFAULT が JSONB キャストを含みません: {default_expr!r}"
    )
    assert "{}" in default_expr, (
        f"raw_payload DEFAULT が空オブジェクトを含みません: {default_expr!r}"
    )


def test_balance_snapshots_の主キーが複合キー(
    psycopg_connection: psycopg.Connection,
) -> None:
    """``balance_snapshots`` の PRIMARY KEY が ``(account_id, as_of)`` の
    複合キーであること（spec §4.2 DDL）。
    """
    with psycopg_connection.cursor() as cur:
        cur.execute(
            """
            SELECT array_agg(att.attname ORDER BY u.ord)
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN unnest(con.conkey) WITH ORDINALITY AS u(attnum, ord) ON TRUE
            JOIN pg_attribute att
              ON att.attrelid = con.conrelid AND att.attnum = u.attnum
            WHERE c.relname = 'balance_snapshots'
              AND con.contype = 'p'
            GROUP BY con.conname
            """,
        )
        row = cur.fetchone()

    assert row is not None, "balance_snapshots に PRIMARY KEY が定義されていません"
    pk_columns = list(row[0])
    assert pk_columns == ["account_id", "as_of"], (
        f"balance_snapshots の PK 構成カラムが一致しません: actual={pk_columns}"
    )


def test_accounts_にinstitution_account_no_のUNIQUE制約(
    psycopg_connection: psycopg.Connection,
) -> None:
    """``accounts(institution, account_no)`` の UNIQUE 制約が存在すること。"""
    with psycopg_connection.cursor() as cur:
        cur.execute(
            """
            SELECT array_agg(att.attname ORDER BY u.ord)
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN unnest(con.conkey) WITH ORDINALITY AS u(attnum, ord) ON TRUE
            JOIN pg_attribute att
              ON att.attrelid = con.conrelid AND att.attnum = u.attnum
            WHERE c.relname = 'accounts'
              AND con.contype = 'u'
            GROUP BY con.conname
            """,
        )
        unique_groups = [tuple(row[0]) for row in cur.fetchall()]

    assert ("institution", "account_no") in unique_groups, (
        f"accounts(institution, account_no) の UNIQUE 制約が見つかりません: "
        f"actual={unique_groups}"
    )


def test_holdings_にaccount_symbol_as_of_のUNIQUE制約(
    psycopg_connection: psycopg.Connection,
) -> None:
    """``holdings(account_id, symbol, as_of)`` の UNIQUE 制約が存在すること。"""
    with psycopg_connection.cursor() as cur:
        cur.execute(
            """
            SELECT array_agg(att.attname ORDER BY u.ord)
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN unnest(con.conkey) WITH ORDINALITY AS u(attnum, ord) ON TRUE
            JOIN pg_attribute att
              ON att.attrelid = con.conrelid AND att.attnum = u.attnum
            WHERE c.relname = 'holdings'
              AND con.contype = 'u'
            GROUP BY con.conname
            """,
        )
        unique_groups = [tuple(row[0]) for row in cur.fetchall()]

    assert ("account_id", "symbol", "as_of") in unique_groups, (
        f"holdings(account_id, symbol, as_of) の UNIQUE 制約が見つかりません: "
        f"actual={unique_groups}"
    )


@pytest.mark.parametrize(
    ("table_name", "fk_columns", "ref_table", "ref_columns"),
    [
        ("accounts", ("institution",), "institutions", ("code",)),
        ("categories", ("parent_id",), "categories", ("id",)),
        ("transactions", ("account_id",), "accounts", ("id",)),
        ("transactions", ("category_id",), "categories", ("id",)),
        ("transactions", ("linked_tx_id",), "transactions", ("id",)),
        ("holdings", ("account_id",), "accounts", ("id",)),
        ("balance_snapshots", ("account_id",), "accounts", ("id",)),
        ("categorization_rules", ("category_id",), "categories", ("id",)),
    ],
)
def test_主要外部キー制約が存在する(
    psycopg_connection: psycopg.Connection,
    table_name: str,
    fk_columns: tuple[str, ...],
    ref_table: str,
    ref_columns: tuple[str, ...],
) -> None:
    """各テーブルが期待される FK を `pg_constraint`（contype='f'）に持つこと。

    §4.2 DDL の REFERENCES を網羅的に検証する。FK 名は実装側で
    ``fk_*`` と名付ける方針だが、ここでは名前ではなく「対象カラム → 参照テーブル
    と列」の意味的合致を検証する（テストが過度に実装名に縛られないように）。
    """
    with psycopg_connection.cursor() as cur:
        cur.execute(
            """
            SELECT
                array_agg(att.attname ORDER BY u.ord) AS local_cols,
                ref.relname AS ref_table,
                array_agg(ref_att.attname ORDER BY u.ord) AS ref_cols
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN pg_class ref ON ref.oid = con.confrelid
            JOIN unnest(con.conkey) WITH ORDINALITY AS u(attnum, ord) ON TRUE
            JOIN pg_attribute att
              ON att.attrelid = con.conrelid AND att.attnum = u.attnum
            JOIN unnest(con.confkey) WITH ORDINALITY AS uref(attnum, ord)
              ON uref.ord = u.ord
            JOIN pg_attribute ref_att
              ON ref_att.attrelid = con.confrelid AND ref_att.attnum = uref.attnum
            WHERE c.relname = %s
              AND con.contype = 'f'
            GROUP BY con.conname, ref.relname
            """,
            (table_name,),
        )
        rows = cur.fetchall()

    matches = [
        (tuple(local), ref, tuple(refcols))
        for (local, ref, refcols) in rows
    ]
    expected = (fk_columns, ref_table, ref_columns)
    assert expected in matches, (
        f"{table_name} の FK {fk_columns} -> {ref_table}{ref_columns} が見つかりません: "
        f"actual={matches}"
    )


@pytest.mark.parametrize(
    "expected_columns",
    [
        ("account_id", "occurred_on"),
        ("category_id", "occurred_on"),
    ],
)
def test_transactionsの主要インデックスが存在する(
    psycopg_connection: psycopg.Connection,
    expected_columns: tuple[str, str],
) -> None:
    """``transactions(account_id, occurred_on)`` と ``(category_id, occurred_on)`` の
    インデックスが存在すること（§4.2 DDL の CREATE INDEX 部分）。

    インデックス名は問わず、対象カラム順序のみで一致を判定する。
    """
    with psycopg_connection.cursor() as cur:
        cur.execute(
            """
            SELECT array_agg(att.attname ORDER BY u.ord)
            FROM pg_index idx
            JOIN pg_class c ON c.oid = idx.indrelid
            JOIN unnest(idx.indkey) WITH ORDINALITY AS u(attnum, ord) ON TRUE
            JOIN pg_attribute att
              ON att.attrelid = c.oid AND att.attnum = u.attnum
            WHERE c.relname = 'transactions'
              AND NOT idx.indisunique
              AND NOT idx.indisprimary
            GROUP BY idx.indexrelid
            """,
        )
        index_columns = [tuple(row[0]) for row in cur.fetchall()]

    assert expected_columns in index_columns, (
        f"transactions{expected_columns} のインデックスが見つかりません: "
        f"actual={index_columns}"
    )
