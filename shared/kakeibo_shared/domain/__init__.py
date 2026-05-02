"""ドメインモデル（Transaction / Holding / BalanceSnapshot 等）の公開 API 集約。

各ドメイン型は標準ライブラリ ``dataclass(frozen=True, slots=True)`` で定義され、
``__post_init__`` で必須バリデーションを行う（pydantic は導入しない、plan §実装方針1）。

参照:
- ``postgres/docs/plans/Ph1/03-domain-types.md`` §対象ファイル
"""

from __future__ import annotations

from kakeibo_shared.domain.balance_snapshot import BalanceSnapshot
from kakeibo_shared.domain.currency import validate_currency_code
from kakeibo_shared.domain.holding import Holding, SymbolKind
from kakeibo_shared.domain.transaction import Transaction, compute_hash

__all__ = [
    "BalanceSnapshot",
    "Holding",
    "SymbolKind",
    "Transaction",
    "compute_hash",
    "validate_currency_code",
]
