"""SMBC（三井住友銀行）CSV 取込アダプタ。

`IngestAdapter` 契約（Phase 1.3）に準拠し、SMBC のお取引明細 CSV（UTF-8 BOM 付き）を
``Iterable[Transaction]`` に正規化する。MUFG（Phase 1.4）とは独立な専用実装で、
共通化は意図的に行わない（plan §TDD Refactor）。

設計準拠:
- ``worker/docs/plans/Ph1/06-smbc-csv-adapter.md`` §実装方針 1〜5 / §受入条件 1〜5
- ``worker/docs/design/02-ingest-adapters.md`` §3.2
- ``shared/kakeibo_shared/domain/transaction.py``（``Transaction`` / ``compute_hash``）

CSV 仕様:
- 文字コードは UTF-8 BOM 付き（``utf-8-sig`` で剥がす）。
- 先頭に複数行のメタヘッダ（口座番号・期間など）。行数は口座状況で揺れるため、
  必須 5 列が揃う行を動的にデータヘッダとして検出する（plan §検討したアプローチ）。
- データ行は ``年月日,お引出し,お預入れ,お取り扱い内容,残高`` の 5 列固定。
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Iterator
from datetime import date, datetime
from decimal import Decimal
from typing import ClassVar

from kakeibo_shared.domain import Holding, Transaction, compute_hash
from kakeibo_worker.adapters.base import IngestAdapter, Payload
from kakeibo_worker.adapters.errors import ColumnMissingError

# SMBC CSV のデータヘッダ列名。`.txt` 仕様書ではなく実 CSV から固定する規約。
# モジュール定数化することで「マジック文字列の散在」を避ける（policy §解決責務の一元化）。
COLUMN_DATE = "年月日"
COLUMN_WITHDRAWAL = "お引出し"
COLUMN_DEPOSIT = "お預入れ"
COLUMN_DESCRIPTION = "お取り扱い内容"
COLUMN_BALANCE = "残高"

# データヘッダ検出に使う必須列の集合。順序は ADAPTER 出力に影響しないため set で扱う。
_REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {COLUMN_DATE, COLUMN_WITHDRAWAL, COLUMN_DEPOSIT, COLUMN_DESCRIPTION, COLUMN_BALANCE}
)

# 通貨コード。SMBC は日本円口座のみ取り扱う（口座種別による切替えは Phase 2 以降）。
_CURRENCY_JPY = "JPY"

# SMBC CSV の日付列フォーマット（``YYYY/MM/DD``）。``date.fromisoformat`` ではなく
# ``strptime`` を使う（``/`` 区切りのため）。
_DATE_FORMAT = "%Y/%m/%d"

# 全角スペース U+3000。摘要正規化で削除する対象（plan §テスト計画3）。
# 半角スペースへの置換ではなく削除を採用する理由は「全角スペースありの摘要 / なしの
# 摘要が同一の正規化済み文字列になること」を要求しているため（plan §検討したアプローチ）。
_FULL_WIDTH_SPACE = "　"


def _normalize_description(s: str) -> str:
    """摘要文字列を正規化する。

    全角スペース U+3000 を削除する。半角スペースや全角ハイフンの変換は plan の
    テスト要件で検証されないため意図的に実装しない（スコープ拡大を避ける）。
    """
    return s.replace(_FULL_WIDTH_SPACE, "")


def _parse_amount(value: str) -> Decimal:
    """カンマ区切りを除去した上で ``Decimal`` に変換する。

    ``"1,000"`` → ``Decimal("1000")``。空文字列はこの関数を呼ぶ前段で判定する責務とし、
    本関数では空文字列を ``Decimal`` に渡して標準エラー（``InvalidOperation``）を伝播させる。
    """
    return Decimal(value.replace(",", ""))


def _detect_header(reader: Iterator[list[str]]) -> list[str]:
    """必須 5 列がすべて含まれる最初の行をデータヘッダとして返す。

    メタヘッダの行数が口座状況で揺れる前提のため、固定行数スキップではなく動的検出を採用。
    必須列が 1 行も見つからずに終端した場合は ``ColumnMissingError`` を送出する
    （plan §受入条件3「列順・列名差分が MUFG と区別される」）。
    """
    for row in reader:
        if _REQUIRED_COLUMNS.issubset(row):
            return row
    raise ColumnMissingError(
        f"required columns not found in CSV: {sorted(_REQUIRED_COLUMNS)}"
    )


def _row_to_transaction(
    row: dict[str, str],
    *,
    account_id: int,
) -> Transaction:
    """1 行分の dict から ``Transaction`` を構築する。

    お引出し列が空でなければ負値、お預入れ列が空でなければ正値で正規化する
    （plan §実装方針4）。摘要は ``_normalize_description`` を適用し、同じ
    正規化済み文字列を ``description`` フィールドおよび ``compute_hash`` の引数に渡す
    （片方だけ正規化するとハッシュ決定性テストが落ちる）。
    """
    occurred_on = _parse_occurred_on(row[COLUMN_DATE])
    amount = _extract_amount(row)
    normalized_description = _normalize_description(row[COLUMN_DESCRIPTION])
    return Transaction(
        account_id=account_id,
        occurred_on=occurred_on,
        occurred_at=None,
        amount=amount,
        currency=_CURRENCY_JPY,
        description=normalized_description,
        category_id=None,
        category_source=None,
        raw_payload=dict(row),
        hash=compute_hash(account_id, occurred_on, amount, normalized_description),
    )


def _parse_occurred_on(value: str) -> date:
    """``YYYY/MM/DD`` 文字列を ``date`` に変換する。"""
    return datetime.strptime(value, _DATE_FORMAT).date()


def _extract_amount(row: dict[str, str]) -> Decimal:
    """お引出し / お預入れ列から符号付き金額を取り出す。

    両方とも空の行は ``_parse_amount("")`` 経由で ``Decimal`` の標準エラー
    （``InvalidOperation``）が伝播し早期検出される（plan §Fail Fast）。
    両方ともに値が入る行は SMBC の CSV 仕様から外れるが、その明示検証は
    plan のスコープ外のため本実装では行わず、お引出し列を優先採用する。
    """
    withdrawal = row[COLUMN_WITHDRAWAL]
    deposit = row[COLUMN_DEPOSIT]
    if withdrawal != "":
        return -_parse_amount(withdrawal)
    return _parse_amount(deposit)


class SmbcCsvAdapter(IngestAdapter):
    """SMBC お取引明細 CSV を ``Transaction`` に正規化するアダプタ。

    ``source = "smbc"`` を Phase 1.6 取込 CLI の ``ADAPTER_REGISTRY`` キーとして
    使う前提（design doc §5）。``__init__`` は ABC 由来の ``__init__(*, account_id: int)``
    をそのまま利用する（Phase 1.3 / 1.4 と同方式）。
    """

    source: ClassVar[str] = "smbc"

    def parse(self, payload: Payload) -> Iterable[Transaction]:
        # Payload は ABC の契約上 ``bytes | str | dict`` だが、SMBC CSV は bytes 入力前提。
        # ``utf-8-sig`` で BOM を剥がしてからデコードする。デコード失敗時は標準
        # ``UnicodeDecodeError`` を素のまま伝播させる（plan §スコープ外）。
        if not isinstance(payload, bytes):
            raise TypeError(
                f"SmbcCsvAdapter.parse expects bytes payload, got {type(payload).__name__}"
            )
        text = payload.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text))
        header = _detect_header(reader)
        for raw_row in reader:
            # 空行スキップ（末尾改行のみの行を弾く。CRLF の最終空行を csv.reader が
            # 拾うケースに備える）。
            if not raw_row:
                continue
            row_dict = dict(zip(header, raw_row, strict=True))
            yield _row_to_transaction(row_dict, account_id=self.account_id)

    def extract_holdings(self, payload: Payload) -> Iterable[Holding]:
        # Phase 1.5 では残高抽出をスコープ外とする（plan §スコープ外）。
        # ABC 契約上、抽象解消には明示的な空イテレータ実装が必要。
        del payload
        return iter(())
