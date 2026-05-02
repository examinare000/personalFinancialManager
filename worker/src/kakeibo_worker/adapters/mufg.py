"""``MufgCsvAdapter`` — 三菱UFJ銀行（MUFG）の Shift_JIS CSV 取込アダプタ。

``IngestAdapter`` 契約（Phase 1.3）に準拠し、出金/入金を符号付き ``Decimal`` に
正規化した ``Transaction`` 列を返す。``compute_hash`` は再実装せず共通実装に委譲する
（ADR-006 / DRY）。

設計準拠:
- ``worker/docs/plans/Ph1/05-mufg-csv-adapter.md`` §実装方針1〜8 / §受入条件
- ``worker/docs/plans/Ph1/04-ingest-adapter-base.md``（``IngestAdapter`` 契約）
- ``docs/adr/006-hash-uniqueness.md``（``compute_hash`` 4 引数 SHA256 hex）
- ``docs/adr/005-decimal-monetary-precision.md``（``amount`` は ``Decimal``）
- リスク R-08（文字コード固定、chardet 不採用）
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import ClassVar

from kakeibo_shared.domain import Holding, Transaction, compute_hash
from kakeibo_worker.adapters.base import IngestAdapter, Payload
from kakeibo_worker.adapters.errors import (
    ColumnMissingError,
    EncodingMismatchError,
    MalformedRowError,
)

# ---------------------------------------------------------------------------
# モジュール定数 — MUFG CSV のフォーマット契約
# ---------------------------------------------------------------------------
# plan §実装方針2: payload は Shift_JIS 固定。
# chardet 等の自動判定は不採用（R-08）。
MUFG_ENCODING = "shift_jis"

# plan §実装方針3 で固定される列名。テストとも同一の文字列を共有するため定数化する。
# ``差引残高`` 列は Transaction 構築に使わず ``raw_payload`` に文字列のままパススルー
# されるだけのため、production では指名しない（定数化は対称性目的の dead code になる）。
COLUMN_OCCURRED_ON = "日付"
COLUMN_DESCRIPTION = "摘要"
COLUMN_WITHDRAWAL = "お支払金額"
COLUMN_DEPOSIT = "お預り金額"

# Transaction 構築に必要な 4 列のみを必須とする（``差引残高`` は raw_payload に保持はする
# が Transaction 構築には使わないため必須ではない: plan §実装ガイドライン §REQUIRED_COLUMNS）。
REQUIRED_COLUMNS: tuple[str, ...] = (
    COLUMN_OCCURRED_ON,
    COLUMN_DESCRIPTION,
    COLUMN_WITHDRAWAL,
    COLUMN_DEPOSIT,
)

# plan §実装方針5: 日付フォーマットは ``%Y/%m/%d`` で固定。
# 2 桁年表記の MUFG CSV 対応は本タスクのスコープ外。
DATE_FORMAT = "%Y/%m/%d"

# plan §背景: MUFG は日本円口座のみを対象とする。
CURRENCY_JPY = "JPY"


class MufgCsvAdapter(IngestAdapter):
    """MUFG（三菱UFJ銀行）の Shift_JIS CSV を ``Transaction`` 列に正規化する。

    ``account_id`` はコンストラクタ注入（``IngestAdapter`` 契約）で固定し、
    ``parse`` の引数は ``payload`` のみで受ける。``extract_holdings`` は MUFG が
    holdings 概念を持たないため明示的に空イテラブルを返す。
    """

    source: ClassVar[str] = "mufg"

    def parse(self, payload: Payload) -> Iterable[Transaction]:
        # ``payload`` は ``bytes`` 前提（plan §実装方針2）。``str``/``dict`` 等が
        # 流入した場合は契約違反として ``TypeError`` で早期失敗する
        # （``Payload`` Union のうち MUFG は CSV bytes のみ扱う）。
        if not isinstance(payload, bytes):
            raise TypeError(
                f"MufgCsvAdapter.parse expects bytes payload, got {type(payload).__name__}"
            )

        text = _decode_shift_jis(payload)
        reader = csv.DictReader(io.StringIO(text))
        _validate_required_columns(reader.fieldnames)

        # 行解析時の例外がジェネレータの遅延評価で漏れないよう、先に list 化しても
        # 良いが、メモリ効率のため yield のままにする（呼出側は ``list(adapter.parse(...))``
        # で実体化する想定。テストでも同パターン）。
        for row in reader:
            yield self._to_transaction(row)

    def extract_holdings(self, payload: Payload) -> Iterable[Holding]:
        # MUFG（普通預金口座）には holdings 概念が存在しないため明示的に空。
        # ``IngestAdapter`` ABC はデフォルト実装を提供しないため、未対応であることを
        # 明示的に表現する（plan §実装方針1）。
        del payload
        return iter(())

    def _to_transaction(self, row: dict[str, str]) -> Transaction:
        """1 行の ``DictReader`` 出力から ``Transaction`` を構築する。

        ``raw_payload`` には ``DictReader`` の行 dict をそのまま保持する
        （``差引残高`` を含む全列の文字列値が残る、plan §実装ガイドライン §_to_transaction 4）。
        ``csv.DictReader`` は行毎に独立した dict を yield するため、防御的な
        ``dict(...)`` コピーは不要（plan §_to_transaction 4「そのまま渡す」と整合）。
        """
        occurred_on = _parse_date(row[COLUMN_OCCURRED_ON])
        amount = _parse_amount(row[COLUMN_WITHDRAWAL], row[COLUMN_DEPOSIT])
        # plan §実装方針6: 摘要の trim/normalize は ADR-006 のハッシュ正準化と
        # 二重処理になるため行わない。
        description = row[COLUMN_DESCRIPTION]
        return Transaction(
            account_id=self.account_id,
            occurred_on=occurred_on,
            occurred_at=None,
            amount=amount,
            currency=CURRENCY_JPY,
            description=description,
            category_id=None,
            category_source=None,
            raw_payload=row,
            hash=compute_hash(self.account_id, occurred_on, amount, description),
        )


# ---------------------------------------------------------------------------
# モジュールプライベートヘルパー
# ---------------------------------------------------------------------------


def _decode_shift_jis(payload: bytes) -> str:
    """``payload`` を Shift_JIS でデコードし、失敗時は ``EncodingMismatchError``。

    chardet 等の自動判定は採用しない（R-08）。想定外のエンコーディングは
    黙って文字化けさせず、明示例外で早期失敗させる。
    """
    try:
        return payload.decode(MUFG_ENCODING)
    except UnicodeDecodeError as exc:
        raise EncodingMismatchError(
            f"failed to decode payload as {MUFG_ENCODING}: {exc}"
        ) from exc


def _validate_required_columns(fieldnames: Sequence[str] | None) -> None:
    """CSV ヘッダに必須列がすべて含まれていることを検証する。

    ``DictReader.fieldnames`` は空 CSV / ヘッダ無しの場合 ``None``。
    その場合も「必須列なし」として ``ColumnMissingError``。
    """
    available = set(fieldnames or [])
    missing = [c for c in REQUIRED_COLUMNS if c not in available]
    if missing:
        raise ColumnMissingError(
            f"required columns missing in MUFG CSV header: {missing}"
        )


def _parse_date(value: str) -> date:
    """``%Y/%m/%d`` で日付をパースし、失敗時は ``MalformedRowError``。"""
    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except ValueError as exc:
        raise MalformedRowError(
            f"invalid date in MUFG CSV row (expected {DATE_FORMAT}): {value!r}"
        ) from exc


def _parse_amount(withdrawal: str, deposit: str) -> Decimal:
    """出金/入金カラムから符号付き ``Decimal`` の ``amount`` を構築する。

    plan §実装方針4 に従い:
    - 両方空 → ``MalformedRowError``（暗黙の 0 円扱いをしない）
    - 両方値あり → ``MalformedRowError``（差引方向が判定不能）
    - 出金のみ → ``-Decimal(value)``（符号反転）
    - 入金のみ → ``Decimal(value)``
    桁区切りカンマは除去してから ``Decimal`` 化する。
    """
    has_withdrawal = withdrawal != ""
    has_deposit = deposit != ""
    if has_withdrawal and has_deposit:
        raise MalformedRowError(
            f"both withdrawal and deposit are filled: {withdrawal!r} / {deposit!r}"
        )
    if not has_withdrawal and not has_deposit:
        raise MalformedRowError("both withdrawal and deposit are empty")

    raw = withdrawal if has_withdrawal else deposit
    try:
        # 桁区切りカンマ（``"1,234"``）を除去してから ``Decimal`` 化する。
        # ``Decimal`` はカンマ入り文字列を直接受け付けない（``InvalidOperation``）ため。
        magnitude = Decimal(raw.replace(",", ""))
    except InvalidOperation as exc:
        raise MalformedRowError(
            f"failed to parse amount as Decimal: {raw!r}"
        ) from exc

    return -magnitude if has_withdrawal else magnitude
