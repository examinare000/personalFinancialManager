"""Phase 1.1 のスキーマが満たすべき制約違反検証テスト。

検証戦略:
- 各制約の違反 INSERT を実行し、psycopg が ``UniqueViolation`` /
  ``InvalidTextRepresentation`` / ``NotNullViolation`` / ``CheckViolation`` 等の
  期待例外を送出することを ``pytest.raises`` で具体例外型を指定して捕捉する。
- ``psycopg.errors.DatabaseError`` のような汎用例外型では受け入れず、
  spec §テスト計画2 の意図に沿って「どの制約が破れたか」を識別できる粒度で固定する。
- conftest の ``psycopg_connection`` フィクスチャがテスト終了時に rollback するため、
  各テストはデータベース状態を相互汚染しない。

設計準拠:
- spec §受入条件「amount に文字列 / NaN 投入で型エラー」「同一 hash 二重 INSERT で
  UNIQUE 違反」「category_source 範囲外値で型エラー」
- planner レポート §5.5 (DoD #7-#9)
- ADR-006（hash UNIQUE による冪等性保証）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import psycopg.errors
import pytest

if TYPE_CHECKING:
    import psycopg


# --- テスト用シードデータ ---------------------------------------------------


def _seed_minimal(connection: psycopg.Connection) -> tuple[int, str]:
    """transactions に依存する institutions / accounts を最小投入する。

    制約違反テストごとに親レコードが必要なため共通化する。テスト終了時に
    フィクスチャがロールバックするため、シード自体も巻き戻る。

    Returns:
        ``(account_id, hash_seed)``。hash は SHA256 hex 64 文字を返す。
    """
    with connection.cursor() as cur:
        cur.execute(
            "INSERT INTO institutions (code, name, kind) VALUES (%s, %s, %s)",
            ("test_bank", "テスト銀行", "bank"),
        )
        cur.execute(
            """
            INSERT INTO accounts (institution, account_no, display_name)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            ("test_bank", "0000001", "メイン口座"),
        )
        row = cur.fetchone()
        assert row is not None, "accounts INSERT で id が返却されません"
        account_id: int = row[0]

    # 64 文字の hex（SHA256 相当）。具体値は固定で十分。
    hash_seed = "a" * 64
    return account_id, hash_seed


def _insert_transaction(
    cursor: psycopg.Cursor,
    account_id: int,
    *,
    amount: object = "1000.0000",
    hash_value: str = "a" * 64,
    category_source: object = None,
    raw_payload: str = "{}",
) -> None:
    """transactions への INSERT ヘルパ。

    制約違反テストでは特定カラムの値だけ動かしたいので、それ以外の
    必須カラムを既定値で埋める。``amount`` は文字列ニーモニックで NUMERIC に
    キャストされる（PostgreSQL 側で変換）。
    """
    cursor.execute(
        """
        INSERT INTO transactions (
            account_id, occurred_on, amount, description, raw_payload, hash, category_source
        ) VALUES (
            %s, '2026-01-15', %s, 'テスト取引', %s::jsonb, %s, %s
        )
        """,
        (account_id, amount, raw_payload, hash_value, category_source),
    )


# --- hash UNIQUE 違反 -------------------------------------------------------


def test_同一hashの2回目INSERTがUniqueViolationを発生させる(
    psycopg_connection: psycopg.Connection,
) -> None:
    """``transactions.hash`` UNIQUE 制約により、同一 hash の重複 INSERT が
    ``psycopg.errors.UniqueViolation`` を送出すること（ADR-006 / spec §受入条件）。
    """
    account_id, hash_seed = _seed_minimal(psycopg_connection)

    with psycopg_connection.cursor() as cur:
        _insert_transaction(cur, account_id, hash_value=hash_seed)

    with psycopg_connection.cursor() as cur, pytest.raises(psycopg.errors.UniqueViolation):
        _insert_transaction(cur, account_id, hash_value=hash_seed)


# --- amount への不正値 ------------------------------------------------------


def test_amount_に文字列を投入すると型エラー(
    psycopg_connection: psycopg.Connection,
) -> None:
    """``transactions.amount`` （NUMERIC(18,4)）に非数値文字列を投入すると、
    PostgreSQL が ``InvalidTextRepresentation`` を返して INSERT が失敗すること。

    spec §受入条件「文字列投入で型エラー」を直接検証する。
    """
    account_id, _ = _seed_minimal(psycopg_connection)

    with (
        psycopg_connection.cursor() as cur,
        pytest.raises(psycopg.errors.InvalidTextRepresentation),
    ):
        _insert_transaction(cur, account_id, amount="not_a_number")


