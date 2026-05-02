"""``MufgCsvAdapter`` の単体テスト（TDD Red 段階）。

検証範囲:
- ``source`` クラス属性が ``"mufg"`` 固定であること
- ``IngestAdapter`` 契約準拠（``isinstance`` / ``account_id`` 注入）
- Shift_JIS ゴールデンマスタからの全件一致
  （``Transaction`` の 10 フィールド、``compute_hash`` 経由のハッシュ値含む）
- 出金 / 入金の符号正規化（出金 → 負、入金 → 正）
- UTF-8 ペイロードでの ``EncodingMismatchError``（chardet 不採用、R-08）
- 必須列欠損での ``ColumnMissingError``（4 列ぶん parametrize）
- 数値化不能行 / 出金入金両方空 / 両方値あり での ``MalformedRowError``
- ハッシュ決定性（同じ CSV を 2 回 parse → ``tx.hash`` 完全一致）
- ``extract_holdings`` が空イテラブルを返す（plan §実装方針1）

設計準拠:
- ``worker/docs/plans/Ph1/05-mufg-csv-adapter.md`` §テスト計画 / §実装方針
- ``worker/docs/plans/Ph1/04-ingest-adapter-base.md``（``IngestAdapter`` 契約）
- ``docs/adr/006-hash-uniqueness.md``（``compute_hash`` 4 引数 SHA256 hex）
- ``docs/adr/005-decimal-monetary-precision.md``（``amount`` は ``Decimal``）

テストは TDD Red 段階で先行作成する。実装（``mufg.py`` / ``errors.py``）は
後続ステップで追加するため、各テスト内で production 側を関数内 import し、
未実装モジュールの ``ImportError`` が他テストを巻き添えにしないようにする
（``test_base.py`` の Red 検出パターンに倣う）。
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# ヘルパー — フィクスチャ・最小 CSV ビルダ
# ---------------------------------------------------------------------------


def _build_csv(rows: list[dict[str, str]]) -> bytes:
    """テスト用に 1〜数行の MUFG 形式 CSV（Shift_JIS）を構築する。

    ``rows`` は列名 → 値の dict。値が空欄の列は ``""`` を渡す（DictReader 挙動と整合）。
    数値の桁区切り（カンマ）はテスト側で必要なら ``csv`` モジュール非経由で
    そのまま埋め込んでも良いが、本ヘルパーは安全のためカンマ含み値を quote する。
    """
    import csv as _csv
    import io

    buf = io.StringIO()
    writer = _csv.writer(buf, quoting=_csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(["日付", "摘要", "お支払金額", "お預り金額", "差引残高"])
    for row in rows:
        writer.writerow(
            [
                row.get("日付", ""),
                row.get("摘要", ""),
                row.get("お支払金額", ""),
                row.get("お預り金額", ""),
                row.get("差引残高", ""),
            ]
        )
    return buf.getvalue().encode("shift_jis")


def _read_fixture_bytes(repo_root: Path, name: str) -> bytes:
    """``tests/fixtures/mufg/<name>`` を bytes で返す。

    ``repo_root`` は ``worker/tests/conftest.py`` の fixture（リポジトリルート）。
    """
    return (repo_root / "tests" / "fixtures" / "mufg" / name).read_bytes()


# ---------------------------------------------------------------------------
# 1. クラス属性 — ``source = "mufg"`` 固定
# ---------------------------------------------------------------------------


def test_MufgCsvAdapterはsource属性がmufgである() -> None:
    """plan §実装方針1: ``source: ClassVar[str] = "mufg"``。

    ``ADAPTER_REGISTRY``（Phase 1.6 で導入予定）のキーが ``"mufg"`` 固定であることを
    アダプタ単体で検証する。値が変わると CLI からのルーティングが破綻するため
    クラス属性の同一性を最初に固定する。
    """
    # Given: 実装モジュール
    from kakeibo_worker.adapters.mufg import MufgCsvAdapter

    # When/Then: ``source`` クラス属性が固定値であること
    assert MufgCsvAdapter.source == "mufg"


# ---------------------------------------------------------------------------
# 2. ABC 契約準拠 — ``isinstance`` と ``account_id`` 注入
# ---------------------------------------------------------------------------


def test_MufgCsvAdapterはIngestAdapter契約を満たす() -> None:
    """plan §実装方針1: ``IngestAdapter`` 継承 / ``account_id`` keyword-only 注入。

    ``isinstance(adapter, IngestAdapter)`` が True であること、
    コンストラクタ注入された ``account_id`` が ``self.account_id`` 経由で読めることを
    一度に検証する。Phase 1.4 のアダプタが Phase 1.3 の契約に確実に乗っていることを
    早期検出する。
    """
    # Given: ABC とサブクラス
    from kakeibo_worker.adapters.base import IngestAdapter
    from kakeibo_worker.adapters.mufg import MufgCsvAdapter

    # When: account_id=42 で初期化する
    adapter = MufgCsvAdapter(account_id=42)

    # Then: ABC のサブクラスインスタンスかつ account_id を保持している
    assert isinstance(adapter, IngestAdapter)
    assert adapter.account_id == 42


# ---------------------------------------------------------------------------
# 3. ゴールデンマスタ — Shift_JIS sample.csv ⇔ expected.json 全件一致
# ---------------------------------------------------------------------------


def test_MufgCsvAdapter_parseはサンプルCSVから期待Transactionリストを返す(
    repo_root: Path,
) -> None:
    """plan §テスト計画1 / §受入条件: ゴールデンマスタ全件完全一致。

    ``tests/fixtures/mufg/sample.csv``（Shift_JIS）を ``parse`` し、
    ``expected.json`` に記述された各 ``Transaction`` フィールド（10 個）と完全一致する
    ことを検証する。``hash`` は ``compute_hash`` で再計算し、ADR-006 の正規化規約が
    アダプタ層で守られていることを併せて検証する（マジックな 16 進数の直書きを避ける）。
    """
    # Given: Shift_JIS ゴールデンマスタとそれに対応する期待値
    from kakeibo_shared.domain import Transaction, compute_hash
    from kakeibo_worker.adapters.mufg import MufgCsvAdapter

    payload = _read_fixture_bytes(repo_root, "sample.csv")
    expected_data = json.loads(
        (repo_root / "tests" / "fixtures" / "mufg" / "expected.json").read_text(encoding="utf-8")
    )
    account_id: int = expected_data["account_id"]
    adapter = MufgCsvAdapter(account_id=account_id)

    # When: parse の戻り値を実体化する
    transactions = list(adapter.parse(payload))

    # Then: 件数・各フィールド・ハッシュが期待値と一致する
    expected_rows: list[dict[str, object]] = expected_data["transactions"]
    assert len(transactions) == len(expected_rows)
    for tx, exp in zip(transactions, expected_rows, strict=True):
        assert isinstance(tx, Transaction)
        assert tx.account_id == account_id
        # ``date`` の比較は ISO 文字列に揃える（fixture 側は JSON の都合で ISO 文字列）。
        assert tx.occurred_on.isoformat() == exp["occurred_on"]
        # ``occurred_at`` は plan §実装方針1 では sample.csv に時刻列がないため None。
        assert tx.occurred_at == exp["occurred_at"]
        # ``amount`` は ``Decimal`` の ``str`` 表現で比較（plan §テスト計画1: 「Decimal は文字列で比較」）。
        assert str(tx.amount) == exp["amount"]
        assert tx.currency == exp["currency"]
        assert tx.description == exp["description"]
        assert tx.category_id == exp["category_id"]
        assert tx.category_source == exp["category_source"]
        # ``raw_payload`` は ``csv.DictReader`` 行 dict をそのまま保持する想定
        # （差引残高を含む全列が文字列値で残る、plan §実装ガイドライン §_to_transaction 4）。
        assert tx.raw_payload == exp["raw_payload"]
        # ハッシュは ``compute_hash`` を再呼出ししてクロスチェック（ADR-006）。
        expected_hash = compute_hash(
            account_id,
            date.fromisoformat(str(exp["occurred_on"])),
            Decimal(str(exp["amount"])),
            str(exp["description"]),
        )
        assert tx.hash == expected_hash


# ---------------------------------------------------------------------------
# 4. 出金行の符号正規化 — お支払金額 → amount 負
# ---------------------------------------------------------------------------


def test_MufgCsvAdapterは出金行のamountを負値に正規化する() -> None:
    """plan §実装方針4 / §テスト計画2: 出金額カラム → ``amount`` 負。

    1 行 CSV を直接構築して符号のみを検証する。ゴールデンマスタは複数行の混在を
    扱うため、符号方針の同定は最小ケースで独立に確認する。
    """
    # Given: 出金 1 行のみの CSV（1234 円の出金）
    from kakeibo_worker.adapters.mufg import MufgCsvAdapter

    payload = _build_csv(
        [
            {
                "日付": "2026/04/01",
                "摘要": "出金テスト",
                "お支払金額": "1234",
                "お預り金額": "",
                "差引残高": "100000",
            }
        ]
    )
    adapter = MufgCsvAdapter(account_id=1)

    # When: parse を実体化する
    transactions = list(adapter.parse(payload))

    # Then: 1 件返り、amount は -1234 の Decimal
    assert len(transactions) == 1
    assert transactions[0].amount == Decimal("-1234")


# ---------------------------------------------------------------------------
# 5. 入金行の符号正規化 — お預り金額 → amount 正
# ---------------------------------------------------------------------------


def test_MufgCsvAdapterは入金行のamountを正値に正規化する() -> None:
    """plan §実装方針4 / §テスト計画2: 入金額カラム → ``amount`` 正。

    1 行 CSV を直接構築して符号のみを検証する。
    """
    # Given: 入金 1 行のみの CSV（5678 円の入金）
    from kakeibo_worker.adapters.mufg import MufgCsvAdapter

    payload = _build_csv(
        [
            {
                "日付": "2026/04/01",
                "摘要": "入金テスト",
                "お支払金額": "",
                "お預り金額": "5678",
                "差引残高": "100000",
            }
        ]
    )
    adapter = MufgCsvAdapter(account_id=1)

    # When: parse を実体化する
    transactions = list(adapter.parse(payload))

    # Then: 1 件返り、amount は +5678 の Decimal
    assert len(transactions) == 1
    assert transactions[0].amount == Decimal("5678")


# ---------------------------------------------------------------------------
# 6. エンコーディング不一致 — UTF-8 payload で EncodingMismatchError
# ---------------------------------------------------------------------------


def test_MufgCsvAdapterはShiftJIS以外のpayloadでEncodingMismatchErrorを送出する(
    repo_root: Path,
) -> None:
    """plan §テスト計画3 / §受入条件: UTF-8 で書かれた CSV → ``EncodingMismatchError``。

    chardet 等の自動判定は採用しないため（リスク R-08）、文字コードが異なるだけで
    黙って文字化けするのではなく、明示例外で早期失敗する規約を検証する。
    """
    # Given: UTF-8 で書かれた壊れエンコーディング fixture
    from kakeibo_worker.adapters.errors import EncodingMismatchError
    from kakeibo_worker.adapters.mufg import MufgCsvAdapter

    payload = _read_fixture_bytes(repo_root, "broken_encoding.csv")
    adapter = MufgCsvAdapter(account_id=1)

    # When/Then: parse の実体化で EncodingMismatchError
    # ``parse`` は generator の可能性があるため list() で実体化する（遅延評価で例外が
    # 漏れる経路を確実に弾く）。
    with pytest.raises(EncodingMismatchError):
        list(adapter.parse(payload))


# ---------------------------------------------------------------------------
# 7. 必須列欠損 — 4 列ぶん parametrize で ColumnMissingError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing_column",
    ["日付", "摘要", "お支払金額", "お預り金額"],
)
def test_MufgCsvAdapterは必須列欠損のCSVでColumnMissingErrorを送出する(
    missing_column: str,
) -> None:
    """plan §テスト計画4 / §受入条件: 必須 4 列のいずれかが欠損で ``ColumnMissingError``。

    必須列は Transaction を組み立てるのに必要な 4 列（日付 / 摘要 / お支払金額 / お預り金額）。
    ``差引残高`` は raw_payload に保持はするが Transaction 構築には使わないため必須ではない
    （plan §実装ガイドライン §モジュール定数 ``REQUIRED_COLUMNS``）。
    """
    # Given: 必須列を 1 つ抜いた CSV ヘッダ（行は空でもヘッダ解析で弾ける想定）
    import io

    from kakeibo_worker.adapters.errors import ColumnMissingError
    from kakeibo_worker.adapters.mufg import MufgCsvAdapter

    columns = ["日付", "摘要", "お支払金額", "お預り金額", "差引残高"]
    columns.remove(missing_column)
    buf = io.StringIO()
    buf.write(",".join(columns) + "\n")
    # 行データはダミー（ヘッダ検証段階で例外が出るため、行解析に到達しない想定）
    buf.write(",".join("x" for _ in columns) + "\n")
    payload = buf.getvalue().encode("shift_jis")
    adapter = MufgCsvAdapter(account_id=1)

    # When/Then: parse の実体化で ColumnMissingError
    with pytest.raises(ColumnMissingError):
        list(adapter.parse(payload))


# ---------------------------------------------------------------------------
# 8. 数値化不能 — お支払金額が "abc" 等で MalformedRowError
# ---------------------------------------------------------------------------


def test_MufgCsvAdapterは出金額が数値化できない行でMalformedRowErrorを送出する() -> None:
    """plan §テスト計画5: 数値化不能 → ``MalformedRowError``（``AdapterError`` 派生）。

    plan §テスト計画5 は「``ValueError``（または専用例外）」を許容するが、Phase 1.3 plan
    §実装方針5「アダプタ例外は ``AdapterError`` 派生」規約に従い専用例外で揃える。
    生 ``ValueError`` を素通しすると CLI 側で例外区別が困難になるため。
    """
    # Given: お支払金額が文字列 "abc" の 1 行 CSV
    from kakeibo_worker.adapters.errors import MalformedRowError
    from kakeibo_worker.adapters.mufg import MufgCsvAdapter

    payload = _build_csv(
        [
            {
                "日付": "2026/04/01",
                "摘要": "数値化不能テスト",
                "お支払金額": "abc",
                "お預り金額": "",
                "差引残高": "100000",
            }
        ]
    )
    adapter = MufgCsvAdapter(account_id=1)

    # When/Then: parse の実体化で MalformedRowError
    with pytest.raises(MalformedRowError):
        list(adapter.parse(payload))


# ---------------------------------------------------------------------------
# 9. 両方空 — 出金額・入金額が両方空欄で MalformedRowError
# ---------------------------------------------------------------------------


def test_MufgCsvAdapterは出金額入金額が両方空の行でMalformedRowErrorを送出する() -> None:
    """plan §実装方針4: 「両方空 / 両方ある行は不正データとして例外」。

    どちらの符号で計上すべきか判定不能なため、暗黙の 0 円扱いで通すのではなく
    明示例外で取込側に判断を返す（Fail Fast）。
    """
    # Given: 出金額・入金額が両方空欄の 1 行 CSV
    from kakeibo_worker.adapters.errors import MalformedRowError
    from kakeibo_worker.adapters.mufg import MufgCsvAdapter

    payload = _build_csv(
        [
            {
                "日付": "2026/04/01",
                "摘要": "両方空テスト",
                "お支払金額": "",
                "お預り金額": "",
                "差引残高": "100000",
            }
        ]
    )
    adapter = MufgCsvAdapter(account_id=1)

    # When/Then: parse の実体化で MalformedRowError
    with pytest.raises(MalformedRowError):
        list(adapter.parse(payload))


# ---------------------------------------------------------------------------
# 10. 両方値あり — 出金額・入金額が両方埋まっていれば MalformedRowError
# ---------------------------------------------------------------------------


def test_MufgCsvAdapterは出金額入金額が両方値ありの行でMalformedRowErrorを送出する() -> None:
    """plan §実装方針4: 「両方空 / 両方ある行は不正データとして例外」。

    両方値があるのは MUFG CSV の仕様外（出金 / 入金 / 残高調整のいずれかは必ず一方）。
    """
    # Given: 出金額・入金額が両方値あり (差引が判定不能) の 1 行 CSV
    from kakeibo_worker.adapters.errors import MalformedRowError
    from kakeibo_worker.adapters.mufg import MufgCsvAdapter

    payload = _build_csv(
        [
            {
                "日付": "2026/04/01",
                "摘要": "両方値ありテスト",
                "お支払金額": "1000",
                "お預り金額": "500",
                "差引残高": "100000",
            }
        ]
    )
    adapter = MufgCsvAdapter(account_id=1)

    # When/Then: parse の実体化で MalformedRowError
    with pytest.raises(MalformedRowError):
        list(adapter.parse(payload))


# ---------------------------------------------------------------------------
# 11. ハッシュ決定性 — 同じ CSV を 2 回 parse すると hash が完全一致
# ---------------------------------------------------------------------------


def test_MufgCsvAdapter_parseはハッシュが決定論的である(repo_root: Path) -> None:
    """plan §テスト計画6 / §受入条件: 同一 CSV の再 parse で ``Transaction.hash`` 一致。

    Phase 1.6 取込 CLI の冪等性（UNIQUE 違反で同じ取引が重複登録されない）の前提を
    アダプタ層で担保する。同じバイト列から同じハッシュが生成されることを
    インスタンス再生成も含めて検証する（インスタンス内部状態の混入を排除）。
    """
    # Given: ゴールデンマスタの payload と 2 つの独立アダプタインスタンス
    from kakeibo_worker.adapters.mufg import MufgCsvAdapter

    payload = _read_fixture_bytes(repo_root, "sample.csv")

    # When: 別インスタンスで 2 回 parse する
    first = list(MufgCsvAdapter(account_id=100).parse(payload))
    second = list(MufgCsvAdapter(account_id=100).parse(payload))

    # Then: 件数一致かつ各行の hash が完全一致
    assert len(first) == len(second)
    for a, b in zip(first, second, strict=True):
        assert a.hash == b.hash


# ---------------------------------------------------------------------------
# 12. extract_holdings — 空イテラブルを返す
# ---------------------------------------------------------------------------


def test_MufgCsvAdapter_extract_holdingsは空イテラブルを返す() -> None:
    """plan §実装方針1: MUFG は holdings 未対応のため明示的に空イテラブル。

    holdings は証券口座の保有資産概念で、銀行 CSV には存在しない。
    デフォルト実装に頼らず明示的に ``return iter(())`` を実装している規約を検証する
    （``IngestAdapter`` ABC は ``extract_holdings`` を抽象メソッドとして強制している）。
    """
    # Given: MufgCsvAdapter
    from kakeibo_worker.adapters.mufg import MufgCsvAdapter

    adapter = MufgCsvAdapter(account_id=1)

    # When: extract_holdings を実体化する（payload は契約上必須だが MUFG は使わない）
    holdings = list(adapter.extract_holdings(b""))

    # Then: 空集合
    assert holdings == []


# ---------------------------------------------------------------------------
# 13. 日付フォーマット不正 — ハイフン区切り等で MalformedRowError
# ---------------------------------------------------------------------------


def test_MufgCsvAdapterは日付フォーマット不正の行でMalformedRowErrorを送出する() -> None:
    """coder-decisions §未記載 / 実装 ``_parse_date`` の ``ValueError`` 再送経路を検証。

    ``DATE_FORMAT = "%Y/%m/%d"`` 固定（plan §実装方針5）であり、ハイフン区切り等は
    ``datetime.strptime`` が ``ValueError`` を送出する。これを生 ``ValueError`` として
    呼出側に漏らさず ``MalformedRowError``（``AdapterError`` 派生）に再送する規約を
    アダプタ層で担保する（Phase 1.3 plan §実装方針5「アダプタ例外は ``AdapterError``
    派生」と整合させる）。
    """
    # Given: 日付がハイフン区切り（"2026-04-01"）の 1 行 CSV
    from kakeibo_worker.adapters.errors import MalformedRowError
    from kakeibo_worker.adapters.mufg import MufgCsvAdapter

    payload = _build_csv(
        [
            {
                "日付": "2026-04-01",
                "摘要": "日付フォーマット不正テスト",
                "お支払金額": "1234",
                "お預り金額": "",
                "差引残高": "100000",
            }
        ]
    )
    adapter = MufgCsvAdapter(account_id=1)

    # When/Then: parse の実体化で MalformedRowError
    with pytest.raises(MalformedRowError):
        list(adapter.parse(payload))


# ---------------------------------------------------------------------------
# 13b. 空白文字列の出金額 — has_withdrawal 判定境界の挙動を担保
# ---------------------------------------------------------------------------


def test_MufgCsvAdapterは出金額が空白文字列の行でMalformedRowErrorを送出する() -> None:
    """``has_withdrawal = withdrawal != ""`` の境界挙動を担保する。

    実装は空欄判定を「完全な空文字列との非一致」で行うため、``"   "`` のような
    空白のみの値は has_withdrawal=True として ``Decimal("   ")`` 経路に進む。
    これは ``InvalidOperation`` を送出し ``_parse_amount`` で
    ``MalformedRowError`` に再送される（``AdapterError`` 派生で吸収される）。
    結果としては「不正データ → 専用例外で Fail Fast」と整合するため、現挙動を
    回帰防止の目的で固定する（``.strip()`` 化等は plan に明示されておらず、
    挙動変更はスコープ外）。
    """
    # Given: お支払金額が空白のみ "   " の 1 行 CSV（""との非一致で
    # has_withdrawal=True と扱われる経路）
    from kakeibo_worker.adapters.errors import MalformedRowError
    from kakeibo_worker.adapters.mufg import MufgCsvAdapter

    payload = _build_csv(
        [
            {
                "日付": "2026/04/01",
                "摘要": "空白文字列テスト",
                "お支払金額": "   ",
                "お預り金額": "",
                "差引残高": "100000",
            }
        ]
    )
    adapter = MufgCsvAdapter(account_id=1)

    # When/Then: parse の実体化で MalformedRowError
    with pytest.raises(MalformedRowError):
        list(adapter.parse(payload))


# ---------------------------------------------------------------------------
# 14. payload が bytes 以外 — TypeError（AdapterError では吸収されない）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "non_bytes_payload",
    [
        "日付,摘要,お支払金額,お預り金額,差引残高\n2026/04/01,テスト,1234,,100000\n",
        {"日付": "2026/04/01", "摘要": "dict 不正", "お支払金額": "1234"},
    ],
    ids=["str", "dict"],
)
def test_MufgCsvAdapterはbytes以外のpayloadでTypeErrorを送出する(
    non_bytes_payload: object,
) -> None:
    """coder-decisions §3: ``payload`` 契約違反は ``TypeError`` で早期失敗する。

    ``Payload = bytes | str | dict[str, Any]`` の Union 上、``str`` / ``dict`` が
    流入し得るが、MUFG アダプタは CSV bytes のみ扱う。これは「呼出側のバグ」
    （アダプタの入力契約違反）であり、入力データ不整合（``AdapterError`` 派生）とは
    性質が異なるため、Python 標準の ``TypeError`` で表現する。
    ``except AdapterError`` で誤って吸収されないこと（``AdapterError`` の派生でない
    こと）も併せて検証する。
    """
    # Given: bytes 以外の payload
    from kakeibo_worker.adapters.errors import AdapterError
    from kakeibo_worker.adapters.mufg import MufgCsvAdapter

    adapter = MufgCsvAdapter(account_id=1)

    # When/Then: parse の実体化で TypeError（AdapterError 派生でないこと）
    with pytest.raises(TypeError) as exc_info:
        list(adapter.parse(non_bytes_payload))  # type: ignore[arg-type]
    assert not isinstance(exc_info.value, AdapterError)
