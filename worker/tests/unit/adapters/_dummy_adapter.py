"""``DummyAdapter`` — ``IngestAdapter`` ABC の契約検証用ダミー実装（テスト fixture）。

worker/tests/unit/adapters/test_base.py から遅延 import して使う。ファイル名先頭の
``_`` は将来 pytest の collect 規則が変わっても収集対象にしない明示。

設計準拠:
- order.md §スコープ「ダミーアダプタを実装し、ユニットテストで契約を検証できる」
- worker/docs/plans/Ph1/04-ingest-adapter-base.md §ダミーアダプタ
- docs/adr/007-adapter-pattern.md（アダプタパターン採用）
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from kakeibo_shared.domain import Holding, Transaction, compute_hash
from kakeibo_worker.adapters.base import IngestAdapter, Payload


class DummyAdapter(IngestAdapter):
    """契約検証専用ダミーアダプタ。

    機関別の実体は持たず、``parse`` は固定 ``Transaction`` 1 件を yield、
    ``extract_holdings`` は空イテレータを返す。``IngestAdapter`` の契約
    （``source`` 属性必須・抽象メソッド・コンストラクタ注入で ``account_id`` 保持）
    が成立していることを単体テストから確認するための最小実装。
    """

    source = "dummy"

    def parse(self, payload: Payload) -> Iterable[Transaction]:
        # ``payload`` は契約検証専用テストでは未使用。pyright ``reportUnusedParameter``
        # を明示的に消費し、サブクラスで「引数を意識していない」誤読を避ける。
        del payload
        occurred_on = date(2026, 4, 30)
        amount = Decimal("1234.56")
        description = "ダミー取引"
        yield Transaction(
            account_id=self.account_id,
            occurred_on=occurred_on,
            occurred_at=None,
            amount=amount,
            currency="JPY",
            description=description,
            category_id=None,
            category_source=None,
            raw_payload={},
            hash=compute_hash(self.account_id, occurred_on, amount, description),
        )

    def extract_holdings(self, payload: Payload) -> Iterable[Holding]:
        del payload
        return iter(())
