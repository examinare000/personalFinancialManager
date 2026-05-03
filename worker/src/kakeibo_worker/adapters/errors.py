"""取込アダプタが送出する例外クラス群。

Phase 1.5 で導入。SMBC アダプタが必須列を検出できないときに送出する
``ColumnMissingError`` を定義する。Phase 1.4 以降の他機関アダプタも同例外を
共通使用する想定（plan §テスト計画2 / §受入条件3 の独立性検証で参照）。

設計準拠:
- ``worker/docs/plans/Ph1/06-smbc-csv-adapter.md`` §受入条件3
- ``worker/docs/design/02-ingest-adapters.md`` §3.2
"""

from __future__ import annotations


class ColumnMissingError(Exception):
    """CSV ヘッダ行に必須列が含まれていない場合に送出する例外。

    SMBC アダプタは ``年月日`` / ``お引出し`` / ``お預入れ`` / ``お取り扱い内容`` /
    ``残高`` の 5 列を必須とする。MUFG 形式 CSV など別機関のフォーマットを
    SMBC アダプタに渡したときに本例外で早期に弾く（plan §テスト計画2「独立性の証明」）。
    """
