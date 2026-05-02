"""``IngestAdapter`` ABC の契約検証テスト（TDD Red 段階）。

検証範囲:
- 抽象メソッド ``parse`` / ``extract_holdings`` 未実装サブクラスのインスタンス化拒否
- ``source`` 属性の必須化（未設定 / 非 str / 空文字列をクラス定義時に弾く）
- ダミーアダプタが契約どおりに ``Transaction`` / ``Holding`` を返す
- ABC 自身を直接インスタンス化できない

設計準拠:
- order.md §スコープ（受入基準 3 点）
- worker/docs/plans/Ph1/04-ingest-adapter-base.md §テスト計画
- docs/adr/007-adapter-pattern.md（アダプタパターン採用）

テストは TDD Red 段階で先行作成する。実装（``base.py`` / ``errors.py``）は
後続ステップで追加するため、各テスト内で production 側を関数内 import し、
未実装モジュールの ``ImportError`` が他テストを巻き添えにしないようにする
（``worker/tests/unit/domain/test_transaction.py`` の Red 検出パターンに倣う）。

``_dummy_adapter`` の import は worker/tests/unit/adapters/ ディレクトリが
pytest の prepend モード（``__init__.py`` を持たないため rootdir = テストファイル
直近のディレクトリ）で sys.path に追加されることに依存する。pyright は
この実行時パスを把握できないため、当該行のみ ``reportMissingImports`` を抑止する。
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest

# ---------------------------------------------------------------------------
# 抽象メソッド契約 — Python ``abc`` 標準挙動の確認
# ---------------------------------------------------------------------------


def test_IngestAdapterは抽象メソッド未実装サブクラスのインスタンス化を拒む() -> None:
    """plan §テスト計画 T1: ``extract_holdings`` 未実装サブクラスは instantiate 時に TypeError。

    Python ``abc`` 標準挙動。``parse`` のみ override したサブクラスはまだ抽象クラスのままで
    インスタンス化できないことを確認する。受入基準「``parse`` / ``extract_holdings`` の両方
    が抽象メソッド」を「片方だけ実装した場合の挙動」で検証する。
    """
    # Given: ``parse`` だけを override し ``extract_holdings`` を残したサブクラス
    from kakeibo_shared.domain import Transaction
    from kakeibo_worker.adapters.base import IngestAdapter, Payload

    class _ParseOnlyAdapter(IngestAdapter):
        source = "parse_only"

        def parse(self, payload: Payload) -> Iterable[Transaction]:
            del payload
            return iter(())

    # When/Then: インスタンス化を試みると Python ``abc`` 標準挙動で TypeError
    with pytest.raises(TypeError):
        _ParseOnlyAdapter(account_id=1)  # pyright: ignore[reportAbstractUsage]


def test_IngestAdapterはABCのため直接インスタンス化できない() -> None:
    """plan §テスト計画 T9: ABC 自身を直接 instantiate できない。

    ``parse`` / ``extract_holdings`` がいずれも抽象なので Python ``abc`` 標準挙動で TypeError。
    """
    # Given: ABC 本体
    from kakeibo_worker.adapters.base import IngestAdapter

    # When/Then: 直接インスタンス化を試みると TypeError
    with pytest.raises(TypeError):
        IngestAdapter(account_id=1)  # pyright: ignore[reportAbstractUsage]


# ---------------------------------------------------------------------------
# ``source`` 属性の必須化 — ``__init_subclass__`` がクラス定義時に弾く
# ---------------------------------------------------------------------------


def test_IngestAdapterはsource未設定サブクラスをクラス定義時にTypeErrorで弾く() -> None:
    """plan §テスト計画 T2: ``source`` を自前定義しないサブクラスはクラス定義時に TypeError。

    親 ``ClassVar[str]`` 宣言だけで通過させないため ``cls.__dict__`` 直参照で
    自前定義の有無を厳密判定する規約（plan §``source`` 検証の判定順 1）を検証する。
    """
    # Given: ABC のみ
    from kakeibo_worker.adapters.base import IngestAdapter

    # When/Then: ``source`` を自前定義しない subclass を作るとクラス定義時に TypeError
    # （クラスは ``__init_subclass__`` が raise するため Python が名前束縛する前に失敗する。
    # 静的解析上は「未使用クラス」に見えるが、定義行そのものが検証対象なので reportUnusedClass を抑止する）
    with pytest.raises(TypeError):

        class _NoSourceAdapter(IngestAdapter):  # pyright: ignore[reportUnusedClass]
            pass


def test_IngestAdapterはsourceが空文字列のサブクラスをTypeErrorで弾く() -> None:
    """plan §テスト計画 T3: 空文字列 ``source`` は登録ミスとして弾く。

    ``source`` は Phase 1.4 の ``ADAPTER_REGISTRY`` キーになる前提なので、
    空文字列のまま通過させるとキー衝突や検索失敗の原因になる。
    """
    # Given: ABC のみ
    from kakeibo_worker.adapters.base import IngestAdapter

    # When/Then: 空文字列で subclass を作るとクラス定義時に TypeError
    # （reportUnusedClass を抑止する理由は T2 と同じ: 定義行そのものが検証対象）
    with pytest.raises(TypeError):

        class _EmptySourceAdapter(IngestAdapter):  # pyright: ignore[reportUnusedClass]
            source = ""


def test_IngestAdapterはsourceが空白のみのサブクラスをTypeErrorで弾く() -> None:
    """plan §テスト計画 T3 補強: 空白のみ ``source`` も登録ミスとして弾く（``value.strip() == ""``）。

    ``source = "   "`` のような whitespace-only は ``ADAPTER_REGISTRY`` キーとして
    実用にならず、空文字列と同様に弾くべき。空文字列ケース（T3）と同型で検証する。
    """
    # Given: ABC のみ
    from kakeibo_worker.adapters.base import IngestAdapter

    # When/Then: 空白のみで subclass を作るとクラス定義時に TypeError
    # （reportUnusedClass を抑止する理由は T2 と同じ: 定義行そのものが検証対象）
    with pytest.raises(TypeError):

        class _WhitespaceSourceAdapter(IngestAdapter):  # pyright: ignore[reportUnusedClass]
            source = "   "


def test_IngestAdapterはsourceが非str型のサブクラスをTypeErrorで弾く() -> None:
    """plan §テスト計画 T4: 非 str（int 等）の ``source`` を弾く。

    ``source`` は文字列キー前提。型注釈を回避して数値が紛れ込むケースを
    実行時にも弾く（plan §``source`` 検証の判定順 2）。
    """
    # Given: ABC のみ
    from kakeibo_worker.adapters.base import IngestAdapter

    # When/Then: ``source = 123`` で subclass を作るとクラス定義時に TypeError
    # （reportUnusedClass を抑止する理由は T2 と同じ: 定義行そのものが検証対象）
    with pytest.raises(TypeError):

        class _NonStrSourceAdapter(IngestAdapter):  # pyright: ignore[reportUnusedClass]
            source = 123  # pyright: ignore[reportAssignmentType]


# ---------------------------------------------------------------------------
# ``DummyAdapter`` — 受入基準「ダミーアダプタで契約検証」
# ---------------------------------------------------------------------------


def test_DummyAdapterはaccount_idなしで初期化するとTypeErrorを出す() -> None:
    """plan §テスト計画 T5: ``account_id`` は keyword-only の必須引数。

    必須 keyword-only 引数の欠落は Python 標準挙動で TypeError。
    Phase 1.4 以降の機関別アダプタが ``account_id`` を渡し忘れたコール経路を早期に弾く。
    """
    # Given: DummyAdapter（テスト fixture）
    from _dummy_adapter import DummyAdapter  # pyright: ignore[reportMissingImports]

    # When/Then: 引数なしで instantiate すると TypeError
    with pytest.raises(TypeError):
        DummyAdapter()  # pyright: ignore[reportCallIssue]


def test_DummyAdapterはaccount_idを保持する() -> None:
    """plan §テスト計画 T6: ABC のコンストラクタ注入で ``self.account_id`` が保持される。

    Phase 1.4 以降の機関別アダプタが ``Transaction(account_id=self.account_id, ...)`` で
    正規化済みトランザクションを生成する前提（``account_id`` は ``parse`` 引数ではなく
    コンストラクタで 1 回だけ注入する）。
    """
    # Given: account_id=42 で初期化した DummyAdapter
    from _dummy_adapter import DummyAdapter  # pyright: ignore[reportMissingImports]

    adapter = DummyAdapter(account_id=42)

    # When/Then: コンストラクタ注入値が ``self.account_id`` に保持されている
    assert adapter.account_id == 42


def test_DummyAdapter_parseは契約どおりIterableTransactionを返す() -> None:
    """plan §テスト計画 T7: ``parse`` の戻り値は ``Iterable[Transaction]``。

    各要素が ``Transaction`` インスタンスかつ ``account_id`` がコンストラクタ注入値と
    一致することを検証し、「アダプタ = 1 口座にバインド」の規約が機能していることを確認する。
    """
    # Given: account_id=7 で初期化した DummyAdapter
    from kakeibo_shared.domain import Transaction

    from _dummy_adapter import DummyAdapter  # pyright: ignore[reportMissingImports]

    adapter = DummyAdapter(account_id=7)

    # When: ``parse`` を呼んで戻り値を実体化する
    transactions = list(adapter.parse({}))

    # Then: 少なくとも 1 件返り、各要素が ``Transaction`` で ``account_id`` 一致
    assert len(transactions) >= 1
    for tx in transactions:
        assert isinstance(tx, Transaction)
        assert tx.account_id == 7


def test_DummyAdapter_extract_holdingsは反復可能なHolding集合を返す() -> None:
    """plan §テスト計画 T8: ``extract_holdings`` の戻り値は ``Iterable[Holding]``（空でも可）。

    ``list(...)`` で実体化してエラーにならないこと、含まれる要素が ``Holding`` であることを確認する。
    DummyAdapter は holdings 未対応のため空集合を返す契約だが、実装上は ``Iterable`` であれば
    空でも要素ありでも本テストは通る（契約検証のみ、件数は問わない）。
    """
    # Given: DummyAdapter
    from kakeibo_shared.domain import Holding

    from _dummy_adapter import DummyAdapter  # pyright: ignore[reportMissingImports]

    adapter = DummyAdapter(account_id=1)

    # When: ``extract_holdings`` を呼んで実体化する
    holdings = list(adapter.extract_holdings({}))

    # Then: 含まれる各要素は ``Holding`` インスタンス（空集合でも通る）
    for holding in holdings:
        assert isinstance(holding, Holding)
