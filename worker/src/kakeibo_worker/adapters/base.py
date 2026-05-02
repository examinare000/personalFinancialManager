"""``IngestAdapter`` 抽象基底クラスと ``Payload`` 型エイリアス。

Phase 1.3 で確立する取込アダプタ層の契約。Phase 1.4 以降の機関別アダプタ
（MUFG / SMBC / 楽天 / Amazon 等）が本 ABC を継承して実装する。

契約:
- ``source: ClassVar[str]`` をサブクラスが必ず自前定義する（``__init_subclass__`` で検証）
- コンストラクタ ``__init__(*, account_id: int)`` で 1 口座にバインドする
- 抽象メソッド ``parse`` / ``extract_holdings`` を実装する
- ``Payload`` は ``bytes | str | dict[str, Any]``（ファイル読込責務は呼出側）

設計準拠:
- ``docs/adr/007-adapter-pattern.md``（アダプタパターン採用、§結果に Phase 1.3 確定事項を追記）
- ``order.md`` §スコープ（受入基準 3 点）
- ``worker/docs/plans/Ph1/04-ingest-adapter-base.md`` §実装方針 1〜4

依存:
- 標準ライブラリ（``abc`` / ``collections.abc`` / ``typing``）のみ。
- ドメイン型は Phase 1.2 実装の ``kakeibo_shared.domain`` から ``Transaction`` / ``Holding``。
- pydantic は導入しない（ADR-018）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, ClassVar

from kakeibo_shared.domain import Holding, Transaction

# ``Payload`` は機関別アダプタが受け取る原本データの型。
# ファイル読込は呼出側（Phase 1.6 取込 CLI）の責務であり、``Path`` は意図的に含めない
# （plan §検討したアプローチ: 「``Payload`` に ``Path`` を含める」を不採用と決定）。
Payload = bytes | str | dict[str, Any]


class IngestAdapter(ABC):
    """機関別取込アダプタの抽象基底クラス。

    各機関のサブクラスは以下を定義する:

    1. クラス変数 ``source``: 機関識別子（``"mufg"`` / ``"smbc"`` 等）。空文字や非 str は禁止。
    2. ``parse(payload)``: 原本（CSV bytes、メール str、API dict 等）から
       ``Iterable[Transaction]`` を返す。
    3. ``extract_holdings(payload)``: 残高 PDF 等から ``Iterable[Holding]`` を返す。
       holdings 未対応のアダプタは明示的に ``return iter(())`` を実装する
       （デフォルト実装は提供しない: plan §検討したアプローチ参照）。

    ``account_id`` はコンストラクタ注入で固定する。``parse`` / ``extract_holdings`` の
    引数は ``payload`` のみで、口座コンテキストは ``self.account_id`` 経由で参照する
    （plan §実装方針3「アダプタ = 1 口座にバインド」）。
    """

    source: ClassVar[str]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # サブクラス定義時に ``source`` 属性の自前定義・型・空文字を検証する。
        # アダプタ登録ミスを実行直前ではなくロード時に検出するため。
        super().__init_subclass__(**kwargs)
        # ``cls.__dict__`` 直参照: 親 ``ClassVar[str]`` の宣言だけで通過させない
        # （``getattr(cls, "source", None)`` だと「サブクラス自身が定義した」かを判定できない）。
        # plan §``source`` 検証の判定順 1〜3 に従う。
        if "source" not in cls.__dict__:
            raise TypeError(
                f"{cls.__name__} must define class attribute 'source' (non-empty str)"
            )
        value = cls.__dict__["source"]
        # 静的型注釈は ``ClassVar[str]`` だが、サブクラス側で型を無視して数値や None を
        # 設定するケースを実行時に弾く（pyright strict は型注釈通りの値しか流入しないと
        # 解釈してしまうため明示的に抑止する。``Transaction.__post_init__`` と同パターン）。
        if not isinstance(value, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(
                f"{cls.__name__}.source must be str, got {type(value).__name__}"
            )
        # ``.strip() == ""`` で whitespace-only も弾く（plan §source 検証の判定順 3）。
        # 空白のみの ``source`` は ``ADAPTER_REGISTRY`` キーとして実用にならず、
        # 単なる空文字列と同様に登録ミスとして扱う。
        if value.strip() == "":
            raise TypeError(f"{cls.__name__}.source must be non-empty str")

    def __init__(self, *, account_id: int) -> None:
        # keyword-only 必須引数。Phase 1.4 以降の機関別アダプタが ``account_id`` を
        # 渡し忘れたコール経路を Python 標準挙動（``TypeError``）で早期に弾く。
        self.account_id = account_id

    @abstractmethod
    def parse(self, payload: Payload) -> Iterable[Transaction]:
        """原本 ``payload`` から正規化済みの ``Transaction`` 列を返す。

        実装は副作用を持たない純粋変換とする（DB 書き込みは ``Reconciler`` の責務、
        ADR-007 §結果）。``account_id`` は ``self.account_id`` を使う。
        """

    @abstractmethod
    def extract_holdings(self, payload: Payload) -> Iterable[Holding]:
        """原本 ``payload`` から保有資産スナップショットの列を返す。

        holdings 未対応の機関アダプタも明示的に ``return iter(())`` を実装する。
        デフォルト実装を提供しないことで「holdings 未対応」を暗黙化させない
        （plan §検討したアプローチ「``extract_holdings`` をデフォルト実装にする」不採用）。
        """
