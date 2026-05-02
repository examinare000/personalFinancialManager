"""``BalanceSnapshot`` ドメイン型の単体テスト（TDD Red 段階）。

検証範囲:
- 正常系インスタンス化（4 フィールド + frozen + slots）
- ``balance`` の ``Decimal`` 強制（``float`` / ``int`` / ``str`` で TypeError）
- ``as_of_date`` の ``date`` 強制（``datetime`` 以外の型で TypeError）
- ``currency`` の通貨コードバリデーション（共通バリデータ経由）

設計準拠:
- ``postgres/docs/plans/Ph1/03-domain-types.md`` §実装方針6 / §テスト計画4
- ``docs/adr/005-decimal-monetary-precision.md``（balance は Decimal 固定）

テストは TDD の Red 段階で先行作成する。実装は後続ステップで追加する。
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime
from decimal import Decimal

import pytest


def _正常な引数() -> dict[str, object]:
    """異常系テストの「他は正常」状態を作るための共通辞書。"""
    return {
        "account_id": 1,
        "as_of_date": date(2026, 4, 30),
        "balance": Decimal("100000.00"),
        "currency": "JPY",
    }


# ---------------------------------------------------------------------------
# 正常系
# ---------------------------------------------------------------------------


def test_BalanceSnapshotは4フィールドで生成できる() -> None:
    """plan §実装方針6 の 4 フィールド構成で問題なくインスタンス化できること。"""
    from kakeibo_shared.domain import BalanceSnapshot

    snap = BalanceSnapshot(**_正常な引数())  # type: ignore[arg-type]
    assert snap.account_id == 1
    assert snap.as_of_date == date(2026, 4, 30)
    assert snap.balance == Decimal("100000.00")
    assert snap.currency == "JPY"


def test_BalanceSnapshotはfrozenで属性更新できない() -> None:
    """plan §実装方針1: ``@dataclass(frozen=True, slots=True)``。"""
    from kakeibo_shared.domain import BalanceSnapshot

    snap = BalanceSnapshot(**_正常な引数())  # type: ignore[arg-type]
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.balance = Decimal("0")  # type: ignore[misc]


def test_BalanceSnapshotはslotsで未定義属性を拒む() -> None:
    """``slots=True`` の効果として ``__dict__`` を持たないこと。"""
    from kakeibo_shared.domain import BalanceSnapshot

    snap = BalanceSnapshot(**_正常な引数())  # type: ignore[arg-type]
    assert not hasattr(snap, "__dict__")


# ---------------------------------------------------------------------------
# balance の Decimal 強制 — plan §テスト計画4
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("invalid_balance", "理由"),
    [
        (100000.0, "float（ADR-005 違反の典型）"),
        (100000, "int（暗黙の Decimal 化を許さない）"),
        ("100000.00", "str（パース処理を埋め込まない）"),
        (None, "None"),
    ],
)
def test_BalanceSnapshotはbalanceが非DecimalならTypeErrorを出す(
    invalid_balance: object, 理由: str
) -> None:
    """plan §テスト計画4: balance の Decimal 強制。

    ADR-005 のとおり、float / int / str を暗黙に Decimal 化しない。
    呼び出し側が Decimal を渡す責務を持つ（Fail Fast）。
    ``理由`` 引数は失敗ケース identifier として可読性のために残す。
    """
    from kakeibo_shared.domain import BalanceSnapshot

    args = _正常な引数()
    args["balance"] = invalid_balance
    with pytest.raises(TypeError):
        BalanceSnapshot(**args)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# as_of_date の date 強制 — plan §テスト計画4
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("invalid_as_of", "理由"),
    [
        ("2026-04-30", "ISO 文字列を date に自動変換しない"),
        (1714435200, "epoch 秒を date に自動変換しない"),
        (None, "None"),
    ],
)
def test_BalanceSnapshotはas_of_dateが非dateならTypeErrorを出す(
    invalid_as_of: object, 理由: str
) -> None:
    """plan §テスト計画4: as_of_date の date 強制。

    呼び出し側が ``date`` を渡す責務を持ち、ライブラリは型変換を行わない。
    """
    from kakeibo_shared.domain import BalanceSnapshot

    args = _正常な引数()
    args["as_of_date"] = invalid_as_of
    with pytest.raises(TypeError):
        BalanceSnapshot(**args)  # type: ignore[arg-type]


def test_BalanceSnapshotはas_of_dateにdatetimeを渡してもdateとして許容する() -> None:
    """``datetime`` は ``date`` のサブクラスなので ``isinstance(_, date)`` は True。

    実装が ``type(_) is date`` で判定すると ``datetime`` を誤って弾く。
    plan は ``date`` 型強制を要求しており ``isinstance`` 判定であれば許容される。
    回帰検出として残す。
    """
    from kakeibo_shared.domain import BalanceSnapshot

    args = _正常な引数()
    args["as_of_date"] = datetime(2026, 4, 30, 12, 0, 0)
    snap = BalanceSnapshot(**args)  # type: ignore[arg-type]
    assert isinstance(snap.as_of_date, date)


# ---------------------------------------------------------------------------
# currency バリデーション — 共通バリデータ経由
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid_currency",
    ["JP", "JPYY", "", "jpy", "Jpy", "JP1"],
)
def test_BalanceSnapshotは不正な通貨コードでValueErrorを出す(invalid_currency: str) -> None:
    """plan §実装方針6: ``BalanceSnapshot.currency`` も 3 文字英大文字バリデーション対象。

    Transaction 側と完全に同じバリデーション規約に従う（``currency.py`` 共通化）。
    """
    from kakeibo_shared.domain import BalanceSnapshot

    args = _正常な引数()
    args["currency"] = invalid_currency
    with pytest.raises(ValueError):
        BalanceSnapshot(**args)  # type: ignore[arg-type]


def test_BalanceSnapshotは通貨コードがstr以外ならTypeErrorを出す() -> None:
    """共通バリデータの ``isinstance(code, str)`` 強制が伝播していること。"""
    from kakeibo_shared.domain import BalanceSnapshot

    args = _正常な引数()
    args["currency"] = 392
    with pytest.raises(TypeError):
        BalanceSnapshot(**args)  # type: ignore[arg-type]