def test_amount_にNaN文字列を投入すると例外(
    psycopg_connection: psycopg.Connection,
) -> None:
    """``transactions.amount`` に ``'NaN'`` を投入する経路が拒否されること。

    spec §受入条件「NaN 投入で型エラー」を検証する。PostgreSQL の NUMERIC 自体は
    ``'NaN'`` リテラルを許容するため、本要件を満たすには CHECK 制約等での
    NaN 拒否が必要になる（実装側の判断）。テストは「NaN を弾く何らかの
    PostgreSQL データエラー」を ``DataError`` 親クラスで捕捉し、具体例外型
    （``CheckViolation`` / ``InvalidTextRepresentation`` 等）を実装に委ねる。
    """
    account_id, _ = _seed_minimal(psycopg_connection)

    with (
        psycopg_connection.cursor() as cur,
        pytest.raises(psycopg.errors.DataError),
    ):
        _insert_transaction(cur, account_id, amount="NaN")


def test_amount_にNULLを投入するとNotNullViolation(
    psycopg_connection: psycopg.Connection,
) -> None:
    """``transactions.amount`` の NOT NULL 制約により、NULL 投入が
    ``NotNullViolation`` を送出すること（ADR-005 / spec §実装方針3）。
    """
    account_id, _ = _seed_minimal(psycopg_connection)

    with (
        psycopg_connection.cursor() as cur,
        pytest.raises(psycopg.errors.NotNullViolation),
    ):
        _insert_transaction(cur, account_id, amount=None)


# --- category_source ENUM 違反 ----------------------------------------------


def test_category_source_の範囲外値INSERTがInvalidTextRepresentation(
    psycopg_connection: psycopg.Connection,
) -> None:
    """``category_source`` に ENUM 範囲外文字列（例: ``'unknown'``）を投入すると、
    PostgreSQL ENUM が ``InvalidTextRepresentation`` を返して INSERT が失敗すること。

    spec §受入条件「ENUM 許容値が rule/llm/manual のみ」を、範囲外側から検証する。
    """
    account_id, _ = _seed_minimal(psycopg_connection)

    with (
        psycopg_connection.cursor() as cur,
        pytest.raises(psycopg.errors.InvalidTextRepresentation),
    ):
        _insert_transaction(cur, account_id, category_source="unknown")


@pytest.mark.parametrize("valid_value", ["rule", "llm", "manual"])
def test_category_sourceの許容値INSERTは成功する(
    psycopg_connection: psycopg.Connection,
    valid_value: str,
) -> None:
    """``category_source`` が ``rule`` / ``llm`` / ``manual`` で受理されること。

    spec §実装方針5「PostgreSQL ENUM ('rule','llm','manual')」のポジティブ検証。
    範囲外拒否のみではなく、許容値の通過も契約として固定する。
    """
    account_id, _ = _seed_minimal(psycopg_connection)

    with psycopg_connection.cursor() as cur:
        _insert_transaction(
            cur,
            account_id,
            hash_value=f"{valid_value:<64}".replace(" ", "0"),
            category_source=valid_value,
        )


# --- raw_payload デフォルト挙動 ---------------------------------------------


def test_raw_payloadを省略するとデフォルトの空オブジェクトが入る(
    psycopg_connection: psycopg.Connection,
) -> None:
    """``raw_payload`` を INSERT で指定しない場合、DEFAULT ``'{}'::jsonb`` が
    適用されること（spec §実装方針6 / ADR-004）。

    NOT NULL かつデフォルトありなので、明示しなくても INSERT は成功する。
    """
    account_id, _ = _seed_minimal(psycopg_connection)
    hash_value = "b" * 64

    with psycopg_connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO transactions (
                account_id, occurred_on, amount, description, hash
            ) VALUES (%s, '2026-01-15', 100.0000, 'デフォルト確認', %s)
            """,
            (account_id, hash_value),
        )
        cur.execute(
            "SELECT raw_payload FROM transactions WHERE hash = %s",
            (hash_value,),
        )
        row = cur.fetchone()

    assert row is not None, "INSERT 直後の行が SELECT で取得できません"
    # psycopg は jsonb を Python dict にデコードする。
    assert row[0] == {}, f"raw_payload のデフォルトが空オブジェクトではありません: {row[0]!r}"
