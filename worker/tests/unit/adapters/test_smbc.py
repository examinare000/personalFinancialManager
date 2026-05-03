"""``SmbcCsvAdapter`` 単体テスト（TDD Red 段階）。

検証範囲（plan §テスト計画 1〜5、§受入条件 1〜5）:

- T1 ``source = "smbc"`` のクラス属性宣言（受入条件 2）
- T2 ABC 由来 ``__init__(*, account_id: int)`` でインスタンス化できる
- T3 ゴールデンマスタ: ``tests/fixtures/smbc/sample.csv`` → ``expected.json`` 完全一致
- T4 お引出し列の値が負の ``Decimal`` に正規化される
- T5 お預入れ列の値が正の ``Decimal`` に正規化される
- T6 同一 CSV の 2 回 parse で各 ``Transaction.hash`` が完全一致（決定性）
- T7 MUFG 形式 CSV を渡すと ``ColumnMissingError``（独立性証明）
- T8 ``_normalize_description`` の全角スペース U+3000 削除
- T9 ``extract_holdings`` は空イテレータを返す（contract 解消）

設計準拠:
- ``worker/docs/plans/Ph1/06-smbc-csv-adapter.md`` §テスト計画 / §受入条件
- ``worker/docs/design/02-ingest-adapters.md`` §3.2 / §4.2
- ``worker/docs/plans/Ph1/04-ingest-adapter-base.md``（コンストラクタ注入規約）
- ``shared/kakeibo_shared/domain/transaction.py``（``Transaction`` / ``compute_hash``）

テストは TDD Red 段階で先行作成する。``smbc.py`` / ``errors.py`` は後続 implement
ステップで追加するため、各テスト内で production 側を関数内 import し、未実装モジュールの
``ImportError`` が他テストを巻き添えにしないようにする
（``test_base.py`` の Red 検出パターンに倣う）。

ファイル位置（``worker/tests/unit/adapters/test_smbc.py``）から見たリポジトリルートは
``parents[4]``。リポジトリ横断 fixtures（ADR-014）は ``<root>/tests/fixtures/smbc/``。
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

# リポジトリ横断 fixture（``tests/fixtures/smbc/``）の絶対パス。
# - ``__file__``                            = ``<root>/worker/tests/unit/adapters/test_smbc.py``
# - ``parents[0]`` = ``adapters/``、``parents[1]`` = ``unit/``、``parents[2]`` = ``tests/``、
#   ``parents[3]`` = ``worker/``、``parents[4]`` = リポジトリルート。
# 設計 doc §4.2 のサンプルは ``parents[3]`` 表記だが、実態の階層数（``adapters`` 含む 4 段）に
# 合わせて ``parents[4]`` を採用する（design doc は例示で誤記、実装版を採用）。
FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "smbc"

# ゴールデンマスタテストで採用する ``account_id``。
# fixture の ``expected.json`` も同値で生成済（hash の事前計算に使われている）。
ACCOUNT_ID = 42


# ---------------------------------------------------------------------------
# T1 / T2 — クラス属性とコンストラクタ注入
# ---------------------------------------------------------------------------


def test_SmbcCsvAdapterはsourceがsmbcである() -> None:
    """plan §受入条件2: ``source: ClassVar[str] = "smbc"`` をクラス属性として宣言する。

    Phase 1.6 取込 CLI が ``ADAPTER_REGISTRY`` キーとして本値を使う前提（design doc §5）。
    クラス属性参照で取得できるかを検証し、サブクラス側で自前定義していることを確認する。
    """
    # Given/When: SmbcCsvAdapter の class object を import する
    from kakeibo_worker.adapters.smbc import SmbcCsvAdapter

    # Then: クラス属性 ``source`` が "smbc" 文字列で取得できる
    assert SmbcCsvAdapter.source == "smbc"


def test_SmbcCsvAdapterはaccount_id注入後インスタンス化できる() -> None:
    """plan §実装方針5: ABC 由来 ``__init__(*, account_id: int)`` をそのまま使う。

    keyword-only 引数で ``account_id`` を受け取り、``self.account_id`` に保持する規約を確認する。
    Phase 1.4 と同方式（IngestAdapter 共通契約）。
    """
    # Given: SmbcCsvAdapter クラス
    from kakeibo_worker.adapters.smbc import SmbcCsvAdapter

    # When: account_id=42 で初期化する
    adapter = SmbcCsvAdapter(account_id=ACCOUNT_ID)

    # Then: コンストラクタ注入値が ``self.account_id`` に保持されている
    assert adapter.account_id == ACCOUNT_ID


# ---------------------------------------------------------------------------
# T3 — ゴールデンマスタ: sample.csv → expected.json 完全一致
# ---------------------------------------------------------------------------


def test_SmbcCsvAdapterはサンプルCSVを期待JSONと完全一致でパースする() -> None:
    """plan §テスト計画1: ``sample.csv`` から ``expected.json`` 記載の 5 件が完全一致で抽出される。

    検査対象は ``Transaction`` の全 10 フィールド:
        ``account_id`` / ``occurred_on`` / ``occurred_at`` / ``amount`` / ``currency``
        / ``description`` / ``category_id`` / ``category_source`` / ``raw_payload`` / ``hash``

    ``raw_payload`` は plan §検討したアプローチで
    「``csv.DictReader`` の row dict をそのまま保存する」方針が採られているため、
    列名キー → 未パース文字列値の dict 完全一致で検証する。
    """
    # Given: sample.csv（UTF-8 BOM 付き 5 件分のデータ）と期待 JSON
    from datetime import date

    from kakeibo_worker.adapters.smbc import SmbcCsvAdapter

    csv_bytes = (FIXTURES / "sample.csv").read_bytes()
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))

    # When: parse を実体化する
    actual = list(SmbcCsvAdapter(account_id=ACCOUNT_ID).parse(csv_bytes))

    # Then: 件数および各フィールドが期待 JSON と完全一致する
    assert len(actual) == len(expected["transactions"])
    for tx, want in zip(actual, expected["transactions"], strict=True):
        assert tx.account_id == want["account_id"]
        assert tx.occurred_on == date.fromisoformat(want["occurred_on"])
        # ``occurred_at`` は SMBC CSV に時刻情報が無いため常に None（plan §実装方針 暗黙）
        assert tx.occurred_at is None
        # Decimal の比較は ``Decimal(str(...))`` を介す（``"-1000"`` などの表現を保つ）
        assert tx.amount == Decimal(want["amount"])
        # plan §実装方針4: 桁区切りカンマを除去した素の Decimal を維持する
        # （``Decimal("1234.560")`` と ``Decimal("1234.56")`` を別ハッシュで扱う規約のため、
        #  str 表現の同値性も併記検証する）
        assert str(tx.amount) == want["amount"]
        assert tx.currency == want["currency"]
        assert tx.description == want["description"]
        assert tx.category_id == want["category_id"]
        assert tx.category_source == want["category_source"]
        assert tx.raw_payload == want["raw_payload"]
        assert tx.hash == want["hash"]


# ---------------------------------------------------------------------------
# T4 / T5 — 金額符号正規化（お引出し → 負、お預入れ → 正）
# ---------------------------------------------------------------------------


def test_SmbcCsvAdapterはお引出し列を負のDecimalに正規化する() -> None:
    """plan §実装方針4 / §テスト計画4: お引出し列が空でない行は ``-Decimal(...)``。

    sample.csv 1 行目（``2026/04/01`` / お引出し ``"1,000"`` / お預入れ空）を最小ケースとし、
    桁区切りカンマ除去後の値に負号が付与されることを検証する。
    """
    # Given: お引出し ``1,000`` / お預入れ空 / 摘要 ``コンビニ　ローソン`` を含む sample.csv
    from kakeibo_worker.adapters.smbc import SmbcCsvAdapter

    csv_bytes = (FIXTURES / "sample.csv").read_bytes()

    # When: parse の最初の Transaction を取得する
    transactions = list(SmbcCsvAdapter(account_id=ACCOUNT_ID).parse(csv_bytes))
    first = transactions[0]

    # Then: 金額は ``Decimal("-1000")``。``Decimal`` 型かつ符号が負であることを併記検証する
    assert isinstance(first.amount, Decimal)
    assert first.amount == Decimal("-1000")
    assert first.amount < Decimal(0)


def test_SmbcCsvAdapterはお預入れ列を正のDecimalに正規化する() -> None:
    """plan §実装方針4 / §テスト計画4: お預入れ列が空でない行は ``+Decimal(...)``。

    sample.csv 2 行目（``2026/04/05`` / お引出し空 / お預入れ ``"50,000"``）を最小ケースとし、
    桁区切りカンマ除去後の値が正値で取り出されることを検証する。
    """
    # Given: お引出し空 / お預入れ ``50,000`` / 摘要 ``給与 振込`` を含む sample.csv
    from kakeibo_worker.adapters.smbc import SmbcCsvAdapter

    csv_bytes = (FIXTURES / "sample.csv").read_bytes()

    # When: parse の 2 件目 Transaction を取得する
    transactions = list(SmbcCsvAdapter(account_id=ACCOUNT_ID).parse(csv_bytes))
    second = transactions[1]

    # Then: 金額は ``Decimal("50000")``。``Decimal`` 型かつ符号が正であることを併記検証する
    assert isinstance(second.amount, Decimal)
    assert second.amount == Decimal("50000")
    assert second.amount > Decimal(0)


# ---------------------------------------------------------------------------
# T6 — ハッシュ決定性
# ---------------------------------------------------------------------------


def test_SmbcCsvAdapterは同一CSVの2回パースで同一ハッシュ列を返す() -> None:
    """plan §テスト計画5 / §受入条件4: 同一 CSV を 2 回 parse して
    各 ``Transaction.hash`` が完全一致する。

    取込冪等性キーが正規化済み描述に対して決定的に算出される
    （Phase 1.7 で評価される境界条件の前提）。生成順序まで含めて一致することを期待する。
    """
    # Given: sample.csv バイト列（同一インスタンスでも別 parse コールで再現性が要る）
    from kakeibo_worker.adapters.smbc import SmbcCsvAdapter

    csv_bytes = (FIXTURES / "sample.csv").read_bytes()

    # When: 2 回 parse する（独立した adapter インスタンスで揺らぎが無いことを併記検証）
    first_run = [tx.hash for tx in SmbcCsvAdapter(account_id=ACCOUNT_ID).parse(csv_bytes)]
    second_run = [tx.hash for tx in SmbcCsvAdapter(account_id=ACCOUNT_ID).parse(csv_bytes)]

    # Then: hash 列が順序まで含めて完全一致する
    assert first_run == second_run
    # 件数 0 で「両方空 = 一致」を許容しないよう件数の存在を併記検証する
    assert len(first_run) == 5


# ---------------------------------------------------------------------------
# T7 — MUFG 形式 CSV に対する独立性検証
# ---------------------------------------------------------------------------


def test_SmbcCsvAdapterはMUFG形式CSVに対しColumnMissingErrorを送出する() -> None:
    """plan §テスト計画2 / §受入条件3:
    MUFG の列名（``日付``, ``摘要``, ``お支払金額``, ...）を渡しても
    SMBC の必須列（``年月日`` / ``お引出し`` / ``お預入れ`` / ``お取り扱い内容``
    / ``残高``）が検出できず ``ColumnMissingError`` が送出されることを確認する。

    Phase 1.4（MUFG）は実装未着手のため、本テストは MUFG 列構成を **インライン bytes** で
    自己完結させる（plan §検討したアプローチ「インライン bytes で組み立てる」）。テストは
    SMBC アダプタが MUFG 列を読めないことだけを検証し、Phase 1.4 のスコープに踏み込まない。
    """
    # Given: MUFG 形式 CSV を UTF-8 で構築（SMBC アダプタは utf-8-sig でデコードするため
    # 文字コードはここでは UTF-8 を採用してデコード成功させ、列名検出のみを失敗させる）
    from kakeibo_worker.adapters.errors import ColumnMissingError
    from kakeibo_worker.adapters.smbc import SmbcCsvAdapter

    mufg_bytes = (
        "日付,摘要,お支払金額,お預り金額,残高\r\n"
        '2026/04/01,ＡＴＭ引出し,"1,000",,"99,000"\r\n'
        '2026/04/05,給与振込,,"50,000","149,000"\r\n'
    ).encode()

    # When/Then: parse を実体化すると ``ColumnMissingError``
    # （実装はジェネレータの可能性が高く、列検出は iterate 時に走る前提で list() で消費する）
    with pytest.raises(ColumnMissingError):
        list(SmbcCsvAdapter(account_id=ACCOUNT_ID).parse(mufg_bytes))


# ---------------------------------------------------------------------------
# T8 — ``_normalize_description`` の全角スペース削除
# ---------------------------------------------------------------------------


def test_normalize_descriptionは全角スペース有無を同一文字列に正規化する() -> None:
    """plan §テスト計画3: 全角スペース U+3000 を削除し、ありなしで同一文字列になる。

    plan §検討したアプローチで「全角スペース → 半角スペース変換」は不採用、
    「全角スペース U+3000 を削除」を採用と確定。摘要 ``コンビニ　ローソン`` と
    ``コンビニローソン`` が同一の正規化済み文字列になることを検証する。
    """
    # Given: ``_normalize_description`` を smbc モジュールから直接 import する
    # （アンダースコア接頭辞のモジュール内ヘルパだが、テスト計画3 が単体テストを
    # 要求するため pyright の reportPrivateUsage を抑止する）
    from kakeibo_worker.adapters.smbc import (
        _normalize_description,  # pyright: ignore[reportPrivateUsage]
    )

    # When: 全角スペースありとなしの 2 入力を正規化する
    with_full_width = _normalize_description("コンビニ　ローソン")
    without_full_width = _normalize_description("コンビニローソン")

    # Then: 結果が完全一致する
    assert with_full_width == without_full_width
    assert with_full_width == "コンビニローソン"


# ---------------------------------------------------------------------------
# T9 — ``extract_holdings`` の contract 解消
# ---------------------------------------------------------------------------


def test_SmbcCsvAdapter_extract_holdingsは空イテレータを返す() -> None:
    """plan §要件5: ABC 抽象メソッド ``extract_holdings`` を ``return iter(())`` で明示実装する。

    SMBC は本 Phase で残高抽出をスコープ外とする（plan §スコープ外）。Phase 1 では
    holdings 列は空集合のままであることを契約レベルで保証する。
    """
    # Given: SmbcCsvAdapter インスタンス
    from kakeibo_worker.adapters.smbc import SmbcCsvAdapter

    csv_bytes = (FIXTURES / "sample.csv").read_bytes()
    adapter = SmbcCsvAdapter(account_id=ACCOUNT_ID)

    # When: extract_holdings を実体化する
    holdings = list(adapter.extract_holdings(csv_bytes))

    # Then: 空集合（Phase 1.5 のスコープ外）
    assert holdings == []
