"""``BalanceSnapshot`` ドメイン型。

設計準拠:
- ``postgres/docs/plans/Ph1/03-domain-types.md`` §実装方針6, §テスト計画4
- ``docs/adr/005-decimal-monetary-precision.md``（``balance`` は ``Decimal`` 固定）

DB 側の ``balance_snapshots`` テーブルには現状 ``currency`` カラムが存在しないが、
plan が明示的に 4 フィールド構成（``account_id`` / ``as_of_date`` / ``balance`` / ``currency``）
を要求しているためドメイン型に含める（plan 優先）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from kakeibo_shared.domain.currency import validate_currency_code


@dataclass(frozen=True, slots=True)
class BalanceSnapshot:
    """口座残高の日次スナップショット。

    plan §実装方針6 のフィールド構成と plan §テスト計画4 のバリデーション規約に従う。
    ``__post_init__`` の検査順序は「型強制 → 通貨バリデーション」。
    通貨検査をフィールド単位の ``isinstance`` より後に置くことで、明らかな型不一致を
    優先報告する。
    """

    account_id: int
    as_of_date: date
    balance: Decimal
    currency: str

    def __post_init__(self) -> None:
        # plan §テスト計画4: ``balance`` の ``Decimal`` 強制（ADR-005）。
        # ``float`` / ``int`` / ``str`` を暗黙に Decimal 化しない。
        # 静的型は ``Decimal`` だが、PDF/CSV パース等で別型が混入するケースを
        # 実行時に弾く（Fail Fast）。pyright は型注釈通りの値しか流入しないと
        # 解釈してしまうため明示的に抑止する。
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            self.balance, Decimal
        ):
            raise TypeError(f"balance must be Decimal, got {type(self.balance).__name__}")
        # plan §テスト計画4: ``as_of_date`` の ``date`` 強制。
        # ``isinstance(_, date)`` を採用し ``datetime``（dateサブクラス）も許容する
        # （plan の規定範囲で許容される。文字列・epoch 秒は明示的に弾く）。
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            self.as_of_date, date
        ):
            raise TypeError(f"as_of_date must be date, got {type(self.as_of_date).__name__}")
        # 共通バリデータに委譲（``Transaction.currency`` と同一規約）。
        validate_currency_code(self.currency)
