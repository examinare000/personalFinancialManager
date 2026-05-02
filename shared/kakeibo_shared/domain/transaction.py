"""``Transaction`` ドメイン型と ``compute_hash`` 関数。

設計準拠:
- ``postgres/docs/plans/Ph1/03-domain-types.md`` §実装方針1〜4, §受入条件1〜4, §テスト計画1〜2
- ``docs/adr/005-decimal-monetary-precision.md``（``amount`` は ``Decimal`` 固定）
- ``docs/adr/006-hash-uniqueness.md``（``compute_hash`` は 4 引数 SHA256 hex）

依存:
- 標準ライブラリのみ（``hashlib`` / ``dataclasses`` / ``decimal`` / ``datetime`` / ``typing``）。
- pydantic は導入しない（plan §実装方針1）。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from kakeibo_shared.domain.currency import validate_currency_code


@dataclass(frozen=True, slots=True)
class Transaction:
    """取込アダプタが返す正規化済みのトランザクション 1 件。

    plan §実装方針2 の 10 フィールド固定。DB 側 ``transactions`` テーブルには
    ``counterparty`` 等の追加カラムが存在するが、本タスクのスコープでは扱わない
    （plan 優先）。

    フィールド順序は plan §実装方針2 の列挙順を厳守する。
    """

    account_id: int
    occurred_on: date
    occurred_at: datetime | None
    amount: Decimal
    currency: str
    description: str
    category_id: int | None
    category_source: Literal["rule", "llm", "manual"] | None
    raw_payload: dict[str, Any]
    hash: str

    def __post_init__(self) -> None:
        # plan §実装方針3 のバリデーション規約。検査順序は plan §実装ガイドライン参照。
        # 静的型は ``Decimal`` だが、CSV/JSON 由来の取込でフィールドに ``None`` や
        # 別型が紛れ込むケースを実行時に弾くため、defensive な isinstance/比較を残す。
        # pyright strict は型注釈通りの値しか流入しないと解釈してしまうため明示的に抑止する。
        if self.amount is None:  # pyright: ignore[reportUnnecessaryComparison]
            raise ValueError("amount must not be None")
        # 通貨コード検査は共通バリデータに委譲（``BalanceSnapshot.currency`` と同一規約）。
        validate_currency_code(self.currency)
        # plan §実装方針3: ``occurred_on`` が ``date`` でなければ ``TypeError``。
        # ``isinstance`` 判定を採用し ``datetime``（``date`` サブクラス）も許容する
        # （write-tests 側で回帰検出が用意されている）。
        if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            self.occurred_on, date
        ):
            raise TypeError(f"occurred_on must be date, got {type(self.occurred_on).__name__}")
        # 受入条件「occurred_at: Optional[datetime]」の実行時保証。
        # ``None`` は許容、それ以外は ``datetime`` 必須（``date`` 単独や文字列は弾く）。
        if self.occurred_at is not None and not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
            self.occurred_at, datetime
        ):
            raise TypeError(
                f"occurred_at must be datetime or None, got {type(self.occurred_at).__name__}"
            )


def compute_hash(
    account_id: int,
    occurred_on: date,
    amount: Decimal,
    description: str,
) -> str:
    """ADR-006 に基づく取込冪等性キーを返す。

    plan §実装方針4 / ADR-006 §決定:
        canonical = f"{account_id}|{occurred_on.isoformat()}|{amount}|{description}"
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    description のトリミング・正規化は意図的に行わない（Phase 1.7 の境界条件テストで
    詳細を確定する。ここでトリミングを入れると Phase 1.7 で導入する正規化と
    二重処理になる）。``Decimal`` の ``str`` 表現も ``normalize`` 等を介さず素のまま使う
    （``Decimal("1234.56")`` と ``Decimal("1234.560")`` は別ハッシュ）。
    """
    canonical = f"{account_id}|{occurred_on.isoformat()}|{amount}|{description}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
