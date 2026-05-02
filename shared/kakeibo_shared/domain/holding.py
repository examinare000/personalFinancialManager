"""``Holding`` ドメイン型と ``SymbolKind`` 列挙。

設計準拠:
- ``postgres/docs/plans/Ph1/03-domain-types.md`` §実装方針5, §受入条件5, §テスト計画3
- ``postgres/docs/design/01-data-model.md`` §3.4 / §7.1
  （``cash, stock, fund, crypto, bond`` の 5 値で確定。``etf`` は不採用）

依存:
- 標準ライブラリのみ（``dataclasses`` / ``enum`` / ``decimal`` / ``datetime`` / ``typing``）。
- pydantic は導入しない（plan §実装方針1）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any


class SymbolKind(StrEnum):
    """保有資産の種別。``design/01-data-model.md`` §3.4 の CHECK 制約と完全一致させる。

    plan §実装方針5 が「design/01 と整合」と明記しているため、design/01 §7.1 の
    決定に従い ``etf`` は採用しない（``stock`` / ``fund`` のいずれかで分類する想定）。
    """

    CASH = "cash"
    STOCK = "stock"
    FUND = "fund"
    CRYPTO = "crypto"
    BOND = "bond"


@dataclass(frozen=True, slots=True)
class Holding:
    """残高 PDF 等から取得した保有資産スナップショット。

    plan §実装ガイドラインに従い ``frozen=True, slots=True`` で構築する。
    ``__post_init__`` で ``symbol_kind`` のみ実行時バリデーションを行う
    （``Decimal`` 強制等は呼び出し側のアダプタ責務で、本タスクの plan §実装方針5
    が要求するのは ``SymbolKind`` 固定のみ）。
    """

    account_id: int
    symbol: str
    symbol_kind: SymbolKind
    quantity: Decimal
    market_value: Decimal | None
    unit_cost: Decimal | None
    as_of: date
    raw_payload: dict[str, Any]

    def __post_init__(self) -> None:
        # plan §受入条件5: ``SymbolKind`` 以外の値（生 ``str`` や ``None``）が
        # 流入するケースを早期に弾く。``StrEnum`` の値（``"stock"``）と等価比較
        # できることと、生 ``str`` で構築させない（必ず ``SymbolKind`` 経由）こと
        # は別問題。pyright は型注釈通りの値しか流入しないと解釈してしまうため
        # 明示的に抑止する。
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            self.symbol_kind, SymbolKind
        ):
            raise TypeError(
                f"symbol_kind must be SymbolKind, got {type(self.symbol_kind).__name__}"
            )
