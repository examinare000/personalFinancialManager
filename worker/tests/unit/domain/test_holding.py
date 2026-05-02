"""``Holding`` ドメイン型と ``SymbolKind`` Enum の単体テスト（TDD Red 段階）。

検証範囲:
- ``Holding`` の正常系インスタンス化（frozen + slots）
- ``SymbolKind`` の値集合が ``design/01`` の CHECK 制約と一致すること
- ``Holding.symbol_kind`` に ``SymbolKind`` 以外（生 ``str`` 等）を渡すと TypeError
- 全 ``SymbolKind`` 値で正常生成

設計準拠:
- ``postgres/docs/plans/Ph1/03-domain-types.md`` §実装方針5 / §受入条件5 / §テスト計画3
- ``postgres/docs/design/01-data-model.md`` §3.4 / §7.1
  （``cash, stock, fund, crypto, bond`` の 5 値で確定。``etf`` は不採用）

テストは TDD の Red 段階で先行作成する。実装は後続ステップで追加する。
"""

from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal

import pytest

# ---------------------------------------------------------------------------
# SymbolKind — design/01 §3.4 の CHECK 制約値と完全一致
# ---------------------------------------------------------------------------


def test_SymbolKindの値集合はdesign01_の5値と一致する() -> None:
    """design/01 §3.4: ``cash, stock, fund, crypto, bond`` の 5 値。

    plan §実装方針5 が「design/01 と整合」と明記しているため、design/01 §7.1 の
    決定（``etf`` は不採用、``bond`` を採用）に合わせる。値集合の差異は
    DB 側 CHECK 制約と乖離して取込失敗を生むため、最初に固定する。
    """
    from kakeibo_shared.domain import SymbolKind

    assert {k.value for k in SymbolKind} == {"cash", "stock", "fund", "crypto", "bond"}


def test_SymbolKindはStrEnumで文字列比較できる() -> None:
    """``StrEnum`` 採用により ``SymbolKind.STOCK == "stock"`` が成立すること。

    DB の文字列カラム（``holdings.symbol_kind TEXT``）との往復で
    余計な変換コードを書かずに済むことを担保する。
    """
    from kakeibo_shared.domain import SymbolKind

    assert SymbolKind.STOCK == "stock"
    assert SymbolKind.CASH == "cash"
    assert SymbolKind.FUND == "fund"
    assert SymbolKind.CRYPTO == "crypto"
    assert SymbolKind.BOND == "bond"


def test_SymbolKindに未定義値を渡すとValueError() -> None:
    """plan §テスト計画3: 未定義値（``etf`` 等）で例外。

    ``etf`` は plan の例示には含まれるが design/01 で不採用と決定された値。
    本テストで誤って復活したケースを早期検出する。
    """
    from kakeibo_shared.domain import SymbolKind

    with pytest.raises(ValueError):
        SymbolKind("etf")
    with pytest.raises(ValueError):
        SymbolKind("unknown")


# ---------------------------------------------------------------------------
# Holding — 正常系
# ---------------------------------------------------------------------------


def _正常な引数(symbol_kind: object) -> dict[str, object]:
    """異常系テストの「symbol_kind 以外は正常」状態を作るための共通辞書。

    plan §実装ガイドラインで指定された Holding フィールド全てを最小限の
    妥当値で埋める。
    """
    return {
        "account_id": 1,
        "symbol": "AAPL",
        "symbol_kind": symbol_kind,
        "quantity": Decimal("10"),
        "market_value": Decimal("18500.00"),
        "unit_cost": Decimal("1700.00"),
        "as_of": date(2026, 4, 30),
        "raw_payload": {"source": "broker_csv", "row": 1},
    }


@pytest.mark.parametrize(
    "kind_value",
    ["cash", "stock", "fund", "crypto", "bond"],
)
def test_Holdingは全てのSymbolKindで生成できる(kind_value: str) -> None:
    """plan §テスト計画3: 列挙値ごとに正常生成。

    全 5 値について dataclass が問題なく構築できることを確認する。
    """
    from kakeibo_shared.domain import Holding, SymbolKind

    holding = Holding(**_正常な引数(SymbolKind(kind_value)))  # type: ignore[arg-type]
    assert holding.symbol_kind == SymbolKind(kind_value)
    assert isinstance(holding.symbol_kind, SymbolKind)


def test_Holdingはfrozenで属性更新できない() -> None:
    """plan §実装方針1: ``@dataclass(frozen=True, slots=True)``。"""
    from kakeibo_shared.domain import Holding, SymbolKind

    holding = Holding(**_正常な引数(SymbolKind.STOCK))  # type: ignore[arg-type]
    with pytest.raises(dataclasses.FrozenInstanceError):
        holding.quantity = Decimal("999")  # type: ignore[misc]


def test_Holdingはslotsで未定義属性を拒む() -> None:
    """``slots=True`` の効果として ``__dict__`` を持たないこと。"""
    from kakeibo_shared.domain import Holding, SymbolKind

    holding = Holding(**_正常な引数(SymbolKind.STOCK))  # type: ignore[arg-type]
    assert not hasattr(holding, "__dict__")


def test_Holding_market_valueとunit_costはNoneも許容する() -> None:
    """残高 PDF で時価が取得できないケースのため Optional を許容する設計。

    design/01 §3.4 の ``market_value NUMERIC NULL``（時価情報が無い証券）に対応。
    """
    from kakeibo_shared.domain import Holding, SymbolKind

    args = _正常な引数(SymbolKind.STOCK)
    args["market_value"] = None
    args["unit_cost"] = None
    holding = Holding(**args)  # type: ignore[arg-type]
    assert holding.market_value is None
    assert holding.unit_cost is None


# ---------------------------------------------------------------------------
# Holding — 異常系
# ---------------------------------------------------------------------------


def test_Holdingはsymbol_kindに生strを渡すとTypeErrorを出す() -> None:
    """plan §実装方針5 / §受入条件5: ``SymbolKind`` 固定で実行時エラー。

    ``StrEnum`` の値（``"stock"``）と等価比較できることと、
    生 ``str`` で構築させない（必ず ``SymbolKind`` 経由）ことは別問題。
    取込アダプタ側で誤って文字列を流し込むケースを早期に弾く。
    """
    from kakeibo_shared.domain import Holding

    with pytest.raises(TypeError):
        Holding(**_正常な引数("stock"))  # type: ignore[arg-type]


def test_Holdingはsymbol_kindにNoneを渡すとTypeErrorを出す() -> None:
    """``symbol_kind`` 必須を実行時保証する。

    None で構築されると DB 側 NOT NULL 違反として遅延発見されてしまう。
    """
    from kakeibo_shared.domain import Holding

    with pytest.raises(TypeError):
        Holding(**_正常な引数(None))  # type: ignore[arg-type]
